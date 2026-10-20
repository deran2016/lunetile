"""Copy the pinned VX Ace template to LunetileVXA without changing its source."""
import json,os,re,shutil,tempfile
from pathlib import Path
from rxdata import read,write
from rgssad import Archive
from inspect_runtime import inspect
from migrate_project import ROOT,MigrationError,sha,read_project_ini,syntax_check
import subprocess

def declarations():
 schema=json.loads((ROOT/'src/runtime/vxa_schema.json').read_text(encoding='utf-8'))
 for name in list(schema):
  parts=name.split('::')
  for count in range(2,len(parts)):schema.setdefault('::'.join(parts[:count]),[])
 return '\n'.join(['module RPG; end']+['class '+name+'; attr_accessor '+','.join(':'+field for field in schema[name])+'; end' for name in sorted(schema,key=lambda value:(value.count('::'),value))])

def inspect_data(source,archive,ruby,staging,project):
 inspection=staging/'inspection';inspection.mkdir()
 files=[(name.rsplit(b'/',1)[-1].decode('utf-8'),archive.read(name)) for name in archive.entries if name.startswith(b'data/') and name.count(b'/')==1 and name.endswith(b'.rvdata2') and name!=b'data/scripts.rvdata2'] if archive else [(path.name,path.read_bytes()) for path in (source/'Data').glob('*.rvdata2') if path.name.lower()!='scripts.rvdata2']
 for name,data in files:(inspection/name).write_bytes(data)
 checker=staging/'check-vxa.rb'
 checker.write_text(declarations()+'\n'+(ROOT/'scripts/check_vxa_data.rb').read_text(encoding='utf-8'),encoding='utf-8')
 result=subprocess.run([str(ruby),'--disable-gems',str(checker),str(inspection)],capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=60)
 (project/'migration/data-inspection.txt').write_text(result.stdout+result.stderr,encoding='utf-8')
 if result.returncode:raise MigrationError('VX Ace data inspection failed: '+result.stderr)

def transform(entries,widescreen=False,high_refresh=False):
 baseline=json.loads((ROOT/'src/runtime/vxa_stock_scripts.json').read_text(encoding='utf-8'))['scripts']
 if len(entries)!=len(baseline):raise MigrationError('Unreviewed VX Ace script collection')
 replacements={};mapping=[]
 for index,(entry,known) in enumerate(zip(entries,baseline)):
  source=entry.source()
  if entry.name.decode('utf-8')!=known['name'] or sha(source)!=known['source_sha256']:
   raise MigrationError(f'Script {index}: unreviewed VX Ace source, identity or order')
  edits=[]
  if known['name']=='Main':
   helper=(ROOT/'src/runtime/vxa_stock.rb').read_bytes()
   replacements[index]=helper+b'\n'+source
   edits=[{'line':1,'reason':'VX Ace stock compatibility bootstrap'}]
  mapping.append({'index':index,'id':entry.id,'name':known['name'],'source_sha256_before':sha(source),'source_sha256_after':sha(replacements.get(index,source)),'changes':edits})
 return replacements,mapping

