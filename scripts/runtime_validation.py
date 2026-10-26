"""Build identity, conservative selection and evidence receipts for runtime checks."""
import hashlib,importlib.metadata,json,os,platform,subprocess,sys,time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SCHEMA=1
DLLS={'xp':'Lunetile.dll','vxa':'LunetileVXA.dll'}
HASH_CALLS=0

def digest(path):
 global HASH_CALLS
 HASH_CALLS+=1
 return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def write_json(path,value):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
 temporary=path.with_suffix(path.suffix+'.tmp')
 temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');temporary.replace(path)

def files_hash(root,paths):return {p.relative_to(root).as_posix():digest(p) for p in sorted(set(paths)) if p.is_file()}

def build_inputs(root=ROOT):
 paths=list((root/'src/runtime').rglob('*'))+[root/'CMakeLists.txt']
 paths+=list((root/'scripts').glob('*runtime*.ps1'))+[root/'scripts/patch_runtime_ruby.py']
 paths+=[p for p in (root/'tests').glob('*') if p.suffix in ('.c','.cpp','.h')]
 return files_hash(root,paths)

def stamp(runtime,root=ROOT):
 runtime=Path(runtime).resolve()
 names=list(DLLS.values())+['rgssxp-ruby.exe','display_geometry_test.exe','direction_input_test.exe','text_submit_test.exe']
 if any(not (runtime/n).is_file() for n in names):raise ValueError('Incomplete build outputs')
 result=dict(schema=SCHEMA,inputs=build_inputs(root),artifacts={n:digest(runtime/n) for n in names})
 write_json(runtime/'build-stamp.json',result);return result

def check_build(runtime,root=ROOT):
 runtime=Path(runtime).resolve();path=runtime/'build-stamp.json'
 if not path.is_file():raise ValueError('Build stamp missing; run scripts/build_runtime.ps1 first')
 result=json.loads(path.read_text(encoding='utf-8'))
 if result.get('schema')!=SCHEMA or result.get('inputs')!=build_inputs(root):raise ValueError('Runtime sources changed; rebuild required')
 if any(not (runtime/n).is_file() or digest(runtime/n)!=h for n,h in result['artifacts'].items()):raise ValueError('Build outputs changed; rebuild required')
 return result

def selection(paths):
 engines=set();groups=set()
 for name in paths:
  name=name.replace('\\','/')
  if name.endswith('.md') or name.startswith('licenses/'):continue
  if name.startswith(('src/runtime/vxa','src/runtime/abi_vxa','tests/runtime_vxa')):engines.add('vxa');groups.add('render')
  elif name.startswith(('src/runtime/xp_tile','src/runtime/tilemap.rb','tests/runtime_xp')):engines.add('xp');groups.add('render')
  elif 'browser' in name:engines.update(DLLS);groups.add('browser')
  elif name.startswith(('src/runtime/network','tests/runtime_network')):engines.update(DLLS);groups.update(['network','mmo'])
  elif name.startswith(('src/runtime/input','src/runtime/ui_input','src/template_scripts','scripts/optimize_template')):engines.update(DLLS);groups.update(['render','browser','mmo'])
  else:engines.update(DLLS);groups.update(['render','browser','network','mmo'])
 return dict(engines=sorted(engines),groups=sorted(groups),reason='changed paths' if paths else 'no changes; unit checks only')

def changed_paths(root=ROOT):
 commands=[['git','diff','--name-only','HEAD','-z'],['git','ls-files','--others','--exclude-standard','-z']]
 return sorted({p for command in commands for p in subprocess.check_output(command,cwd=root).decode('utf-8').split('\0') if p})

def environment(root=ROOT):
 value=dict(os=platform.platform(),python=sys.version,executable=sys.executable,machine=platform.node(),workspace=str(root.resolve()))
 value['packages']={}
 for name in ['psutil','Pillow','numpy']:
  try:value['packages'][name]=importlib.metadata.version(name)
  except importlib.metadata.PackageNotFoundError:value['packages'][name]='missing'
 if os.name=='nt':
  import winreg
  rtp=[];fonts=[]
  for keyname in ['SOFTWARE/Enterbrain/RGSS/RTP','SOFTWARE/Enterbrain/RGSS3/RTP']:
   for view in [winreg.KEY_WOW64_32KEY,winreg.KEY_WOW64_64KEY]:
    try:
     with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,keyname.replace('/','\\'),0,winreg.KEY_READ|view) as key:
      i=0
      while True:
       try:n,p,_=winreg.EnumValue(key,i);i+=1;rtp.append((n,p))
       except OSError:break
    except OSError:pass
  value['rtp']=[list(entry) for entry in sorted(set(rtp))]
  drivers=[]
  try:
   with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,r'SYSTEM\CurrentControlSet\Control\Video') as video:
    index=0
    while True:
     try:name=winreg.EnumKey(video,index);index+=1
     except OSError:break
     try:
      with winreg.OpenKey(video,name+r'\0000') as adapter:
       row={}
       for field in ['DriverVersion','DriverDesc','MatchingDeviceId']:
        try:row[field]=str(winreg.QueryValueEx(adapter,field)[0])
        except OSError:pass
       if row:drivers.append(row)
     except OSError:pass
  except OSError:pass
  value['graphics_drivers']=sorted(drivers,key=lambda r:json.dumps(r,sort_keys=True))
  fontdir=Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts'
  for p in fontdir.glob('*'):
   if p.is_file():fonts.append([p.name,p.stat().st_size,p.stat().st_mtime_ns])
  value['fonts']=fonts
  edge=Path(os.environ.get('ProgramFiles(x86)','C:/Program Files (x86)'))/'Microsoft/EdgeWebView/Application'
  value['webview2']=sorted(p.name for p in edge.glob('*') if (p/'msedgewebview2.exe').is_file())
 return value

