"""Exercise WebView2 in owned XP/VXA windows with isolated project profiles."""
import argparse,ctypes,hashlib,http.server,json,os,shutil,subprocess,sys,threading,time,traceback,urllib.parse,uuid
from ctypes import wintypes as W
from pathlib import Path
import psutil
from test_runtime import scripts,run as xp_run
from test_runtime_vxa import run as vxa_run
from inspect_runtime import inspect
from runtime_validation import record_process

ROOT=Path(__file__).resolve().parents[1]
user=ctypes.windll.user32;gdi=ctypes.windll.gdi32
user.SetProcessDPIAware()
CALLBACK=ctypes.WINFUNCTYPE(W.BOOL,W.HWND,W.LPARAM)
for name,args,result in [
 ('GetForegroundWindow',[],W.HWND),('SetForegroundWindow',[W.HWND],W.BOOL),
 ('EnumWindows',[CALLBACK,W.LPARAM],W.BOOL),('EnumChildWindows',[W.HWND,CALLBACK,W.LPARAM],W.BOOL),
 ('GetWindowThreadProcessId',[W.HWND,ctypes.POINTER(W.DWORD)],W.DWORD),
 ('GetClientRect',[W.HWND,ctypes.POINTER(W.RECT)],W.BOOL),('GetWindowRect',[W.HWND,ctypes.POINTER(W.RECT)],W.BOOL),
 ('ClientToScreen',[W.HWND,ctypes.POINTER(W.POINT)],W.BOOL),('SetCursorPos',[ctypes.c_int,ctypes.c_int],W.BOOL),
 ('GetClassNameW',[W.HWND,W.LPWSTR,ctypes.c_int],ctypes.c_int),('GetDC',[W.HWND],W.HDC),
 ('ReleaseDC',[W.HWND,W.HDC],ctypes.c_int),('PostMessageW',[W.HWND,W.UINT,W.WPARAM,W.LPARAM],W.BOOL),
 ('SetWindowPos',[W.HWND,W.HWND,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,W.UINT],W.BOOL),
 ('GetDpiForWindow',[W.HWND],W.UINT),('ShowWindow',[W.HWND,ctypes.c_int],W.BOOL)]:
 f=getattr(user,name);f.argtypes=args;f.restype=result
gdi.GetPixel.argtypes=[W.HDC,ctypes.c_int,ctypes.c_int];gdi.GetPixel.restype=W.DWORD
class Mouse(ctypes.Structure):_fields_=[('dx',W.LONG),('dy',W.LONG),('data',W.DWORD),('flags',W.DWORD),('time',W.DWORD),('extra',ctypes.c_size_t)]
class Keyboard(ctypes.Structure):_fields_=[('vk',W.WORD),('scan',W.WORD),('flags',W.DWORD),('time',W.DWORD),('extra',ctypes.c_size_t)]
class Hardware(ctypes.Structure):_fields_=[('message',W.DWORD),('low',W.WORD),('high',W.WORD)]
class InputUnion(ctypes.Union):_fields_=[('mouse',Mouse),('keyboard',Keyboard),('hardware',Hardware)]
class NativeInput(ctypes.Structure):_fields_=[('kind',W.DWORD),('value',InputUnion)]
user.SendInput.argtypes=[W.UINT,ctypes.POINTER(NativeInput),ctypes.c_int];user.SendInput.restype=W.UINT
user.GetWindowLongW.argtypes=[W.HWND,ctypes.c_int];user.GetWindowLongW.restype=W.LONG
user.SendMessageW.argtypes=[W.HWND,W.UINT,W.WPARAM,W.LPARAM];user.SendMessageW.restype=ctypes.c_ssize_t
user.WindowFromPoint.argtypes=[W.POINT];user.WindowFromPoint.restype=W.HWND
user.GetAncestor.argtypes=[W.HWND,W.UINT];user.GetAncestor.restype=W.HWND

