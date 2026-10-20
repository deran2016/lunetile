"""Post F12/close only to the owned VX Ace launcher window, including during movies."""
import argparse,ctypes,json,shutil,subprocess,threading,time
from ctypes import wintypes
from pathlib import Path
import psutil
from test_runtime_vxa import ROOT,run

def inject(output,message,errors):
 try:
  user=ctypes.windll.user32;callback=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,wintypes.LPARAM)
  user.EnumWindows.argtypes=[callback,wintypes.LPARAM]
  user.GetWindowThreadProcessId.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.DWORD)]
  user.PostMessageW.argtypes=[wintypes.HWND,wintypes.UINT,wintypes.WPARAM,wintypes.LPARAM]
  handles=[]
  @callback
  def window(handle,_):
   pid=wintypes.DWORD();user.GetWindowThreadProcessId(handle,ctypes.byref(pid))
   try:
    if Path(psutil.Process(pid.value).exe()).resolve()==output/'Game.exe':handles.append(handle)
   except (psutil.NoSuchProcess,psutil.AccessDenied):pass
   return True
  deadline=time.monotonic()+45
  while time.monotonic()<deadline:
   if (output/'ready.txt').exists():
    user.EnumWindows(window,0)
    if handles:break
   time.sleep(.02)
  if not handles:raise RuntimeError('Owned launcher window was not ready')
  time.sleep(.2)
  if message=='reset':
   if not user.PostMessageW(handles[0],0x100,0x7b,1):raise RuntimeError('F12 post failed')
   user.PostMessageW(handles[0],0x101,0x7b,0xc0000001)
  elif not user.PostMessageW(handles[0],0x10,0,0):raise RuntimeError('Close post failed')
 except Exception as error:errors.append(repr(error))

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('output',type=Path)
 args=parser.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
 movie=out/'owned.ogv';bad=out/'bad.ogv';bad.write_bytes(b'OggS'+b'\0'*40)
 ffmpeg=shutil.which('ffmpeg')
 if not ffmpeg:raise RuntimeError('ffmpeg is needed to generate the owned movie fixture')
 subprocess.run([ffmpeg,'-hide_banner','-loglevel','error','-f','lavfi','-i','testsrc2=size=96x64:rate=20','-t','2','-c:v','libtheora',str(movie)],check=True)
 reports={}
 for mode in ('game','movie'):
  for action in ('reset','close'):
   target=out/f'{mode}-{action}'
   playback=f'Graphics.__play_movie({json.dumps(movie.as_posix())})' if mode=='movie' else 'Graphics.update'
   source=f"""passes = 0
rgss_main do
  passes += 1
  Graphics.update
  begin
    Graphics.__play_movie({json.dumps(bad.as_posix())})
    raise 'Invalid movie accepted'
  rescue RGSSError
  end
  if passes == 1
    File.write('ready.txt','ready')
    {'File.write("runtime-complete.txt","close requested")' if action=='close' else ''}
    loop do
      {playback}
    end
  end
  raise 'Unexpected repeated reset' unless passes == 2
  {playback}
  File.write('runtime-complete.txt','F12 reset recovered and playback resources reusable')
end
""".encode()
   errors=[];injector=threading.Thread(target=inject,args=(target,action,errors));injector.start()
   try:reports[f'{mode}-{action}']=run(target,source,timeout=60)
   finally:injector.join()
   assert not errors,errors
 (out/'summary.json').write_text(json.dumps({'passed':True,'scope':'Synthetic HWND-scoped F12/WM_CLOSE; original launcher, error recovery and native movie cleanup; not physical keyboard testing','runs':reports},indent=2))
 print('VX Ace F12 and close, during gameplay and movie playback: PASS')

if __name__=='__main__':main()