def migrate(source,output,dll,ruby,data_encoding=None,ini_encoding=None,widescreen=False,high_refresh=False):
 source,output,dll,ruby=[Path(p).resolve() for p in (source,output,dll,ruby)]
 if data_encoding not in (None,'UTF-8'):raise MigrationError('VX Ace Marshal uses encoded strings; only UTF-8 is supported')
 if output.exists():raise MigrationError('Output already exists; refusing to overwrite')
 if not source.is_dir() or not output.parent.is_dir():raise MigrationError('Source and output parent directories must exist')
 if output.is_relative_to(source) or source.is_relative_to(output):raise MigrationError('Source and output must be separate directory trees')
 baseline=json.loads((ROOT/'src/runtime/vxa_stock_scripts.json').read_text(encoding='utf-8'))
 if sha((source/'Game.exe').read_bytes())!=baseline['launcher_sha256']:raise MigrationError('Unreviewed VX Ace launcher')
 if sha(dll.read_bytes())==baseline['original_dll_sha256']:raise MigrationError('Independently built VX Ace runtime DLL is required')
 inspect(dll,'vxa')
 for item in source.rglob('*'):
  if item.is_symlink() or item.is_junction():raise MigrationError('Project links require explicit review')
 archive=Archive(source/'Game.rgss3a') if (source/'Game.rgss3a').is_file() else None
 script_path='Data/Scripts-LunetileVXA.rvdata2' if archive else 'Data/Scripts.rvdata2'
 if archive and ((source/script_path).exists() or archive.normalize(script_path) in archive.entries):raise MigrationError('Reserved converted script path already exists')
 raw=archive.read('Data/Scripts.rvdata2') if archive else (source/script_path).read_bytes()
 entries=read(raw);replacements,mapping=transform(entries,widescreen,high_refresh);converted=write(entries,replacements)
 manifest={'format':'Lunetile VXA migration 1','engine':'vxa','ruby':'4.0.7','runtime_sha256':sha(dll.read_bytes()),'source_scripts_sha256':sha(raw),'result_scripts_sha256':sha(converted),'result_scripts_path':script_path,'scripts':mapping,'files':[],'imported_saves':[],'removed_engine_files':[],
  'display':{'width':1280 if widescreen else 544,'height':720 if widescreen else 416},
  'timing':{'profile':'stock120' if high_refresh else 'legacy','logic_rate':120 if high_refresh else 60,'render_rate':60}}
 with tempfile.TemporaryDirectory(prefix=output.name+'.migrate-',dir=output.parent) as temporary:
  project=Path(temporary)/'project';project.mkdir()
  for item in sorted(source.rglob('*')):
   relative=item.relative_to(source)
   if any(part.lower() in ('.git','migration') for part in relative.parts) or not item.is_file():continue
   record={'path':relative.as_posix(),'sha256':sha(item.read_bytes())};manifest['files'].append(record)
   if item.suffix.lower() in ('.dll','.log') or item.name.lower().endswith('.dmp'):
    manifest['removed_engine_files'].append(record);continue
   if relative.parts[0].lower()=='saves':raise MigrationError('Existing Saves directory requires explicit review')
   destination=project/relative
   if len(relative.parts)==1 and re.fullmatch(r'Save\d+\.rvdata2',item.name,re.I):
    destination=project/'Saves/Import'/item.name;manifest['imported_saves'].append(record)
   destination.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(item,destination)
  (project/script_path).parent.mkdir(parents=True,exist_ok=True);(project/script_path).write_bytes(converted)
  shutil.copy2(dll,project/'LunetileVXA.dll')
  ini,encoding=read_project_ini(project/'Game.ini',ini_encoding)
  sections=[section for section in ini.sections() if section.lower()=='game']
  if len(sections)!=1:raise MigrationError('Expected one Game INI section')
  if sections[0]!='Game':
   values=dict(ini.items(sections[0]));ini.remove_section(sections[0]);ini['Game']=values
  ini.set('Game','Library','LunetileVXA.dll');ini.set('Game','Scripts',script_path)
  for section in list(ini.sections()):
   if section.lower() in ('lunetile','rgssxp'):ini.remove_section(section)
  ini['RGSSXP']={'DataEncoding':'UTF-8','SaveFormat':'3','Engine':'vxa'}
  ini['Lunetile']={'Width':str(manifest['display']['width']),'Height':str(manifest['display']['height']),'TimingProfile':manifest['timing']['profile'],'RenderRate':'60'}
  with (project/'Game.ini').open('w',encoding='utf-16') as stream:ini.write(stream,space_around_delimiters=False)
  syntax_check(entries,replacements,ruby,project)
  inspect_data(source,archive,ruby,Path(temporary),project)
  manifest['ini_encoding_before']=encoding
  (project/'migration/manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
  os.rename(project,output)
 return manifest
