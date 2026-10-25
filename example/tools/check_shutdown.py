"""Verify a console break drains acknowledged writes into JSON (isolated hidden console)."""
import argparse,ctypes,hashlib,json,shutil,socket,subprocess,tempfile,time
from pathlib import Path
from smoke_test import connect,send,stop
def check(bundle,output):
 bundle=bundle.resolve();output=output.resolve()
 if output.exists():raise ValueError('Use a new output')
 output.mkdir(parents=True);temporary=Path(tempfile.mkdtemp(prefix='lunetile-stop-')).resolve();assert temporary.is_relative_to(Path(tempfile.gettempdir()).resolve())
 server=temporary/'server';shutil.copytree(bundle/'server/data',server/'data');exe=server/'lunetile-mmo-server.exe';shutil.copy2(bundle/'server/lunetile-mmo-server.exe',exe)
 with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
 config=json.loads((server/'data/server.json').read_text(encoding='utf-8'));config['bind']=f'127.0.0.1:{port}';(server/'data/server.json').write_text(json.dumps(config),encoding='utf-8')
 startup=subprocess.STARTUPINFO();startup.dwFlags|=subprocess.STARTF_USESHOWWINDOW;startup.wShowWindow=0
 process=None;attached=False;report={'passed':False,'server_sha256':hashlib.sha256(exe.read_bytes()).hexdigest()}
 with (output/'server.log').open('wb') as log:
  try:
   process=subprocess.Popen([str(exe),'--root',str(server)],creationflags=subprocess.CREATE_NEW_CONSOLE|subprocess.CREATE_NEW_PROCESS_GROUP,startupinfo=startup,stdout=log,stderr=log)
   end=time.monotonic()+10
   while time.monotonic()<end:
    try:connection=connect(port);break
    except OSError:time.sleep(.05)
   else:raise TimeoutError('startup')
   welcome=send(connection,dict(type='register',protocol=11,name='Shutdown test'));id=welcome['id']
   state=send(connection,dict(type='progress',action='learn',key='fire_wave'));assert state['progress']['skills']['fire_wave']==1
   kernel=ctypes.windll.kernel32;kernel.FreeConsole();assert kernel.AttachConsole(process.pid),'Cannot attach isolated console';attached=True
   handler=ctypes.WINFUNCTYPE(ctypes.c_int,ctypes.c_uint32)(lambda _:1);assert kernel.SetConsoleCtrlHandler(handler,1)
   assert kernel.GenerateConsoleCtrlEvent(1,0),'Cannot generate break in isolated console'
   process.wait(timeout=15);assert process.returncode==0;connection.close()
   saved=json.loads((server/'players'/f'{id}.json').read_text(encoding='utf-8'));assert saved['progress']['skills']['fire_wave']==1
   assert (server/'transactions/active.wal').stat().st_size==0
   report.update(passed=True,console_break_exit_code=process.returncode,acknowledged_skill_present_in_json_without_recovery=True,remaining_wal_bytes=0)
  finally:
   if attached:ctypes.windll.kernel32.FreeConsole()
   stop(process);shutil.copytree(server,output/'server');assert temporary.is_relative_to(Path(tempfile.gettempdir()).resolve());shutil.rmtree(temporary)
   (output/'summary.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
 print('Graceful console shutdown PASS')
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('bundle',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args();check(a.bundle,a.output)
