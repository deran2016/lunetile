"""Run the same owned story/inputs/RNG through original and replacement default scenes."""
import argparse,json,shutil,subprocess,time,zlib
from pathlib import Path
import psutil
from PIL import Image
from test_runtime import ROOT,ORIGINAL_EXE,ORIGINAL_DLL,sha
from test_runtime_graphics import records
from test_runtime_stock_boot import copy_missing
from rxdata import read,write,Entry

REQUIRED={'switches','variables','party','items','player','timer','frame_rate','frame_count','driver_tick'}

def shared_probe():
 story=(ROOT/'tests/runtime_stock_scenario.rb').read_text().split('module ScenarioGraphics\n',1)[0]
 assert story.count('RGSSXP::Saves.exist?(0)')==1
 story=story.replace('RGSSXP::Saves.exist?(0)','scene_save_exists')
 marker="File.write('runtime-complete.txt','stock-scenario,false,false')"
 assert story.count(marker)==1
 story=story.replace(marker,'scene_write_oracle\n        '+marker)
 combat=(ROOT/'tests/runtime_full_combat.rb').read_text().split('module FixtureGameoverRecovery\n',1)[0]
 compatibility="Graphics.frame_rate=40\nGraphics.frame_count=0\nunless File.respond_to?(:write)\n class << File\n  def write(path,value)\n   open(path,'wb') { |file| file.write(value) }\n  end\n end\nend\n"
 hooks=(ROOT/'tests/rgss_scene_story_hooks.rb').read_text()
 return (compatibility+story+'\n'+combat+'\n'+hooks).encode('utf-8')

def run_case(project,dll,out,rtp,probe):
 shutil.copytree(project,out,ignore=shutil.ignore_patterns('Saves','*.log','manual-*'))
 library='RGSS104E.dll' if sha(dll)==ORIGINAL_DLL else 'Lunetile.dll'
 shutil.copy2(dll,out/library)
 for name in ('Graphics','Audio'):shutil.copytree(rtp/name,out/name,dirs_exist_ok=True,copy_function=copy_missing)
 pictures=out/'Graphics/Pictures';pictures.mkdir(parents=True,exist_ok=True)
 Image.new('RGBA',(96,64),(255,100,30,180)).save(pictures/'Validation.png')
 path=out/'Data/Scripts.rxdata';entries=read(path.read_bytes());index=len(entries)-1
 entry=Entry(0,b'Owned original/new scene oracle',zlib.compress(probe),b'')
 path.write_bytes(write(entries[:index]+[entry]+entries[index:],{index:probe}))
 (out/'Game.ini').write_text(f'[Game]\nLibrary={library}\nScripts=Data/Scripts.rxdata\nTitle=RGSS full-scene comparison\nRTP1=\nRTP2=\nRTP3=\n')
 process=subprocess.Popen([str(out/'Game.exe')],cwd=out);print('Full-scene oracle PID='+str(process.pid)+' '+str(out),flush=True)
 started=time.monotonic();images={}
 try:
  while process.poll() is None:
   if time.monotonic()-started>240:raise TimeoutError('Full-scene oracle did not finish')
   if sha(dll) not in images.values():
    try:images.update({item.path:sha(Path(item.path)) for item in psutil.Process(process.pid).memory_maps() if Path(item.path).suffix.lower() in ('.exe','.dll') and Path(item.path).is_file()})
    except psutil.NoSuchProcess:pass
   time.sleep(.1)
 finally:
  if process.poll() is None:process.terminate();process.wait()
  (out/'modules.json').write_text(json.dumps(images,indent=2))
  (out/'process-result.json').write_text(json.dumps({'exit_code':process.returncode,'dll_sha256':sha(dll)},indent=2))
 assert process.returncode==0 and (out/'runtime-complete.txt').exists()
 assert sha(dll) in images.values()
 if sha(dll)!=ORIGINAL_DLL:assert ORIGINAL_DLL not in images.values()
 assert not any(Path(name).name.lower()=='rgssframepacing.dll' for name in images)
 result=records(out/'types-reference.txt');assert set(result)==REQUIRED
 combat={key:int(value) for key,value in (line.split('=') for line in (out/'full-combat-result.txt').read_text().splitlines())}
 assert combat['turns']>=3 and combat['enemy_actions']>=2 and combat['actor_damage']>0 and combat['enemy_damage']>=10000
 return result,combat

def main():
 ap=argparse.ArgumentParser(description=__doc__)
 for name in ('project','migrated','original','dll','rtp','output'):ap.add_argument(name,type=Path)
 a=ap.parse_args();project,migrated,old,new,rtp=[p.resolve() for p in (a.project,a.migrated,a.original,a.dll,a.rtp)]
 assert sha(project/'Game.exe')==sha(migrated/'Game.exe')==ORIGINAL_EXE and sha(old)==ORIGINAL_DLL
 inputs=[project/'Game.exe',project/'Data/Scripts.rxdata',migrated/'Data/Scripts.rxdata',old,new];before={str(p):sha(p) for p in inputs}
 out=a.output.resolve();out.mkdir(parents=True,exist_ok=False);probe=shared_probe();(out/'shared-probe.rb').write_bytes(probe)
 original,old_combat=run_case(project,old,out/'original',rtp,probe)
 replacement,new_combat=run_case(migrated,new,out/'replacement',rtp,probe)
 different=sorted(key for key in REQUIRED if original[key]!=replacement[key])
 assert before=={str(p):sha(p) for p in inputs}
 report={'passed':not different and old_combat==new_combat,'dll_sha256':sha(new),'original_sha256':ORIGINAL_DLL,'shared_probe_sha256':sha(out/'shared-probe.rb'),'original_records':original,'replacement_records':replacement,'different_records':different,'original_combat':old_combat,'replacement_combat':new_combat,'inputs_preserved':True,'scope':'Same own content, logical confirmation input, fixed 37-percent RNG and default scenes through save/load, gameover/restart, multi-turn combat and ending. Original writes only its isolated root save; replacement uses its separate versioned saves. Numeric/state/frame-count oracle, not all pixels, audio or physical-key parity.'}
 (out/'summary.json').write_text(json.dumps(report,indent=2));assert report['passed'],report
 print('Original/replacement complete owned story oracle: PASS')

if __name__=='__main__':main()
