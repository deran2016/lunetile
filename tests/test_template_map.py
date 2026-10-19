import hashlib,json,shutil,subprocess,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from package_template import ROOT,expand_map

RUBY=ROOT/'build/runtime-native/bin/Release/rgssxp-ruby.exe'

@unittest.skipUnless(RUBY.is_file(),'Build the pinned Ruby helper to check template Marshal data')
class TemplateMapTests(unittest.TestCase):
 def setUp(self):
  root=ROOT/'build/test-template-map';root.mkdir(parents=True,exist_ok=True)
  self.temp=tempfile.TemporaryDirectory(dir=root);self.addCleanup(self.temp.cleanup)
  self.staging=Path(self.temp.name);self.project=self.staging/'project';(self.project/'Data').mkdir(parents=True)
  for name in ('Map001','System'):shutil.copy2(ROOT/f'template/Data/{name}.rxdata',self.project/f'Data/{name}.rxdata')
  self.declarations=['module RPG; end']
  for name,fields in json.loads((ROOT/'src/runtime/rpg_schema.json').read_text()).items():
   self.declarations.append('class '+name+'; attr_accessor '+','.join(':'+field for field in fields)+'; end')
  self.declarations.append('class Table; attr_accessor :raw; def self._load(bytes); value=allocate;value.raw=bytes;value;end; def _dump(depth);raw;end;end')

 def ruby(self,body):
  result=subprocess.run([str(RUBY),'--disable-gems','-e','\n'.join(self.declarations)+'\n'+body,str(self.project)],capture_output=True,text=True,encoding='utf-8',timeout=15)
  self.assertEqual(result.returncode,0,result.stderr)
  return result.stdout

 def mutate(self,body):
  self.ruby("path=File.join(ARGV[0],'Data/Map001.rxdata');map=Marshal.load(File.binread(path));"+body+";File.binwrite(path,Marshal.dump(map))")

 def test_expansion_preserves_tiles_metadata_and_start(self):
  self.mutate("cells=map.data.raw.byteslice(20..-1).unpack('s<*');cells[0]=385;cells[300+3*20+2]=386;cells[600+14*20+19]=387;map.data.raw=map.data.raw.byteslice(0,20)+cells.pack('s<*')")
  report=expand_map(self.project,RUBY,self.staging)
  self.assertEqual(report['size_after'],[40,23,3]);self.assertEqual(report['start'],[1,9,7])
  self.assertEqual(report['magic_number_after'],(report['magic_number_before']+1)&0x7fffffff)
  output=self.ruby("map=Marshal.load(File.binread(File.join(ARGV[0],'Data/Map001.rxdata')));cells=map.data.raw.byteslice(20..-1).unpack('s<*');p [map.width,map.height,map.tileset_id,map.events.size,map.data.raw.unpack('V5'),cells[0],cells[920+3*40+2],cells[1840+14*40+19],cells[22*40+39],cells[1840+22*40+39]]")
  self.assertEqual(json.loads(output),[40,23,1,0,[3,40,23,3,2760],385,386,387,384,0])
  for name,digest in report['sha256_after'].items():self.assertEqual(hashlib.sha256((self.project/name).read_bytes()).hexdigest(),digest)

 def test_data_version_wraps_without_changing_start(self):
  self.ruby("path=File.join(ARGV[0],'Data/System.rxdata');system=Marshal.load(File.binread(path));system.magic_number=0x7fffffff;File.binwrite(path,Marshal.dump(system))")
  report=expand_map(self.project,RUBY,self.staging)
  self.assertEqual(report['magic_number_after'],0);self.assertEqual(report['start'],[1,9,7])

 def test_bad_table_or_dimensions_are_rejected_without_writes(self):
  original=(self.project/'Data/Map001.rxdata').read_bytes()
  for change in ('map.data.raw=map.data.raw.byteslice(0,100)','map.data.raw[4,4]=[21].pack("V")','map.width=21'):
   with self.subTest(change=change):
    (self.project/'Data/Map001.rxdata').write_bytes(original);self.mutate(change)
    before={p:p.read_bytes() for p in (self.project/'Data').iterdir()}
    with self.assertRaises(ValueError):expand_map(self.project,RUBY,self.staging)
    self.assertEqual({p:p.read_bytes() for p in before},before)

 def test_invalid_start_is_rejected_without_writes(self):
  self.ruby("path=File.join(ARGV[0],'Data/System.rxdata');system=Marshal.load(File.binread(path));system.start_x=20;File.binwrite(path,Marshal.dump(system))")
  before={p:p.read_bytes() for p in (self.project/'Data').iterdir()}
  with self.assertRaises(ValueError):expand_map(self.project,RUBY,self.staging)
  self.assertEqual({p:p.read_bytes() for p in before},before)
