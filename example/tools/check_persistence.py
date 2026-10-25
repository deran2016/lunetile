"""Crash/recovery and locked-WAL ACK checks against an isolated Windows server."""
import argparse,hashlib,json,msvcrt,shutil,socket,struct,subprocess,tempfile,threading,time
from pathlib import Path
from smoke_test import start_server,stop,connect,send

def check(bundle,output):
 bundle=bundle.resolve();output=output.resolve()
 if output.exists():raise ValueError('Use a new output folder')
 output.mkdir(parents=True);temporary=Path(tempfile.mkdtemp(prefix='lunetile-recovery-')).resolve();assert temporary.is_relative_to(Path(tempfile.gettempdir()).resolve())
 server=temporary/'server';shutil.copytree(bundle/'server/data',server/'data');exe=server/'lunetile-mmo-server.exe';shutil.copy2(bundle/'server/lunetile-mmo-server.exe',exe)
 with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
 config=json.loads((server/'data/server.json').read_text(encoding='utf-8'));config['bind']=f'127.0.0.1:{port}';(server/'data/server.json').write_text(json.dumps(config),encoding='utf-8')
 monsters=json.loads((server/'data/monsters.json').read_text(encoding='utf-8'))
 for m in monsters:m['spawns']=[]
 (server/'data/monsters.json').write_text(json.dumps(monsters),encoding='utf-8');(server/'data/npcs.json').write_text('[]',encoding='utf-8')
 report={'passed':False,'server_sha256':hashlib.sha256(exe.read_bytes()).hexdigest(),'checks':[]};process=None;connections=[]
 def social(s,action,key='',amount=0,revision=0):return send(s,dict(type='social',action=action,key=key,amount=amount,text='',revision=revision))
 def recover():
  r=subprocess.run([str(exe),'--root',str(server),'--recover-only'],capture_output=True,text=True,encoding='utf-8',timeout=15)
  assert r.returncode==0,r.stderr
 def player(id):return json.loads((server/'players'/f'{id}.json').read_text(encoding='utf-8'))
 with (output/'server.log').open('wb') as log:
  try:
   process=start_server(exe,server,port,log);a,b=connect(port),connect(port);connections=[a,b]
   wa=send(a,dict(type='register',protocol=11,name='Recovery A'));wb=send(b,dict(type='register',protocol=11,name='Recovery B'));aid,bid=wa['id'],wb['id']
   sa=send(a,dict(type='move',direction=6));assert sa['move_ack']['accepted']
   send(a,dict(type='use',item_id='potion'));social(a,'trade_invite',bid);social(b,'accept')
   social(a,'trade_item','potion',1);social(b,'trade_item','mana_potion',1);revision=send(a,dict(type='poll'))['social']['trade']['revision']
   social(a,'trade_confirm',revision=revision);social(b,'trade_confirm',revision=revision)
   expected={aid:send(a,dict(type='poll')),bid:send(b,dict(type='poll'))}
   stop(process);process=None
   for c in connections:c.close()
   connections=[];shutil.copytree(server/'transactions',output/'transactions-after-kill')
   recover()
   for id,state in expected.items():
    p=player(id);assert p['inventory']==state['inventory'] and p['progress']==state['progress'];assert p['position']==state['self']['position']
   before={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (server/'players').glob('*.json')};recover();assert before=={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (server/'players').glob('*.json')}
   report['checks'].append('Hard process termination after acknowledged movement/use/two-player trade: complete, idempotent --recover-only recovery')
   process=start_server(exe,server,port,log);a=connect(port);connections=[a];sa=send(a,dict(type='login',protocol=11,id=aid,token=wa['token']))['state'];before=player(aid)
   wal=server/'transactions/active.wal'
   with wal.open('r+b') as held:
    held.seek(0);msvcrt.locking(held.fileno(),msvcrt.LK_NBLCK,64*1024*1024)
    try:
     m=sa['self']['motion'];message=dict(type='move',seq=1,origin=[m['x'],m['y']],epoch=m['epoch'],parts=[dict(direction=6,ms=100)])
     data=json.dumps(message).encode();a.sendall(struct.pack('!I',len(data))+data)
     poll=json.dumps(dict(type='poll')).encode();a.sendall(struct.pack('!I',len(poll))+poll);a.settimeout(5)
     states=[]
     from smoke_test import receive
     try:
      while True:states.append(receive(a))
     except (OSError,EOFError):pass
     assert not any(s.get('move_ack',{}).get('seq')==1 and s['move_ack']['accepted'] for s in states),states
    finally:held.seek(0);msvcrt.locking(held.fileno(),msvcrt.LK_UNLCK,64*1024*1024)
   a.close();connections=[];process.wait(timeout=10);process=None;recover();assert player(aid)['position']==before['position']
   report['checks'].append('Windows byte-range WAL write failure: no success ACK or committed movement, restart recovery succeeds')
   process=start_server(exe,server,port,log);a=connect(port);b=connect(port);connections=[a,b]
   send(a,dict(type='login',protocol=11,id=aid,token=wa['token']));send(b,dict(type='login',protocol=11,id=bid,token=wb['token']));b.setsockopt(socket.SOL_SOCKET,socket.SO_RCVBUF,1024)
   def slow():
    data=b'\x00\x00\x00\x0f{"type":"poll"}'
    try:
     for _ in range(240):b.sendall(data);time.sleep(1/60)
    except OSError:pass
   job=threading.Thread(target=slow);job.start();times=[]
   for _ in range(120):
    began=time.perf_counter();assert send(a,dict(type='poll'))['type']=='state';times.append((time.perf_counter()-began)*1000);time.sleep(.025)
   job.join(timeout=6);times.sort();report['healthy_poll_p95_ms_with_slow_reader']=times[int(len(times)*.95)];assert report['healthy_poll_p95_ms_with_slow_reader']<=20
   report['checks'].append('Slow/non-reading peer does not block healthy polling');report['passed']=True
  finally:
   for c in connections:c.close()
   stop(process);shutil.copytree(server,output/'server');assert temporary.is_relative_to(Path(tempfile.gettempdir()).resolve());shutil.rmtree(temporary)
   (output/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print('Persistence/slow-peer PASS:',len(report['checks']))
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('bundle',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args();check(a.bundle,a.output)
