"""Stock title/new-game/menu test with explicitly injected logical input."""
import argparse,json,shutil,statistics,subprocess,sys,time
import psutil
from pathlib import Path
from rxdata import read,write,Entry
import zlib
from test_runtime import ROOT,sha

def copy_missing(source,target):
 if not Path(target).exists():shutil.copy2(source,target)
 return target

def progress(path):
 try:return {key:float(value) for key,value in (line.split('=',1) for line in path.read_text().splitlines())}
 except (OSError,ValueError):return {}

def endurance_monitor(process,out,seconds):
 samples=[];began=time.monotonic();next_notice=0;images={}
 try:
  while process.poll() is None:
   elapsed=time.monotonic()-began
   if elapsed>seconds*2+300:raise TimeoutError('Active endurance run exceeded bounded wall time')
   try:
    target=psutil.Process(process.pid);memory=target.memory_info()
    state=progress(out/'endurance-progress.txt')
    samples.append({'wall_seconds':elapsed,'active_seconds':state.get('active_seconds',0),'rss':memory.rss,'private_bytes':memory.private,'handles':target.num_handles()})
    if not images and elapsed>5:
     images={item.path:sha(Path(item.path)) for item in target.memory_maps() if Path(item.path).suffix.lower() in ('.dll','.exe') and Path(item.path).is_file()}
    if elapsed>=next_notice:
     print(f"Endurance active={state.get('active_seconds',0):.1f}s transfers={state.get('transfers',0):.0f} private={memory.private/1048576:.1f}MiB",flush=True);next_notice=elapsed+60
   except psutil.NoSuchProcess:break
   time.sleep(1)
 finally:
  (out/'memory-samples.json').write_text(json.dumps(samples,indent=2))
  (out/'modules.json').write_text(json.dumps(images,indent=2))
 return samples,images

