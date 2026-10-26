"""Sequential quick/release/formal runtime validation with content-bound receipts."""
import argparse,json,shutil,subprocess,sys,time,traceback
from pathlib import Path
import runtime_validation as policy

ROOT=policy.ROOT

def prepare_projects(runtime,output,engines):
 from migrate_project import migrate
 from optimize_template_scripts import optimize
 from package_template import ASSETS,expand_map
 from package_template_vxa import expand_map as expand_vxa
 output.mkdir(parents=True)
 for engine in engines:
  source=ROOT/f'template-{engine}';clean=output/(engine+'-source');clean.mkdir()
  project_file='Game.rxproj' if engine=='xp' else 'Game.rvproj2'
  for name in ['Game.exe','Game.ini',project_file]:shutil.copy2(source/name,clean/name)
  for directory,extensions in ASSETS.items():
   for path in (source/directory).rglob('*'):
    allowed=extensions if engine=='xp' else ({'.rvdata2'} if directory=='Data' else extensions)
    if path.is_file() and path.suffix.lower() in allowed:
     if path.is_symlink() or not path.resolve().is_relative_to(source.resolve()):raise ValueError('Unsafe template input')
     target=clean/path.relative_to(source);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
  project=output/engine
  migrate(clean,project,runtime/policy.DLLS[engine],runtime/'rgssxp-ruby.exe',data_encoding='UTF-8',widescreen=True,high_refresh=True,engine=engine)
  optimize(project,engine,runtime/'rgssxp-ruby.exe')
  (expand_map if engine=='xp' else expand_vxa)(project,runtime/'rgssxp-ruby.exe',output)
 return output

def launch(engine,runtime,folder,source,**options):
 if engine=='xp':
  from test_runtime import run
  return run(ROOT/'template-xp/Game.exe',runtime/'Lunetile.dll',folder,'',source,**options)
 from test_runtime_vxa import run
 return run(folder,source,dll=runtime/'LunetileVXA.dll',**options)

def deterministic(engine,runtime,out):
 if engine=='xp':
  cases={'types': ['rgss_types_reference.rb','runtime_types.rb','runtime_smoke.rb'],
   'tiles':['fixtures/xp_tilemap_reference.rb','runtime_xp_tile_cache.rb'], 'tile-d3d':['runtime_xp_d3d.rb']}
 else:
  cases={'types':['runtime_vxa_features.rb'],'tiles':['fixtures/vxa_tilemap_reference.rb','runtime_vxa_tilemap.rb'],'tile-d3d':['runtime_vxa_d3d.rb']}
 cases.update({name.replace('_','-'):[f'runtime_{name}.rb'] for name in ['display_commands','text_cache','tile_parser_gc']})
 for name,files in cases.items():
  source=b'\n'.join((ROOT/'tests'/f).read_bytes() for f in files)
  launch(engine,runtime,out/name,source,timeout=180)

def save_restart(engine,runtime,project,out):
 from benchmark_stock_scripts import source
 prefix=source(project,engine)
 if engine=='xp':
  write=b"$game_variables[1]=1977\nRGSSXP::Saves.write(RGSSXP::Saves.filename(0,:write)) { |f| Scene_Save.new.write_save_data(f) }\nFile.write('runtime-complete.txt','saved,false,false')"
  first=out/'write';launch(engine,runtime,first,prefix+write,data=project/'Data',rtp=True,screen_size=(1280,720),timing_profile='stock120',timeout=60)
  path=first/'Saves/RGSSXP/Save1.rxdata'
  read=("Dir.mkdir('Saves');Dir.mkdir('Saves/RGSSXP')\nFile.binwrite(RGSSXP::Saves.filename(0,:write),File.binread("+repr(path.as_posix())+"))\nf=RGSSXP::Saves.open_read(RGSSXP::Saves.filename(0));Scene_Load.new.read_save_data(f);f.close\nRGSSXP.restore_game_compatibility\nraise 'Restart state' unless $game_variables[1]==1977 && $game_map.map_id==1\nFile.write('runtime-complete.txt','loaded,false,false')").encode()
  launch(engine,runtime,out/'read',prefix+read,data=project/'Data',rtp=True,screen_size=(1280,720),timing_profile='stock120',timeout=60)
 else:
  write=b"$game_variables[1]=1977\nraise 'Save failed' unless DataManager.save_game(15)\nFile.write('runtime-complete.txt','saved')"
  first=out/'write';launch(engine,runtime,first,prefix+write,data=project/'Data',rtp=True,high=True,wide=True,timeout=60)
  read=b"raise 'Load failed' unless DataManager.load_game(15)\n$game_system.on_after_load\nraise 'Restart state' unless $game_variables[1]==1977 && $game_map.map_id==1\nFile.write('runtime-complete.txt','loaded')"
  launch(engine,runtime,out/'read',prefix+read,data=project/'Data',saves=first/'Saves',rtp=True,high=True,wide=True,timeout=60)