def identity(runtime,projects,root=ROOT):
 inputs=list((root/'scripts').glob('*.py'))+list((root/'tests').rglob('*'))
 inputs+=[root/f'template-{e}/Game.exe' for e in DLLS]
 inputs.append(root/'requirements-dev.txt')
 fixtures={}
 for engine in DLLS:
  project=projects/engine
  for directory in ['Data','Graphics','Audio']:
   for path in (project/directory).rglob('*'):
    if path.is_file():fixtures[engine+'/'+path.relative_to(project).as_posix()]=digest(path)
 base=files_hash(root,[p for p in inputs if p.is_relative_to(root)])
 # Explicit external fixture directories also participate in identity.
 external={str(p.resolve()):digest(p) for p in inputs if p.is_file() and not p.is_relative_to(root)}
 return dict(schema=SCHEMA,dlls={e:digest(runtime/n) for e,n in DLLS.items()},files=base,fixtures=fixtures,external=external,environment=environment(root),config=dict(width=1280,height=720,logic=120))

def receipt_key(case,context):return hashlib.sha256(json.dumps(dict(case=case,context=context),sort_keys=True).encode()).hexdigest()

class Receipts:
 def __init__(self,directory):self.directory=Path(directory);self.directory.mkdir(parents=True,exist_ok=True)
 def load(self,case,context):
  path=self.directory/(receipt_key(case,context)+'.json')
  try:
   value=json.loads(path.read_text(encoding='utf-8'))
   if value.get('status')!='passed' or value.get('case')!=case or value.get('key')!=receipt_key(case,context):return None
   if not value.get('evidence'):return None
   if any(not Path(p).is_file() or digest(p)!=h for p,h in value['evidence'].items()):return None
   return value
  except (OSError,ValueError,TypeError,KeyError):return None
 def store(self,case,context,status,folder):
  evidence={str(p.resolve()):digest(p) for p in Path(folder).rglob('*') if p.is_file()}
  value=dict(case=case,key=receipt_key(case,context),status=status,evidence=evidence)
  write_json(self.directory/(value['key']+'.json'),value);return value

def require_cases(report,required=None):
 records=report.get('checks',[]);ids=[r['id'] for r in records]
 if len(ids)!=len(set(ids)):raise ValueError('Duplicate validation IDs')
 for case in required if required is not None else report.get('required',[]):
  row=next((r for r in records if r['id']==case),None)
  if row is None or row.get('status') not in ('passed','reused'):raise ValueError('Required check did not pass: '+case)
 return True

def expected_cases(report,prepackage=False):
 selected=report['selection'];mode=report['mode'];cases=['python']
 for engine in selected['engines']:
  cases += [engine+'.abi',engine+'.logic']
  if mode!='quick':cases += [engine+'.core',engine+'.save-restart',engine+'.lifecycle']
  elif 'render' in selected['groups']:cases.append(engine+'.deterministic')
 if 'network' in selected['groups']:cases.append('network')
 if 'browser' in selected['groups']:cases.append('browser.smoke' if mode=='quick' else 'browser.full')
 if report.get('mmo_requested'):cases.append('mmo')
 if selected['engines']:cases.append('output.quick')
 if mode=='performance':cases.append('output.formal')
 if not prepackage and mode!='quick':cases.append('package.extraction')
 return cases

def require_report(report,runtime,purpose='release'):
 if report.get('validation_schema')!=SCHEMA or report.get('passed') is not True:raise ValueError('Incomplete validation report')
 if report.get('mode') not in ('quick','release','performance') or bool(report.get('formal'))!=(report['mode']=='performance'):raise ValueError('Validation mode/formal claim mismatch')
 prepackage=purpose=='package' and report.get('phase')=='prepackage'
 if not prepackage and report.get('phase')!='complete':raise ValueError('Validation not completed')
 require_cases(report,expected_cases(report,prepackage))
 if not report.get('identity') or not report.get('projects_directory'):raise ValueError('Validation input identity missing')
 if report['identity']!=identity(Path(runtime),Path(report['projects_directory'])):raise ValueError('Validation inputs/environment changed')
 if set(report['artifacts'])!=set(report['selection']['engines']):raise ValueError('Missing validation artifact')
 for engine,artifact in report['artifacts'].items():
  if digest(Path(runtime)/DLLS[engine])!=artifact['sha256']:raise ValueError('Validation DLL mismatch')
 for row in report['checks']:
  if row.get('status')=='reused':
   evidence=row.get('receipt',{}).get('evidence',{})
   if not evidence or any(not Path(p).is_file() or digest(p)!=h for p,h in evidence.items()):raise ValueError('Cached evidence changed')
 return True

def record_process(folder,pid,hash_calls=0):
 path=Path(folder)/'validation-processes.json'
 rows=json.loads(path.read_text()) if path.exists() else []
 rows.append(dict(pid=pid,monitor_hash_calls=hash_calls));write_json(path,rows)

if __name__=='__main__':
 import argparse
 ap=argparse.ArgumentParser();ap.add_argument('action',choices=['stamp','check']);ap.add_argument('runtime',type=Path)
 a=ap.parse_args();(stamp if a.action=='stamp' else check_build)(a.runtime);print('Runtime build identity '+a.action+' PASS')