def memory_trend(samples):
 if len(samples)>=120:
  width=min(120,len(samples)//3);first=samples[:width];last=samples[-width:]
  growth=statistics.median(item['private_bytes'] for item in last)-statistics.median(item['private_bytes'] for item in first)
  handles=statistics.median(item['handles'] for item in last)-statistics.median(item['handles'] for item in first)
  chunks=[samples[i:i+60] for i in range(0,len(samples)-59,60)]
  points=[(statistics.mean(item['wall_seconds'] for item in part),statistics.median(item['private_bytes'] for item in part)) for part in chunks]
  x=statistics.mean(t for t,_ in points);y=statistics.mean(v for _,v in points)
  slope=sum((t-x)*(v-y) for t,v in points)/sum((t-x)**2 for t,_ in points)*60/1048576 if len(points)>1 else 0
  return {'evaluated':True,'private_median_growth_bytes':growth,'private_slope_mib_per_minute':slope,'handle_median_growth':handles,'bounded':growth<=16*1048576 and slope<=0.5 and handles<=24,'method':'First/last up-to-120-sample private-memory medians; one-minute wall-time median slope including pauses; thresholds 16MiB, 0.5MiB/min and 24 handles; not proof that every allocation is leak-free'}
 return {'evaluated':False,'reason':'Fewer than 120 samples in this analysis window'}

def endurance_result(out,samples,images,seconds,roundtrips):
 result=progress(out/'endurance-result.txt')
 assert result.get('active_seconds',0)>=seconds and result.get('frames',0)>=seconds*40,result
 assert result.get('roundtrips',0)>=roundtrips,result
 original='7b6acb5e2c245b8cfda77fced2cc0e94108384cd1b9ffc8510e7304fcb9feb6c'
 assert images and original not in images.values() and not any(Path(name).name.lower()=='rgssframepacing.dll' for name in images)
 warmup=max(10,seconds/3)
 memory=memory_trend([item for item in samples if item['active_seconds']>=warmup])
 memory['warmup_active_seconds']=warmup
 early=memory_trend([item for item in samples if 60<=item['active_seconds']<=600])
 early['active_time_window_seconds']=[60,600]
 early['scope']='Early repeated map-load phase; excludes initial cache loading. Roundtrip completion is checked separately.'
 full=seconds>=1800 and roundtrips>=100
 if full:assert memory['evaluated'] and memory['bounded'] and early['evaluated'] and early['bounded'],{'steady':memory,'early':early}
 return {'requested_seconds':seconds,'requested_roundtrips':roundtrips,'observed':result,'memory':memory,'early_map_memory':early,'meets_duration_and_roundtrip_gate':full,'loaded_image_count':len(images)}

def main():
 ap=argparse.ArgumentParser();ap.add_argument('project',type=Path);ap.add_argument('output',type=Path)
 ap.add_argument('--scenario',action='store_true')
 ap.add_argument('--full-combat',action='store_true',help='Use a multi-turn basic-attack fixture with fixed test RNG; requires --scenario')
 ap.add_argument('--manual',action='store_true',help='Observe the story without injecting input; requires --scenario')
 ap.add_argument('--endurance-seconds',type=int,help='After the short scenario, keep moving/transferring in the actual map scene; requires --scenario')
 ap.add_argument('--roundtrips',type=int,default=100)
 ap.add_argument('--rtp',type=Path,help='Copy missing local RTP assets into this private test copy; existing project files win')
 ap.add_argument('--render-rate',type=int,choices=[40,60,120],help='Exercise the stock120 settings scene; requires --scenario')
 ap.add_argument('--widescreen-checks',action='store_true',help='Check wide stock window bounds and list layout; requires --scenario')
 ap.add_argument('--map-checks',action='store_true',help='Walk the packaged 40x23 map and check terrain at screen edges; requires --scenario and --widescreen-checks')
 a=ap.parse_args();out=a.output.resolve()
 if a.render_rate and not a.scenario:ap.error('--render-rate requires --scenario')
 if a.widescreen_checks and not a.scenario:ap.error('--widescreen-checks requires --scenario')
 if a.map_checks and (not a.scenario or not a.widescreen_checks or a.manual):ap.error('--map-checks requires --scenario, --widescreen-checks and injected input')
 if a.manual and not a.scenario:ap.error('--manual requires --scenario')
 if a.full_combat and (not a.scenario or a.endurance_seconds is not None):ap.error('--full-combat requires --scenario and no endurance')
 if a.endurance_seconds is not None and (not a.scenario or a.manual or not 1<=a.endurance_seconds<=7200 or not 1<=a.roundtrips<=1000):ap.error('Endurance requires --scenario, no --manual, 1..7200 seconds and 1..1000 roundtrips')
 if a.rtp and not all((a.rtp/name).is_dir() for name in ('Graphics','Audio')):ap.error('RTP must contain Graphics and Audio directories')
 shutil.copytree(a.project,out,ignore=shutil.ignore_patterns('Saves','*.log','manual-*.png','manual-*.json'))
 if a.rtp:
  for name in ('Graphics','Audio'):shutil.copytree(a.rtp/name,out/name,dirs_exist_ok=True,copy_function=copy_missing)
 path=out/'Data/Scripts.rxdata';entries=read(path.read_bytes())
 # Preserve the migrated entries; prepend one visible, separately owned test entry.
 source=(ROOT/'tests'/('runtime_stock_scenario.rb' if a.scenario else 'runtime_stock_boot.rb')).read_bytes()
 if a.render_rate:
  source+=b'\n'+(ROOT/'tests/runtime_refresh_scenario.rb').read_bytes()
  (out/'refresh-test-rate.txt').write_text(str(a.render_rate))
 if a.widescreen_checks:source+=b'\n'+(ROOT/'tests/runtime_widescreen_ui.rb').read_bytes()
 if a.map_checks:source+=b'\n'+(ROOT/'tests/runtime_template_map.rb').read_bytes()
 if a.full_combat:source+=b'\n'+(ROOT/'tests/runtime_full_combat.rb').read_bytes()
 if a.endurance_seconds is not None:
  (out/'scenario-endurance.txt').write_text(f'{a.endurance_seconds}\n{a.roundtrips}\n')
  source+=b'\n'+(ROOT/'tests/endurance_focus.rb').read_bytes()+b'\n'+(ROOT/'tests/runtime_endurance.rb').read_bytes()
 probe=Entry(0,b'RGSSXP stock boot test',zlib.compress(source),b'')
 if a.scenario:
  from PIL import Image
  pictures=out/'Graphics/Pictures';pictures.mkdir(parents=True,exist_ok=True)
  Image.new('RGBA',(96,64),(255,100,30,180)).save(pictures/'Validation.png')
  if a.manual:(out/'scenario-manual.txt').write_text('Manual UI input; no ScenarioDriver')
  # Stock RPG classes must be defined before the content fixture is generated.
  index=len(entries)-1;combined=entries[:index]+[probe]+entries[index:]
 else:index=0;combined=[probe,*entries]
 path.write_bytes(write(combined,{index:source}))
 import os
 environment=os.environ.copy()
 if a.manual:environment.pop('LUNETILE_TEST_BACKGROUND',None)
 else:environment['LUNETILE_TEST_BACKGROUND']='1'
 p=subprocess.Popen([str(out/'Game.exe')],cwd=out,env=environment)
 print(f'PID={p.pid} output={out}',flush=True)
 try:
  if a.endurance_seconds is not None:samples,images=endurance_monitor(p,out,a.endurance_seconds)
  else:p.wait(timeout=300 if a.manual or a.full_combat else 150 if a.map_checks else 75 if a.scenario else 45)
 finally:
  if p.poll() is None:p.terminate();p.wait()
 state_path=out/('scenario-states.txt' if a.scenario else 'scene-states.txt')
 states=state_path.read_text() if state_path.exists() else ''
 required=('Scene_Title','Scene_Map','Scene_Menu','Scene_Save','Scene_Load','Scene_Battle') if a.scenario else ('Scene_Title','Scene_Map','Scene_Menu')
 passed=p.returncode==0 and ((out/'manual-ending-reached.txt').exists() if a.manual else all(scene in states for scene in required) and (out/'runtime-complete.txt').exists())
 if a.render_rate:passed=passed and (out/'refresh-settings-selected.txt').is_file()
 if a.widescreen_checks:passed=passed and (out/'wide-ui-checked.txt').is_file()
 if a.map_checks:passed=passed and all((out/name).is_file() for name in ('template-map-checked.txt','template-large-map-checked.txt'))
 restarted=None
 if passed and a.render_rate:
  original=path.read_bytes()
  probe_source=("RGSSXP::Timing.load_settings\nraise 'FPS did not survive restart' unless Graphics.render_rate == "+str(a.render_rate)+"\nFile.write('refresh-settings-restarted.txt',Graphics.render_rate.to_s)\nexit\n").encode()
  startup=Entry(0,b'Lunetile restart settings test',zlib.compress(probe_source),b'')
  try:
   path.write_bytes(write([startup,*read(original)],{0:probe_source}))
   restarted=subprocess.run([str(out/'Game.exe')],cwd=out,env=environment,timeout=15).returncode==0 and (out/'refresh-settings-restarted.txt').read_text()==str(a.render_rate)
  finally:path.write_bytes(original)
  passed &= restarted
 report={'passed':passed,'exit_code':p.returncode,'states':states,'dll_sha256':sha(out/'Lunetile.dll'),'scope':('Manual UI input' if a.manual else 'Injected logical input')+'; one-hit fixture encounter; no original-gameplay comparison'}
 if restarted is not None:report['settings_restart_passed']=restarted
 if a.render_rate:report['render_rate']=a.render_rate;report['logic_rate']=120
 if a.map_checks:report['map_walk']={'passed':all((out/name).is_file() for name in ('template-map-checked.txt','template-large-map-checked.txt')),'tiles':[40,23],'screen':[1280,720],'vertical_scroll_pixels':16,'scope':'Injected directions through stock movement; four corners/out-of-bounds attempts; terrain pixel readback at all four screen edges; separate 80x45 colored tilemap camera/render checks'}
 if a.full_combat:
  combat=progress(out/'full-combat-result.txt')
  report['combat']=combat
  report['passed'] &= combat.get('turns',0)>=3 and combat.get('enemy_actions',0)>=2 and combat.get('actor_damage',0)>0 and combat.get('enemy_damage',0)>=10000 and (a.manual or 'Scene_Gameover' in states)
  report['scope']=('Manual UI input' if a.manual else 'Injected logical input')+'; gameover/restart, one enemy HP=10000, zero gear defense/evasion, fixed 37-percent test RNG, multi-turn basic attacks; no original-gameplay comparison'
 if a.endurance_seconds is not None and passed:
  report['endurance']=endurance_result(out,samples,images,a.endurance_seconds,a.roundtrips)
  report['scope']+='; active map endurance with movement, stock map transfers, MIDI pitch changes, private-memory and handle sampling'
 (out/'boot-result.json').write_text(json.dumps(report,indent=2))
 if not report['passed']:raise RuntimeError('Stock boot failed; see scene-states.txt and rgssxp.log')
 if a.endurance_seconds is not None:print('Stock endurance: PASS ('+str(a.endurance_seconds)+' requested active seconds; '+str(a.roundtrips)+' roundtrips; '+('full duration/memory gate' if report['endurance']['meets_duration_and_roundtrip_gate'] else 'short driver smoke only')+')')
 elif a.full_combat:print('Stock multi-turn combat and scene integration: PASS ('+report['scope']+')')
 elif a.manual:print('Stock scenario: PASS (manual UI input; one-hit encounter)')
 else:print('Stock scenario: PASS (injected logical input)' if a.scenario else 'Stock title -> new game -> map -> menu: PASS (injected logical input)')

if __name__=='__main__':main()
