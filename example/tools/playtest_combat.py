"""Exercise a review_gui --combat-arena copy through real scenes and TCP; activate client-0 first."""
import argparse,json,time
from pathlib import Path

def run(root,focus):
 root=root.resolve();seq=[-1,-1]
 def live(i):
  for _ in range(100):
   try:return json.loads((root/f'client-{i}/gui-live.json').read_text(encoding='utf-8'))
   except (PermissionError,FileNotFoundError,json.JSONDecodeError):time.sleep(.01)
  raise RuntimeError('Telemetry unavailable')
 def wait(predicate,seconds=12):
  deadline=time.monotonic()+seconds
  while not predicate():
   assert time.monotonic()<deadline,'scenario timeout';time.sleep(.03)
 def send(i,kind,**kw):
  seq[i]+=1;p=root/f'client-{i}/gui-control.json';tmp=p.with_suffix('.tmp')
  tmp.write_text(json.dumps(dict(seq=seq[i],type=kind,**kw)),encoding='utf-8')
  deadline=time.monotonic()+4
  while True:
   try:tmp.replace(p);break
   except PermissionError:
    assert time.monotonic()<deadline,'control file locked';time.sleep(.01)
  wait(lambda:live(i)['command']==seq[i],4)
 def count(i=0):return live(i)['effect_counts']['attack']
 seq[:]=[live(i)['command'] for i in range(2)]
 report={'scope':'Two real Windows XP scenes, scripted keys and real server; optional real foreground switching','checks':[]}
 ids=[live(i)['state']['self']['id'] for i in range(2)]
 send(0,'attack',direction=6,skill='basic')
 wait(lambda:all(m['hp']==20 for m in live(0)['state']['monsters']))
 send(1,'attack',direction=6,skill='burst')
 wait(lambda:not live(0)['state']['monsters'] and not live(1)['state']['monsters'])
 wait(lambda:all(live(i)['effect_counts']['ghost']==3 for i in range(2)))
 a,b=[live(i)['state']['self'] for i in range(2)]
 assert (a['exp'],b['exp'],b['mp'])==(9,21,40),(a,b)
 report['first_multi_kill']={'experience':[a['exp'],b['exp']],'caster_mp':b['mp'],'ghosts':[live(i)['effect_counts']['ghost'] for i in range(2)]}
 report['checks'].append('no selected target; three monsters hit; shared XP 9/21; MP charged once; hit flashes and death afterimages')
 wait(lambda:len(live(0)['state']['monsters'])==3,8)
 before=count();send(0,'buttons',keys=[]);send(0,'buttons',keys=['z'])
 wait(lambda:count()>=before+3)
 send(0,'bag',open=True);time.sleep(.25);paused=count();time.sleep(.8);assert count()==paused,'attacked through bag'
 send(0,'close');time.sleep(.8);assert count()==paused,'held key resumed after bag'
 send(0,'buttons',keys=[]);send(0,'buttons',keys=['z']);wait(lambda:count()>paused)
 send(0,'chat',open=True);time.sleep(.2);paused=count();time.sleep(.7);assert count()==paused,'attacked through chat'
 send(0,'chat',open=False);time.sleep(.8);assert count()==paused,'held key resumed after chat'
 send(0,'buttons',keys=[]);send(0,'buttons',keys=['z','x']);before=count();wait(lambda:count()>=before+2)
 send(0,'buttons',keys=[])
 attacks=[e for e in live(0)['events_seen'] if e['kind']=='attack' and e['source']==ids[0]]
 assert all(e['skill_id']=='burst' for e in attacks[-2:]),attacks[-2:]
 report['checks'].append('held Z repeats; bag/chat pause and require release; X has priority over Z')
 if focus:
  send(0,'buttons',keys=['z']);before=count();wait(lambda:count()>before)
  (root/'focus-away.ready').touch();print('FOCUS AWAY: activate client-1, then create focus-away.done',flush=True)
  wait(lambda:(root/'focus-away.done').exists(),120);time.sleep(.25);paused=count();time.sleep(.8);assert count()==paused,'background attack continued'
  (root/'focus-back.ready').touch();print('FOCUS BACK: activate client-0, then create focus-back.done',flush=True)
  wait(lambda:(root/'focus-back.done').exists(),120);time.sleep(.9);assert count()==paused,'focus regain resumed held key'
  send(0,'buttons',keys=[]);send(0,'buttons',keys=['z']);wait(lambda:count()>paused);send(0,'buttons',keys=[])
  report['checks'].append('actual Windows focus loss stops repetition; regain requires release and new press')
 time.sleep(1)
 data=[live(i) for i in range(2)]
 for d in data:
  events=d['events_seen'];casts=sum(e['kind']=='attack' for e in events);hits=sum(e['kind']=='damage' for e in events)
  assert d['effect_counts']['attack']==casts and d['effect_counts']['hit']==hits,'missing or duplicated visual event'
  assert d['active_effects']==0,'transient effect leaked'
 assert data[0]['effect_counts']==data[1]['effect_counts'],'peers saw different effects'
 report.update(passed=True,effect_counts=[d['effect_counts'] for d in data],final_players=[{k:d['state']['self'][k] for k in ('level','exp','hp','mp')} for d in data])
 (root/'combat-scenario.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
 print('FORWARD AREA COMBAT / HOLD / VISUAL SYNC PASS',flush=True)

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('review_folder',type=Path);parser.add_argument('--focus',action='store_true')
 args=parser.parse_args();run(args.review_folder,args.focus)