def lifecycle(engine,runtime,out):
 import test_runtime_vxa_window as window
 window.verify(out/'window',engine,runtime/policy.DLLS[engine])
 from test_runtime_browser import Game,wait
 game=Game(out/'reset',engine,runtime)
 try:
  game.start();game.tap(0x7b);wait(lambda:game.live().get('runs')==2,'Game-focus F12 did not reset')
 finally:game.stop(validate=sys.exc_info()[0] is None)

class Validator:
 def __init__(self,output,mode,runtime,projects,selected,cache):
  self.output=output;self.mode=mode;self.runtime=runtime;self.projects=projects;self.selected=selected
  self.cache=policy.Receipts(cache);self.context=policy.identity(runtime,projects)
  self.started=time.monotonic();self.ids=set()
  self.report=dict(validation_schema=1,mode=mode,phase='running',formal=mode=='performance',passed=False,required=[],checks=[],selection=selected,
   artifacts={},identity=self.context,projects_directory=str(projects.resolve()),scope='Throughput smoke; no comparative CPU improvement claim' if mode!='performance' else 'Formal comparative performance')
  self.report['skipped_groups']=[dict(group=g,reason='Not affected by selected changes') for g in ['render','browser','network'] if g not in selected['groups']]
  if mode!='performance':self.report['skipped_groups'].append(dict(group='formal-performance',reason='Select --mode performance for 30-second x 3-pair comparison'))
 def save(self):
  self.report['elapsed_seconds']=time.monotonic()-self.started
  processes=[]
  for path in self.output.rglob('validation-processes.json'):processes+=json.loads(path.read_text())
  self.report['game_processes']=len({r['pid'] for r in processes})
  for path in self.output.rglob('validation-extra-processes.json'):self.report['game_processes']+=json.loads(path.read_text())['game_processes']
  self.report['monitor_hash_calls']=sum(r['monitor_hash_calls'] for r in processes)
  self.report['identity_hash_calls']=policy.HASH_CALLS
  policy.write_json(self.output/'verification.json',self.report)
 def case(self,case,action,cacheable=False):
  if case in self.ids:raise ValueError('Duplicate case: '+case)
  self.ids.add(case);self.report['required'].append(case);folder=self.output/case
  if self.report.get('only') and case!=self.report['only'].split('/')[0]:
   self.report['checks'].append(dict(id=case,status='skipped',reason='Diagnostic --only selection'));self.save();return
  if self.report.get('only'):cacheable=False
  cached=self.cache.load(case,self.context) if cacheable else None
  if cached:
   self.report['checks'].append(dict(id=case,status='reused',reason='All identity and evidence hashes match',receipt=cached));self.save();return
  folder.mkdir();began=time.monotonic();print('RUN',case,flush=True)
  row=dict(id=case,status='failed',reason='first execution',output=str(folder))
  self.report['checks'].append(row)
  try:
   result=action(folder)
   if result is not None:policy.write_json(folder/'check.json',result)
   elif not any(folder.iterdir()):policy.write_json(folder/'check.json',dict(passed=True))
   row['status']='passed'
  except BaseException:
   row['reason']=traceback.format_exc();raise
  finally:
   row['seconds']=time.monotonic()-began
   if cacheable:row['receipt']=self.cache.store(case,self.context,row['status'],folder)
   self.save()
 def command(self,args,folder):
  with (folder/'command.log').open('wb') as log:
   result=subprocess.run(args,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
  if result.returncode:raise RuntimeError('First failure retained: '+str(folder/'command.log'))
  policy.write_json(folder/'exit.json',dict(passed=True,exit_code=0))
 def finish(self):
  required=[self.report['only'].split('/')[0]] if self.report.get('only') else policy.expected_cases(self.report)
  policy.require_cases(self.report,required)
  if self.context!=policy.identity(self.runtime,self.projects):raise ValueError('Validation inputs/environment changed during execution')
  self.report['passed']=True;self.report['phase']='diagnostic' if self.report.get('only') else 'complete';self.save();return self.report

def mmo(bundle,runtime,out):
 from test_runtime_client_gui import verify
 sys.path.insert(0,str(ROOT/'example/tools'));from smoke_test import verify as native
 clean=out/'bundle';(clean/'server').mkdir(parents=True)
 shutil.copytree(bundle/'server/data',clean/'server/data',ignore=shutil.ignore_patterns('accounts','players','*.log','*.bak','backups'))
 shutil.copy2(bundle/'server/lunetile-mmo-server.exe',clean/'server/lunetile-mmo-server.exe')
 shutil.copytree(bundle/'client',clean/'client',ignore=shutil.ignore_patterns('ClientProfile','Saves','*.log'))
 shutil.copy2(runtime/'Lunetile.dll',clean/'client/Lunetile.dll')
 native(clean,out/'native',True);verify(clean,out/'gui')
 policy.write_json(out/'validation-extra-processes.json',dict(game_processes=4,reason='Two completed native clients and two completed GUI clients; server processes excluded'))

def extract_browser(runtime,verification,out):
 from package_browser import package
 from test_runtime_browser import Game,windows,user,gdi,wait
 import ctypes,os,zipfile
 from ctypes import wintypes as W
 package(runtime,verification,out/'package')
 class Gui(ctypes.Structure):_fields_=[('size',W.DWORD),('flags',W.DWORD),('active',W.HWND),('focus',W.HWND),('capture',W.HWND),('menu',W.HWND),('move',W.HWND),('caret',W.HWND),('rect',W.RECT)]
 user.GetGUIThreadInfo.argtypes=[W.DWORD,ctypes.POINTER(Gui)];user.GetGUIThreadInfo.restype=W.BOOL
 for engine in policy.DLLS:
  project=out/engine;project.mkdir()
  with zipfile.ZipFile(out/'package'/f'lunetile-browser-{engine}-demo.zip') as z:
   if z.testzip() or any(Path(n).is_absolute() or '..' in Path(n).parts for n in z.namelist()):raise ValueError('Unsafe ZIP')
   z.extractall(project)
  before={p.name:policy.digest(p) for p in project.glob('*') if p.is_file()}
  env=os.environ.copy();env.pop('LUNETILE_TEST_BACKGROUND',None)
  process=subprocess.Popen([str(project/'Game.exe')],cwd=project,env=env);policy.record_process(project,process.pid)
  game=Game.__new__(Game);game.process=process;game.held=set()
  try:
   game.window=wait(lambda:next((h for h,n,r in windows(process.pid) if user.IsWindowVisible(h) and r.bottom-r.top>200),None),'Extracted game missing')
   game.activate()
   def panel():return next(((h,r) for h,n,r in windows(process.pid,game.window) if n=='LunetileBrowserPanel' and user.IsWindowVisible(h) and r.right-r.left>300),None)
   wait(panel,'Extracted browser missing')
   def page_ready():
    current=panel()
    if not current:return False
    rect=current[1];dc=user.GetDC(None)
    try:return gdi.GetPixel(dc,rect.left+5,rect.top+30)==0x60a020
    finally:user.ReleaseDC(None,dc)
   wait(page_ready,'Extracted offline HTML not presented')
   def focus_page():
    wait(page_ready,'Reopened offline HTML not presented')
    h,rect=panel();game.click_screen(rect.left+40,rect.top+45)
    tid=user.GetWindowThreadProcessId(game.window,None)
    def focused():
     info=Gui();info.size=ctypes.sizeof(info);user.GetGUIThreadInfo(tid,ctypes.byref(info));return info.focus==h or user.IsChild(h,info.focus)
    wait(focused,'Extracted browser did not acquire keyboard focus')
   focus_page();game.tap(0x1b);wait(lambda:not panel(),'Extracted Esc failed')
   game.tap(0x0d);wait(panel,'Extracted reopen failed');focus_page();old=panel()[0];game.tap(0x7b)
   wait(lambda:panel() and panel()[0]!=old,'Extracted F12 did not replace old panel');wait(page_ready,'Reset offline HTML not presented')
   user.PostMessageW(game.window,0x10,0,0);process.wait(15)
   assert process.returncode==0 and 'Ruby finalized' in (project/'rgssxp.log').read_text() and all(policy.digest(project/n)==h for n,h in before.items())
  finally:
   if process.poll() is None:process.terminate();process.wait()
 policy.write_json(out/'extraction.json',dict(passed=True,original_rgss=False,rtp=False))

def extract_runtime(runtime,verification,out):
 """A release without browser changes still executes freshly extracted engine ZIPs."""
 from test_runtime import scripts
 from package_template_vxa import archive
 import os,zipfile
 proof=json.loads(verification.read_text());policy.require_report(proof,runtime,purpose='package')
 for engine,name in policy.DLLS.items():
  stage=out/(engine+'-stage');stage.mkdir()
  shutil.copy2(ROOT/f'template-{engine}/Game.exe',stage/'Game.exe');shutil.copy2(runtime/name,stage/name)
  ext='rxdata' if engine=='xp' else 'rvdata2'
  source=b"s=Sprite.new;s.bitmap=Bitmap.new(32,32);s.bitmap.fill_rect(s.bitmap.rect,Color.new(30,60,90))\n120.times { Graphics.update;Input.update }\nraise 'Extracted pixels' unless Graphics.__scene_pixel(8,8)==[30,60,90,255]\nFile.write('runtime-complete.txt','extracted')"
  (stage/f'Scripts.{ext}').write_bytes(scripts(source))
  (stage/'Game.ini').write_text(f'[Game]\nLibrary={name}\nScripts=Scripts.{ext}\nRTP=\nRTP1=\n[Lunetile]\nTimingProfile=stock120\nRenderRate=120\nWidth=1280\nHeight=720\n')
  path=out/(engine+'.zip');archive(stage,path);project=out/engine;project.mkdir()
  with zipfile.ZipFile(path) as z:z.extractall(project)
  expected={p.name:policy.digest(p) for p in stage.iterdir()}
  env=os.environ.copy();env['LUNETILE_TEST_BACKGROUND']='1'
  process=subprocess.Popen([str(project/'Game.exe')],cwd=project,env=env);policy.record_process(project,process.pid)
  try:process.wait(20)
  finally:
   if process.poll() is None:process.terminate();process.wait()
  assert process.returncode==0 and (project/'runtime-complete.txt').is_file() and 'Ruby finalized' in (project/'rgssxp.log').read_text()
  assert all(policy.digest(project/n)==h for n,h in expected.items())
 policy.write_json(out/'extraction.json',dict(passed=True,original_rgss=False,rtp=False,scope='Fresh CRC-checked minimal engine ZIPs, pixel assertion and normal shutdown; browser not requested'))

def verify(args):
 if args.mode=='performance' and args.baseline is None:raise ValueError('Performance mode requires --baseline')
 if args.mode=='performance' and any(not (args.baseline/n).is_file() for n in policy.DLLS.values()):raise ValueError('Baseline DLL directory incomplete')
 started=time.monotonic();runtime=args.runtime.resolve();policy.check_build(runtime)
 selected=policy.selection(args.changed if args.changed is not None else (['*'] if args.all or args.mode!='quick' else policy.changed_paths()))
 if args.mode!='quick':selected['engines']=list(policy.DLLS)
 out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
 if args.projects:
  projects=out/'projects';projects.mkdir()
  for engine in selected['engines']:
   target=projects/engine;target.mkdir()
   for directory in ['Data','Graphics','Audio']:
    source=args.projects.resolve()/engine/directory
    if source.exists():shutil.copytree(source,target/directory)
   shutil.copy2(runtime/policy.DLLS[engine],target/policy.DLLS[engine])
 else:projects=prepare_projects(runtime,out/'projects',selected['engines'])
 validator=Validator(out,args.mode,runtime,projects,selected,args.cache.resolve());validator.started=started
 validator.report['mmo_requested']=args.mmo_bundle is not None
 validator.report['only']=args.only
 py=[sys.executable,'-X','utf8','-B']
 try:
  validator.case('python',lambda f:validator.command(py+['-m','unittest','discover','-s','tests','-v'],f))
  from inspect_runtime import inspect
  from benchmark_stock_scripts import run
  for engine in selected['engines']:
   artifact=inspect(runtime/policy.DLLS[engine],engine=engine);validator.report['artifacts'][engine]=artifact
   validator.case(engine+'.abi',lambda f,a=artifact:a,cacheable=True)
   if args.mode!='quick':
    command=py+(['scripts/test_runtime.py',str(ROOT/'template-xp/Game.exe'),str(runtime/'Lunetile.dll')] if engine=='xp' else ['scripts/test_runtime_vxa.py','--dll',str(runtime/'LunetileVXA.dll')])
    validator.case(engine+'.core',lambda f,c=command:validator.command(c+[str(f/'native')],f))
   elif 'render' in selected['groups']:
    validator.case(engine+'.deterministic',lambda f,e=engine:deterministic(e,runtime,f),cacheable=True)
   validator.case(engine+'.logic',lambda f,e=engine:run(e,projects/e,f/'native',(ROOT/'tests/runtime_stock_script_speed.rb').read_bytes()))
   if args.mode!='quick':
    validator.case(engine+'.save-restart',lambda f,e=engine:save_restart(e,runtime,projects/e,f))
    validator.case(engine+'.lifecycle',lambda f,e=engine:lifecycle(e,runtime,f))
  if 'network' in selected['groups']:
   validator.case('network',lambda f:validator.command(py+['scripts/test_runtime_network.py',str(f/'native'),'--dll',str(runtime/'Lunetile.dll')]+(['--high-only'] if args.mode=='quick' else []),f))
  if 'browser' in selected['groups']:
   import test_runtime_browser as browser
   if args.mode=='quick':
    validator.case('browser.smoke',lambda f:browser.smoke(f/'native',runtime,selected['engines']))
   else:validator.case('browser.full',lambda f:validator.command(py+['scripts/test_runtime_browser.py',str(f/'native'),'--dll-dir',str(runtime)],f))
  if args.mmo_bundle:
   validator.case('mmo',lambda f:mmo(args.mmo_bundle.resolve(),runtime,f))
  else:validator.report['checks'].append(dict(id='mmo',status='skipped',reason='No MMO bundle requested; no MMO certification'))
  if selected['engines']:
   from benchmark_runtime_browser import quick
   validator.case('output.quick',lambda f:quick(runtime,projects,f/'native',selected['engines'],'browser' in selected['groups'],args.only.split('/',1)[1] if args.only and '/' in args.only else None))
   if (out/'output.quick/native/summary.json').exists():validator.report['performance']=json.loads((out/'output.quick/native/summary.json').read_text())
  if args.mode=='performance':
   if args.baseline is None:raise ValueError('Performance mode requires --baseline')
   validator.case('output.formal',lambda f:validator.command(py+['scripts/benchmark_runtime_browser.py',str(args.baseline.resolve()),str(runtime),str(projects),str(f/'native')],f))
   if (out/'output.formal/native/summary.json').exists():
    validator.report['performance']=json.loads((out/'output.formal/native/summary.json').read_text());validator.report['performance']['formal']=True
  extractor=extract_browser if 'browser' in selected['groups'] else extract_runtime
  if not args.only and args.mode!='quick':
   # Packaging consumes the same receipts; it does not launch a second test suite.
   policy.require_cases(validator.report,policy.expected_cases(validator.report,prepackage=True))
   proof=dict(validator.report,phase='prepackage',passed=True)
   policy.write_json(out/'packaging-proof.json',proof)
   validator.case('package.extraction',lambda f:extractor(runtime,out/'packaging-proof.json',f))
  elif args.only=='package.extraction':
   if args.evidence is None:raise ValueError('Package-only diagnosis requires --evidence with prepackage proof')
   validator.case('package.extraction',lambda f:extractor(runtime,args.evidence.resolve(),f))
  return validator.finish()
 except BaseException:
  validator.report['passed']=False;validator.report['error']=traceback.format_exc();validator.save();raise

def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('paths',nargs='+',type=Path)
 ap.add_argument('--mode',choices=['quick','release','performance'],default='quick')
 ap.add_argument('--runtime',type=Path,default=ROOT/'build/runtime-native/bin/Release')
 ap.add_argument('--projects',type=Path);ap.add_argument('--baseline',type=Path)
 ap.add_argument('--cache',type=Path,default=ROOT/'build/validation-cache')
 ap.add_argument('--all',action='store_true');ap.add_argument('--changed',nargs='+');ap.add_argument('--mmo-bundle',type=Path)
 ap.add_argument('--only',help='Diagnostic only, e.g. output.quick/xp-cadence; cannot certify a release')
 ap.add_argument('--evidence',type=Path,help='Prior prepackage proof for package-only diagnosis')
 ap.add_argument('--dll',type=Path,help=argparse.SUPPRESS);ap.add_argument('--ruby',type=Path,help=argparse.SUPPRESS)
 a=ap.parse_args()
 if len(a.paths)==4:
  from verify_runtime_legacy import main as legacy
  return legacy()
 if len(a.paths)!=1:ap.error('Use one output path, or the original four-path detailed verification command')
 if a.dll or a.ruby:ap.error('Use --runtime DIRECTORY for the new verifier; --dll/--ruby belong to the original four-path command')
 a.output=a.paths[0]
 if a.only:a.all=True
 report=verify(a);print(f"{a.mode} PASS: {report['elapsed_seconds']:.2f}s, {report['game_processes']} game processes; formal={report['formal']}, phase={report['phase']}",flush=True)
if __name__=='__main__':main()
