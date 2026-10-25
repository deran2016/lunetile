"""Compare the preserved runtime with WebView2 unused and with an owned local panel."""
import argparse,json,shutil,statistics
from pathlib import Path
from benchmark_stock_scripts import ROOT,render_probe,run,sha
from benchmark_runtime_client import render_accepted
from test_runtime_browser import windows,user,wait,activate_owned

def foreground_ready(process,folder):
 def find():
  assert process.poll() is None,'Owned benchmark game exited before activation'
  return next((h for h,n,r in windows(process.pid) if n!='#32770' and user.IsWindowVisible(h) and r.right-r.left>300 and r.bottom-r.top>200),None)
 activate_owned(wait(find,'Owned benchmark HWND missing'))
 (folder/'benchmark-foreground-ready').write_bytes(b'1')

def compare(rows):
 comparisons=[]
 for engine in ('xp','vxa'):
  for moving in (False,True):
   groups=[[r for r in rows if r['engine']==engine and r['moving']==moving and r['render_rate']==120 and r['build']==label and not r['browser_open']] for label in ('baseline','candidate')]
   ratios={k:statistics.mean(r['total_ms'][k] for r in groups[1])/statistics.mean(r['total_ms'][k] for r in groups[0]) for k in ('mean','p95')}
   comparisons.append(dict(engine=engine,moving=moving,ratios=ratios,passed=all(v<=1.05 for v in ratios.values())))
 return comparisons

def main():
 ap=argparse.ArgumentParser(description=__doc__)
 for name in ('baseline','candidate','projects','output'):ap.add_argument(name,type=Path)
 a=ap.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
 projects={};hashes={};rows=[]
 for label,dlls in [('baseline',a.baseline.resolve()),('candidate',a.candidate.resolve())]:
  for engine,name in [('xp','Lunetile.dll'),('vxa','LunetileVXA.dll')]:
   project=out/'projects'/label/engine;project.mkdir(parents=True)
   shutil.copytree(a.projects/engine/'Data',project/'Data');shutil.copy2(dlls/name,project/name)
   projects[label,engine]=project;hashes[label,engine]=sha(project/name)
 for engine in ('xp','vxa'):
  setup,probe=render_probe(engine)
  foreground="""limit=Process.clock_gettime(Process::CLOCK_MONOTONIC)+10
until File.exist?('benchmark-foreground-ready')
  Graphics.update
  raise 'Owned foreground activation timeout' if Process.clock_gettime(Process::CLOCK_MONOTONIC)>limit
end
active=Win32API.new('user32','GetActiveWindow','','L').call
raise 'Missing owned HWND' if active==0
Win32API.new('user32','SetWindowPos','LLLLLLL','L').call(active,-1,0,0,0,0,3)
Win32API.new('user32','SetForegroundWindow','L','L').call(active)
raise 'Performance game not foreground' unless Win32API.new('user32','GetForegroundWindow','','L').call==active
"""
  local='Dir.mkdir("Web") unless Dir.exist?("Web")\n'
  for path in sorted((ROOT/'tests/fixtures/browser').iterdir()):local+=f'File.binwrite("Web/{path.name}",["{path.read_bytes().hex()}"].pack("H*"))\n'
  local+='''$browser=Lunetile::Browser.new(Rect.new(80,60,1120,600))
$browser.load_file('Web/index.html')
limit=Process.clock_gettime(Process::CLOCK_MONOTONIC)+20
until [:ready,:failed].include?($browser.state)
  scene.update
  raise 'Browser performance initialization timeout' if Process.clock_gettime(Process::CLOCK_MONOTONIC)>limit
end
raise "Browser performance initialization failed #{$browser.error}" unless $browser.state==:ready
$browser.focus
60.times { scene.update }
'''
  cases=[(120,moving,pair,label,False,30) for moving in (False,True) for pair in range(3) for label in (('baseline','candidate') if pair%2==0 else ('candidate','baseline'))]
  cases += [(120,moving,0,'candidate',True,30) for moving in (False,True)]
  cases += [(rate,moving,0,'candidate',opened,10) for rate in (40,60) for moving in (False,True) for opened in (False,True)]
  for rate,moving,pair,label,opened,seconds in cases:
   folder=out/f'{engine}-{label}-{rate}-{int(moving)}-{int(opened)}-{pair}'
   check="""
foreground=Win32API.new('user32','GetForegroundWindow','','L').call
if foreground!=active
  pid=[0].pack('L');Win32API.new('user32','GetWindowThreadProcessId','Lp','L').call(foreground,pid)
  File.write('foreground-interrupted.json',JSON.generate({owned:active,foreground:foreground,pid:pid.unpack1('L')}))
  raise 'Performance game lost foreground'
end
"""
   body=(foreground+setup+(local if opened else '')+f'FPS_MOVING={str(moving).lower()};FPS_SECONDS={seconds}\n'+probe+check).encode('utf-8')
   run(engine,projects[label,engine],folder,body,rate,on_start=foreground_ready)
   row=json.loads((folder/'fps.json').read_text(encoding='utf-8'));rows.append(dict(row,engine=engine,build=label,pair=pair,browser_open=opened))
   (out/'progress.json').write_text(json.dumps(rows,indent=2)+'\n',encoding='utf-8')
   print(folder.name,f'{row["present_fps"]:.3f} FPS, {row["logic_fps"]:.3f} Hz, work {row["total_ms"]["mean"]:.4f}ms',flush=True)
 comparisons=compare(rows)
 report=dict(passed=all(c['passed'] for c in comparisons) and all(render_accepted(r) for r in rows),comparisons=comparisons,results=rows,hashes={label:{e:hashes[label,e] for e in ('xp','vxa')} for label in ('baseline','candidate')},scope='Same optimized stock scripts, preserved/candidate DLLs, foreground owned HWND. Full Scene update minus scheduler wait. Open local HTML uses WebView2 child overlay; successful Present submissions, not physical scanout.')
 (out/'summary.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
 if not report['passed']:raise AssertionError('Browser performance acceptance failed; first results retained')

if __name__=='__main__':main()
