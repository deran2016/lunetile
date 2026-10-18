import hashlib,json,shutil,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from package_template import package

class TemplatePackageTests(unittest.TestCase):
 def setUp(self):
  root=Path(__file__).resolve().parents[1]/'build/test-template-package';root.mkdir(parents=True,exist_ok=True)
  self.temp=tempfile.TemporaryDirectory(dir=root);self.addCleanup(self.temp.cleanup)
  self.root=Path(self.temp.name);self.source=self.root/'source';self.runtime=self.root/'runtime';self.output=self.root/'output'
  self.source.mkdir();self.runtime.mkdir()
  for name in ('Game.exe','Game.ini','Game.rxproj','RGSS104E.dll','Save1.rxdata','private.log'):(self.source/name).write_bytes(b'original')
  (self.source/'Data').mkdir();(self.source/'Data/Scripts.rxdata').write_bytes(b'scripts')
  for name in ('LICENSE','artifact.json','ruby.lock.json','dependencies.lock.json','ruby-msvc32-size-fetch-add.patch','rgssxp-ruby.exe'):(self.runtime/name).write_bytes(b'notice')
  (self.runtime/'RGSS104E.dll').write_bytes(b'new runtime')
  for name in ('docs','licenses'):(self.runtime/name).mkdir()
  (self.runtime/'verification.json').write_text(json.dumps({'passed':True,'runtime_sha256':hashlib.sha256(b'new runtime').hexdigest()}))

 def migrate(self,source,out,dll,ruby,**kwargs):
  self.assertTrue(kwargs.get('widescreen'))
  self.assertTrue(kwargs.get('high_refresh'))
  self.assertFalse((source/'Save1.rxdata').exists())
  self.assertFalse((source/'RGSS104E.dll').exists())
  shutil.copytree(source,out);shutil.copy2(dll,out/'RGSS104E.dll')
  (out/'migration').mkdir();(out/'migration/manifest.json').write_text('{}')

 def test_only_project_files_and_verified_runtime_are_shipped(self):
  with patch('package_template.migrate',side_effect=self.migrate):hashes=package(self.source,self.runtime,self.output)
  self.assertEqual((self.source/'RGSS104E.dll').read_bytes(),b'original')
  self.assertEqual((self.output/'RGSS104E.dll').read_bytes(),b'new runtime')
  self.assertFalse((self.output/'Save1.rxdata').exists())
  self.assertFalse((self.output/'private.log').exists())
  self.assertFalse((self.output/'rgssxp-ruby.exe').exists())
  for name,digest in hashes.items():self.assertEqual(hashlib.sha256((self.output/name).read_bytes()).hexdigest(),digest)

 def test_wrong_runtime_hash_is_rejected_without_output(self):
  (self.runtime/'RGSS104E.dll').write_bytes(b'unverified')
  with self.assertRaises(ValueError):package(self.source,self.runtime,self.output)
  self.assertFalse(self.output.exists())

 def test_conversion_failure_does_not_publish_partial_output(self):
  with patch('package_template.migrate',side_effect=ValueError('invalid template')):
   with self.assertRaises(ValueError):package(self.source,self.runtime,self.output)
  self.assertFalse(self.output.exists())
