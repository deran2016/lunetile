"""Start two isolated interactive GUI clients; gui-live.json contains public state only."""
import argparse,json,os,shutil,socket,subprocess,time
from pathlib import Path
from smoke_test import ROOT,start_server,stop
from rxdata import read,write
from prepare_example import MAIN_ENTRY

def combat_arena(server):
 config=json.loads((server/'data/server.json').read_text(encoding='utf-8'));p=config['spawn']
 monsters=json.loads((server/'data/monsters.json').read_text(encoding='utf-8'))
 monster=monsters[0];monster.update(move_ms=60000,attack_ms=60000,aggro=1,attack=0,spawns=[dict(map_id=p['map_id'],x=p['x']+1,y=p['y']+dy) for dy in (-1,0,1)])
 (server/'data/monsters.json').write_text(json.dumps(monsters,ensure_ascii=False),encoding='utf-8')
 (server/'data/npcs.json').write_text('[]',encoding='utf-8')

def review(bundle,output,duration,normal_focus=False,arena=False):
 bundle,output=bundle.resolve(),output.resolve()
 if output.exists() or output.is_relative_to(bundle) or bundle.is_relative_to(output):raise ValueError('Use a new separate verification folder')
 shutil.copytree(bundle/'server/data',output/'server/data')
 server=output/'server';shutil.copy2(bundle/'server/lunetile-mmo-server.exe',server/'lunetile-mmo-server.exe')
 with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
 config=json.loads((server/'data/server.json').read_text(encoding='utf-8'));config['bind']=f'127.0.0.1:{port}'
 (server/'data/server.json').write_text(json.dumps(config),encoding='utf-8')
 if arena:combat_arena(server)
 processes=[];process=None
 with (output/'server.log').open('wb') as log:
  try:
   process=start_server(server/'lunetile-mmo-server.exe',server,port,log)
   for index in range(2):
    folder=output/f'client-{index}';shutil.copytree(bundle/'client',folder,ignore=shutil.ignore_patterns('ClientProfile','Saves','*.log'))
    path=folder/'Data/Scripts.rxdata';entries=read(path.read_bytes());main=next(i for i,e in enumerate(entries) if e.name==b'Main')
    original=entries[main].source();assert original.endswith(MAIN_ENTRY)
    setup=f'GUI_TEST_PORT={port}\nGUI_TEST_INDEX={index}\nGUI_TEST_DURATION={duration}\n'.encode()
    path.write_bytes(write(entries,{main:original[:-len(MAIN_ENTRY)]+setup+(ROOT/'tests/runtime_gui.rb').read_bytes()}))
    environment=os.environ.copy()
    if normal_focus:environment.pop('LUNETILE_TEST_BACKGROUND',None)
    else:environment['LUNETILE_TEST_BACKGROUND']='1'
    processes.append(subprocess.Popen([str(folder/'Game.exe')],cwd=folder,env=environment))
   print('Interactive GUI review ready:',output,flush=True)
   deadline=time.monotonic()+duration+20
   while any(p.poll() is None for p in processes):
    if time.monotonic()>deadline:raise TimeoutError('GUI review timeout')
    time.sleep(.2)
   for p in processes:assert p.returncode==0,'Inspect client rgssxp.log'
  finally:
   for p in processes:stop(p)
   stop(process)

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('bundle',type=Path);parser.add_argument('--output',required=True,type=Path);parser.add_argument('--duration',type=int,default=300)
 parser.add_argument('--normal-focus',action='store_true',help='Use the scene background option without test environment flags')
 parser.add_argument('--combat-arena',action='store_true',help='Place three quiet monsters in front of the test spawn')
 args=parser.parse_args();review(args.bundle,args.output,args.duration,args.normal_focus,args.combat_arena)
