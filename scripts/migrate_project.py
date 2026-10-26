"""Copy a reviewed stock XP project to the independent Ruby 4 runtime; never overwrite."""
import argparse,configparser,hashlib,json,os,shutil,subprocess,tempfile
from pathlib import Path
from rxdata import read,write,Reader
from inspect_runtime import inspect
from rgssad import Archive

ROOT=Path(__file__).resolve().parents[1]
RUNTIME_BIN=ROOT if (ROOT/'rgssxp-ruby.exe').is_file() else ROOT/'build/runtime-native/bin/Release'
ORIGINAL_EXE='0ed9b5139edb0ad0f0f4b5b88dd0265ddbf56d36d6f173d6a22f3b23e8212e22'
ORIGINAL_DLL='7b6acb5e2c245b8cfda77fced2cc0e94108384cd1b9ffc8510e7304fcb9feb6c'
def sha(data):return hashlib.sha256(data).hexdigest()

# Exact replacements are restricted to the pinned stock source hashes below.
RULES={
 'Game_Battler 1':[('@states_turn = {}','@states_turn = RGSSXP::IntegerMap.new')],
 'Game_Actor':[('@states_turn = {}','@states_turn = RGSSXP::IntegerMap.new')],
 'Game_Map':[
  ('@events = {}','@events = RGSSXP::IntegerMap.new'),
  ('for i in @map.events.keys','for i in RGSSXP.original_integer_keys(@map.events)'),
  ('@common_events = {}','@common_events = RGSSXP::IntegerMap.new')],
 'Window_SaveFile':[
  ('@filename = "Save#{@file_index + 1}.rxdata"','@filename = RGSSXP::Saves.filename(@file_index)'),
  ('file = File.open(@filename, "r")','file = RGSSXP::Saves.open_read(@filename)')],
 'Scene_Title':[
  ('FileTest.exist?("Save#{i+1}.rxdata")','RGSSXP::Saves.exist?(i)')],
 'Scene_File':[
  ('return "Save#{file_index + 1}.rxdata"','return RGSSXP::Saves.filename(file_index, self.is_a?(Scene_Save) ? :write : :read)')],
 'Scene_Save':[
  ('file = File.open(filename, "wb")\n    write_save_data(file)\n    file.close','RGSSXP::Saves.write(filename) do |file|\n      write_save_data(file)\n    end')],
 'Scene_Load':[
  ('file = File.open(filename, "rb")','file = RGSSXP::Saves.open_read(filename)'),
  ('read_save_data(file)\n    file.close','read_save_data(file)\n    RGSSXP.restore_game_compatibility\n    file.close')],
}

class MigrationError(ValueError):pass

def strip_legacy_pacing(text,main_hash,legacy,separate_bootstrap=False):
 text=text.replace('\r\n','\n')
 inline=[body for body in legacy['bootstrap_sources'] if text.startswith(body)]
 if len(inline)>1 or (inline and separate_bootstrap) or (not inline and not separate_bootstrap):return None
 if inline:text=text[len(inline[0]):]
 for hook in (legacy['start_line'],legacy['detach_block']):
  if text.count(hook)!=1:return None
  text=text.replace(hook,'',1)
 # Line-ending changes are allowed only after restoring the exact reviewed Main body.
 if main_hash not in (sha(text.encode()),sha(text.replace('\n','\r\n').encode())):return None
 return text

def read_project_ini(path,encoding=None):
 raw=path.read_bytes()
 if encoding not in (None,'UTF-8','CP949','CP932'):raise MigrationError('Unsupported explicit INI encoding')
 if raw.startswith((b'\xff\xfe',b'\xfe\xff')):chosen='UTF-16'
 elif raw.startswith(b'\xef\xbb\xbf'):chosen='UTF-8-SIG'
 elif encoding:chosen=encoding
 elif raw.isascii():chosen='ASCII'
 else:raise MigrationError('Game.ini: non-ASCII text requires explicit --ini-encoding UTF-8, CP949 or CP932')
 try:text=raw.decode(chosen)
 except UnicodeDecodeError as error:raise MigrationError(f'Game.ini: invalid {chosen} bytes at offset {error.start}') from error
 ini=configparser.ConfigParser(interpolation=None);ini.read_string(text)
 return ini,chosen