def dump(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def download_folder():
 guid=(ctypes.c_ubyte*16).from_buffer_copy(uuid.UUID('374de290-123f-4565-9164-39c4925e467b').bytes_le);value=ctypes.c_void_p()
 shell=ctypes.windll.shell32;free=ctypes.windll.ole32.CoTaskMemFree;free.argtypes=[ctypes.c_void_p]
 shell.SHGetKnownFolderPath.argtypes=[ctypes.c_void_p,W.DWORD,W.HANDLE,ctypes.POINTER(ctypes.c_void_p)];shell.SHGetKnownFolderPath.restype=W.LONG
 assert shell.SHGetKnownFolderPath(ctypes.byref(guid),0,None,ctypes.byref(value))==0
 try:return Path(ctypes.wstring_at(value))
 finally:free(value)
def wait(predicate,label,timeout=20):
 end=time.monotonic()+timeout
 while time.monotonic()<end:
  value=predicate()
  if value:return value
  time.sleep(.025)
 raise AssertionError(label)
def windows(pid,parent=None):
 result=[]
 @CALLBACK
 def visit(hwnd,_):
  owner=W.DWORD();user.GetWindowThreadProcessId(hwnd,ctypes.byref(owner))
  if owner.value==pid:
   name=ctypes.create_unicode_buffer(256);user.GetClassNameW(hwnd,name,256);rect=W.RECT();user.GetWindowRect(hwnd,ctypes.byref(rect))
   result.append((hwnd,name.value,rect))
  return True
 if parent:user.EnumChildWindows(parent,visit,0)
 else:user.EnumWindows(visit,0)
 return result
def activate_owned(window):
 user.SetWindowPos(window,W.HWND(-1),0,0,0,0,0x1|0x2|0x10)
 if user.GetForegroundWindow()==window:return
 user.ShowWindow(window,9)
 user.SetWindowPos(window,W.HWND(-1),0,0,0,0,0x1|0x2)
 user.SetForegroundWindow(window)
 if user.GetForegroundWindow()!=window:
  point=W.POINT(5,5);user.ClientToScreen(window,ctypes.byref(point))
  hit=user.WindowFromPoint(point)
  assert hit and user.GetAncestor(hit,2)==window,'Activation point is not the owned game'
  user.SetCursorPos(point.x,point.y)
  for flag in [2,4]:
   event=NativeInput(kind=0);event.value.mouse=Mouse(0,0,0,flag,0,0)
   assert user.SendInput(1,ctypes.byref(event),ctypes.sizeof(event))==1
 wait(lambda:user.GetForegroundWindow()==window,'Cannot focus owned game window',5)

def prepare(folder,engine,dlls,source):
 folder.mkdir(parents=True,exist_ok=False)
 dll='Lunetile.dll' if engine=='xp' else 'LunetileVXA.dll';ext='rxdata' if engine=='xp' else 'rvdata2'
 shutil.copy2(ROOT/f'template-{engine}/Game.exe',folder/'Game.exe');shutil.copy2(dlls/dll,folder/dll)
 (folder/f'Scripts.{ext}').write_bytes(scripts(source))
 (folder/'Game.ini').write_text(f'[Game]\nLibrary={dll}\nScripts=Scripts.{ext}\nTitle=Lunetile browser verification\nRTP=\nRTP1=\nRTP2=\nRTP3=\n[Lunetile]\nTimingProfile=stock120\nRenderRate=120\n',encoding='utf-8')
 shutil.copytree(ROOT/'tests/fixtures/browser',folder/'Web')
 return dll
class Game:
 def __init__(self,folder,engine,dlls):
  self.folder=folder;self.engine=engine;self.command_id=0
  self.dll=prepare(folder,engine,dlls,(ROOT/'tests/runtime_browser_control.rb').read_bytes())
  self.process=None;self.held=set()
 def start(self):
  for name in ['runtime-complete.txt','browser-live.json','browser-started.json','browser-command.json']:
   path=self.folder/name
   if path.exists():path.unlink()
  env=os.environ.copy();env.pop('LUNETILE_TEST_BACKGROUND',None)
  self.process=subprocess.Popen([str(self.folder/'Game.exe')],cwd=self.folder,env=env)
  record_process(self.folder,self.process.pid)
  def find():
   assert self.process.poll() is None,'Owned game exited during startup'
   return next((h for h,n,r in windows(self.process.pid) if user.IsWindowVisible(h) and r.right-r.left>300 and r.bottom-r.top>200),None)
  self.window=wait(find,'Owned game window missing')
  self.activate();wait(lambda:self.live().get('ticks',0)>5,'Game did not tick')
 def activate(self):activate_owned(self.window)
 def live(self):
  assert self.process.poll() is None,'Owned game exited'
  try:return json.loads((self.folder/'browser-live.json').read_text(encoding='utf-8'))
  except (FileNotFoundError,json.JSONDecodeError,PermissionError):return {}
 def command(self,action,**data):
  self.command_id+=1
  temporary=self.folder/'browser-command.tmp';dump(temporary,dict(id=self.command_id,action=action,**data))
  def publish():
   try:os.replace(temporary,self.folder/'browser-command.json');return True
   except PermissionError:return False
  wait(publish,'Cannot publish owned test command',2)
  return wait(lambda:(d:=self.live()).get('command',0)>=self.command_id and d,'Command failed: '+action)
 def ready(self):
  def check():
   row=self.live();assert row.get('state')!='failed',row
   return row if row.get('state')=='ready' else None
  return wait(check,'Browser navigation timeout',30)
 def resources(self):
  children=[p for p in psutil.Process(self.process.pid).children(recursive=True) if p.name().lower()=='msedgewebview2.exe']
  return dict(process_count=len(children),private_bytes=sum(getattr(p.memory_info(),'private',p.memory_info().rss) for p in children),cpu_seconds=sum(p.cpu_times().user+p.cpu_times().system for p in children),pids=[p.pid for p in children])
 def send(self,event):
  assert user.GetForegroundWindow()==self.window,'Input must target owned foreground game'
  assert user.SendInput(1,ctypes.byref(event),ctypes.sizeof(event))==1,'SendInput failed'
 def key(self,vk,down=True):
  event=NativeInput(kind=1);event.value.keyboard=Keyboard(vk,0,0 if down else 2,0,0);self.send(event)
  if down:self.held.add(vk)
  else:self.held.discard(vk)
 def tap(self,vk):self.key(vk);time.sleep(.06);self.key(vk,False)
 def type(self,text):
  raw=text.encode('utf-16-le')
  for i in range(0,len(raw),2):
   code=int.from_bytes(raw[i:i+2],'little')
   for flag in [4,6]:
    event=NativeInput(kind=1);event.value.keyboard=Keyboard(0,code,flag,0,0);self.send(event)
 def screen(self,x,y):
  client=W.RECT();user.GetClientRect(self.window,ctypes.byref(client));origin=W.POINT();user.ClientToScreen(self.window,ctypes.byref(origin));sw,sh=self.live()['size'];scale=min(client.right/sw,client.bottom/sh)
  return int(origin.x+(client.right-sw*scale)/2+x*scale),int(origin.y+(client.bottom-sh*scale)/2+y*scale)
 def click_screen(self,x,y):
  self.activate();user.SetCursorPos(x,y)
  for flag in [2,4]:event=NativeInput(kind=0);event.value.mouse=Mouse(0,0,0,flag,0,0);self.send(event)
  time.sleep(.12)
 def web_click(self,x,y):
  panel=next(r for _,n,r in windows(self.process.pid,self.window) if n=='LunetileBrowserPanel')
  client=W.RECT();user.GetClientRect(self.window,ctypes.byref(client));sw,sh=self.live()['size'];scale=min(client.right/sw,client.bottom/sh);dpi=user.GetDpiForWindow(self.window)/96
  self.click_screen(panel.left+int(x*dpi),panel.top+int(24*scale+y*dpi))
 def color(self,x,y):
  px,py=self.screen(x,y);dc=user.GetDC(None)
  try:return gdi.GetPixel(dc,px,py)
  finally:user.ReleaseDC(None,dc)
 def layout(self,bounds):
  client=W.RECT();user.GetClientRect(self.window,ctypes.byref(client));origin=W.POINT();user.ClientToScreen(self.window,ctypes.byref(origin));sw,sh=self.live()['size'];scale=min(client.right/sw,client.bottom/sh)
  x,y,w,h=bounds
  expected=[origin.x+int((client.right-sw*scale)/2+x*scale),origin.y+int((client.bottom-sh*scale)/2+y*scale),origin.x+int((client.right-sw*scale)/2+(x+w)*scale),origin.y+int((client.bottom-sh*scale)/2+(y+h)*scale)]
  actual=next(r for _,n,r in windows(self.process.pid,self.window) if n=='LunetileBrowserPanel')
  assert all(abs(a-b)<=1 for a,b in zip([actual.left,actual.top,actual.right,actual.bottom],expected)),([actual.left,actual.top,actual.right,actual.bottom],expected)
  chrome=next(r for _,n,r in windows(self.process.pid) if n=='LunetileBrowserChrome')
  assert all(abs(a-b)<=1 for a,b in zip([chrome.left,chrome.top,chrome.right],[actual.left,actual.top,actual.right])) and abs(chrome.bottom-chrome.top-24*scale)<=1,'Close bar failed to follow game layout'
 def stop(self,validate=True):
  if not self.process:return
  if self.process.poll() is None and user.GetForegroundWindow()==self.window:
   for vk in list(self.held):self.key(vk,False)
  if self.process.poll() is None:
   try:self.command('quit');self.process.wait(timeout=15)
   except BaseException:
    if self.process.poll() is None:user.PostMessageW(self.window,0x10,0,0)
    try:self.process.wait(timeout=10)
    except subprocess.TimeoutExpired:self.process.terminate();self.process.wait()
  if validate:
   assert self.process.returncode==0,'Owned game failed shutdown'
   assert (self.folder/'runtime-complete.txt').exists(),'Missing normal shutdown marker'

class Site(http.server.BaseHTTPRequestHandler):
 events=[]
 download_name='lunetile-browser-owned-probe.txt'
 def log_message(self,*args):pass
 def do_GET(self):
  path=urllib.parse.urlparse(self.path).path
  Site.events.append((path,self.headers.get('Cookie','')))
  self.send_response(200)
  if path=='/set-cookie':self.send_header('Set-Cookie','lunetile_probe=owned; Max-Age=3600; SameSite=Lax')
  if path=='/download':
   self.send_header('Content-Type','application/octet-stream');self.send_header('Content-Disposition',f'attachment; filename="{Site.download_name}"');body=b'owned fixture'
  else:
   self.send_header('Content-Type','text/html; charset=utf-8')
   body=b'''<!doctype html><meta charset="utf-8"><style>body{margin:0;background:#20a060;color:white;font:18px sans-serif}form{position:absolute;left:20px;top:50px}input{width:250px;font:18px sans-serif;padding:6px}a,button{position:absolute;left:20px;top:140px;font:18px sans-serif}#media{top:190px}#download{top:240px}#external{top:290px}#tail{height:1500px}</style><div id="tail"></div><form method="POST" action="/submit"><input name="text" aria-label="text"><input type="submit" hidden></form><a href="/popup" target="_blank">popup</a><button id="media" onclick="navigator.mediaDevices.getUserMedia({audio:true}).then(()=>fetch('/unexpected-permission')).catch(()=>fetch('/denied'))">permission</button><a id="download" href="/download">download</a><a id="external" href="lunetile-test-invalid://blocked">external</a><script>onscroll=()=>fetch('/scrolled');</script>'''
  self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
 def do_POST(self):
  body=self.rfile.read(int(self.headers.get('Content-Length','0')))
  Site.events.append(('submitted',urllib.parse.parse_qs(body.decode('utf-8')).get('text',[''])[0]))
  self.send_response(303);self.send_header('Location','/page');self.end_headers()

def close_button(game):
 chrome=next(h for h,n,_ in windows(game.process.pid) if n=='LunetileBrowserChrome')
 button=next(r for _,n,r in windows(game.process.pid,chrome) if n=='Button')
 def painted():
  dc=user.GetDC(None)
  try:
   colors=[gdi.GetPixel(dc,x,y) for y in range(button.top+2,button.bottom-2) for x in range(button.left+2,button.right-2)]
   return any(all((c>>shift)&255<170 for shift in (0,8,16)) for c in colors) and any(all((c>>shift)&255>180 for shift in (0,8,16)) for c in colors)
  finally:user.ReleaseDC(None,dc)
 wait(painted,'Native close X pixels missing over flip-model game output');return button

def smoke(output,dlls,engines=('xp','vxa')):
 output.mkdir(parents=True,exist_ok=False);results=[]
 for engine in engines:
  game=Game(output/engine,engine,dlls)
  try:
   game.start();game.command('new');game.command('file',value='Web/index.html');game.ready();game.command('focus')
   start=game.live();game.key(0x27)
   try:time.sleep(.25);after=game.live()
   finally:game.key(0x27,False)
   assert after['ticks']>start['ticks'] and after['actor_x']==start['actor_x'] and not after['ui_right']
   close_button(game);game.tap(0x1b);wait(lambda:game.live().get('state')=='disposed','Browser Esc failed')
   game.command('new');game.command('file',value='Web/index.html');game.ready();button=close_button(game)
   game.click_screen((button.left+button.right)//2,(button.top+button.bottom)//2)
   wait(lambda:game.live().get('state')=='disposed','Browser X failed')
   results.append(dict(engine=engine,passed=True,scope='Offline visible X, focus/input isolation, continuing logic and Esc/X disposal'))
  finally:game.stop(validate=sys.exc_info()[0] is None)
 dump(output/'summary.json',dict(passed=True,results=results));return dict(passed=True,results=results)

def gui(folder,engine,dlls,url):
 game=Game(folder,engine,dlls);rows=[]
 try:
  game.start();background_color=game.color(55,80);first=time.monotonic();game.command('new',rect=[40,40,400,360]);game.command('file',value='Web/index.html');game.ready();first_creation_ms=(time.monotonic()-first)*1000
  wait(lambda:game.color(55,80)==0x60a020,'Local HTML not presented')
  rows.append('local HTML presented over game')
  game.command('url',value=url+'/page');game.ready();game.command('focus');time.sleep(.2)
  start=game.live();game.key(0x27)
  try:time.sleep(.4);held=game.live()
  finally:game.key(0x27,False)
  assert held['actor_x']==start['actor_x'] and held['ticks']>start['ticks']+20 and not held['ui_right'] and not held['ui_pointer'],(start,held)
  rows.append('browser focus blocks game input while logic continues')
  game.web_click(70,65);game.key(0x11);game.tap(0x41);game.key(0x11,False);game.type('한글 가나다 ABC');game.tap(0x0d)
  wait(lambda:('submitted','한글 가나다 ABC') in Site.events,'Committed Korean form input failed')
  rows.append('committed Korean Unicode input, form submit')
  game.command('url',value='https://example.com');game.ready()
  game.command('url',value=url+'/page?after-https');game.ready()
  rows.append('remote HTTPS page navigation and return to local HTTP fixture')
  game.web_click(300,100);event=NativeInput(kind=0);event.value.mouse=Mouse(0,0,(-480)&0xffffffff,0x800,0,0);game.send(event)
  wait(lambda:any(p=='/scrolled' for p,v in Site.events),'Browser wheel scroll failed')
  assert game.live()['ui_wheel']==0
  game.command('url',value=url+'/page?after-scroll');game.ready()
  rows.append('browser wheel scroll is isolated from game')
  game.click_screen(*game.screen(5,5));start=game.live();game.key(0x27)
  try:time.sleep(.3);moved=game.live()
  finally:game.key(0x27,False)
  assert moved['actor_x']>start['actor_x']+5,(start,moved)
  game.key(0x27);time.sleep(.15);game.command('focus-blur');settled=game.live();time.sleep(.25)
  try:assert game.live()['actor_x']==settled['actor_x'],'Same-tick focus/blur leaked held key'
  except BaseException:game.key(0x27,False);raise
  user.PostMessageW(game.window,0x100,0x27,(1<<30)|1);time.sleep(.12)
  try:assert not game.live()['ui_right'],'Held browser key repeated into UIInput'
  finally:game.key(0x27,False)
  resumed=game.live();game.key(0x27)
  try:time.sleep(.2);assert game.live()['actor_x']>resumed['actor_x']+3,'Blur did not restore game keyboard focus'
  finally:game.key(0x27,False)
  rows.append('outside click restores game input; same-tick focus/blur suppresses held key')
  game.web_click(50,150);wait(lambda:any(p=='/popup' for p,v in Site.events),'New window link did not navigate in panel');game.ready()
  assert len([1 for _,n,r in windows(game.process.pid,game.window) if n=='LunetileBrowserPanel'])==1
  game.web_click(50,200);wait(lambda:any(p=='/denied' for p,v in Site.events),'Permission not denied')
  assert not any(p=='/unexpected-permission' for p,v in Site.events)
  rows.append('same-panel new-window link and media permission denial')
  Site.download_name='lunetile-browser-probe-'+uuid.uuid4().hex+'.txt';download=download_folder()/Site.download_name
  assert not download.exists()
  game.web_click(50,250);wait(lambda:any(p=='/download' for p,v in Site.events),'Download fixture link not requested');time.sleep(.3)
  assert not download.exists(),'Blocked browser download wrote a file'
  game.command('url',value=url+'/page?after-download');game.ready()
  rows.append('download cancellation prevents file creation')
  game.web_click(50,300);wait(lambda:game.live().get('error') and game.live()['error'][0]=='navigation_blocked','External scheme not blocked')
  game.command('url',value=url+'/page?recovered');game.ready()
  rows.append('external URI blocked and navigation recovered')
  game.command('hide');wait(lambda:game.color(55,80)==background_color,'Hidden browser still visible')
  assert not any(user.IsWindowVisible(h) for h,n,_ in windows(game.process.pid) if n=='LunetileBrowserChrome'),'Hidden close bar remained visible'
  game.command('show');wait(lambda:game.color(55,80)==0x60a020,'Shown browser missing')
  game.command('rect',value=[-10,10,400,280]);game.layout([-10,10,400,280]);game.command('resize',value=[1280,720]);game.command('rect',value=[80,60,1120,600]);game.layout([80,60,1120,600])
  wait(lambda:game.color(85,100)==0x60a020,'Wide browser layout failed')
  user.SetWindowPos(game.window,None,0,0,960,650,0x2|0x4);time.sleep(.2);game.layout([80,60,1120,600])
  user.ShowWindow(game.window,3);time.sleep(.2);game.layout([80,60,1120,600]);user.ShowWindow(game.window,9);time.sleep(.2)
  suggested=W.RECT();user.GetWindowRect(game.window,ctypes.byref(suggested));user.SendMessageW(game.window,0x02e0,144|(144<<16),ctypes.addressof(suggested));game.layout([80,60,1120,600])
  style=user.GetWindowLongW(game.window,-16)
  game.command('focus');game.key(0x12);game.tap(0x0d);game.key(0x12,False);time.sleep(.3)
  assert user.GetWindowLongW(game.window,-16)&0x00c00000==0,'Fullscreen style not applied';game.layout([80,60,1120,600])
  game.key(0x12);game.tap(0x0d);game.key(0x12,False);time.sleep(.3)
  assert user.GetWindowLongW(game.window,-16)==style,'Window style not restored'
  rows.append('hide/show, clipping, resize/maximize, synthetic DPI message, browser-focused fullscreen bounds/styles')
  game.command('focus');game.tap(0x1b);wait(lambda:game.live().get('state')=='disposed','Browser Esc did not close')
  assert not any(n=='LunetileBrowserChrome' for _,n,_ in windows(game.process.pid)),'Disposed close bar retained'
  game.command('new');game.command('file',value='Web/index.html');game.ready()
  button=close_button(game)
  rows.append('native close button has visible glyph and background over live D3D output')
  game.click_screen((button.left+button.right)//2,(button.top+button.bottom)//2);wait(lambda:game.live().get('state')=='disposed','Browser X did not close')
  rows.append('Esc and X dispose panel')
  game.command('new');game.command('file',value='Web/index.html');game.ready();game.command('focus');game.tap(0x7b)
  wait(lambda:game.live().get('runs')==2,'Browser-focused F12 did not reset')
  game.command('new');game.command('url',value=url+'/set-cookie');game.ready();time.sleep(.3)
  modules={Path(m.path).name.lower() for m in psutil.Process(game.process.pid).memory_maps()}
  assert game.dll.lower() in modules and not any(n.startswith(('rgss10','rgss30')) for n in modules)
  rows.append('browser-focused F12 disposes old controller; exact native DLL loaded')
  resource_a=game.resources();began=time.monotonic();time.sleep(1);resource_b=game.resources()
  browser_resources=dict(process_count=resource_b['process_count'],private_bytes=resource_b['private_bytes'],cpu_percent_one_core=100*(resource_b['cpu_seconds']-resource_a['cpu_seconds'])/(time.monotonic()-began),first_creation_ms=first_creation_ms)
  game.stop();wait(lambda:all(not psutil.pid_exists(pid) for pid in resource_b['pids']),'Owned browser processes did not exit',15)
  old=len(Site.events);game.start();game.command('new');game.command('url',value=url+'/cookie');game.ready()
  wait(lambda:any(p=='/cookie' and 'lunetile_probe=owned' in v for p,v in Site.events[old:]),'Persistent project cookie lost')
  rows.append('project cookie survives process restart')
  game.stop();isolated=Game(folder.parent/(engine+'-profile-isolation'),engine,dlls)
  try:
   old=len(Site.events);isolated.start();isolated.command('new');isolated.command('url',value=url+'/cookie');isolated.ready()
   request=wait(lambda:next(((p,v) for p,v in Site.events[old:] if p=='/cookie'),None),'Isolated cookie request missing')
   assert 'lunetile_probe=' not in request[1],'Cookie leaked to another project'
  finally:isolated.stop()
  rows.append('different project has a separate cookie profile')
  return dict(passed=True,engine=engine,dll_sha256=sha(folder/game.dll),checks=rows,browser_resources=browser_resources,scope='Owned HWND and injected logical/Unicode input, synthetic DPI message; not physical keyboard IME composition or mixed-monitor DPI')
 finally:game.stop(validate=sys.exc_info()[0] is None)

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('output',type=Path);parser.add_argument('--dll-dir',type=Path,default=ROOT/'build/runtime-native/bin/Release');parser.add_argument('--engine',choices=['xp','vxa','both'],default='both');parser.add_argument('--skip-smoke',action='store_true')
 args=parser.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=False);dlls=args.dll_dir.resolve()
 results=[];server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Site);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
 previous=user.GetForegroundWindow()
 try:
  for engine in (['xp','vxa'] if args.engine=='both' else [args.engine]):
   if not args.skip_smoke:
    probe=(ROOT/'tests/runtime_browser.rb').read_bytes()
    if engine=='xp':xp_run(ROOT/'template-xp/Game.exe',dlls/'Lunetile.dll',out/'xp-smoke','',probe,timeout=120)
    else:vxa_run(out/'vxa-smoke',probe,dll=dlls/'LunetileVXA.dll',timeout=120)
   Site.events=[]
   result=gui(out/(engine+'-gui'),engine,dlls,f'http://127.0.0.1:{server.server_port}');results.append(result);dump(out/'progress.json',dict(results=results));print(engine,'browser UI PASS',flush=True)
  dump(out/'summary.json',dict(passed=True,results=results))
 except BaseException:
  dump(out/'failure.json',dict(passed=False,results=results,error=traceback.format_exc()));raise
 finally:
  server.shutdown();server.server_close()
  if previous:user.SetForegroundWindow(previous)

if __name__=='__main__':main()
