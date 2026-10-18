"""Fallback passive API trace using a workspace-isolated Python Frida installation."""
import argparse,ctypes,hashlib,json,threading,time
from ctypes import wintypes
from pathlib import Path
import frida

ROOT=Path(__file__).resolve().parents[1]

def process_path(pid):
 kernel=ctypes.WinDLL('kernel32',use_last_error=True)
 kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD];kernel.OpenProcess.restype=wintypes.HANDLE
 kernel.QueryFullProcessImageNameW.argtypes=[wintypes.HANDLE,wintypes.DWORD,wintypes.LPWSTR,ctypes.POINTER(wintypes.DWORD)]
 kernel.CloseHandle.argtypes=[wintypes.HANDLE]
 handle=kernel.OpenProcess(0x1000,False,pid)
 if not handle:raise ctypes.WinError(ctypes.get_last_error())
 try:
  size=wintypes.DWORD(32768);buffer=ctypes.create_unicode_buffer(size.value)
  if not kernel.QueryFullProcessImageNameW(handle,0,buffer,ctypes.byref(size)):raise ctypes.WinError(ctypes.get_last_error())
  return Path(buffer.value).resolve()
 finally:kernel.CloseHandle(handle)

def main():
 ap=argparse.ArgumentParser();ap.add_argument('project',type=Path)
 mode=ap.add_mutually_exclusive_group(required=True);mode.add_argument('--pid',type=int);mode.add_argument('--spawn',action='store_true')
 ap.add_argument('--seconds',type=float,default=7)
 a=ap.parse_args();project=a.project.resolve();exe=project/'Game.exe'
 if not 0<a.seconds<=60:ap.error('--seconds must be 0..60')
 if hashlib.sha256(exe.read_bytes()).hexdigest()!='0ed9b5139edb0ad0f0f4b5b88dd0265ddbf56d36d6f173d6a22f3b23e8212e22':raise ValueError('Unexpected launcher')
 runtime=project/'RGSS104E.dll'
 if hashlib.sha256(runtime.read_bytes()).hexdigest()!='7b6acb5e2c245b8cfda77fced2cc0e94108384cd1b9ffc8510e7304fcb9feb6c':raise ValueError('Unexpected original runtime')
 device=frida.get_local_device()
 pid=device.spawn(str(exe),cwd=str(project)) if a.spawn else a.pid
 if process_path(pid)!=exe:
  if a.spawn:device.kill(pid)
  raise ValueError('PID does not identify the selected owned probe')
 source=(ROOT/'scripts/trace_original_audio.js').read_text();messages=[];detached=threading.Event()
 session=device.attach(pid);session.on('detached',lambda *args:detached.set())
 script=session.create_script(source)
 script.on('message',lambda message,data:messages.append(message))
 cleanup='detached'
 began=time.monotonic()
 try:
  script.load()
  if a.spawn:device.resume(pid)
  detached.wait(a.seconds)
 finally:
  if not detached.is_set():
   script.unload();session.detach()
   if a.spawn:device.kill(pid);cleanup='owned target killed at explicit trace deadline'
  else:cleanup='target exited'
 report={'provider':'Python Frida fallback; not REA Evidence','version':frida.__version__,'mode':'spawn' if a.spawn else 'attach','pid':pid,'executable':str(exe),'executable_sha256':hashlib.sha256(exe.read_bytes()).hexdigest(),'runtime_sha256':hashlib.sha256(runtime.read_bytes()).hexdigest(),'source_sha256':hashlib.sha256(source.encode()).hexdigest(),'observed_seconds':time.monotonic()-began,'messages':messages,'cleanup':cleanup}
 (project/'capture.json').write_text(json.dumps(report,indent=2))
 if any(item.get('type')=='error' for item in messages):raise RuntimeError('Frida script failed; see capture.json')
 if not (project/'audio-api.jsonl').is_file():raise RuntimeError('Audio API trace was not created')
 print('Passive original audio trace captured: '+str(project))

if __name__=='__main__':main()
