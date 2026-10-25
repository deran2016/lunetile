import subprocess,unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
RUBY=ROOT/'build/runtime-native/bin/Release/rgssxp-ruby.exe'

@unittest.skipUnless(RUBY.exists(),'Build the pinned Ruby helper first')
class MMOAppearanceTests(unittest.TestCase):
 def ruby(self,body):
  setup="""
Rect=Struct.new(:x,:y,:width,:height) do
 def set(*v);self.x,self.y,self.width,self.height=v;end
end
class Sprite
 attr_accessor :bitmap,:x,:y,:z,:ox,:oy,:angle,:zoom_x,:zoom_y,:opacity,:visible,:src_rect
 attr_reader :viewport,:disposed
 def initialize(viewport=nil);@viewport=viewport;@visible=true;@opacity=255;@src_rect=Rect.new;end
 def dispose;@disposed=true;end
end
class Sprite_Character < Sprite
 def initialize(viewport,character);super(viewport);@character=character;@cw,@ch=character.name=='Lunetile_Portal' ? [313,313] : [32,48];update;end
 def update;self.x=100;self.y=200;self.z=230;self.src_rect.set(@character.pattern*@cw,(@character.direction-2)/2*@ch,@cw,@ch);end
end
class Game_Character;end
module RPG
 module Cache
  def self.icon(id);(@icons||={})[id]||=Struct.new(:width,:height,:disposed).new(24,24,false);end
 end
end
module LunetileMMO
 def self.now;$clock||0;end
end
load 'example/client/mmo_character.rb';load 'example/client/mmo_windows.rb'
actor=Struct.new(:name,:direction,:pattern).new('001-Fighter01',2,1)
state={'progression'=>{'equipment'=>[{'id'=>'weapon_1','slot'=>'weapon','icon'=>'001-Weapon01'},{'id'=>'weapon_2','slot'=>'weapon','icon'=>'002-Weapon02'}]}}
sprite=LunetileMMO::CombatCharacter.new(:field,actor)
"""
  r=subprocess.run([str(RUBY),'--disable-gems','-'],input=setup+body,cwd=ROOT,text=True,encoding='utf-8',capture_output=True,timeout=10)
  self.assertEqual(r.returncode,0,r.stdout+r.stderr)

 def test_weapon_tracks_four_hands_changes_icon_and_disposes_only_sprite(self):
  self.ruby("""
sprite.appearance({'weapon'=>'weapon_1'},state);sprite.update
weapon=sprite.instance_variable_get(:@held_weapon);icon=weapon.bitmap
raise unless weapon.viewport==:field && weapon.ox==18 && weapon.oy==18
[2,4,6,8].each do |d|
 actor.direction=d;sprite.update
 raise 'weapon on wrong hand side' unless [4,8].include?(d) ? weapon.x<sprite.x : weapon.x>sprite.x
 raise 'weapon not attached to arm height' unless weapon.y.between?(sprite.y-20,sprite.y-14)
 raise 'up-facing weapon not behind body' unless weapon.z==sprite.z+(d==8 ? -1 : 1)
end
actor.pattern=0;sprite.update;y=weapon.y;actor.pattern=2;sprite.update;raise 'walking hand did not move' unless weapon.y!=y
sprite.appearance({'weapon'=>'weapon_2'},state);raise 'wrong equipped icon' unless weapon.bitmap==RPG::Cache.icon('002-Weapon02') && !icon.disposed
sprite.appearance({},state);raise 'unequip retained weapon' unless weapon.disposed && sprite.instance_variable_get(:@held_weapon).nil?
sprite.appearance({'weapon'=>'weapon_1'},state);held=sprite.instance_variable_get(:@held_weapon);sprite.dispose
raise 'shared icon disposed or sprite leaked' unless held.disposed && !icon.disposed && sprite.disposed
""")

 def test_attack_weapon_rotates_then_returns_without_moving_server_character(self):
  self.ruby("""
sprite.appearance({'weapon'=>'weapon_1'},state);actor.direction=6;sprite.update;weapon=sprite.instance_variable_get(:@held_weapon);rest=weapon.angle
sprite.attack_motion({'direction'=>6,'motion'=>'slash','motion_ms'=>240});$clock=0.05;sprite.update;first=weapon.angle
$clock=0.18;sprite.update;raise 'swing did not rotate' unless weapon.angle!=first && weapon.angle!=rest
raise 'server avatar was changed' unless actor.direction==6 && actor.pattern==1
$clock=0.25;sprite.update;raise 'weapon failed to return to hand' unless weapon.angle==rest && weapon.x>sprite.x
sprite.attack_motion({'direction'=>2,'motion'=>'magic','motion_ms'=>360});$clock=0.4;sprite.update
raise 'skill casting hand is stationary' unless weapon.y<sprite.y-17
""")

 def test_portal_uses_new_sheet_four_phases_and_fixed_foot_anchor(self):
  self.ruby("""
scene=LunetileMMO::Scene.allocate
entities=scene.portal_entities({'self'=>{'position'=>{'map_id'=>1}},'services'=>{'portals'=>[{'id'=>'gate','name'=>'Gate','level'=>1,'from'=>{'map_id'=>1,'x'=>2,'y'=>3}}]}})
data=entities[0][1];raise unless data['character']=='Lunetile_Portal' && data['portal']
portal=LunetileMMO::CombatCharacter.new(:field,Struct.new(:name,:direction,:pattern).new('Lunetile_Portal',2,1));portal.appearance(data,state)
frames=[];anchors=[]
[0,0.21,0.41,0.61,0.81].each{|t|$clock=t;portal.update;frames<<portal.src_rect.x;anchors<<[portal.x,portal.y,portal.ox,portal.oy,portal.zoom_x]}
raise 'portal phases do not loop' unless frames==[0,313,626,939,0]
raise 'portal anchor moved' unless anchors.uniq.size==1 && (portal.zoom_x*313-72).abs<0.001
portal.dispose
""")
