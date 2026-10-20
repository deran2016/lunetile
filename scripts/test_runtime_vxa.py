"""Run VX Ace's Unicode launcher against the independent DLL in disposable copies."""
import argparse,hashlib,json,os,shutil,subprocess,time
from pathlib import Path
import psutil
from inspect_runtime import inspect
from test_runtime import scripts
from rxdata import read

ROOT=Path(__file__).resolve().parents[1]

def run(output,source,*,dll=None,high=False,rate=60,wide=False,rtp=False,timeout=90,saves=None):
 output=output.resolve();output.mkdir(parents=True,exist_ok=False)
 dll=dll or ROOT/'build/runtime-native/bin/Release/LunetileVXA.dll'
 artifact=inspect(dll,engine='vxa')
 shutil.copy2(ROOT/'template-vxa/Game.exe',output/'Game.exe')
 shutil.copy2(dll,output/'LunetileVXA.dll')
 (output/'Scripts.rvdata2').write_bytes(scripts(source))
 ini='[Game]\nLibrary=LunetileVXA.dll\nScripts=Scripts.rvdata2\nTitle=Lunetile VX Ace verification\nRTP='+('RPGVXAce' if rtp else '')+'\n[Lunetile]\n'
 if high:ini+=f'TimingProfile=stock120\nRenderRate={rate}\n'
 if wide:ini+='Width=1280\nHeight=720\n'
 (output/'Game.ini').write_text(ini,encoding='utf-8')
 if rtp:shutil.copytree(ROOT/'template-vxa/Data',output/'Data')
 if saves:shutil.copytree(saves,output/'Saves')
 environment=os.environ.copy();environment['LUNETILE_TEST_BACKGROUND']='1'
 process=subprocess.Popen([str(output/'Game.exe')],cwd=output,env=environment)
 modules=set();deadline=time.monotonic()+timeout
 try:
  while process.poll() is None:
   if time.monotonic()>deadline:raise TimeoutError(f'VX Ace runtime timed out: {output}')
   try:modules.update(str(Path(m.path).resolve()) for m in psutil.Process(process.pid).memory_maps())
   except (psutil.NoSuchProcess,psutil.AccessDenied):pass
   time.sleep(.02)
 finally:
  if process.poll() is None:process.terminate();process.wait()
 log=(output/'rgssxp.log').read_text(encoding='utf-8',errors='replace') if (output/'rgssxp.log').exists() else ''
 report={'exit_code':process.returncode,'runtime_sha256':artifact['sha256'],'modules':sorted(modules),'log':log,'completed':(output/'runtime-complete.txt').exists()}
 (output/'result.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
 assert not any(Path(p).name.lower().startswith('rgss30') for p in modules),report
 assert str((output/'LunetileVXA.dll').resolve()) in modules,report
 assert report['completed'] and 'Ruby finalized' in log,report
 return report

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('output',type=Path);parser.add_argument('--stock',action='store_true')
 args=parser.parse_args();out=args.output.resolve()
 smoke=b"""raise 'size' unless [Graphics.width,Graphics.height]==[544,416]
raise 'rate' unless Graphics.frame_rate==60
raise 'symbols' unless Input.press?(:C)==false
Graphics.update
File.write('runtime-complete.txt','VXA ABI and renderer')
"""
 run(out/'basic',smoke)
 for rate in (40,60,120):
  run(out/f'wide-{rate}',b"""raise 'size' unless [Graphics.width,Graphics.height]==[1280,720]
raise 'rate' unless Graphics.frame_rate==120
raise 'scale' unless RGSSXP::Timing.scale==2
120.times { Graphics.update }
raise 'output scheduler' unless Graphics.__refresh_stats[0]==Graphics.render_rate
File.write('runtime-complete.txt','VXA wide refresh')
""",high=True,wide=True,rate=rate)
 run(out/'한글-경로',smoke)
 run(out/'features',(ROOT/'tests/runtime_vxa_features.rb').read_bytes())
 if args.stock:
  entries=read((ROOT/'template-vxa/Data/Scripts.rvdata2').read_bytes())
  definitions=b'\n'.join(e.source().replace(b'\r\r\n',b'\n') for e in entries if e.name!=b'Main')
  stock=definitions+b'\n'+(ROOT/'src/runtime/vxa_entry.rb').read_bytes()+b'\n'+(ROOT/'src/runtime/vxa_stock.rb').read_bytes()+b'\n'+(ROOT/'tests/runtime_vxa_stock.rb').read_bytes()
  run(out/'stock-60',stock,rtp=True,timeout=180)
  for rate in (40,60,120):run(out/f'stock-120-{rate}',stock,rtp=True,wide=True,high=True,rate=rate,timeout=180)
  reload=definitions+b'\n'+(ROOT/'src/runtime/vxa_stock.rb').read_bytes()+b"""
DataManager.init
raise 'restart load' unless DataManager.load_game(15)
raise 'restart variable' unless $game_variables[1]==1977
$game_system.on_after_load
Graphics.update
File.write('runtime-complete.txt','save restored in new process')
"""
  run(out/'restart-load',reload,rtp=True,wide=True,high=True,saves=out/'stock-120-60/Saves')
 artifact=inspect(ROOT/'build/runtime-native/bin/Release/LunetileVXA.dll',engine='vxa')
 report={'passed':True,'runtime_sha256':artifact['sha256'],'scope':'Original Unicode launcher, independent DLL load, basic rendering, 544x416 and 1280x720, 120Hz logic and 40/60/120FPS output, archive and graphics API regression; no full campaign or pixel/audio parity certification','cases':['basic','wide-40','wide-60','wide-120','한글-경로','features']}
 if args.stock:
  report['stock_scenarios']=[json.loads((out/name/'vxa-stock-result.json').read_text(encoding='utf-8')) for name in ['stock-60','stock-120-40','stock-120-60','stock-120-120']]
  report['process_restart_save_load']=True
 (out/'summary.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
 (ROOT/'build/runtime-native/bin/Release/verification-vxa.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
 print('VX Ace launcher smoke PASS')

if __name__=='__main__':main()
