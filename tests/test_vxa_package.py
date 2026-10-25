import json,shutil,subprocess,sys,tempfile,unittest,zipfile
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from package_template_vxa import package,expand_map,archive,digest,editor_fix_archive,runtime_patch_archive

RUBY=ROOT/'build/runtime-native/bin/Release/rgssxp-ruby.exe'
class VXAPackageTests(unittest.TestCase):
 def setUp(self):
  (ROOT/'build').mkdir(exist_ok=True)
  self.tmp=tempfile.TemporaryDirectory(dir=ROOT/'build');self.addCleanup(self.tmp.cleanup)
  self.root=Path(self.tmp.name);self.source=self.root/'source';self.runtime=self.root/'runtime'
  self.source.mkdir();self.runtime.mkdir()
  optimization=patch('package_template_vxa.optimize',side_effect=lambda project,engine,ruby:(project/'migration/stock-performance.rb').write_bytes(b'optimized helper'));self.optimize=optimization.start();self.addCleanup(optimization.stop)
 def test_editor_fix_contains_only_entry_script_and_instructions(self):
  target=self.root/'fix.zip';editor_fix_archive(target)
  with zipfile.ZipFile(target) as zipped:
   self.assertEqual(set(zipped.namelist()),{'LunetileEditorFix.rb','README.txt'})
   self.assertEqual(zipped.read('LunetileEditorFix.rb'),(ROOT/'src/runtime/vxa_entry.rb').read_bytes())
 def test_verification_gate(self):
  (self.runtime/'LunetileVXA.dll').write_bytes(b'runtime')
  (self.runtime/'verification-vxa.json').write_text(json.dumps({'passed':True,'runtime_sha256':'wrong'}))
  with self.assertRaises(ValueError):package(self.source,self.runtime,self.root/'out',self.root/'diag')
  self.assertFalse((self.root/'out').exists())
 def test_runtime_patch_preserves_project_data(self):
  for name in ('LunetileVXA.dll','LICENSE','Game.ini','Save01.rvdata2'):(self.source/name).write_bytes(b'fixture')
  (self.source/'licenses').mkdir();(self.source/'licenses/notice.txt').write_bytes(b'notice')
  target=self.root/'patch.zip';runtime_patch_archive(self.source,target)
  with zipfile.ZipFile(target) as zipped:
   self.assertEqual(set(zipped.namelist()),{'LunetileVXA.dll','LICENSE','licenses/notice.txt','README.txt'})
   self.assertEqual(zipped.read('LunetileVXA.dll'),b'fixture')
   self.assertIn(digest(self.source/'LunetileVXA.dll'),zipped.read('README.txt').decode('utf-8'))
 def test_performance_report_must_match_verified_dll(self):
  (self.runtime/'LunetileVXA.dll').write_bytes(b'runtime')
  expected=digest(self.runtime/'LunetileVXA.dll')
  (self.runtime/'verification-vxa.json').write_text(json.dumps({'passed':True,'runtime_sha256':expected}))
  performance=self.root/'performance.json'
  for report in ({'passed':True,'candidate_sha256':'wrong'},{'passed':False,'candidate_sha256':expected}):
   performance.write_text(json.dumps(report))
   with self.assertRaisesRegex(ValueError,'Performance report'):package(self.source,self.runtime,self.root/'out',self.root/'diag',performance=performance)
 def test_packaging_excludes_private_files_and_checks_zip(self):
  for name in ('Game.exe','Game.ini','Game.rvproj2','Save01.rvdata2','RGSS301.dll','private.log'):(self.source/name).write_bytes(b'source')
  (self.source/'Data').mkdir();(self.source/'Data/Scripts.rvdata2').write_bytes(b'scripts')
  (self.runtime/'LunetileVXA.dll').write_bytes(b'runtime')
  (self.runtime/'verification-vxa.json').write_text(json.dumps({'passed':True,'runtime_sha256':digest(self.runtime/'LunetileVXA.dll')}))
  before={p.relative_to(self.source):p.read_bytes() for p in self.source.rglob('*') if p.is_file()}
  def convert(source,target,dll,ruby,**kwargs):
   self.assertEqual(kwargs['engine'],'vxa');self.assertTrue(kwargs['high_refresh'])
   self.assertFalse((source/'Save01.rvdata2').exists());self.assertFalse((source/'RGSS301.dll').exists())
   shutil.copytree(source,target);shutil.copy2(dll,target/'LunetileVXA.dll')
   (target/'migration').mkdir();(target/'migration/manifest.json').write_text('{}')
   (target/'migration/sources').mkdir();(target/'migration/sources/stock.rb').write_text('original stock source')
  output,diag=self.root/'out',self.root/'diag'
  performance=self.root/'performance.json'
  performance.write_text(json.dumps({'passed':True,'candidate_sha256':digest(self.runtime/'LunetileVXA.dll')}))
  with patch('package_template_vxa.migrate',side_effect=convert),patch('package_template_vxa.expand_map',return_value={'size_after':[40,23,4]}):
   hashes=package(self.source,self.runtime,output,diag,performance=performance)
  self.assertEqual(before,{p.relative_to(self.source):p.read_bytes() for p in self.source.rglob('*') if p.is_file()})
  self.assertNotIn('Save01.rvdata2',hashes);self.assertNotIn('RGSS301.dll',hashes)
  self.assertEqual(json.loads((diag/'SHA256SUMS.json').read_text()),hashes)
  self.assertEqual((diag/'render-performance.json').read_bytes(),performance.read_bytes())
  self.assertEqual({p.relative_to(diag/'migration').as_posix() for p in (diag/'migration').rglob('*') if p.is_file()},{'manifest.json','stock-performance.rb'})
  self.assertEqual(self.optimize.call_args.args[1],'vxa')
  self.assertEqual((diag/'migration/stock-performance.rb').read_bytes(),b'optimized helper')
  self.assertFalse((output/'migration').exists())
  archive(output,self.root/'game.zip')
  with zipfile.ZipFile(self.root/'game.zip') as zipped:self.assertEqual(set(zipped.namelist()),set(hashes))
  with self.assertRaises(ValueError):archive(output,self.root/'game.zip')
 @unittest.skipUnless(RUBY.is_file(),'Pinned Ruby helper is required')
 def test_expansion_preserves_original_cells_events_and_system(self):
  shutil.copytree(ROOT/'template-vxa/Data',self.source/'Data')
  before=(self.source/'Data/System.rvdata2').read_bytes()
  original=self.root/'original.rvdata2';shutil.copy2(self.source/'Data/Map001.rvdata2',original)
  report=expand_map(self.source,RUBY,self.root)
  self.assertEqual(report['size_after'],[40,23,4]);self.assertEqual(report['start'],[1,8,6])
  self.assertEqual((self.source/'Data/System.rvdata2').read_bytes(),before)
  # Reuse declarations from the exercised helper, replacing its command section.
  helper=(self.root/'expand-vxa.rb').read_text(encoding='utf-8').split("project = ARGV.fetch(0)")[0]
  check=helper+"""
before = Marshal.load(File.binread(ARGV[0]))
after = Marshal.load(File.binread(ARGV[1]))
left=before.data._dump(0).byteslice(20..).unpack('v*')
right=after.data._dump(0).byteslice(20..).unpack('v*')
4.times { |z| before.height.times { |y| before.width.times { |x|
  abort 'Tile changed' unless left[z*before.width*before.height+y*before.width+x] == right[z*after.width*after.height+y*after.width+x]
} } }
abort 'Events changed' unless Marshal.dump(before.events)==Marshal.dump(after.events)
"""
  result=subprocess.run([str(RUBY),'--disable-gems','-e',check,str(original),str(self.source/'Data/Map001.rvdata2')],capture_output=True,text=True)
  self.assertEqual(result.returncode,0,result.stderr)

if __name__=='__main__':unittest.main()
