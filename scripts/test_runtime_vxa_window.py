"""Exercise the owned VX Ace HWND and sample its presented quadrant content."""
import argparse,ctypes,json,threading,time
from ctypes import wintypes
from pathlib import Path
import psutil
from test_runtime_vxa import run

class MonitorInfo(ctypes.Structure):
 _fields_=[('size',wintypes.DWORD),('monitor',wintypes.RECT),('work',wintypes.RECT),('flags',wintypes.DWORD)]

def exercise(output,logical,report,errors):
 user=ctypes.windll.user32;gdi=ctypes.windll.gdi32
 callback=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,wintypes.LPARAM)
 user.EnumWindows.argtypes=[callback,wintypes.LPARAM]
 user.GetWindowThreadProcessId.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.DWORD)]
 user.GetClientRect.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.RECT)]
 user.GetWindowRect.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.RECT)]
 user.ClientToScreen.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.POINT)]
 user.GetWindowLongW.argtypes=[wintypes.HWND,ctypes.c_int]
 user.MonitorFromWindow.argtypes=[wintypes.HWND,wintypes.DWORD];user.MonitorFromWindow.restype=wintypes.HMONITOR
 user.GetMonitorInfoW.argtypes=[wintypes.HMONITOR,ctypes.POINTER(MonitorInfo)]
 user.GetDC.argtypes=[wintypes.HWND];user.GetDC.restype=wintypes.HDC
 user.ReleaseDC.argtypes=[wintypes.HWND,wintypes.HDC]
 user.SetWindowPos.argtypes=[wintypes.HWND,wintypes.HWND,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,wintypes.UINT]
 user.ShowWindow.argtypes=[wintypes.HWND,ctypes.c_int]
 user.SetForegroundWindow.argtypes=[wintypes.HWND]
 user.PostMessageW.argtypes=[wintypes.HWND,wintypes.UINT,wintypes.WPARAM,wintypes.LPARAM]
 gdi.GetPixel.argtypes=[wintypes.HDC,ctypes.c_int,ctypes.c_int];gdi.GetPixel.restype=wintypes.DWORD
 handles=[]
 @callback
 def found(handle,_):
  pid=wintypes.DWORD();user.GetWindowThreadProcessId(handle,ctypes.byref(pid))
  try:
   if Path(psutil.Process(pid.value).exe()).resolve()==output/'Game.exe':handles.append(handle)
  except (psutil.NoSuchProcess,psutil.AccessDenied):pass
  return True
 try:
  deadline=time.monotonic()+40
  while time.monotonic()<deadline:
   if (output/'ready.txt').exists():
    user.EnumWindows(found,0)
    if handles:break
   time.sleep(.02)
  if not handles:raise RuntimeError('Owned game window not found')
  window=handles[0]
  def snapshot(name):
   # Foreground activation may be denied while Codex owns focus; keep this owned test window visible for capture.
   assert user.SetWindowPos(window,wintypes.HWND(-1),0,0,0,0,0x0001|0x0002|0x0010)
   user.SetForegroundWindow(window);time.sleep(.3)
   client=wintypes.RECT();outer=wintypes.RECT();monitor=MonitorInfo();monitor.size=ctypes.sizeof(monitor)
   assert user.GetClientRect(window,ctypes.byref(client))
   assert user.GetWindowRect(window,ctypes.byref(outer))
   assert user.GetMonitorInfoW(user.MonitorFromWindow(window,2),ctypes.byref(monitor))
   scale=min(client.right/logical[0],client.bottom/logical[1]);w,h=logical[0]*scale,logical[1]*scale
   origin=wintypes.POINT();assert user.ClientToScreen(window,ctypes.byref(origin))
   dc=user.GetDC(None);assert dc
   colors=[]
   try:
    for x,y in ((.25,.25),(.75,.25),(.25,.75),(.75,.75)):
     pixel=gdi.GetPixel(dc,origin.x+int((client.right-w)/2+w*x),origin.y+int((client.bottom-h)/2+h*y))
     colors.append([pixel&255,(pixel>>8)&255,(pixel>>16)&255])
   finally:user.ReleaseDC(None,dc)
   # Desktop SDR/HDR conversion can change numeric RGB; preserve measured baseline and quadrant identity.
   assert all(colors[i][i]>max(colors[i][j] for j in range(3) if j!=i)+30 for i in range(3)),(name,colors)
   assert min(colors[3])>180 and max(colors[3])-min(colors[3])<=3,(name,colors)
   if 'initial' in report:
    assert all(abs(a-b)<=3 for color,want in zip(colors,report['initial']['colors']) for a,b in zip(color,want)),(name,colors)
   result={'client':[client.right,client.bottom],'outer':[outer.left,outer.top,outer.right,outer.bottom],
           'monitor':[monitor.monitor.left,monitor.monitor.top,monitor.monitor.right,monitor.monitor.bottom],
           'style':user.GetWindowLongW(window,-16)&0xffffffff,'colors':colors}
   report[name]=result;return result
  initial=snapshot('initial')
  assert user.SetWindowPos(window,None,0,0,900,700,0x0002|0x0004)
  resized=snapshot('resized');assert resized['client']!=initial['client']
  user.ShowWindow(window,3);maximized=snapshot('maximized')
  assert maximized['style']&0x01000000 and maximized['client']!=resized['client']
  user.ShowWindow(window,9);restored=snapshot('restored');assert restored['client']==resized['client']
  assert user.PostMessageW(window,0x104,13,1|(1<<29))
  fullscreen=snapshot('fullscreen')
  assert fullscreen['outer']==fullscreen['monitor'] and not fullscreen['style']&0x00cf0000
  assert user.PostMessageW(window,0x105,13,1|(1<<29)|(1<<30)|(1<<31))
  assert user.PostMessageW(window,0x104,13,1|(1<<29))
  back=snapshot('fullscreen_restored')
  assert back['client']==restored['client'] and back['outer']==restored['outer']
  user.PostMessageW(window,0x105,13,1|(1<<29)|(1<<30)|(1<<31))
 except Exception as error:errors.append(repr(error))
 finally:
  if output.exists():(output/'done.txt').write_text('done')

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('output',type=Path)
 args=parser.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
 ctypes.windll.user32.SetProcessDPIAware()
 source=b"""width, height = Graphics.width, Graphics.height
bitmap = Bitmap.new(width,height)
[[0,0,Color.new(220,40,40)],[width/2,0,Color.new(40,180,40)],[0,height/2,Color.new(40,40,220)],[width/2,height/2,Color.new(230,230,230)]].each do |x,y,color|
  bitmap.fill_rect(x,y,width/2,height/2,color)
end
sprite=Sprite.new
sprite.bitmap=bitmap
Graphics.transition(0)
Graphics.update
File.write('ready.txt','ready')
until File.exist?('done.txt')
  Graphics.update
  raise 'Logical size changed with window size' unless [Graphics.width,Graphics.height]==[width,height]
end
File.write('runtime-complete.txt','Window resizing retained logical geometry and visible content')
"""
 reports={}
 for name,logical,wide in [('default',[544,416],False),('wide',[1280,720],True)]:
  output=out/name;observed={};errors=[]
  thread=threading.Thread(target=exercise,args=(output,logical,observed,errors));thread.start()
  try:runtime=run(output,source,wide=wide,high=wide,timeout=60)
  finally:thread.join()
  assert not errors,errors
  reports[name]={'runtime':runtime,'window':observed}
 (out/'summary.json').write_text(json.dumps({'passed':True,'scope':'Owned HWND resize/maximize/restore/fullscreen messages and presented pixel sampling; not physical keyboard testing','runs':reports},indent=2))
 print('VX Ace default/wide resize, maximize and fullscreen with presented quadrant pixels: PASS')

if __name__=='__main__':main()
