import subprocess,unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
RUBY=ROOT/'build/runtime-native/bin/Release/rgssxp-ruby.exe'

@unittest.skipUnless(RUBY.exists(),'Build the pinned Ruby helper first')
@unittest.skipUnless((ROOT/'example/server/data/particles.json').is_file(),'Local MMO particle database is excluded from Git')
class MMOParticleTests(unittest.TestCase):
 def ruby(self,body):
  setup="""# encoding: UTF-8
require 'json'
Color=Struct.new(:r,:g,:b,:a)
class Bitmap
 attr_reader :disposed
 @@count=0
 def initialize(*);@@count+=1;end
 def fill_rect(*);end
 def dispose;@disposed=true;end
 def self.count;@@count;end
end
class Sprite
 attr_accessor :bitmap,:visible,:ox,:oy,:blend_type,:z,:angle,:x,:y,:zoom_x,:zoom_y,:opacity,:color
 attr_reader :disposed
 @@count=0
 def initialize;@@count+=1;end
 def dispose;@disposed=true;end
 def self.count;@@count;end
end
module Graphics
 def self.width;1280;end
 def self.height;720;end
end
module LunetileMMO
 def self.now;$clock||0.0;end
end
$game_map=Struct.new(:display_x,:display_y).new(0,0)
load 'example/client/mmo_particles.rb'
definitions=JSON.parse(File.read('example/server/data/particles.json'))
system=LunetileMMO::ParticleSystem.new;system.configure(definitions)
"""
  result=subprocess.run([str(RUBY),'--disable-gems','-'],input=setup+body,cwd=ROOT,text=True,encoding='utf-8',capture_output=True,timeout=10)
  self.assertEqual(result.returncode,0,result.stdout+result.stderr)

 def test_presets_are_deterministic_camera_relative_and_spawn_at_their_real_position(self):
  self.ruby("""
other=LunetileMMO::ParticleSystem.new;other.configure(definitions)
%w[fire light water].each{|name|[system,other].each{|s|raise unless s.emit(name,{'x'=>8,'y'=>7},direction:6,seed:17)}}
$clock=0.2;system.update;other.update
signature=->(s){s.instance_variable_get(:@active).map{|p|[p.x,p.y,p.vx,p.vy,p.life,p.sprite.x,p.sprite.y,p.sprite.color]}}
raise 'clients differ with the same seed' unless signature.call(system)==signature.call(other)
raise 'new particles flashed at origin' unless system.instance_variable_get(:@active).all?{|p|p.sprite.x>150&&p.sprite.y>100}
particle=system.instance_variable_get(:@active).first;before=[particle.sprite.x,particle.sprite.y]
$game_map.display_x=128;$game_map.display_y=64;system.update
raise 'camera changed particle physics' unless particle.sprite.x==before[0]-32 && particle.sprite.y==before[1]-16
raise 'presets did not emit' unless system.stats[:by_preset].keys.sort==%w[fire light water]
system.dispose;other.dispose
""")

 def test_pool_limits_clear_reuse_and_dispose_do_not_allocate_per_particle_bitmaps(self):
  self.ruby("""
bitmaps=Bitmap.count;raise 'unused pool allocated sprites' unless Sprite.count==0
map=$game_map;$game_map=nil;system.update;$game_map=map
stress=Marshal.load(Marshal.dump(definitions.first));stress['id']='stress';stress['layers']=Array.new(4){l=Marshal.load(Marshal.dump(stress['layers'][0]));l['count']=24;l['emit_ms']=0;l['delay_ms']=0;l}
system.configure([stress]);30.times{system.emit('stress',{'x'=>8,'y'=>7},seed:1)};system.update
raise 'particle or emitter limit exceeded' unless system.stats[:active]<=160 && system.stats[:emitters]<=24 && system.stats[:dropped]>0
sprites=Sprite.count
raise 'pool exceeded its sprite budget' unless sprites<=160 && Bitmap.count==bitmaps
$clock=5;system.update;raise 'expired particles retained' unless system.stats[:active]==0 && system.stats[:free]==160
system.emit('stress',{'x'=>8,'y'=>7},seed:1);system.update;raise 'pool was not reused' unless system.stats[:active]>0 && Sprite.count==sprites
system.clear;raise 'map clear leaked particles' unless system.stats[:active]==0 && system.stats[:free]==160 && system.stats[:emitters]==0
system.dispose;system.dispose;system.clear
raise 'owned resources leaked' unless system.instance_variable_get(:@all).all?{|p|!p.sprite || p.sprite.disposed} && system.instance_variable_get(:@textures).values.all?(&:disposed)
raise 'disposed system emitted' if system.emit('stress',{'x'=>8,'y'=>7})
""")

 def test_malformed_presets_are_rejected_and_mutable_callers_cannot_change_cached_layers(self):
  self.ruby("""
bad_cases=[['count',49],['shape','../file'],['life_ms',[0,100]],['size',[0,1]],['colors',[[999,0,0]]],['gravity',[Float::INFINITY,0]],['blend',2]]
bad_cases.each do |key,value|
 bad=Marshal.load(Marshal.dump(definitions));bad[0]['layers'][0][key]=value
 raise 'bad definition accepted' if LunetileMMO::ParticleSystem.valid?(bad)
 begin;system.configure(bad);raise 'bad preset configured';rescue RuntimeError=>e;raise unless e.message.include?('파티클 JSON');end
end
long_id=Marshal.load(Marshal.dump(definitions));long_id[0]['id']='a'*48
raise 'server-compatible ID rejected' unless LunetileMMO::ParticleSystem.valid?(long_id)
long_id[0]['id']+='a';raise 'oversized ID accepted' if LunetileMMO::ParticleSystem.valid?(long_id)
system.configure(definitions);definitions[0]['layers'][0]['speed'][0]=9999
raise 'caller mutated internal layers' if system.instance_variable_get(:@presets)['fire'][0]['speed'][0]==9999
raise 'unknown preset emitted' if system.emit('unknown',{'x'=>0,'y'=>0})
raise 'nonfinite position emitted' if system.emit('light',{'x'=>Float::INFINITY,'y'=>0})
system.dispose
""")
