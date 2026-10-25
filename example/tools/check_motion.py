"""Measure held input and turns in two isolated real XP clients."""
import argparse,json,os,shutil,socket,subprocess,time
from pathlib import Path
from smoke_test import ROOT,start_server,stop
from rxdata import read,write
from prepare_example import MAIN_ENTRY,digest
from review_gui import combat_arena

def summarize(report):
 samples=report['samples'];frames=[];gaps=[];gap=0;diagonal=0;maximum=0;first=None
 for previous,current in zip(samples,samples[1:]):
  dt=current[0]-previous[0];dx=current[2]-previous[2];dy=current[3]-previous[3]
  frames.append(dt*1000);maximum=max(maximum,abs(dx),abs(dy))
  diagonal+=bool(dx and dy)
  if first is None and (dx or dy):first=current[0]*1000
  # Exclude deliberate turns/stops and startup; inspect held straight input.
  if first is not None and current[1] in report.get('held_phases',[0,1,2,3]) and current[1]==previous[1] and current[0]>report.get('movement_delay_ms',0)/1000+.3:
   if not dx and not dy:gap+=dt
   elif gap:gaps.append(gap*1000);gap=0
  elif gap:gaps.append(gap*1000);gap=0
 frames.sort()
 rendered=report.get('render_samples',[])
 intervals=sorted((b[0]-a[0])*1000 for a,b in zip(rendered,rendered[1:]))
 camera=max((max(abs(b[4]-a[4]),abs(b[5]-a[5])) for a,b in zip(samples,samples[1:])),default=0)
 summary={'input_to_first_motion_ms':first-report.get('movement_delay_ms',0) if first is not None else None,'max_step_real_units':maximum,'diagonal_ticks':diagonal,
         'held_gaps_over_frame_ms':[round(g,3) for g in gaps if g>1000/60+.5],
         'longest_held_gap_ms':max(gaps,default=0),'logic_frame_p95_ms':frames[int(len(frames)*.95)],
         'logic_frame_max_ms':max(frames),'samples':len(samples),
         'move_intervals_ms':[round((b[0]-a[0])*1000,3) for a,b in zip(report['moves'],report['moves'][1:])],
         'foreground_required':report['foreground_required'],'pixel':report['pixel'],'notices':report.get('notices',[]),
         'max_camera_step_real_units':camera,'render_frames':len(rendered),
         'render_frame_p95_ms':intervals[int(len(intervals)*.95)] if intervals else None,
         'render_frame_max_ms':max(intervals,default=None),
         'settled':all(abs(a-b*128)<.001 for a,b in zip(samples[-1][2:4],samples[-1][6:8])),'combat_counts':report.get('combat_counts'),
         'max_active_effects':report.get('max_active_effects',0),'max_projectiles':report.get('max_projectiles',0),'max_held_weapons':report.get('max_held_weapons',0),'max_particles':report.get('max_particles',0),'foreground_lost_ticks':report.get('foreground_lost_ticks',0)}
 trials=report.get('latency_trials',[])
 if trials:
  assert len(trials)==40 and all(t.get('present_ms') is not None and t.get('ack_ms') is not None for t in trials),trials
  latencies=sorted(t['present_ms'] for t in trials)
  summary.update(latency_trials=trials,input_to_present_p95_ms=latencies[int(len(latencies)*.95)],
   input_to_present_max_ms=max(latencies),all_presented_before_ack=all(t['present_ms']<t['ack_ms'] for t in trials))
 turns=report.get('turn_trials',[])
 if turns:
  assert len(turns)==80 and all(t.get('wait_ticks')==0 and t.get('present_ms') is not None for t in turns),turns
  latency=sorted(t['present_ms'] for t in turns)
  summary.update(rapid_turns=len(turns),off_center_turns=sum(t['off_center'] for t in turns),
   direction_change_max_wait_ticks=max(t['wait_ticks'] for t in turns),turn_present_p95_ms=latency[int(len(latency)*.95)],turn_trials=turns)
 return summary

