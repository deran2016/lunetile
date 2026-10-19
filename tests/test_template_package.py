import hashlib,json,shutil,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from package_template import package

class TemplatePackageTests(unittest.TestCase):
 def setUp(self):
  root=Path(__file__).resolve().parents[1]/'build/test-template-package';root.mkdir(parents=True,exist_ok=True)
  self.temp=tempfile.TemporaryDirectory(dir=root);self.addCleanup(self.temp.cleanup)
  self.root=Path(self.temp.name);self.source=self.root/'source';self.runtime=self.root/'runtime';self.output=self.root/'output';self.diagnostics=self.root/'diagnostics'
  self.source.mkdir();self.runtime.mkdir()
  for name in ('Game.exe','Game.ini','Game.rxproj','RGSS104E.dll','Save1.rxdata','private.log'):(self.source/name).write_bytes(b'original')
  (self.source/'Data').mkdir()
  for name in ('Scripts','Map001','System'):(self.source/f'Data/{name}.rxdata').write_bytes(name.encode())
  for name in ('LICENSE','artifact.json','ruby.lock.json','dependencies.lock.json','ruby-msvc32-size-fetch-add.patch','rgssxp-ruby.exe'):(self.runtime/name).write_bytes(b'notice')
  (self.runtime/'Lunetile.dll').write_bytes(b'new runtime')
  for name in ('docs','licenses'):(self.runtime/name).mkdir()
  (self.runtime/'licenses/notice').write_bytes(b'original notice')
  (self.runtime/'docs/history.md').write_bytes(b'historical documentation')
  (self.runtime/'verification.json').write_text(json.dumps({'passed':True,'runtime_sha256':hashlib.sha256(b'new runtime').hexdigest()}))
  self.expansion=patch('package_template.expand_map',return_value={'size_after':[40,23,3]})
  self.expansion.start();self.addCleanup(self.expansion.stop)

 def package(self):return package(self.source,self.runtime,self.output,self.diagnostics)

 def migrate(self,source,out,dll,ruby,**kwargs):
  self.assertTrue(kwargs.get('widescreen'))
  self.assertTrue(kwargs.get('high_refresh'))
  self.assertFalse((source/'Save1.rxdata').exists())
  self.assertFalse((source/'RGSS104E.dll').exists())
  shutil.copytree(source,out);shutil.copy2(dll,out/'Lunetile.dll')
  (out/'migration').mkdir();(out/'migration/manifest.json').write_text('{}')

 def test_only_project_files_and_verified_runtime_are_shipped(self):
  with patch('package_template.migrate',side_effect=self.migrate):hashes=self.package()
  self.assertEqual((self.source/'RGSS104E.dll').read_bytes(),b'original')
  self.assertEqual((self.output/'Lunetile.dll').read_bytes(),b'new runtime')
  self.assertFalse((self.output/'RGSS104E.dll').exists())
  self.assertFalse((self.output/'Save1.rxdata').exists())
  self.assertFalse((self.output/'private.log').exists())
  self.assertFalse((self.output/'rgssxp-ruby.exe').exists())
  self.assertEqual({p.name for p in self.output.iterdir()},{'Game.exe','Game.ini','Game.rxproj','Lunetile.dll','Data','Graphics','Audio','README.txt','LICENSE','licenses'})
  self.assertEqual({p.relative_to(self.diagnostics).as_posix() for p in self.diagnostics.rglob('*') if p.is_file()},
   {'migration/manifest.json','artifact.json','verification.json','ruby.lock.json','dependencies.lock.json','ruby-msvc32-size-fetch-add.patch','template-source.json','template-map.json','SHA256SUMS.json'})
  self.assertEqual((self.output/'licenses/notice').read_bytes(),b'original notice')
  self.assertEqual(json.loads((self.diagnostics/'SHA256SUMS.json').read_text()),hashes)
  self.assertEqual(json.loads((self.diagnostics/'template-map.json').read_text())['size_after'],[40,23,3])
  for name,digest in hashes.items():self.assertEqual(hashlib.sha256((self.output/name).read_bytes()).hexdigest(),digest)

 def test_wrong_runtime_hash_is_rejected_without_output(self):
  (self.runtime/'Lunetile.dll').write_bytes(b'unverified')
  with self.assertRaises(ValueError):self.package()
  self.assertFalse(self.output.exists())
  self.assertFalse(self.diagnostics.exists())

 def test_conversion_failure_does_not_publish_partial_output(self):
  with patch('package_template.migrate',side_effect=ValueError('invalid template')):
   with self.assertRaises(ValueError):self.package()
  self.assertFalse(self.output.exists())
  self.assertFalse(self.diagnostics.exists())

 def test_invalid_map_does_not_publish_either_output(self):
  with patch('package_template.migrate',side_effect=self.migrate),patch('package_template.expand_map',side_effect=ValueError('invalid map')):
   with self.assertRaises(ValueError):self.package()
  self.assertFalse(self.output.exists());self.assertFalse(self.diagnostics.exists())

 def test_outputs_must_be_separate_and_new(self):
  for target in (self.source,self.runtime,self.output,self.output/'nested'):
   with self.subTest(target=target),self.assertRaises(ValueError):package(self.source,self.runtime,self.output,target)
  self.diagnostics.mkdir()
  with self.assertRaises(ValueError):self.package()
  self.assertFalse(self.output.exists())
