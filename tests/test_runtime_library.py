import configparser,hashlib,shutil,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from inspect_runtime import PE
from migrate_project import ROOT,migrate

DLL=ROOT/'build/runtime-native/bin/Release/Lunetile.dll'
RUBY=DLL.with_name('rgssxp-ruby.exe')

@unittest.skipUnless(DLL.is_file() and RUBY.is_file(),'Build Lunetile and its pinned Ruby helper first')
class RuntimeLibraryTests(unittest.TestCase):
 def test_export_library_name_matches_the_distribution(self):
  pe=PE(DLL);rva,_=pe.directory(0)
  self.assertEqual(pe.text(pe.u32(pe.offset(rva)+12)),'Lunetile.dll')

 def test_migration_selects_new_name_and_removes_stale_engines(self):
  staging=ROOT/'build/test-runtime-library';staging.mkdir(parents=True,exist_ok=True)
  with tempfile.TemporaryDirectory(dir=staging) as folder:
   root=Path(folder);source=root/'original';output=root/'converted'
   shutil.copytree(ROOT/'template',source,ignore=shutil.ignore_patterns('*.dll','Saves','*.log'))
   for name in ('RGSS104E.dll','Lunetile.dll'):(source/name).write_bytes(b'unchanged source engine fixture')
   before={p.relative_to(source):hashlib.sha256(p.read_bytes()).hexdigest() for p in source.rglob('*') if p.is_file()}
   manifest=migrate(source,output,DLL,RUBY,data_encoding='UTF-8')
   ini=configparser.ConfigParser();ini.read(output/'Game.ini',encoding='utf-16')
   self.assertEqual(ini.get('Game','Library'),'Lunetile.dll')
   self.assertEqual((output/'Lunetile.dll').read_bytes(),DLL.read_bytes())
   self.assertFalse((output/'RGSS104E.dll').exists())
   self.assertEqual({item['path'] for item in manifest['removed_engine_files']},{'RGSS104E.dll','Lunetile.dll'})
   self.assertEqual({p.relative_to(source):hashlib.sha256(p.read_bytes()).hexdigest() for p in source.rglob('*') if p.is_file()},before)
