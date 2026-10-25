"""Render isolated native entry scenes; authentication uses test-only in-process fixtures."""
import argparse,json,os,shutil,socket,subprocess,time
from pathlib import Path
from smoke_test import ROOT,read,write,MAIN_ENTRY,start_server,stop

def review(bundle,output):
 bundle,output=bundle.resolve(),output.resolve()
 if output.exists():raise ValueError('Use a new isolated output')
 server=output/'server';shutil.copytree(bundle/'server/data',server/'data');shutil.copy2(bundle/'server/lunetile-mmo-server.exe',server/'lunetile-mmo-server.exe')
 with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
 c=json.loads((server/'data/server.json').read_text(encoding='utf-8'));c['bind']=f'127.0.0.1:{port}';(server/'data/server.json').write_text(json.dumps(c),encoding='utf-8')
 monsters=json.loads((server/'data/monsters.json').read_text(encoding='utf-8'))
 for m in monsters:m['spawns']=[]
 (server/'data/monsters.json').write_text(json.dumps(monsters),encoding='utf-8')
 process=None;clients=[]
 with (output/'server.log').open('wb') as log:
  try:
   process=start_server(server/'lunetile-mmo-server.exe',server,port,log)
   for i in range(2):
    target=output/f'client-{i}';shutil.copytree(bundle/'client',target,ignore=shutil.ignore_patterns('ClientProfile','Saves','*.log'))
    path=target/'Data/Scripts.rxdata';entries=read(path.read_bytes());main=next(i for i,e in enumerate(entries) if e.name==b'Main');source=entries[main].source();assert source.endswith(MAIN_ENTRY)
    setup=f'ENTRY_PORT={port}\nENTRY_INDEX={i}\n'.encode();path.write_bytes(write(entries,{main:source[:-len(MAIN_ENTRY)]+setup+(ROOT/'tests/runtime_entry.rb').read_bytes()}))
    clients.append(subprocess.Popen([str(target/'Game.exe')],cwd=target))
   print('Entry scene review ready:',output,flush=True);deadline=time.monotonic()+660
   while any(p.poll() is None for p in clients):
    if time.monotonic()>deadline:raise TimeoutError('Entry review timed out')
    time.sleep(.1)
   assert all(p.returncode==0 for p in clients),'Inspect client rgssxp.log'
  finally:
   for p in clients:stop(p)
   stop(process)
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('bundle',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args();review(a.bundle,a.output)
