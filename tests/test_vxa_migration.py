import json,shutil,struct,subprocess,sys,tempfile,unittest,zlib
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from rxdata import read,write,integer,string,Reader
from rgssad import Archive
from migrate_project import detect_engine,MigrationError
from migrate_vxa import transform,inspect_data,migrate

def pack_v3(entries):
 seed=17;key=seed*9+3
 offset=12+sum(16+len(name) for name,_ in entries)+4
 index=bytearray(b'RGSSAD\0\3'+struct.pack('<I',seed));payload=bytearray()
 for name,data in entries:
  entry_key=0x12345678
  index.extend(struct.pack('<4I',offset^key,len(data)^key,entry_key^key,len(name)^key))
  index.extend(byte^((key>>((i%4)*8))&255) for i,byte in enumerate(name))
  for i,byte in enumerate(data):
   payload.append(byte^((entry_key>>((i%4)*8))&255))
   if i%4==3:entry_key=Archive.step(entry_key)
  offset+=len(data)
 index.extend(struct.pack('<I',key))
 return bytes(index+payload)

class VXAMigrationTests(unittest.TestCase):
 def setUp(self):(ROOT/'build').mkdir(exist_ok=True)
 @unittest.skipUnless((ROOT/'build/runtime-native/bin/Release/rgssxp-ruby.exe').is_file(),'Pinned Ruby helper is required')
 def test_entry_recovery_errors_and_test_flags(self):
  script=r"""
entry = File.read(ARGV.fetch(0))
class File
  def self.file?(path); ENV['CASE'] != 'missing'; end
end
class Win32API
  def initialize(dll,name,*args); @name=name; end
  def call(*args)
    if @name == 'WritePrivateProfileStringW'
      raise 'wrong Library' unless args[2].force_encoding('UTF-16LE').encode('UTF-8') == "LunetileVXA.dll\0"
      return ENV['CASE'] == 'write-fail' ? 0 : 1
    end
    expected = ENV['CASE'] == 'battle' ? 'btest' : (ENV['CASE'] == 'test' ? 'test' : '')
    raise 'wrong flags' unless args[3].force_encoding('UTF-16LE').encode('UTF-8') == expected+"\0"
    ENV['CASE'] == 'launch-fail' ? 31 : 33
  end
end
$TEST = ENV['CASE'] == 'test'
$BTEST = ENV['CASE'] == 'battle'
begin
  eval(entry)
  abort 'entry unexpectedly returned'
rescue SystemExit
  raise unless ['normal','test','battle'].include?(ENV['CASE'])
rescue RuntimeError => error
  expected={'missing'=>'missing','write-fail'=>'Cannot restore','launch-fail'=>'Cannot restart'}[ENV['CASE']]
  raise unless expected && error.message.include?(expected)
end
"""
  import os
  for case in ('normal','test','battle','missing','write-fail','launch-fail'):
   result=subprocess.run([str(ROOT/'build/runtime-native/bin/Release/rgssxp-ruby.exe'),'--disable-gems','-e',script,str(ROOT/'src/runtime/vxa_entry.rb')],env={**os.environ,'CASE':case},capture_output=True,text=True)
   self.assertEqual(result.returncode,0,(case,result.stderr))
 @unittest.skipUnless((ROOT/'build/runtime-native/bin/Release/LunetileVXA.dll').is_file(),'Built VX Ace runtime is required')
 def test_editor_recovery_is_injected_and_original_is_preserved(self):
  with tempfile.TemporaryDirectory(dir=ROOT/'build') as tmp:
   source=Path(tmp)/'source';shutil.copytree(ROOT/'template-vxa',source)
   (source/'System').mkdir(exist_ok=True)
   original=b'original engine sentinel';(source/'System/RGSS301.dll').write_bytes(original)
   runtime=ROOT/'build/runtime-native/bin/Release'
   output=Path(tmp)/'converted'
   migrate(source,output,runtime/'LunetileVXA.dll',runtime/'rgssxp-ruby.exe')
   self.assertEqual((source/'System/RGSS301.dll').read_bytes(),original)
   self.assertFalse((output/'System/RGSS301.dll').exists())
   self.assertEqual((output/'LunetileVXA.dll').read_bytes(),(runtime/'LunetileVXA.dll').read_bytes())
   main=next(e.source() for e in read((output/'Data/Scripts.rvdata2').read_bytes()) if e.name==b'Main')
   self.assertTrue(main.startswith((ROOT/'src/runtime/vxa_entry.rb').read_bytes()))
 def test_metadata_and_symbol_links_survive_edit(self):
  raw=b'\x04\x08['+integer(2)
  for i in range(2):
   name=b'I'+string(b'script'+str(i).encode())+integer(1)+(b':'+integer(1)+b'E' if i==0 else b';'+integer(0))+b'T'
   raw+=b'['+integer(3)+b'i'+integer(i)+name+string(zlib.compress(b'puts 1'))
  entries=read(raw)
  self.assertEqual(write(entries,{}),raw)
  changed=read(write(entries,{0:b'puts 2'}))
  self.assertEqual(changed[0].source(),b'puts 2')
  self.assertEqual(changed[1].raw,entries[1].raw)
 def test_invalid_references_metadata_and_negative_lengths(self):
  for payload in (b'@\x06',b';\0',b'I"\0\xff',b'"\xff'):
   with self.assertRaises(ValueError):Reader(payload).object()
 def test_shared_payload_links_are_preserved_or_rejected_on_edit(self):
  compressed=string(zlib.compress(b'puts 1'))
  # Slots: outer array=0, first entry=1, name=2, payload=3, second entry=4.
  raw=b'\x04\x08['+integer(2)+b'['+integer(3)+b'i'+integer(1)+string(b'one')+compressed
  raw+=b'['+integer(3)+b'i'+integer(2)+string(b'two')+b'@'+integer(3)
  entries=read(raw);self.assertEqual(write(entries,{}),raw)
  self.assertEqual(entries[1].source(),b'puts 1')
  for replacements in ({0:b'changed'},{1:b'changed'},{9:b'changed'}):
   with self.assertRaises(ValueError):write(entries,replacements)
 def test_template_roundtrip_and_baseline(self):
  raw=(ROOT/'template-vxa/Data/Scripts.rvdata2').read_bytes()
  entries=read(raw)
  self.assertEqual(len(entries),126);self.assertEqual(write(entries,{}),raw)
  with patch.object(Path,'read_bytes',return_value=b'# helper'):
   replacements,mapping=transform(entries,True,True)
  self.assertEqual(list(replacements),[124])
  output=read(write(entries,replacements))
  self.assertEqual(output[123].raw,entries[123].raw)
  entries[3].name=b'custom'
  with self.assertRaises(MigrationError):transform(entries)
 def test_engine_detection_rejects_conflicts(self):
  self.assertEqual(detect_engine(ROOT/'template-vxa'),'vxa')
  with tempfile.TemporaryDirectory(dir=ROOT/'build') as tmp:
   path=Path(tmp);(path/'Game.rxproj').write_bytes(b'')
   self.assertEqual(detect_engine(path),'xp')
   with self.assertRaises(MigrationError):detect_engine(path,'vxa')
   (path/'Game.rvproj2').write_bytes(b'')
   with self.assertRaises(MigrationError):detect_engine(path)
 def test_v3_archive_tails_and_bounds(self):
  entries=[(f'Data/{n}'.encode(),bytes(range(n))) for n in range(17)]
  with tempfile.TemporaryDirectory(dir=ROOT/'build') as tmp:
   path=Path(tmp)/'Game.rgss3a';blob=pack_v3(entries);path.write_bytes(blob)
   archive=Archive(path)
   for name,data in entries:self.assertEqual(archive.read(name),data)
   for bad in (blob[:-1],pack_v3([(b'../bad',b'x')]),pack_v3([(b'A',b'x'),(b'a',b'y')])):
    path.write_bytes(bad)
    with self.assertRaises(ValueError):Archive(path)
   bad=bytearray(pack_v3([(b'Data/a',b'x')]))
   struct.pack_into('<I',bad,12,12^(17*9+3));path.write_bytes(bad)
   with self.assertRaises(ValueError):Archive(path)
 @unittest.skipUnless((ROOT/'build/runtime-native/bin/Release/rgssxp-ruby.exe').is_file(),'Pinned Ruby helper is required')
 def test_data_validation_and_trailing_bytes(self):
  with tempfile.TemporaryDirectory(dir=ROOT/'build') as tmp:
   directory=Path(tmp);source=directory/'source';shutil.copytree(ROOT/'template-vxa/Data',source/'Data')
   project=directory/'project';(project/'migration').mkdir(parents=True)
   staging=directory/'valid';staging.mkdir()
   ruby=ROOT/'build/runtime-native/bin/Release/rgssxp-ruby.exe'
   inspect_data(source,None,ruby,staging,project)
   path=source/'Data/Map001.rvdata2';before=path.read_bytes();path.write_bytes(before+b'trailing')
   staging=directory/'invalid';staging.mkdir()
   with self.assertRaises(MigrationError):inspect_data(source,None,ruby,staging,project)
   self.assertEqual(path.read_bytes(),before+b'trailing')

if __name__=='__main__':unittest.main()
