"""Isolated account/character TCP checks. Test secrets are never included in reports."""
import argparse,concurrent.futures,hashlib,json,shutil,socket,subprocess,tempfile,time
from pathlib import Path
from smoke_test import connect,send,start_server,stop

def check(bundle,output):
 bundle,output=bundle.resolve(),output.resolve()
 if output.exists():raise ValueError('Use a new isolated output')
 output.mkdir(parents=True);temporary=Path(tempfile.mkdtemp(prefix='lunetile-accounts-')).resolve();assert temporary.is_relative_to(Path(tempfile.gettempdir()).resolve())
 root=temporary/'server';shutil.copytree(bundle/'server/data',root/'data');exe=root/'lunetile-mmo-server.exe';shutil.copy2(bundle/'server/lunetile-mmo-server.exe',exe)
 with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
 config=json.loads((root/'data/server.json').read_text(encoding='utf-8'));config['bind']=f'127.0.0.1:{port}';(root/'data/server.json').write_text(json.dumps(config),encoding='utf-8')
 monsters=json.loads((root/'data/monsters.json').read_text(encoding='utf-8'))
 for m in monsters:m['spawns']=[]
 (root/'data/monsters.json').write_text(json.dumps(monsters),encoding='utf-8')
 secret='Isolated_test_only_1234';process=None;connections=[];report={'passed':False,'checks':[],'server_sha256':hashlib.sha256(exe.read_bytes()).hexdigest()}
 def connection():c=connect(port);c.settimeout(8);connections.append(c);return c
 def account(c,name,new=False,password=secret):return send(c,dict(type='account_register' if new else 'account_login',protocol=11,username=name,password=password))
 with (output/'server.log').open('wb') as log:
  try:
   process=start_server(exe,root,port,log);legacy=connection();old=send(legacy,dict(type='register',protocol=11,name='기존모험가'));legacy.close();time.sleep(.15)
   a=connection();assert account(a,'tester_a',True)['type']=='account';slots=send(a,dict(type='character_claim',id=old['id'],token=old['token']))
   assert slots['characters'][0]['id']==old['id'] and 'token' not in json.dumps(slots)
   for slot in [1,2]:
    nickname=['','한별하나','별빛둘'][slot];slots=send(a,dict(type='character_create',slot=slot,appearance=slot,name=nickname));assert slots['characters'][slot]['name']==nickname
    assert slots['characters'][slot]['character']==slots['appearances'][slot]
   assert len(slots['appearances'])==3
   assert send(a,dict(type='character_create',slot=3,appearance=0,name='잘못된칸'))['type']=='account_error'
   assert send(a,dict(type='character_create',slot=1,appearance=0,name='다른이름'))['characters'][1]['id']==slots['characters'][1]['id']
   report['checks'].append('Signup, three slots, chosen Korean names and appearances, idempotent creation and legacy claim')
   duplicate=connection();assert account(duplicate,'tester_a')['type']=='account_error';duplicate.close()
   b=connection();assert account(b,'tester_b',True)['type']=='account'
   assert send(b,dict(type='character_claim',id=old['id'],token=old['token']))['type']=='account_error'
   for name,appearance in [('한별하나',0),('기존모험가',0),('공백 이름',0),('짧',0),('가'*13,0),('정상이름',3)]:
    result=send(b,dict(type='character_create',slot=0,appearance=appearance,name=name));assert result['type']=='account_error'
   c=connection();assert account(c,'tester_c',True)['type']=='account'
   with concurrent.futures.ThreadPoolExecutor(2) as pool:
    jobs=[pool.submit(send,conn,dict(type='character_create',slot=0,appearance=i,name=name)) for i,(conn,name) in enumerate([(b,'RaceHero'),(c,'racehero')])]
    results=[j.result() for j in jobs]
   assert sorted(r['type'] for r in results)==['account','account_error']
   winner=next(r for r in results if r['type']=='account');assert winner['characters'][0]['name'].lower()=='racehero'
   report['checks'].append('Global duplicate, legacy name, ASCII case, invalid nickname/image and simultaneous creation checks')
   c.close();b.close()
   bypass=connection();assert send(bypass,dict(type='login',protocol=11,id=old['id'],token=old['token']))['type']=='account_error';bypass.close()
   selected=send(a,dict(type='character_select',slot=0));assert selected['type']=='welcome' and selected['id']==old['id'];assert selected['state']['inventory']==old['state']['inventory']
   report['checks'].append('Duplicate account session, foreign claim and direct-token bypass rejected; selected character retains inventory')
   c=connection();assert account(c,'tester_b',False,'Wrong_password_123')['type']=='account_error';assert account(c,'tester_b')['type']=='account';c.close()
   def hash_attempt(i):
    with connect(port) as c:account(c,f'new_hash_{i}',True)
   times=[]
   with concurrent.futures.ThreadPoolExecutor(2) as pool:
    jobs=[pool.submit(hash_attempt,i) for i in range(2)]
    for _ in range(40):
     began=time.perf_counter();assert send(a,dict(type='poll'))['type']=='state';times.append((time.perf_counter()-began)*1000);time.sleep(.005)
    for j in jobs:j.result()
   times.sort();report['world_poll_p95_during_password_hash_ms']=times[int(len(times)*.95)];assert report['world_poll_p95_during_password_hash_ms']<=20
   assert secret not in ''.join(p.read_text() for p in (root/'accounts').glob('*.json'))
   report['checks'].append('Wrong password rejected, passwords stored as salted hashes, world polls continue during hashing')
   for c in connections:c.close()
   connections=[];stop(process);process=None
   recovered=subprocess.run([str(exe),'--root',str(root),'--recover-only'],capture_output=True,text=True,timeout=20);assert recovered.returncode==0,recovered.stderr
   process=start_server(exe,root,port,log);a=connection();restored=account(a,'tester_a');assert [c['id'] for c in restored['characters']]==[c['id'] for c in slots['characters']]
   assert send(a,dict(type='character_select',slot=2))['type']=='welcome'
   report['checks'].append('Hard restart/recovery preserves account password, slots, character IDs and selectable world session');report['passed']=True
  finally:
   for c in connections:c.close()
   stop(process);assert temporary.is_relative_to(Path(tempfile.gettempdir()).resolve());shutil.rmtree(temporary)
   (output/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print('Account/character TCP PASS:',len(report['checks']))
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('bundle',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args();check(a.bundle,a.output)
