"""Test a copied Windows server with real TCP clients; optionally run two real XP launchers."""
import argparse,hashlib,json,os,shutil,socket,struct,subprocess,sys,time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
from rxdata import read,write
from prepare_example import CLIENT_SCRIPTS,MAIN_ENTRY

def receive(connection):
 def exact(size):
  data=b''
  while len(data)<size:
   part=connection.recv(size-len(data))
   if not part:raise EOFError('Server closed connection')
   data+=part
  return data
 size=struct.unpack('!I',exact(4))[0]
 assert 0<size<=262144,size
 return json.loads(exact(size))

def send(connection,message,fragment=False):
 if message['type']=='move' and 'seq' not in message:
  message=dict(message,seq=_move_sequences.get(connection,0)+1);_move_sequences[connection]=message['seq']
 if message['type']=='move' and 'direction' in message:
  message=message.copy();direction=message.pop('direction');motion=_motions[connection]
  message.update(origin=[motion['x'],motion['y']],epoch=motion['epoch'],parts=[{'direction':direction,'ms':200}])
 body=json.dumps(message,ensure_ascii=False).encode();frame=struct.pack('!I',len(body))+body
 if fragment:
  for part in (frame[:1],frame[1:3],frame[3:8],frame[8:]):connection.sendall(part)
 else:connection.sendall(frame)
 result=receive(connection)
 state=result.get('state',result)
 if 'self' in state:_motions[connection]=state['self']['motion']
 return result

_move_sequences={}
_motions={}

def connect(port):return socket.create_connection(('127.0.0.1',port),timeout=4)

def start_server(exe,server,port,log,default_root=False):
 process=subprocess.Popen([str(exe)]+([] if default_root else ['--root',str(server)]),stdout=log,stderr=subprocess.STDOUT)
 deadline=time.monotonic()+10
 while time.monotonic()<deadline:
  if process.poll() is not None:raise RuntimeError('Server failed to start; inspect server.log')
  try:
   with connect(port):return process
  except OSError:time.sleep(.05)
 process.terminate();process.wait();raise TimeoutError('Server startup timed out')

def stop(process):
 if process and process.poll() is None:process.terminate();process.wait(timeout=5)

def native_clients(bundle,output,port):
 processes=[];folders=[]
 probe=(ROOT/'tests/runtime_mmo.rb').read_bytes()
 try:
  for index in range(2):
   folder=output/f'native-{index}'
   shutil.copytree(bundle/'client',folder,ignore=shutil.ignore_patterns('ClientProfile','Saves','*.log','mmo-native-result.json','runtime-complete.txt'))
   folders.append(folder)
   assert not list(folder.rglob('*.rb')),'Client must execute from Scripts.rxdata only'
   entries=read((folder/'Data/Scripts.rxdata').read_bytes());main=next(i for i,e in enumerate(entries) if e.name==b'Main')
   assert [e.name.decode() for e in entries[main-len(CLIENT_SCRIPTS):main]]==[name for name,_ in CLIENT_SCRIPTS]
   setup=f"MMO_TEST_PORT={port}\nMMO_TEST_NAME='Native{index}'\n".encode()
   original=entries[main].source()
   assert original.endswith(MAIN_ENTRY),'Expected the packaged online entrypoint'
   bootstrap=original[:-len(MAIN_ENTRY)]
   (folder/'Data/Scripts.rxdata').write_bytes(write(entries,{main:bootstrap+setup+probe}))
   environment=os.environ.copy();environment['LUNETILE_TEST_BACKGROUND']='1'
   processes.append(subprocess.Popen([str(folder/'Game.exe')],cwd=folder,env=environment))
  deadline=time.monotonic()+35
  while any(p.poll() is None for p in processes):
   if time.monotonic()>deadline:raise TimeoutError('Native XP clients timed out')
   time.sleep(.1)
  reports=[]
  for process,folder in zip(processes,folders):
   if process.returncode or not (folder/'mmo-native-result.json').is_file():
    log=(folder/'rgssxp.log').read_text(encoding='utf-8',errors='replace') if (folder/'rgssxp.log').exists() else ''
    raise AssertionError(f'Native client failed ({process.returncode}): {log[-4500:]}')
   reports.append(json.loads((folder/'mmo-native-result.json').read_text(encoding='utf-8')))
  return reports
 finally:
  for process in processes:stop(process)

