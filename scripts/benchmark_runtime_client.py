"""Sequential XP/VXA display-list and text acceptance; no changes to input projects."""
import argparse,json,statistics
from pathlib import Path
from inspect_runtime import inspect
from test_runtime import run as run_xp
from test_runtime_vxa import run as run_vxa

ROOT=Path(__file__).resolve().parents[1]

def render_accepted(row):
 minimum=118 if row['render_rate']==120 else row['render_rate']*.98
 return 119<=row['logic_fps']<=121 and row['present_fps']>=minimum and row['missing_fraction']<=.02

def compare(rows):
 results=[]
 for engine in ('xp','vxa'):
  for kind in ('objects','text'):
   selected=[r for r in rows if r['engine']==engine and r['kind']==kind]
   keys={(r.get('sprites'),r.get('viewports'),r.get('profile')) for r in selected}
   for count,views,profile in sorted(keys,key=str):
    groups=[[r for r in selected if r['build']==build and (r.get('sprites'),r.get('viewports'),r.get('profile'))==(count,views,profile)] for build in ('baseline','candidate')]
    old,new=groups
    ratio=lambda name:statistics.mean(r[name] for r in new)/statistics.mean(r[name] for r in old)
    mean,p95=ratio('mean_ms'),ratio('p95_ms')
    allocation=ratio('allocated_per_frame' if kind=='objects' else 'allocated_per_call')
    passed=True
    if kind=='objects' and count>=300:passed=mean<=.75 and allocation<=.7 and p95<=1.05
    if kind=='text':passed=mean<=.7 if profile=='repeated' else mean<=1.1 and p95<=1.1
    results.append(dict(engine=engine,kind=kind,sprites=count,viewports=views,profile=profile,mean_ratio=mean,p95_ratio=p95,allocation_ratio=allocation,baseline_mean_ms=statistics.mean(r['mean_ms'] for r in old),candidate_mean_ms=statistics.mean(r['mean_ms'] for r in new),passed=passed))
 return results

def launch(engine,dll,folder,source,**kwargs):
 if engine=='xp':return run_xp(ROOT/'template-xp/Game.exe',dll,folder,'',source,timeout=180,**kwargs)
 return run_vxa(folder,source,dll=dll,timeout=180,**kwargs)

