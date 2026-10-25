import subprocess,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
RUBY=ROOT/'build/runtime-native/bin/Release/rgssxp-ruby.exe'
@unittest.skipUnless(RUBY.exists(),'Build the Ruby helper first')
class CatalogTests(unittest.TestCase):
 def test_catalog_is_required_cached_and_replaced_only_by_a_new_welcome(self):
  script="""# encoding: UTF-8
require 'json'
load 'example/client/mmo_network.rb'
dir=File.expand_path("build/catalog-#{Process.pid}");Dir.mkdir(dir);previous=Dir.pwd
begin
 Dir.chdir(dir)
 c=LunetileMMO::Connection.allocate;c.instance_variable_set(:@profile_path,File.join(dir,'p.json'));c.instance_variable_set(:@states,[])
 state={'type'=>'state','move_ack'=>{'seq'=>0,'accepted'=>false},'self'=>{'hp'=>10}}
 begin;c.receive(state);raise 'state before catalog accepted';rescue RuntimeError=>e;raise unless e.message.include?('서버 정의');end
 catalog={'items'=>[],'skills'=>[{'id'=>'fire_wave'}],'progression'=>{},'services'=>{},'particle_presets'=>[]}
 welcome={'type'=>'welcome','protocol'=>11,'id'=>'player','token'=>'token','catalog'=>catalog,'state'=>state}
 begin;c.receive(welcome.merge('protocol'=>8));raise 'old version accepted';rescue RuntimeError=>e;raise unless e.message.include?('Protocol 11');end
 begin;c.receive(welcome.merge('catalog'=>{}));raise 'bad catalog accepted';rescue RuntimeError=>e;raise unless e.message.include?('캐시 형식');end
 raise 'bad welcome overwrote credentials' if File.exist?(File.join(dir,'p.json'))
 c.receive(welcome);first=c.state;raise 'welcome missing catalog' unless first['skills'].equal?(catalog['skills'])
 c.receive(state.merge('self'=>{'hp'=>5}));raise 'state did not reuse cache' unless c.state['skills'].equal?(first['skills']) && first['self']['hp']==10 && c.state['self']['hp']==5
 new_catalog=catalog.merge('skills'=>[{'id'=>'water_wave'}]);c.receive(welcome.merge('catalog'=>new_catalog))
 raise 'stale catalog survived welcome' unless c.state['skills']==[{'id'=>'water_wave'}]
ensure
 Dir.chdir(previous);Dir.children(dir).each{|name|p=File.join(dir,name);File.directory?(p) ? Dir.rmdir(p) : File.delete(p)};Dir.rmdir(dir)
end
"""
  r=subprocess.run([str(RUBY),'--disable-gems','-'],input=script,cwd=ROOT,capture_output=True,text=True,encoding='utf-8',timeout=10)
  self.assertEqual(r.returncode,0,r.stdout+r.stderr)
