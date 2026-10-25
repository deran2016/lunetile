import hashlib,json,subprocess,sys,tempfile,unittest,zlib
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'));sys.path.insert(0,str(ROOT/'example/tools'))
from rxdata import integer,string,read,write
from prepare_example import CLIENT_SCRIPTS,MAIN_ENTRY,prepare

@unittest.skipUnless((ROOT/'example/server/data/server.json').is_file(),'Local MMO JSON database is excluded from Git')
class MMOExampleTests(unittest.TestCase):
 def setUp(self):
  parent=ROOT/'build/test-mmo-package';parent.mkdir(parents=True,exist_ok=True)
  temp=tempfile.TemporaryDirectory(dir=parent);self.addCleanup(temp.cleanup);self.root=Path(temp.name)
  self.source=self.root/'source';(self.source/'Data').mkdir(parents=True)
  self.output=self.root/'output';self.server=self.root/'server.exe';self.server.write_bytes(b'own rust server')
  (self.root/'ruby.exe').write_bytes(b'test helper')
  for name in ('Game.exe','Game.rxproj','Lunetile.dll','RGSS104E.dll','Save1.rxdata','personal.log'):(self.source/name).write_bytes(name.encode())
  (self.source/'Game.ini').write_text('[Game]\nLibrary=Lunetile.dll\nScripts=Data/Scripts.rxdata\nRTP1=Standard\n[RGSSXP]\nDataEncoding=UTF-8\n',encoding='utf-8')
  (self.source/'ClientProfile').mkdir();(self.source/'ClientProfile/p.json').write_text('SECRET')
  blob=b'\x04\x08['+integer(2)
  stock_main=next(e.source() for e in read((ROOT/'template-xp/Data/Scripts.rxdata').read_bytes()) if e.name==b'Main')
  for index,name in enumerate((b'Game_Temp',b'Main')):
   source=b'PRESERVED_MAIN_HELPER = true\n'+stock_main if name==b'Main' else b'# original '+name
   blob+=b'['+integer(3)+b'i'+integer(index+1)+string(name)+string(zlib.compress(source))
  (self.source/'Data/Scripts.rxdata').write_bytes(blob)
  self.world={key:json.loads((ROOT/f'example/server/data/{key}.json').read_text(encoding='utf-8')) for key in ('maps','server','npcs')}

 def build(self):
  with patch('prepare_example.subprocess.run',return_value=SimpleNamespace(returncode=0,stdout=json.dumps(self.world),stderr='')):
   return prepare(self.source,self.output,self.server,self.root/'ruby.exe')

 def test_package_preserves_source_and_non_main_script_and_excludes_private_files(self):
  before={str(p.relative_to(self.source)):hashlib.sha256(p.read_bytes()).hexdigest() for p in self.source.rglob('*') if p.is_file()}
  hashes=self.build()
  after={str(p.relative_to(self.source)):hashlib.sha256(p.read_bytes()).hexdigest() for p in self.source.rglob('*') if p.is_file()}
  self.assertEqual(before,after)
  original=read((self.source/'Data/Scripts.rxdata').read_bytes());converted=read((self.output/'client/Data/Scripts.rxdata').read_bytes())
  self.assertEqual(original[0].raw,converted[0].raw)
  self.assertEqual(len(converted),len(original)+len(CLIENT_SCRIPTS))
  self.assertEqual(converted[-1].source(),b'PRESERVED_MAIN_HELPER = true\n'+MAIN_ENTRY)
  self.assertEqual((original[1].id,original[1].name),(converted[-1].id,converted[-1].name))
  self.assertEqual(len({e.id for e in converted}),len(converted))
  self.assertEqual(next(e.id for e in converted if e.name==b'MMO_UI'),6) # Keep the original four MMO IDs stable.
  self.assertEqual([e.name.decode() for e in converted[1:-1]],[name for name,_ in CLIENT_SCRIPTS])
  for entry,(_,filename) in zip(converted[1:-1],CLIENT_SCRIPTS):
   self.assertEqual(entry.source(),(ROOT/'example/client'/filename).read_bytes())
  self.assertFalse(list((self.output/'client').rglob('*.rb')))
  self.assertEqual((self.output/'client/Graphics/Characters/Lunetile_Portal.png').read_bytes(),(ROOT/'example/assets/Graphics/Characters/Lunetile_Portal.png').read_bytes())
  self.assertTrue((self.output/'ART_ASSETS.md').is_file())
  self.assertEqual((self.output/'server/data/particles.json').read_bytes(),(ROOT/'example/server/data/particles.json').read_bytes())
  self.assertTrue((self.output/'PARTICLES.md').is_file())
  self.assertTrue((self.output/'PERFORMANCE.md').is_file())
  self.assertTrue((self.output/'ACCOUNTS.md').is_file())
  self.assertIn(b'--recover-only',(self.output/'Recover Server.cmd').read_bytes())
  self.assertIn(b'if errorlevel 1 echo',(self.output/'Start Server.cmd').read_bytes())
  self.assertEqual(json.loads((self.output/'build-info.json').read_text())['protocol'],11)
  for name in ('RGSS104E.dll','Save1.rxdata','personal.log','ClientProfile'):self.assertFalse((self.output/'client'/name).exists())
  for name,digest in hashes.items():self.assertEqual(hashlib.sha256((self.output/name).read_bytes()).hexdigest(),digest)

 def test_reserved_portal_asset_collision_does_not_replace_source_or_publish(self):
  asset=self.source/'Graphics/Characters/Lunetile_Portal.png';asset.parent.mkdir(parents=True);asset.write_bytes(b'CUSTOM ORIGINAL')
  with self.assertRaisesRegex(ValueError,'Lunetile_Portal'):self.build()
  self.assertEqual(asset.read_bytes(),b'CUSTOM ORIGINAL');self.assertFalse(self.output.exists())

 def test_original_engine_and_existing_output_are_rejected(self):
  (self.source/'Game.ini').write_text('[Game]\nLibrary=RGSS104E.dll\n',encoding='utf-8')
  with self.assertRaises(ValueError):self.build()
  self.assertFalse(self.output.exists())
  self.output.mkdir();marker=self.output/'players.json';marker.write_bytes(b'keep')
  with self.assertRaises(ValueError):self.build()
  self.assertEqual(marker.read_bytes(),b'keep')

 def test_world_export_failure_does_not_publish_partial_distribution(self):
  with patch('prepare_example.subprocess.run',return_value=SimpleNamespace(returncode=1,stdout='',stderr='invalid map')):
   with self.assertRaises(ValueError):prepare(self.source,self.output,self.server,self.root/'ruby.exe')
  self.assertFalse(self.output.exists())

 def test_changed_world_exports_new_geometry_and_npc(self):
  self.world['maps'][0]['name']='Another XP map'
  self.world['npcs'][0]['name']='새 안내인'
  self.build()
  actual=json.loads((self.output/'server/data/npcs.json').read_text(encoding='utf-8'))
  self.assertEqual(actual[0]['name'],'새 안내인')

 def test_nested_output_is_rejected(self):
  self.output=self.source/'nested'
  with self.assertRaises(ValueError):self.build()
  self.assertFalse(self.output.exists())

 def test_converted_utf16_ini_is_supported(self):
  path=self.source/'Game.ini';text=path.read_text(encoding='utf-8');path.write_text(text,encoding='utf-16')
  self.build()
  self.assertTrue((self.output/'client/Game.ini').is_file())

 def test_custom_main_is_not_silently_replaced(self):
  path=self.source/'Data/Scripts.rxdata';entries=read(path.read_bytes())
  path.write_bytes(write(entries,{1:b'puts "custom startup"'}))
  with self.assertRaises(ValueError):self.build()
  self.assertFalse(self.output.exists())

 def test_existing_online_script_name_is_rejected_without_output(self):
  path=self.source/'Data/Scripts.rxdata'
  path.write_bytes(path.read_bytes().replace(string(b'Game_Temp'),string(b'MMO_Network'),1))
  with self.assertRaisesRegex(ValueError,'Online script names already exist'):self.build()
  self.assertFalse(self.output.exists())

 @unittest.skipUnless((ROOT/'build/runtime-native/bin/Release/rgssxp-ruby.exe').exists(),'Build the pinned Ruby helper first')
 def test_inventory_mouse_selection_use_and_empty_bag(self):
  source="""
module Lunetile
 module UIInput
  def self.keys=(v); @keys=v; end
  def self.key_trigger?(v); (@keys||[]).include?(v); end
 end
end
load 'example/client/mmo_inventory.rb'
scene=LunetileMMO::Scene.allocate
scene.instance_variable_set(:@inventory_index,0)
used=[]
scene.define_singleton_method(:use_item) { |id| used << id }
state={'inventory'=>{'potion'=>2,'badge'=>1},'items'=>[{'id'=>'potion','heal'=>30},{'id'=>'badge','heal'=>0}]}
scene.inventory_click(state,75,80)
scene.inventory_click(state,260,330)
raise 'wrong selected item' unless used==['badge']
scene.inventory_click(state,17,80)
scene.inventory_click(state,260,330)
raise 'mouse use failed' unless used==['badge','potion']
state['inventory']={};scene.inventory_click(state,260,330)
raise 'empty bag used an item' unless used.size==2
"""
  result=subprocess.run([str(ROOT/'build/runtime-native/bin/Release/rgssxp-ruby.exe'),'--disable-gems','-e',source],cwd=ROOT,capture_output=True,text=True,encoding='utf-8',timeout=10)
  self.assertEqual(result.returncode,0,result.stdout+result.stderr)