def measure(bundle,output,foreground=None,assert_smooth=False,combat=False,latency=False,rapid=False,projectile=False):
 combat=combat or projectile
 bundle,output=bundle.resolve(),output.resolve()
 if output.exists():raise ValueError('Use a new verification directory')
 if output.is_relative_to(bundle) or bundle.is_relative_to(output):raise ValueError('Verification must be separate from distribution')
 output.mkdir(parents=True)
 (output/'build.json').write_text(json.dumps({name:digest(bundle/name) for name in ['client/Lunetile.dll','client/Data/Scripts.rxdata','server/lunetile-mmo-server.exe']},indent=2)+'\n')
 server=output/'server';shutil.copytree(bundle/'server/data',server/'data')
 shutil.copy2(bundle/'server/lunetile-mmo-server.exe',server/'lunetile-mmo-server.exe')
 with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
 config=json.loads((server/'data/server.json').read_text(encoding='utf-8'));config['bind']=f'127.0.0.1:{port}'
 (server/'data/server.json').write_text(json.dumps(config),encoding='utf-8')
 if combat:combat_arena(server)
 else:
  monsters=json.loads((server/'data/monsters.json').read_text(encoding='utf-8'))
  for monster in monsters:monster['spawns']=[]
  (server/'data/monsters.json').write_text(json.dumps(monsters,ensure_ascii=False),encoding='utf-8')
 if latency or rapid:(server/'data/npcs.json').write_text('[]',encoding='utf-8')
 processes=[];folders=[];process=None
 with (output/'server.log').open('wb') as log:
  try:
   process=start_server(server/'lunetile-mmo-server.exe',server,port,log)
   for index in range(2):
    folder=output/f'client-{index}';shutil.copytree(bundle/'client',folder,ignore=shutil.ignore_patterns('ClientProfile','Saves','*.log'))
    folders.append(folder)
    path=folder/'Data/Scripts.rxdata';entries=read(path.read_bytes());main=next(i for i,e in enumerate(entries) if e.name==b'Main')
    original=entries[main].source();assert original.endswith(MAIN_ENTRY)
    setup=f'MMO_TEST_PORT={port}\nMMO_TEST_INDEX={index}\nMMO_TEST_FOREGROUND={str(foreground==index).lower()}\nMMO_TEST_COMBAT={str(combat).lower()}\nMMO_TEST_PROJECTILE={str(projectile).lower()}\nMMO_TEST_LATENCY={str(latency).lower()}\nMMO_TEST_RAPID={str(rapid).lower()}\n'.encode()
    path.write_bytes(write(entries,{main:original[:-len(MAIN_ENTRY)]+setup+(ROOT/'tests/runtime_mmo_motion.rb').read_bytes()}))
    environment=os.environ.copy()
    if foreground==index:environment.pop('LUNETILE_TEST_BACKGROUND',None)
    else:environment['LUNETILE_TEST_BACKGROUND']='1'
    processes.append(subprocess.Popen([str(folder/'Game.exe')],cwd=folder,env=environment))
   deadline=time.monotonic()+20
   while not all((folder/'motion-ready.txt').exists() for folder in folders):
    if any(p.poll() is not None for p in processes):raise RuntimeError('Client exited before readiness; inspect rgssxp.log')
    if time.monotonic()>deadline:raise TimeoutError('Clients did not finish loading')
    time.sleep(.05)
   (output/'ready.txt').write_text(f'Activate client-{foreground}, then create start.txt here for a foreground run.\n')
   deadline=time.monotonic()+180
   while not (output/'start.txt').exists():
    if foreground is None:break
    if time.monotonic()>deadline:raise TimeoutError('Foreground activation timed out')
    time.sleep(.1)
   for folder in folders:(folder/'motion-start.txt').touch()
   deadline=time.monotonic()+35
   while any(p.poll() is None for p in processes):
    if time.monotonic()>deadline:raise TimeoutError('Motion clients timed out')
    time.sleep(.1)
   reports=[];raw=[]
   for folder,client in zip(folders,processes):
    if client.returncode or not (folder/'motion-result.json').exists():
     raise RuntimeError((folder/'rgssxp.log').read_text(encoding='utf-8',errors='replace')[-4000:])
    raw.append(json.loads((folder/'motion-result.json').read_text(encoding='utf-8')))
    reports.append(summarize(raw[-1]))
   if raw[0].get('latency_trials'):
    trials=[];observer=raw[1];rendered=observer['render_samples']
    for trial in raw[0]['latency_trials']:
     at=raw[0]['started']+trial['input_at']-observer['started'];x,y=trial['origin'];d=trial['direction']
     visible=next((r[0] for r in rendered if r[0]>=at and
      ((d==6 and r[2]>x+.001) or (d==4 and r[2]<x-.001) or (d==2 and r[3]>y+.001) or (d==8 and r[3]<y-.001))),None)
     trials.append({'direction':d,'input_at':at,'present_ms':(visible-at)*1000 if visible is not None else None})
    assert all(t['present_ms'] is not None for t in trials),trials
    times=sorted(t['present_ms'] for t in trials)
    reports[1].update(observer_latency_trials=trials,observer_input_to_present_p95_ms=times[int(len(times)*.95)],
     observer_input_to_present_max_ms=max(times),observer_input_to_present_median_ms=times[len(times)//2])
   (output/'summary.json').write_text(json.dumps(reports,indent=2)+'\n',encoding='utf-8')
   print(json.dumps(reports,indent=2))
   if assert_smooth:
    for report in reports:
     assert report['max_step_real_units']<=6.00001 and report['max_camera_step_real_units']<=6.00001,report
     assert report['diagonal_ticks']==0 and report['settled'],report
     assert not report['foreground_required'] or report['foreground_lost_ticks']==0,report
     assert not report['foreground_required'] or report['render_frame_p95_ms']<=20,report
     assert len(report['held_gaps_over_frame_ms'])<=1,report
     assert not any('cooldown' in notice.lower() for _,notice in report['notices']),report
     if report.get('latency_trials'):assert report['input_to_present_p95_ms']<=33 and report['all_presented_before_ack'],report
     if report.get('rapid_reserved_turns'):assert max(report['rapid_turn_center_wait_ticks'])<=1,report
  finally:
   for client in processes:stop(client)
   stop(process)

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('bundle',type=Path);parser.add_argument('--output',required=True,type=Path)
 parser.add_argument('--foreground',type=int,choices=(0,1),help='Index of client to activate before creating start.txt')
 parser.add_argument('--assert-smooth',action='store_true');parser.add_argument('--combat',action='store_true')
 parser.add_argument('--projectile',action='store_true',help='Use grenade instead of burst in the combat workload')
 parser.add_argument('--latency',action='store_true',help='Measure 40 isolated taps, ten per direction, before move acknowledgement')
 parser.add_argument('--rapid',action='store_true',help='Twenty rapid four-direction bursts, measuring immediate off-center turns')
 args=parser.parse_args()
 if sum((args.latency,args.combat or args.projectile,args.rapid))>1:parser.error('Measure isolated, rapid and combat input separately')
 measure(args.bundle,args.output,args.foreground,args.assert_smooth,args.combat,args.latency,args.rapid,args.projectile)