def verify(bundle,output,native=False):
 bundle,output=bundle.resolve(),output.resolve()
 if output.exists():raise ValueError('Verification output must be a new folder')
 if output.is_relative_to(bundle) or bundle.is_relative_to(output):raise ValueError('Verification must be separate from distribution')
 output.mkdir(parents=True)
 server=output/'server';(server/'data').mkdir(parents=True)
 shutil.copytree(bundle/'server/data',server/'data',dirs_exist_ok=True)
 exe=server/'lunetile-mmo-server.exe';shutil.copy2(bundle/'server/lunetile-mmo-server.exe',exe)
 with socket.socket() as available:available.bind(('127.0.0.1',0));port=available.getsockname()[1]
 monsters=json.loads((server/'data/monsters.json').read_text(encoding='utf-8'))
 for monster in monsters:monster['spawns']=[]
 (server/'data/monsters.json').write_text(json.dumps(monsters,ensure_ascii=False),encoding='utf-8')
 config=json.loads((server/'data/server.json').read_text(encoding='utf-8'));config['bind']=f'127.0.0.1:{port}'
 (server/'data/server.json').write_text(json.dumps(config,ensure_ascii=False),encoding='utf-8')
 report={'passed':False,'server_sha256':hashlib.sha256(exe.read_bytes()).hexdigest(),'dll_sha256':hashlib.sha256((bundle/'client/Lunetile.dll').read_bytes()).hexdigest(),'checks':[],
  'scope':'Two loopback TCP clients; Windows process restart; optional real XP scenes. No two-PC LAN or load/endurance proof.'}
 process=None;connections=[]
 with (output/'server.log').open('wb') as log:
  try:
   process=start_server(exe,server,port,log,default_root=True)
   first,second=connect(port),connect(port);connections=[first,second]
   a=send(first,{'type':'register','protocol':11,'name':'검사A'},fragment=True)
   b=send(second,{'type':'register','protocol':11,'name':'검사B'})
   assert a['type']==b['type']=='welcome'
   assert a['protocol']==b['protocol']==11 and a['state']['move_ack']['seq']==0
   state=send(first,{'type':'poll'})
   assert len(state['players'])==2 and 'token' not in json.dumps(state)
   report['checks'].append('two clients, fragmented framing, public state without tokens')
   npc=state['npcs'][0]['id']
   state=send(first,{'type':'talk','npc_id':npc});assert state['inventory']['potion']==5
   state=send(first,{'type':'talk','npc_id':npc});assert state['inventory']['potion']==5
   state=send(first,{'type':'use','item_id':'potion'});assert state['self']['hp']==100 and state['inventory']['potion']==4
   report['checks'].append('NPC once-only reward and authoritative item consumption')
   state=send(first,{'type':'chat','text':'한글 채팅 검사'})
   assert send(second,{'type':'poll'})['chat'][-1]['text']=='한글 채팅 검사'
   position=state['self']['position'];before=position.copy()
   # Find one valid neighboring direction in the exported map, excluding NPCs.
   maps=json.loads((server/'data/maps.json').read_text(encoding='utf-8'));grid=next(m for m in maps if m['id']==position['map_id'])
   for direction,dx,dy,bit,reverse in [(6,1,0,4,2),(4,-1,0,2,4),(8,0,-1,8,1),(2,0,1,1,8)]:
    x,y=position['x']+dx,position['y']+dy
    if 0<=x<grid['width'] and 0<=y<grid['height'] and not grid['passages'][position['y']][position['x']]&bit and not grid['passages'][y][x]&reverse and not any(n['position']['x']==x and n['position']['y']==y for n in state['npcs']):break
   else:raise AssertionError('No valid spawn exit')
   state=send(first,{'type':'move','direction':direction});assert state['self']['position']!=before
   moved=state['self']['position']
   assert next(p for p in send(second,{'type':'poll'})['players'] if p['id']==a['id'])['position']==moved
   report['checks'].append('movement replication and Korean chat')
   for seq in (1,3):
    duplicate=send(first,{'type':'move','seq':seq,'direction':direction})
    assert duplicate['self']['position']==moved and duplicate['move_ack']=={'seq':1,'accepted':True}
    assert 'sequence' in duplicate['notice']
   with connect(port) as outdated:
    assert 'Protocol 11' in send(outdated,{'type':'register','protocol':5,'name':'구버전'})['message']
   report['checks'].append('v10 ack, duplicate/skipped move sequences and old protocol rejection')
   with connect(port) as collision:
    collision_state=send(collision,{'type':'register','protocol':11,'name':'충돌검사'})['state']
    origin=collision_state['self']['position'].copy()
    npc_position=collision_state['npcs'][0]['position']
    dx,dy=npc_position['x']-origin['x'],npc_position['y']-origin['y']
    direction={(0,1):2,(-1,0):4,(1,0):6,(0,-1):8}[(dx,dy)]
    blocked=send(collision,{'type':'move','direction':direction})
    assert blocked['self']['position']==origin and blocked['self']['motion']!=collision_state['self']['motion']
    for _ in range(origin['x']):
     time.sleep(.21)
     collision_state=send(collision,{'type':'move','direction':4})
    assert collision_state['self']['position']['x']==0
    time.sleep(.21)
    edge=send(collision,{'type':'move','direction':4})
    assert edge['self']['position']==collision_state['self']['position'] and edge['move_ack']['accepted']
   report['checks'].append('NPC collision and map edge clamp fractional movement without entering blocked tiles')
   with connect(port) as wrong:assert send(wrong,{'type':'login','protocol':11,'id':a['id'],'token':'wrong'})['type']=='error'
   with connect(port) as duplicate:assert send(duplicate,{'type':'login','protocol':11,'id':a['id'],'token':a['token']})['type']=='error'
   with connect(port) as malicious:
    malicious.sendall(struct.pack('!I',16385));assert malicious.recv(1)==b''
   with connect(port) as stalled:
    stalled.sendall(struct.pack('!I',200)+b'{')
    assert send(second,{'type':'poll'})['type']=='state'
   for connection in connections:connection.close()
   connections=[];stop(process)
   process=start_server(exe,server,port,log)
   with connect(port) as resumed:
    restored=send(resumed,{'type':'login','protocol':11,'id':a['id'],'token':a['token']})['state']
    assert restored['inventory']['potion']==4 and restored['self']['hp']==100 and restored['self']['position']==moved
   report['checks'].append('bad login, duplicate session, oversized/stalled frames, restart persistence')
   if native:report['native_clients']=native_clients(bundle,output,port)
   report['passed']=True
  finally:
   for connection in connections:connection.close()
   stop(process)
   (output/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 return report

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('bundle',type=Path)
 parser.add_argument('--output',type=Path,default=ROOT/'build'/('mmo-verification-'+time.strftime('%Y%m%d-%H%M%S')))
 parser.add_argument('--native',action='store_true',help='Also run two actual XP launchers with scripted scene input')
 args=parser.parse_args();report=verify(args.bundle,args.output,args.native)
 print(f"MMO smoke PASS: {len(report['checks'])} network scenarios, {len(report.get('native_clients',[]))} native XP clients; {args.output}")
