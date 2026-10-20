"""Generated media through the VX Ace launcher, without installed OGV codecs."""
import argparse,ctypes,json,shutil,subprocess,threading
from ctypes import wintypes
from pathlib import Path
from test_runtime_vxa import ROOT,run
from test_runtime import sha
import psutil

def observe_movie(output,stop,observed):
 user=ctypes.windll.user32;gdi=ctypes.windll.gdi32
 user.GetDC.argtypes=[wintypes.HWND];user.GetDC.restype=wintypes.HDC
 user.ReleaseDC.argtypes=[wintypes.HWND,wintypes.HDC]
 gdi.GetPixel.argtypes=[wintypes.HDC,ctypes.c_int,ctypes.c_int];gdi.GetPixel.restype=wintypes.DWORD
 callback=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,wintypes.LPARAM)
 user.EnumWindows.argtypes=[callback,wintypes.LPARAM];user.EnumChildWindows.argtypes=[wintypes.HWND,callback,wintypes.LPARAM]
 user.GetClassNameW.argtypes=[wintypes.HWND,wintypes.LPWSTR,ctypes.c_int]
 user.GetClientRect.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.RECT)]
 user.GetWindowThreadProcessId.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.DWORD)]
 @callback
 def child(window,_):
  name=ctypes.create_unicode_buffer(64);user.GetClassNameW(window,name,64)
  if name.value!='Static':return True
  rect=wintypes.RECT();user.GetClientRect(window,ctypes.byref(rect));dc=user.GetDC(window)
  if dc:
   colors={gdi.GetPixel(dc,int(rect.right*x/9),int(rect.bottom*y/9)) for x in range(1,9) for y in range(1,9)}
   colors.discard(0xffffffff);user.ReleaseDC(window,dc)
   observed['max_frame_colors']=max(observed['max_frame_colors'],len(colors))
  return True
 @callback
 def window(handle,_):
  pid=wintypes.DWORD();user.GetWindowThreadProcessId(handle,ctypes.byref(pid))
  try:
   if Path(psutil.Process(pid.value).exe()).resolve()==output/'Game.exe':user.EnumChildWindows(handle,child,0)
  except (psutil.NoSuchProcess,psutil.AccessDenied):pass
  return True
 while not stop.wait(.05):user.EnumWindows(window,0)

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('output',type=Path)
 args=parser.parse_args();output=args.output.resolve();output.mkdir(parents=True,exist_ok=False)
 fixtures=output/'fixtures';fixtures.mkdir()
 ffmpeg=shutil.which('ffmpeg')
 if not ffmpeg:raise RuntimeError('Installed ffmpeg is required only to generate test fixtures')
 movies=[]
 for name,audio in [('sound',True),('silent',False)]:
  movie=fixtures/(name+'.ogv');movies.append(movie.as_posix())
  command=[ffmpeg,'-hide_banner','-loglevel','error','-f','lavfi','-i','testsrc2=size=96x64:rate=20']
  if audio:command+=['-f','lavfi','-i','sine=frequency=440:sample_rate=22050','-c:a','libvorbis']
  command+=['-t','1','-c:v','libtheora','-pix_fmt','yuv420p',str(movie)]
  subprocess.run(command,check=True)
 corrupt=fixtures/'corrupt.ogv';corrupt.write_bytes(b'OggS'+b'\0'*40)
 truncated=fixtures/'truncated.ogv';original=(fixtures/'sound.ogv').read_bytes();truncated.write_bytes(original[:len(original)//2])
 bad=[(fixtures/'missing.ogv').as_posix(),corrupt.as_posix(),truncated.as_posix()]
 prefix=f'MOVIE_PATHS = {json.dumps(movies)}\nBAD_MOVIE_PATHS = {json.dumps(bad)}\n'
 reports={}
 reports['audio']=run(output/'audio',(ROOT/'tests/runtime_vxa_audio_position.rb').read_bytes())
 stop=threading.Event();observed={'max_frame_colors':0}
 observer=threading.Thread(target=observe_movie,args=(output/'movie',stop,observed));observer.start()
 try:reports['movie']=run(output/'movie',prefix.encode()+(ROOT/'tests/runtime_vxa_movie.rb').read_bytes())
 finally:stop.set();observer.join()
 assert observed['max_frame_colors']>8,observed
 (output/'summary.json').write_text(json.dumps({'passed':True,'scope':'Native playback, visible movie surface colors, timing and error rejection; no acoustic capture or original-frame comparison','video_observation':observed,'fixtures':{p.name:sha(p) for p in fixtures.iterdir()},'runs':reports},indent=2))
 print('VX Ace audio seek/position and self-contained OGV playback: PASS')

if __name__=='__main__':main()