def transform(entries,widescreen=False,high_refresh=False):
 baseline=json.loads((ROOT/'src/runtime/stock_scripts.json').read_text())
 legacy=json.loads((ROOT/'src/runtime/legacy_pacing.json').read_text())
 helper_index=len(entries)-2 if len(entries)==len(baseline['scripts'])+1 else None
 if len(entries)!=len(baseline['scripts']) and helper_index is None:raise MigrationError('Unreviewed script collection: expected 90 stock entries or the exact legacy bootstrap above Main')
 if helper_index is not None and entries[helper_index].source().replace(b'\r\n',b'\n') not in [body.encode() for body in legacy['bootstrap_sources']]:raise MigrationError(f'Script {helper_index}: unreviewed extra script; expected exact legacy pacing bootstrap above Main')
 replacements={};mapping=[]
 stock_index=0
 for index,entry in enumerate(entries):
  source=entry.source()
  try:
   name=entry.name.decode('utf-8');text=source.decode('utf-8')
  except UnicodeDecodeError as error:raise MigrationError(f'Script {index}: encoding is ambiguous at byte {error.start}; no automatic conversion') from error
  edits=[]
  if index==helper_index:
   converted=legacy['disabled_source']
   edits.append({'line':1,'before':text,'after':converted,'reason':'remove-exact-legacy-pacing-bootstrap'})
   text=converted
  else:
   known=baseline['scripts'][stock_index];stock_index+=1
   if name!=known['name']:raise MigrationError(f'Script {index} ({name}), line 1: unreviewed script identity/order')
   if sha(source)!=known['source_sha256']:
    restored=strip_legacy_pacing(text,known['source_sha256'],legacy,helper_index is not None) if name=='Main' else None
    if restored is None:raise MigrationError(f'Script {index} ({name}), line 1: unreviewed source; no user Main or helper code will be guessed or removed')
    edits.append({'line':1,'before':text,'after':restored,'reason':'remove-exact-legacy-pacing-main-hooks'})
    text=restored
  for before,after in (RULES.get(name,[]) if index!=helper_index else []):
   # Only changed entries normalize their original CRLF line endings.
   text=text.replace('\r\n','\n')
   if text.count(before)!=1:raise MigrationError(f'Script {index} ({name}): expected exact migration rule once')
   line=text[:text.index(before)].count('\n')+1
   text=text.replace(before,after)
   edits.append({'line':line,'before':before,'after':after})
  if widescreen:
   from widescreen import adapt
   text,wide_edits=adapt(name,text.replace('\r\n','\n'));edits.extend(wide_edits)
  if high_refresh:
   from high_refresh import adapt
   text,timing_edits=adapt(name,text.replace('\r\n','\n'));edits.extend(timing_edits)
  if name=='Main':
   text='Lunetile.install_stock\n'+text
   edits.append({'line':1,'reason':'stock controls autosave and recovery menus'})
  converted=text.encode('utf-8') if edits else source
  if edits:replacements[index]=converted
  mapping.append({'index':index,'id':entry.id,'name':name,'encoding_before':'UTF-8','encoding_after':'UTF-8','source_sha256_before':sha(source),'source_sha256_after':sha(converted),'compressed_sha256_before':sha(entry.compressed),'changes':edits})
 return replacements,mapping

def syntax_check(entries,replacements,ruby,directory):
 version=subprocess.run([str(ruby),'--disable-gems','-e','abort "Ruby 4.0.7 x86 required" unless RUBY_VERSION=="4.0.7" && [0].pack("J").bytesize==4'],capture_output=True,text=True)
 if version.returncode:raise MigrationError(version.stderr or 'Ruby syntax checker failed')
 source_dir=directory/'migration/sources';source_dir.mkdir(parents=True)
 for index,entry in enumerate(entries):
  (source_dir/f'{index:03d}.rb').write_bytes(replacements.get(index,entry.source()))
 result=subprocess.run([str(ruby),'--disable-gems','-e','ARGV.each { |path| RubyVM::InstructionSequence.compile_file(path) }; puts "#{ARGV.size} scripts compile"',*[str(path) for path in sorted(source_dir.glob('*.rb'))]],capture_output=True,text=True)
 (directory/'migration/syntax-check.txt').write_text(result.stdout+result.stderr,encoding='utf-8')
 if result.returncode:raise MigrationError('Ruby 4 syntax check failed: '+result.stderr)

