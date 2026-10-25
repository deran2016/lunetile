"""Compare template Ruby scripts using the same immutable DLL for both builds."""
import argparse,hashlib,json,statistics
from pathlib import Path
from benchmark_runtime_client import render_accepted
from test_runtime import run as run_xp
from test_runtime_vxa import run as run_vxa
from rxdata import read

ROOT=Path(__file__).resolve().parents[1]

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def source(project,engine):
 ext='rxdata' if engine=='xp' else 'rvdata2'
 entries=read((project/f'Data/Scripts.{ext}').read_bytes())
 stock=read((ROOT/f'template-{engine}/Data/Scripts.{ext}').read_bytes())
 original=next(e.source() for e in stock if e.name==b'Main')
 if engine=='xp':original=original.replace(b'\r\n',b'\n')
 main=next(e.source() for e in entries if e.name==b'Main')
 if not main.endswith(original):raise ValueError('Reviewed template Main suffix missing')
 definitions=b'\n'.join(e.source().replace(b'\r\r\n',b'\n') for e in entries if e.name!=b'Main')
 prefix=definitions+b'\n'+main[:-len(original)]
 if engine=='xp':prefix+=b'\n'+(ROOT/'tests/runtime_client_fps_xp.rb').read_bytes().split(b'sprites=Spriteset_Map.new')[0]
 else:prefix+=b'\nDataManager.init\nDataManager.setup_new_game\n'
 prefix+=f'\nSTOCK_EXT={ext!r}\n'.encode()
 prefix+=(ROOT/'tests/stock_script_fixture.rb').read_bytes()
 return prefix+b"\n$stock_base=Marshal.load(Marshal.dump(load_data('Data/Map001.'+STOCK_EXT)))\n"

def run(engine,project,output,probe,rate=120,on_start=None):
 name='Lunetile.dll' if engine=='xp' else 'LunetileVXA.dll'
 options=dict(data=project/'Data',rtp=True,on_start=on_start)
 options.update(dict(screen_size=(1280,720),timing_profile='stock120',render_rate=rate) if engine=='xp' else dict(wide=True,high=True,rate=rate))
 combined=source(project,engine)+probe
 if engine=='xp':return run_xp(ROOT/'template-xp/Game.exe',project/name,output,'',combined,timeout=900,**options)
 return run_vxa(output,combined,dll=project/name,timeout=900,**options)

def compare(rows):
 result=[]
 for engine in ('xp','vxa'):
  groups={(r['kind'],r['count']) for r in rows if r['engine']==engine}
  for kind,count in sorted(groups):
   old,new=[[r for r in rows if r['engine']==engine and r['build']==label and r['kind']==kind and r['count']==count] for label in ('baseline','candidate')]
   mean=lambda group,key:statistics.mean(r[key] for r in group)
   b,a=mean(old,'mean_ms'),mean(new,'mean_ms');bp,ap=mean(old,'p95_ms'),mean(new,'p95_ms')
   allocation=mean(new,'allocated_per_call')/mean(old,'allocated_per_call')
   if count<300:passed=a-b<=max(b*.1,.05) and ap-bp<=max(bp*.1,.1)
   elif kind=='characters_idle':passed=a<=b*.7 and allocation<=.6
   elif kind=='queries':passed=a<=b*.3 and allocation<=(.75 if engine=='vxa' else 1.0)
   elif kind=='map_moving':passed=a<=b*.7
   else:passed=a<=b*1.1 and ap<=bp*1.1
   result.append(dict(engine=engine,kind=kind,count=count,mean_ratio=a/b,p95_ratio=ap/bp,allocation_ratio=allocation,passed=bool(passed)))
 return result

