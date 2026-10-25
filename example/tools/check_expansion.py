"""Exercise expanded systems through two actual XP scenes in an isolated, seeded world.

This is scripted scene input, not physical keyboard/IME evidence or balance testing.
"""
import argparse,json,os,shutil,socket,subprocess,time
from pathlib import Path
from smoke_test import ROOT,start_server,stop,connect,send
from prepare_example import MAIN_ENTRY,digest
from rxdata import read,write

def dump(path,value):
 path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def verify(bundle,output):
 bundle,output=bundle.resolve(),output.resolve()
 if output.exists() or output.is_relative_to(bundle) or bundle.is_relative_to(output):raise ValueError('Use a new separate output')
 server=output/'server';shutil.copytree(bundle/'server',server,ignore=shutil.ignore_patterns('players','transactions','*.log'))
 with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
 config=json.loads((server/'data/server.json').read_text(encoding='utf-8'));config['bind']=f'127.0.0.1:{port}';dump(server/'data/server.json',config)
 monsters=json.loads((server/'data/monsters.json').read_text(encoding='utf-8'))
 for monster in monsters:monster.update(hp=30,attack=0,move_ms=60000,attack_ms=60000,aggro=1)
 dump(server/'data/monsters.json',monsters)
 report={'passed':False,'scope':'Two native XP scenes; scripted commands; seeded level 25/currency, quiet 30HP monsters including boss. Not natural leveling, boss balance or physical IME evidence.',
  'hashes':{name:digest(bundle/name) for name in ['client/Data/Scripts.rxdata','client/Lunetile.dll','server/lunetile-mmo-server.exe']},'checks':[]}
 clients=[];process=None;folders=[];credentials=[];seq=[0,0]
 log=(output/'server.log').open('wb')
 def read_live(i):
  try:return json.loads((folders[i]/'gui-live.json').read_text(encoding='utf-8'))
  except (FileNotFoundError,PermissionError,json.JSONDecodeError):return None
 def wait(i,predicate,description,timeout=12):
  end=time.monotonic()+timeout
  while time.monotonic()<end:
   data=read_live(i)
   if data and predicate(data):return data
   if clients[i].poll() is not None:raise AssertionError((folders[i]/'rgssxp.log').read_text(encoding='utf-8'))
   time.sleep(.06)
  raise AssertionError(f'{description}: {data["state"].get("notice") if data else "no telemetry"}')
 def control(i,event,**args):
  seq[i]+=1;path=folders[i]/'gui-control.json';temporary=path.with_suffix('.tmp');dump(temporary,dict(seq=seq[i],type=event,**args))
  for attempt in range(40):
   try:os.replace(temporary,path);break
   except PermissionError:
    if attempt==39:raise
    time.sleep(.025)
  if event=='quit':clients[i].wait(timeout=10)
  else:wait(i,lambda d:d['command']==seq[i],event)
 def command(i,kind,action,key='',amount=1,text='',revision=0):control(i,'system',kind=kind,action=action,key=key,amount=amount,text=text,revision=revision)
 def state(i):return read_live(i)['state']
 def progress(i,field,value):wait(i,lambda d:d['state']['progress'][field]==value,field)
 def walk(i,x,y):
  control(i,'walk',position=[x,y]);wait(i,lambda d:abs(d['avatars'][credentials[i]['id']]['real_x']/128-x)<.08 and abs(d['avatars'][credentials[i]['id']]['real_y']/128-y)<.08,'walk',20);control(i,'stop')
 try:
  process=start_server(server/'lunetile-mmo-server.exe',server,port,log)
  for i in range(2):
   with connect(port) as connection:
    result=send(connection,{'type':'register','protocol':11,'name':f'확장검사{i}'})
    credentials.append({k:result[k] for k in ['id','token']})
  stop(process);process=None
  for c in credentials:
   path=server/'players'/f'{c["id"]}.json';p=json.loads(path.read_text(encoding='utf-8'));p.update(level=25,exp=0,hp=500,max_hp=580,mp=290,max_mp=290)
   p['progress'].update(skill_points=25,coins=10000);p['inventory']['upgrade_stone']=10;dump(path,p)
  process=start_server(server/'lunetile-mmo-server.exe',server,port,log)
  for i in range(2):
   folder=output/f'client-{i}';shutil.copytree(bundle/'client',folder,ignore=shutil.ignore_patterns('ClientProfile','Saves','*.log'));folders.append(folder)
   profile=json.loads((folder/'client.json').read_text(encoding='utf-8'))['profile'];(folder/'ClientProfile').mkdir();dump(folder/'ClientProfile'/f'{profile}.json',credentials[i])
   path=folder/'Data/Scripts.rxdata';entries=read(path.read_bytes());main=next(j for j,e in enumerate(entries) if e.name==b'Main');original=entries[main].source();assert original.endswith(MAIN_ENTRY)
   setup=f'GUI_TEST_PORT={port}\nGUI_TEST_INDEX={i}\nGUI_TEST_DURATION=600\n'.encode()
   path.write_bytes(write(entries,{main:original[:-len(MAIN_ENTRY)]+setup+(ROOT/'tests/runtime_gui.rb').read_bytes()}))
   env=os.environ.copy();env['LUNETILE_TEST_BACKGROUND']='1';clients.append(subprocess.Popen([str(folder/'Game.exe')],cwd=folder,env=env))
  for i in range(2):wait(i,lambda d:len(d['state']['players'])==2,'both native logins')
  for i,job in enumerate(['warrior','mage']):
   command(i,'progress','job',job);progress(i,'job',job);command(i,'progress','job',job+'2');progress(i,'job',job+'2')
   for skill in [job+'_1',job+'_2',job+'_3']:
    command(i,'progress','learn',skill);wait(i,lambda d:d['state']['progress']['skills'].get(skill)==1,'learn')
   command(i,'progress','bind',job+'_2');progress(i,'quick_skill',job+'_2')
  report['checks'].append('Native first/second advancement, active/passive learning and X binding')
  gear=next(k for k,g in state(0)['progress']['gear'].items() if g['definition']=='weapon_1')
  command(0,'progress','equip',gear);wait(0,lambda d:d['state']['progress']['equipped'].get('weapon')==gear,'equip')
  command(0,'progress','enhance',gear);wait(0,lambda d:d['state']['progress']['gear'][gear]['enhancement']==1,'enhance')
  command(0,'progress','unequip','weapon');command(0,'service','store_gear',gear);wait(0,lambda d:gear in d['state']['progress']['storage_gear'],'gear storage')
  command(0,'service','withdraw_gear',gear);wait(0,lambda d:gear in d['state']['progress']['gear'],'gear withdrawal')
  command(0,'service','store_coins',amount=100);progress(0,'storage_coins',100);command(0,'service','withdraw_coins',amount=100);progress(0,'storage_coins',0)
  old=state(0)['inventory']['potion'];command(0,'service','buy','potion',2);wait(0,lambda d:d['state']['inventory']['potion']==old+2,'buy')
  control(0,'use',item='potion');wait(0,lambda d:d['state']['inventory']['potion']==old+1,'potion')
  report['checks'].append('Native equip/enhance/unequip, instance-preserving storage, coin storage, shop and potion')
  a,b=[c['id'] for c in credentials]
  for kind in ['party','guild']:
   command(0,'social',kind+'_create',text='검증 길드');wait(0,lambda d:d['state']['social'][kind] is not None,'create '+kind)
   command(0,'social',kind+'_invite',b);wait(1,lambda d:d['state']['social']['invite'] is not None,'invite');command(1,'social','accept');wait(1,lambda d:d['state']['social'][kind] is not None,'join')
  command(0,'social','trade_invite',b);wait(1,lambda d:d['state']['social']['invite'] is not None,'trade invite');command(1,'social','accept');wait(0,lambda d:d['state']['social']['trade'] is not None,'trade accepted')
  command(0,'social','trade_gear',gear);wait(1,lambda d:gear in d['state']['social']['trade']['offers'][a]['gear'],'offered gear visible')
  revision=state(0)['social']['trade']['revision'];command(0,'social','trade_confirm',revision=revision);command(1,'social','trade_confirm',revision=revision)
  wait(1,lambda d:gear in d['state']['progress']['gear'] and d['state']['social']['trade'] is None,'trade committed');assert state(1)['progress']['gear'][gear]['enhancement']==1
  report['checks'].append('Two native clients: party, persistent guild, consented trade retaining +1 equipment')
  for key in ['bag','skills','equipment','quests','jobs','shop','storage','enhance','party','guild','trade']:
   control(0,'window',key=key);wait(0,lambda d:d['panels'][key][2],key);time.sleep(.15);control(0,'close')
  report['checks'].append('All eleven feature windows rendered without runtime errors')
  portals=state(0)['services']['portals'];map_ids=[]
  for target in [2,3,4,5]:
   portal=next(p for p in portals if p['from']['map_id']==1 and p['to']['map_id']==target)
   walk(0,portal['from']['x'],portal['from']['y']-1);command(0,'service','portal',portal['id']);wait(0,lambda d:d['state']['self']['position']['map_id']==target,'enter map');map_ids.append(target)
   if target==5:
    walk(1,portal['from']['x'],portal['from']['y']-1);command(1,'service','portal',portal['id']);wait(1,lambda d:d['state']['self']['position']['map_id']==5,'boss observer')
    walk(0,19,14);walk(1,19,14);control(0,'attack',skill='warrior_2',direction=6)
    for i in range(2):wait(i,lambda d:any(e.get('killed') and e.get('target')=='ancient_guardian_0' for e in d['events_seen']),'shared boss death')
    report['checks'].append('Boss map: server-approved cast, shared damage/death effects and party reward in two actual scenes (30HP fixture)')
   back=next(p for p in portals if p['from']['map_id']==target)
   walk(0,3,14);command(0,'service','portal',back['id']);wait(0,lambda d:d['state']['self']['position']['map_id']==1,'return town')
  report['maps']=map_ids;report['checks'].append('All four new maps load, minimaps regenerate, portals return to original town')
  for i in range(2):
   control(i,'quit');clients[i].wait(timeout=10)
  stop(process);process=None
  process=start_server(server/'lunetile-mmo-server.exe',server,port,log)
  for i,c in enumerate(credentials):
   with connect(port) as connection:
    s=send(connection,dict(type='login',protocol=11,**c))['state'];assert s['progress']['guild']==a;assert s['progress']['job']==['warrior2','mage2'][i]
    if i==1:assert s['progress']['gear'][gear]['enhancement']==1
  report['checks'].append('Real server restart/reconnect preserves jobs, guild and transferred enhanced gear');report['passed']=True
 finally:
  for client in clients:stop(client)
  stop(process);log.close();dump(output/'summary.json',report)
 return report

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('bundle',type=Path);parser.add_argument('--output',required=True,type=Path)
 args=parser.parse_args();report=verify(args.bundle,args.output);print('Expansion native PASS:',len(report['checks']),'checks')