def inspect_data(source,archive,ruby,staging,project,data_encoding):
 inspection=staging/'inspection';inspection.mkdir()
 if archive:
  files=[(name.rsplit(b'/',1)[-1].decode('utf-8'),archive.read(name)) for name in archive.entries if name.startswith(b'data/') and name.endswith(b'.rxdata') and name!=b'data/scripts.rxdata']
 else:files=[(path.name,path.read_bytes()) for path in (source/'Data').glob('*.rxdata') if path.name!='Scripts.rxdata']
 for name,raw in files:(inspection/name).write_bytes(raw)
 schema=json.loads((ROOT/'src/runtime/rpg_schema.json').read_text())
 declarations=['module RPG; end']
 for name in schema:
  declarations.append('class '+name+'; end')
  declarations.append(name+'.class_eval { attr_accessor '+','.join(':'+field for field in schema[name])+' }')
 checker=staging/'check-data.rb'
 setup="module RGSSXP; DATA_ENCODING = ARGV[1]=='ASCII' ? 'UTF-8' : ARGV[1]; end\n"
 checker.write_text('\n'.join(declarations)+'\n'+setup+(ROOT/'src/runtime/text.rb').read_text()+'\n'+(ROOT/'scripts/check_project_data.rb').read_text(),encoding='utf-8')
 changes=staging/'text-changes.rxdata'
 result=subprocess.run([str(ruby),'--disable-gems',str(checker),str(inspection),data_encoding or 'ASCII',str(changes)],capture_output=True,text=True,encoding='utf-8',errors='replace')
 (project/'migration/data-inspection.txt').write_text(result.stdout+result.stderr,encoding='utf-8')
 if result.returncode:raise MigrationError('Project data inspection failed: '+result.stderr)
 reader=Reader(changes.read_bytes())
 if reader.take(2)!=b'\x04\x08':raise MigrationError('Invalid text conversion report')
 records=reader.object()
 if reader.pos!=len(reader.data):raise MigrationError('Trailing text conversion report data')
 return [{'location':location.decode('utf-8'),'encoding_before':encoding.decode(),'encoding_after':'UTF-8','source_bytes_hex':before.decode(),'utf8_bytes_hex':after.decode(),'source_sha256':sha(bytes.fromhex(before.decode())),'utf8_sha256':sha(bytes.fromhex(after.decode()))} for location,encoding,before,after in records]

def detect_engine(source,engine='auto',ini_encoding=None):
 if engine not in ('auto','xp','vxa'):raise MigrationError('Unknown engine')
 signals=set()
 for filename,kind in (('Game.rxproj','xp'),('Game.rvproj2','vxa'),('Data/Scripts.rxdata','xp'),('Data/Scripts.rvdata2','vxa'),('Game.rgssad','xp'),('Game.rgss3a','vxa')):
  if (source/filename).exists():signals.add(kind)
 if (source/'Game.ini').is_file():
  ini,_=read_project_ini(source/'Game.ini',ini_encoding)
  for section in ini.sections():
   if section.lower()=='game':
    library=ini.get(section,'Library',fallback='').lower()
    if 'rgss301' in library or 'lunetilevxa' in library:signals.add('vxa')
    elif 'rgss104' in library or library=='lunetile.dll':signals.add('xp')
 if (source/'Game.exe').is_file():
  launcher=sha((source/'Game.exe').read_bytes())
  if launcher==ORIGINAL_EXE:signals.add('xp')
  baseline=ROOT/'src/runtime/vxa_stock_scripts.json'
  if baseline.is_file() and launcher==json.loads(baseline.read_text(encoding='utf-8'))['launcher_sha256']:signals.add('vxa')
 if len(signals)>1:raise MigrationError('Conflicting project engine identifiers')
 if engine!='auto' and signals and engine not in signals:raise MigrationError('Requested engine conflicts with project identifiers')
 if engine=='auto':
  if not signals:raise MigrationError('Unable to identify project engine')
  return signals.pop()
 return engine