def cpu(baseline,candidate,out,samples=1500,warmup=200,pairs=3):
 rows=[];hashes={}
 probe=f'STOCK_SAMPLES={samples};STOCK_WARMUP={warmup}\n'.encode()+(ROOT/'tests/runtime_stock_script_bench.rb').read_bytes()
 for engine in ('xp','vxa'):
  name='Lunetile.dll' if engine=='xp' else 'LunetileVXA.dll'
  if (baseline/engine/name).read_bytes()!=(candidate/engine/name).read_bytes():raise ValueError('Script comparison requires exactly the same DLL')
  hashes[engine]=dict(dll=sha(baseline/engine/name),scripts={label:sha(root/engine/f'Data/Scripts.{"rxdata" if engine=="xp" else "rvdata2"}') for label,root in [('baseline',baseline),('candidate',candidate)]})
  for pair in range(pairs):
   for label in (('baseline','candidate') if pair%2==0 else ('candidate','baseline')):
    project=(baseline if label=='baseline' else candidate)/engine
    folder=out/f'{engine}-{pair}-{label}'
    run(engine,project,folder,probe)
    data=json.loads((folder/'stock-script-bench.json').read_text())
    rows.extend(dict(row,engine=engine,build=label,pair=pair) for row in data)
    print(engine,pair,label,'complete',flush=True)
 comparisons=compare(rows)
 report=dict(passed=all(r['passed'] for r in comparisons),formal=samples==1500 and warmup==200 and pairs==3,hashes=hashes,comparisons=comparisons,results=rows,samples=samples,warmup=warmup,pairs=pairs,scope='Unpaced stock Ruby calls; no physical FPS claim; same DLL for each engine')
 (out/'summary.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
 if not report['passed']:raise AssertionError('Stock script performance gate failed; first report retained')

def render_probe(engine):
 probe=(ROOT/'tests/runtime_vxa_fps.rb').read_text(encoding='utf-8')
 probe=probe[probe.index('$game_player.instance_variable_set'):]
 if engine=='xp':
  probe=probe.replace('$game_player.real_x',"($game_player.instance_variable_get(:@real_x)/128.0)").replace("'FPS measured'","'FPS measured,false,false'")
 # Scene.update contains Graphics.update: subtract its measured scheduler wait.
 probe=probe.replace('  scene.update\n','  began=Process.clock_gettime(Process::CLOCK_MONOTONIC)\n  scene.update\n  $stock_frame_ms=(Process.clock_gettime(Process::CLOCK_MONOTONIC)-began)*1000\n')
 probe=probe.replace('native,parse,gpu,combined,total = [],[],[],[],[]','native,parse,gpu,combined,total = [],[],[],[],[]\nframe_work=[]')
 probe=probe.replace('    native << timing[0]','    frame_work << [$stock_frame_ms-timing[1],0.0].max\n    native << timing[0]')
 probe=probe.replace("File.write('fps.json',JSON.generate(result))", "result[:render_total_ms]=result[:total_ms]\nresult[:total_ms]=summary.call(frame_work)\nFile.write('fps.json',JSON.generate(result))")
 setup='sprites=Spriteset_Map.new\nscene=Object.new\nscene.define_singleton_method(:update) { $game_system.map_interpreter.update;$game_map.update;$game_player.update;$game_system.update;$game_screen.update;sprites.update;Graphics.update }\n' if engine=='xp' else 'SceneManager.goto(Scene_Map)\nscene=SceneManager.scene\nscene.start\nscene.post_start\n'
 return setup,probe


def render(baseline,candidate,out):
 rows=[];hashes={}
 for engine in ('xp','vxa'):
  name='Lunetile.dll' if engine=='xp' else 'LunetileVXA.dll'
  if (baseline/engine/name).read_bytes()!=(candidate/engine/name).read_bytes():raise ValueError('Different comparison DLLs')
  hashes[engine]=dict(dll=sha(candidate/engine/name),scripts={label:sha(root/engine/f'Data/Scripts.{"rxdata" if engine=="xp" else "rvdata2"}') for label,root in [('baseline',baseline),('candidate',candidate)]})
  setup,probe=render_probe(engine)
  cases=[(120,moving,pair,label,30) for moving in (False,True) for pair in range(3) for label in (('baseline','candidate') if pair%2==0 else ('candidate','baseline'))]
  cases += [(rate,moving,0,'candidate',10) for rate in (40,60) for moving in (False,True)]
  for rate,moving,pair,label,seconds in cases:
   folder=out/f'{engine}-{label}-{rate}-{int(moving)}-{pair}'
   body=(setup+f'FPS_MOVING={str(moving).lower()};FPS_SECONDS={seconds}\n'+probe).encode()
   run(engine,(baseline if label=='baseline' else candidate)/engine,folder,body,rate)
   row=json.loads((folder/'fps.json').read_text());rows.append(dict(row,engine=engine,build=label,pair=pair))
   print(folder.name,f'{row["present_fps"]:.3f}FPS {row["logic_fps"]:.3f}Hz',flush=True)
 comparisons=[]
 for engine in ('xp','vxa'):
  for moving in (False,True):
   old,new=[[r for r in rows if r['engine']==engine and r['build']==label and r['moving']==moving and r['render_rate']==120] for label in ('baseline','candidate')]
   ratios={k:statistics.mean(r['total_ms'][k] for r in new)/statistics.mean(r['total_ms'][k] for r in old) for k in ('mean','p95')}
   comparisons.append(dict(engine=engine,moving=moving,ratios=ratios,passed=all(v<=1.05 for v in ratios.values())))
 report=dict(passed=all(c['passed'] for c in comparisons) and all(render_accepted(r) for r in rows if r['build']=='candidate'),hashes=hashes,comparisons=comparisons,results=rows,scope='Complete Scene update minus scheduler wait, including logic/sprite synchronization/generation/parsing/submission/Present. GPU recorded separately. Successful DXGI submissions; physical scanout unverified.')
 (out/'summary.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
 if not report['passed']:raise AssertionError('Stock template frame acceptance failed; report retained')

def save(baseline,candidate,out):
 if (baseline/'vxa/LunetileVXA.dll').read_bytes()!=(candidate/'vxa/LunetileVXA.dll').read_bytes():raise ValueError('Script comparison requires exactly the same DLL')
 rows=[]
 for pair in range(3):
  for label in (('baseline','candidate') if pair%2==0 else ('candidate','baseline')):
   root=baseline if label=='baseline' else candidate
   folder=out/f'{pair}-{label}'
   run('vxa',root/'vxa',folder,(ROOT/'tests/runtime_stock_script_save_bench.rb').read_bytes())
   rows.extend(dict(row,build=label,pair=pair) for row in json.loads((folder/'stock-script-save-bench.json').read_text()))
 comparisons=[]
 for count in (0,300):
  old,new=[[r for r in rows if r['count']==count and r['build']==label] for label in ('baseline','candidate')]
  ratio=statistics.mean(r['mean_ms'] for r in new)/statistics.mean(r['mean_ms'] for r in old)
  reads=all(r['reads']==[16]*5 for r in new) and all(r['reads']==[32]*5 for r in old)
  comparisons.append(dict(count=count,mean_ratio=ratio,reads_verified=reads,passed=reads and ratio<=(.7 if count==300 else 1.1)))
 report=dict(passed=all(c['passed'] for c in comparisons),comparisons=comparisons,results=rows,dll_sha256=sha(candidate/'vxa/LunetileVXA.dll'),scope='Five warm 16-slot constructions per case, three alternating pairs; full save validation retained')
 (out/'summary.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
 if not report['passed']:raise AssertionError('Stock save preview acceptance failed')

def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('baseline',type=Path);ap.add_argument('candidate',type=Path);ap.add_argument('output',type=Path)
 ap.add_argument('--samples',type=int,default=1500);ap.add_argument('--warmup',type=int,default=200);ap.add_argument('--pairs',type=int,default=3)
 ap.add_argument('--profile',choices=('cpu','render','save'),default='cpu')
 a=ap.parse_args()
 if not 20<=a.samples<=3000 or not 0<=a.warmup<=500 or not 1<=a.pairs<=3:ap.error('Unsupported diagnostic sample bounds')
 out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
 if a.profile=='cpu':cpu(a.baseline.resolve(),a.candidate.resolve(),out,a.samples,a.warmup,a.pairs)
 elif a.profile=='render':render(a.baseline.resolve(),a.candidate.resolve(),out)
 else:save(a.baseline.resolve(),a.candidate.resolve(),out)

if __name__=='__main__':main()