def render_runs(out,baseline):
 import shutil
 from rxdata import read
 from migrate_project import transform
 from package_template import expand_map as expand_xp
 from package_template_vxa import expand_map as expand_vxa
 rows=[];hashes={}
 for engine,name in [('xp','Lunetile.dll'),('vxa','LunetileVXA.dll')]:
  fixture=out/('fixture-'+engine);shutil.copytree(ROOT/f'template-{engine}/Data',fixture/'Data')
  (expand_xp if engine=='xp' else expand_vxa)(fixture,ROOT/'build/runtime-native/bin/Release/rgssxp-ruby.exe',fixture)
  entries=read((ROOT/f'template-{engine}/Data'/('Scripts.rxdata' if engine=='xp' else 'Scripts.rvdata2')).read_bytes())
  replacements=transform(entries,high_refresh=True,widescreen=True)[0] if engine=='xp' else {}
  definitions=b'\n'.join(replacements.get(i,e.source()).replace(b'\r\r\n',b'\n') for i,e in enumerate(entries) if e.name!=b'Main')
  helper=ROOT/'src/runtime'/('stock_timing.rb' if engine=='xp' else 'vxa_stock.rb')
  if engine=='xp':definitions+=b'\n'+(ROOT/'src/runtime/widescreen.rb').read_bytes()
  probe=(ROOT/'tests/runtime_vxa_fps.rb').read_text(encoding='utf-8')
  if engine=='xp':
   setup=(ROOT/'tests/runtime_client_fps_xp.rb').read_text(encoding='utf-8')
   probe=setup+probe[probe.index('$game_player.instance_variable_set'):]
   probe=probe.replace('$game_player.real_x',"($game_player.instance_variable_get(:@real_x)/128.0)")
   probe=probe.replace("'FPS measured'","'FPS measured,false,false'")
  dlls={'baseline':baseline/name,'candidate':ROOT/'build/runtime-native/bin/Release'/name}
  hashes[engine]={label:inspect(dll,engine=engine)['sha256'] for label,dll in dlls.items()}
  cases=[(120,moving,repeat,label,30) for moving in (False,True) for repeat in range(3) for label in (('baseline','candidate') if repeat%2==0 else ('candidate','baseline'))]
  cases += [(rate,moving,0,'candidate',10) for rate in (40,60) for moving in (False,True)]
  for rate,moving,repeat,label,seconds in cases:
   folder=out/f'{engine}-{label}-{rate}-{int(moving)}-{repeat}'
   source=definitions+b'\n'+helper.read_bytes()+f'\nFPS_MOVING={str(moving).lower()}; FPS_SECONDS={seconds}\n'.encode()+probe.encode()
   options=dict(data=fixture/'Data',rtp=True)
   options.update(dict(screen_size=(1280,720),timing_profile='stock120',render_rate=rate) if engine=='xp' else dict(high=True,wide=True,rate=rate))
   launch(engine,dlls[label],folder,source,**options)
   assert inspect(dlls[label],engine=engine)['sha256']==hashes[engine][label]
   row=json.loads((folder/'fps.json').read_text());row.update(engine=engine,build=label,repeat=repeat)
   rows.append(row);print(f'{folder.name}: {row["present_fps"]:.2f}FPS {row["logic_fps"]:.2f}Hz',flush=True)
 report=dict(passed=all(render_accepted(r) for r in rows if r['build']=='candidate'),hashes=hashes,results=rows,measurement='DXGI Present submissions; physical scan-out not measured')
 (out/'summary.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
 assert report['passed'],'Shared map FPS acceptance failed; inspect summary.json'

def memory_runs(out,baseline):
 rows=[]
 for engine,name in [('xp','Lunetile.dll'),('vxa','LunetileVXA.dll')]:
  for label,dll in [('baseline',baseline/name),('candidate',ROOT/'build/runtime-native/bin/Release'/name)]:
   folder=out/f'{engine}-{label}'
   launch(engine,dll,folder,(ROOT/'tests/runtime_client_memory.rb').read_bytes())
   row=json.loads((folder/'client-memory.json').read_text())
   rows.append(dict(row,engine=engine,build=label,dll_sha256=inspect(dll,engine=engine)['sha256']))
 (out/'summary.json').write_text(json.dumps(dict(passed=True,results=rows,scope='Single-process diagnostic snapshots; private/working-set counters include Ruby and D3D driver allocations, not a RAM reduction guarantee'),indent=2)+'\n',encoding='utf-8')

def output_allocations(out,baseline):
 rows=[];comparisons=[]
 prefix=b'''CLIENT_BENCH_COUNTS=[300,1000]
module RGSSXP
 class << self
  alias allocation_scene_commands scene_commands
  def scene_commands
   commands=allocation_scene_commands
   Graphics.__present(commands,-1.0,nil,0.0)
   commands
  end
 end
end
'''
 for engine,name in [('xp','Lunetile.dll'),('vxa','LunetileVXA.dll')]:
  for label,dll in [('baseline',baseline/name),('candidate',ROOT/'build/runtime-native/bin/Release'/name)]:
   folder=out/f'{engine}-{label}'
   launch(engine,dll,folder,prefix+(ROOT/'tests/runtime_client_bench.rb').read_bytes())
   rows.extend(dict(row,engine=engine,build=label,dll_sha256=inspect(dll,engine=engine)['sha256']) for row in json.loads((folder/'client-bench.json').read_text()))
  for count in (300,1000):
   for views in (1,8,32):
    old,new=[next(r for r in rows if r['engine']==engine and r['build']==label and r['sprites']==count and r['viewports']==views)['allocated_per_frame'] for label in ('baseline','candidate')]
    comparisons.append(dict(engine=engine,sprites=count,viewports=views,baseline=old,candidate=new,ratio=new/old,passed=new/old<=.7))
 report=dict(passed=all(r['passed'] for r in comparisons),comparisons=comparisons,results=rows,scope='160 forced native output submissions per case; allocation includes command generation, native parsing and D3D submission; overloaded scene FPS is not gated')
 (out/'summary.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
 assert report['passed'],'Full output-frame allocation acceptance failed'

def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('output',type=Path);ap.add_argument('--baseline',type=Path,required=True)
 ap.add_argument('--profile',choices=('cpu','render','memory','output-allocation'),default='cpu')
 args=ap.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
 if args.profile=='render':render_runs(out,args.baseline.resolve());return
 if args.profile=='memory':memory_runs(out,args.baseline.resolve());return
 if args.profile=='output-allocation':output_allocations(out,args.baseline.resolve());return
 rows=[];hashes={}
 for engine,name in [('xp','Lunetile.dll'),('vxa','LunetileVXA.dll')]:
  dlls={'baseline':args.baseline.resolve()/name,'candidate':ROOT/'build/runtime-native/bin/Release'/name}
  hashes[engine]={label:inspect(dll,engine=engine)['sha256'] for label,dll in dlls.items()}
  for repeat in range(3):
   for kind,script,file in [('objects','runtime_client_bench.rb','client-bench.json'),('text','runtime_text_bench.rb','text-bench.json')]:
    for label in (('baseline','candidate') if repeat%2==0 else ('candidate','baseline')):
     folder=out/f'{engine}-{kind}-{repeat}-{label}'
     launch(engine,dlls[label],folder,(ROOT/'tests'/script).read_bytes())
     assert inspect(dlls[label],engine=engine)['sha256']==hashes[engine][label],'DLL changed during capture'
     for row in json.loads((folder/file).read_text(encoding='utf-8')):rows.append(dict(row,engine=engine,kind=kind,repeat=repeat,build=label))
     print(f'{engine} {kind} {repeat} {label} PASS',flush=True)
 comparisons=compare(rows)
 report=dict(passed=all(r['passed'] for r in comparisons),hashes=hashes,comparisons=comparisons,results=rows,scope='CPU-only command generation and draw_text, three alternating pairs, no physical scan-out claim')
 (out/'summary.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
 assert report['passed'],'Shared client acceptance failed; inspect summary.json'
 print('Shared client CPU/allocation acceptance PASS')

if __name__=='__main__':main()