def migrate(source,output,dll,ruby,data_encoding=None,ini_encoding=None,widescreen=False,high_refresh=False,engine='auto'):
 engine=detect_engine(source,engine,ini_encoding)
 if engine=='vxa':
  from migrate_vxa import migrate as migrate_vxa
  return migrate_vxa(source,output,dll,ruby,data_encoding,ini_encoding,widescreen,high_refresh)
 source,output,dll,ruby=[path.resolve() for path in (source,output,dll,ruby)]
 if data_encoding not in (None,'UTF-8','CP949','CP932'):raise MigrationError('Unsupported explicit project data encoding')
 if not source.is_dir():raise MigrationError('Original project directory does not exist')
 if output.exists():raise MigrationError('Output already exists; refusing to overwrite')
 if not output.parent.is_dir():raise MigrationError('Output parent directory must exist')
 if output.is_relative_to(source) or source.is_relative_to(output):raise MigrationError('Source and output must be separate directory trees')
 if sha((source/'Game.exe').read_bytes())!=ORIGINAL_EXE:raise MigrationError('Game.exe does not match the verified original launcher ABI')
 if not dll.is_file() or sha(dll.read_bytes())==ORIGINAL_DLL:raise MigrationError('Independently built runtime DLL is required')
 inspect(dll)
 archive=Archive(source/'Game.rgssad') if (source/'Game.rgssad').is_file() else None
 script_path='Data/Scripts-RGSSXP.rxdata' if archive else 'Data/Scripts.rxdata'
 if archive and ((source/script_path).exists() or archive.normalize(script_path) in archive.entries):raise MigrationError('Reserved converted script path already exists')
 raw=archive.read('Data/Scripts.rxdata') if archive else (source/'Data/Scripts.rxdata').read_bytes()
 entries=read(raw)
 replacements,mapping=transform(entries,widescreen,high_refresh)
 converted=write(entries,replacements)
 for item in source.rglob('*'):
  if item.is_symlink() or item.is_junction():raise MigrationError(f'Project links require explicit review: {item.relative_to(source)}')
 manifest={'format':'RGSSXP migration 1','engine':'RGSSXP 0.1.0','ruby':'4.0.7','data_encoding':'UTF-8','data_encoding_explicit':data_encoding=='UTF-8','source_archive':bool(archive),'result_scripts_path':script_path,'source_scripts_sha256':sha(raw),'result_scripts_sha256':sha(converted),'original_launcher_sha256':ORIGINAL_EXE,'runtime_sha256':sha(dll.read_bytes()),'scripts':mapping,'files':[],'removed_engine_files':[],'imported_saves':[],'limitations':['Stock XP script sources only; unreviewed scripts are rejected','Reviewed stock-XP validation scope; arbitrary games/plugins and pixel-identical rendering/audio are not certified','Original GPU execution time and GPU speedup remain unconfirmed']}
 with tempfile.TemporaryDirectory(prefix=output.name+'.migrate-',dir=output.parent) as staging:
  project=Path(staging)/'project';project.mkdir()
  for item in sorted(source.rglob('*')):
   relative=item.relative_to(source)
   if any(part in ('.git','migration') for part in relative.parts):continue
   if not item.is_file():continue
   record={'path':relative.as_posix(),'sha256':sha(item.read_bytes())}
   manifest['files'].append(record)
   if item.name.lower() in ('rgss104e.dll','lunetile.dll','rgssframepacing.dll') or record['sha256']==ORIGINAL_DLL:
    manifest['removed_engine_files'].append(record);continue
   if relative.parts[0].lower()=='saves':raise MigrationError('Existing Saves/ directory requires explicit review; refusing to mix engine save formats')
   destination=project/relative
   if len(relative.parts)==1 and item.name in [f'Save{i}.rxdata' for i in range(1,5)]:
    destination=project/'Saves/Import'/item.name;manifest['imported_saves'].append(record)
   destination.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(item,destination)
  (project/script_path).parent.mkdir(parents=True,exist_ok=True)
  (project/script_path).write_bytes(converted)
  shutil.copy2(dll,project/'Lunetile.dll')
  ini=configparser.ConfigParser(interpolation=None);ini_before=None
  if (project/'Game.ini').exists():ini,ini_before=read_project_ini(project/'Game.ini',ini_encoding)
  for section in ('Game','RGSSXP') + (('Lunetile',) if widescreen or high_refresh else ()):
   matching=[name for name in ini.sections() if name.casefold()==section.casefold()]
   if len(matching)>1:raise MigrationError('Ambiguous case-insensitive INI section: '+section)
   if matching and matching[0]!=section:
    values=list(ini.items(matching[0],raw=True));ini.remove_section(matching[0]);ini.add_section(section)
    for key,value in values:ini.set(section,key,value)
   if not matching:ini.add_section(section)
  ini.set('Game','Library','Lunetile.dll');ini.set('Game','Scripts',script_path)
  if not ini.has_option('Game','Title'):ini.set('Game','Title','RGSSXP compatibility project')
  if widescreen:
   if ini.has_section('Lunetile'):ini.remove_section('Lunetile')
   ini.add_section('Lunetile');ini.set('Lunetile','Width','1280');ini.set('Lunetile','Height','720')
  if high_refresh:
   ini.set('Lunetile','TimingProfile','stock120');ini.set('Lunetile','RenderRate','60')
  manifest['timing']={'profile':'stock120','logic_rate':120,'render_rate':60} if high_refresh else {'profile':'legacy'}
  manifest['display']={'width':1280,'height':720,'layout':'stock-wide'} if widescreen else {'layout':'original'}
  ini.set('RGSSXP','DataEncoding',data_encoding or 'UTF-8');ini.set('RGSSXP','SaveFormat','2' if high_refresh else '1')
  # The unchanged ANSI launcher and the new wide Windows APIs both understand BOM-marked UTF-16 INI files.
  with (project/'Game.ini').open('w',encoding='utf-16') as stream:ini.write(stream,space_around_delimiters=False)
  manifest['ini_encoding_before']=ini_before;manifest['ini_encoding_after']='UTF-16LE-BOM'
  syntax_check(entries,replacements,ruby,project)
  manifest['data_encoding']=data_encoding or 'UTF-8'
  manifest['data_encoding_explicit']=data_encoding is not None
  manifest['data_text_changes']=inspect_data(source,archive,ruby,Path(staging),project,data_encoding)
  manifest['data_conversion']='Explicit source encoding; UTF-8 conversion in memory at load; original data/archive bytes preserved'
  (project/'migration/manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
  os.rename(project,output)
 return manifest

def main():
 ap=argparse.ArgumentParser(description=__doc__)
 ap.add_argument('source',type=Path);ap.add_argument('output',type=Path)
 ap.add_argument('--dll',type=Path)
 ap.add_argument('--engine',choices=('auto','xp','vxa'),default='auto')
 ap.add_argument('--ruby',type=Path,default=RUNTIME_BIN/'rgssxp-ruby.exe')
 ap.add_argument('--data-encoding',choices=['UTF-8','CP949','CP932'],help='Required for non-ASCII project text; explicit decoding is validated before copying')
 ap.add_argument('--ini-encoding',choices=['UTF-8','CP949','CP932'],help='Explicit source Game.ini encoding when it contains non-ASCII text without a BOM')
 ap.add_argument('--widescreen',action='store_true',help='Adapt reviewed stock UI/camera to 1280x720')
 ap.add_argument('--high-refresh',action='store_true',help='Convert reviewed stock timing to 120 Hz logic and selectable 40/60/120 FPS output')
 a=ap.parse_args()
 try:
  engine=detect_engine(a.source,a.engine,a.ini_encoding)
  manifest=migrate(a.source,a.output,a.dll or RUNTIME_BIN/('LunetileVXA.dll' if engine=='vxa' else 'Lunetile.dll'),a.ruby,a.data_encoding,a.ini_encoding,a.widescreen,a.high_refresh,engine)
 except (MigrationError,OSError,ValueError,configparser.Error) as error:ap.exit(1,f'Migration stopped: {error}\n')
 print(f"Project copy created: {a.output}\n{len(manifest['scripts'])} scripts validated; {sum(bool(x['changes']) for x in manifest['scripts'])} entries changed; original files preserved")

if __name__=='__main__':main()
