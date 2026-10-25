"""Exercise Korean committed text and panel dragging in two isolated MMO windows."""
import argparse,ctypes,json,sys,threading,time,traceback
from ctypes import wintypes
from pathlib import Path
import psutil
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'example/tools'))
from review_gui import review

def verify(bundle,output):
 user=ctypes.windll.user32
 user.GetForegroundWindow.restype=wintypes.HWND
 user.SetForegroundWindow.argtypes=[wintypes.HWND]
 user.PostMessageW.argtypes=[wintypes.HWND,wintypes.UINT,wintypes.WPARAM,wintypes.LPARAM]
 user.GetClientRect.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.RECT)]
 user.ClientToScreen.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.POINT)]
 user.GetWindowThreadProcessId.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.DWORD)]
 callback=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,wintypes.LPARAM)
 user.EnumWindows.argtypes=[callback,wintypes.LPARAM]
 old_cursor=wintypes.POINT();user.GetCursorPos(ctypes.byref(old_cursor))
 old_window=user.GetForegroundWindow()
 errors=[];checks=[]
 def wait(test,timeout=12):
  deadline=time.monotonic()+timeout
  while time.monotonic()<deadline:
   try:
    value=test()
    if value:return value
   except (FileNotFoundError,json.JSONDecodeError,KeyError):pass
   time.sleep(.05)
  raise AssertionError('GUI condition timed out')
 def state(index):return json.loads((output/f'client-{index}/gui-live.json').read_text(encoding='utf-8'))
 def control(index,seq,kind,**args):
  folder=output/f'client-{index}';temporary=folder/'control.tmp'
  temporary.write_text(json.dumps(dict(args,seq=seq,type=kind)),encoding='utf-8');temporary.replace(folder/'gui-control.json')
  wait(lambda:state(index)['command']==seq)
 def post(window,message,wparam=0,lparam=0):assert user.PostMessageW(window,message,wparam,lparam)
 def drive():
  try:
   wait(lambda:all(state(i)['state']['self'] for i in range(2)),30)
   windows={}
   @callback
   def found(window,_):
    pid=wintypes.DWORD();user.GetWindowThreadProcessId(window,ctypes.byref(pid))
    try:
     path=Path(psutil.Process(pid.value).exe()).resolve()
     rect=wintypes.RECT()
     if not user.IsWindowVisible(window) or not user.GetClientRect(window,ctypes.byref(rect)) or rect.right<600 or rect.bottom<300:return True
     for i in range(2):
      if path==output/f'client-{i}/Game.exe':windows[i]=window
    except (psutil.NoSuchProcess,psutil.AccessDenied):pass
    return True
   user.EnumWindows(found,0);assert len(windows)==2,'Owned MMO windows missing'
   for i,window in windows.items():
    user.SetForegroundWindow(window)
    wait(lambda:user.GetForegroundWindow()==window)
    control(i,1,'chat',open=True)
    wait(lambda:state(i)['chat_open'] and state(i)['input_stats'][3])
    for character in '한글 입력 검사':post(window,0x102,ord(character))
    wait(lambda:state(i)['draft']=='한글 입력 검사')
    post(window,0x100,13);post(window,0x101,13)
    wait(lambda:any(c['text']=='한글 입력 검사' for c in state(1-i)['state']['chat']))
    checks.append(dict(client=i,korean_committed_input=True,peer_chat=True))
    control(i,2,'bag',open=True)
    panel=wait(lambda:state(i)['panel_bounds']['bag'] if state(i)['panel_bounds']['bag'][4] else None)
    rect=wintypes.RECT();assert user.GetClientRect(window,ctypes.byref(rect))
    origin=wintypes.POINT();assert user.ClientToScreen(window,ctypes.byref(origin))
    scale=min(rect.right/1280,rect.bottom/720)
    def pointer(x,y):
     px=int((rect.right-1280*scale)/2+x*scale);py=int((rect.bottom-720*scale)/2+y*scale)
     assert user.SetCursorPos(origin.x+px,origin.y+py)
     return (px&65535)|((py&65535)<<16)
    x,y=panel[0]+60,panel[1]+16
    position=pointer(x,y);post(window,0x201,1,position);time.sleep(.15)
    for step in range(1,5):
     position=pointer(x-step*10,y+step*8);post(window,0x200,1,position);time.sleep(.08)
    post(window,0x202,0,position)
    moved=wait(lambda:state(i)['panel_bounds']['bag'] if state(i)['panel_bounds']['bag'][:2]!=panel[:2] else None)
    checks[-1]['window_drag_delta']=[moved[0]-panel[0],moved[1]-panel[1]]
    control(i,3,'close')
   initial={m['id']:m['hp'] for m in state(0)['state']['monsters']}
   control(0,4,'attack',direction=6)
   wait(lambda:any(m['hp']<initial.get(m['id'],m['hp']) for m in state(0)['state']['monsters']))
   checks.append(dict(combat_damage=True))
  except BaseException:errors.append(traceback.format_exc())
  finally:
   for i in range(2):
    folder=output/f'client-{i}'
    if folder.exists():(folder/'gui-exit.txt').write_text('verification complete')
   user.SetCursorPos(old_cursor.x,old_cursor.y)
   if old_window:user.SetForegroundWindow(old_window)
 thread=threading.Thread(target=drive);thread.start()
 try:review(bundle,output,90,arena=True)
 finally:thread.join(timeout=40)
 report=dict(passed=not errors and len(checks)==3,checks=checks,errors=errors,scope='Owned two-client loopback GUI; Unicode WM_CHAR committed Korean input, not physical IME composition; original profiles excluded')
 (output/'gui-summary.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
 assert report['passed'],report

if __name__=='__main__':
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('bundle',type=Path);ap.add_argument('output',type=Path)
 args=ap.parse_args();verify(args.bundle.resolve(),args.output.resolve())
