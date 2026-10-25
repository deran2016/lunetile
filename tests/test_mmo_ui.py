import subprocess,unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
RUBY=ROOT/'build/runtime-native/bin/Release/rgssxp-ruby.exe'

@unittest.skipUnless(RUBY.exists(),'Build the Ruby helper first')
class MMOUITests(unittest.TestCase):
 def run_ruby(self,body):
  setup="""# encoding: UTF-8
Color=Struct.new(:r,:g,:b,:a)
module Graphics
 def self.width;1280;end
 def self.height;720;end
end
module Lunetile
 module UIInput
  class << self
   attr_accessor :keys,:held,:typing,:value,:ime,:pointer,:press_pointer,:wheel,:clicked,:right_clicked
   def key_trigger?(k);(@keys||[]).include?(k);end
   def key_press?(k);(@held||[]).include?(k);end
   def direction4;0;end
   def direction_trigger;0;end
   def mouse_position;@pointer;end
   def mouse_press_position;@press_pointer;end
   def mouse_trigger?(button);button==:right ? !!@right_clicked : @clicked!=false;end
   def wheel_delta;@wheel||0;end
   def text_input=(v);@typing=v;end
   def text;s=@value||'';@value='';s;end
   def composition;@ime||'';end
   def composing?;!composition.empty?;end
  end
 end
end
load 'example/client/mmo_hud.rb'
load 'example/client/mmo_chat.rb'
load 'example/client/mmo_combat.rb'
load 'example/client/mmo_ui.rb'
load 'example/client/mmo_windows.rb'
scene=LunetileMMO::Scene.allocate
messages=[]
connection=Object.new
connection.define_singleton_method(:send_message){|message|messages<<message}
connection.define_singleton_method(:id){'player'}
scene.instance_variable_set(:@connection,connection)
scene.instance_variable_set(:@messages,[])
scene.instance_variable_set(:@draft,'')
scene.instance_variable_set(:@chat_scroll,0)
module LunetileMMO
 def self.now;$combat_clock||1.0;end
end
scene.define_singleton_method(:physical_attack_down?){|k|Lunetile::UIInput.key_press?(k)}
scene.define_singleton_method(:combat_active?){@fake_active!=false}
"""
  result=subprocess.run([str(RUBY),'--disable-gems','-'],input=setup+body,cwd=ROOT,capture_output=True,text=True,encoding='utf-8',timeout=10)
  self.assertEqual(result.returncode,0,result.stdout+result.stderr)

 def test_chat_blocks_gameplay_and_composition_enter_does_not_send(self):
  self.run_ruby("""
scene.chat_focus(true)
Lunetile::UIInput.keys=[:z,:x,:right,:enter]
Lunetile::UIInput.value='안녕'
Lunetile::UIInput.ime='하'
scene.handle_input({})
raise 'composition enter sent or attacked' unless messages.empty?
raise 'committed text was lost' unless scene.instance_variable_get(:@draft)=='안녕'
Lunetile::UIInput.ime='';Lunetile::UIInput.keys=[:enter]
scene.handle_input({})
raise 'chat sent more than once' unless messages==[{'type'=>'chat','text'=>'안녕'}]
raise 'chat focus did not close' if Lunetile::UIInput.typing
""")

 def test_input_gates_clear_reserved_direction_and_old_dll_is_explained(self):
  self.run_ruby("""
scene.instance_variable_set(:@direction_buffer,[6,1.0]);scene.chat_focus(true)
raise 'chat retained direction' if scene.instance_variable_get(:@direction_buffer)
scene.chat_focus(false);scene.instance_variable_set(:@direction_buffer,[4,1.0])
scene.instance_variable_set(:@fake_active,false);scene.handle_input({})
raise 'focus loss retained direction' if scene.instance_variable_get(:@direction_buffer)
class << Lunetile::UIInput;undef_method :direction_trigger;end
begin
 LunetileMMO::Scene.new({})
 raise 'old DLL was accepted'
rescue RuntimeError=>e
 raise unless e.message.include?('Lunetile.dll') && e.message.include?('Scripts.rxdata')
end
""")

 def test_chat_length_cancel_and_backspace(self):
  self.run_ruby("""
scene.chat_focus(true);Lunetile::UIInput.value='가'*101;Lunetile::UIInput.keys=[]
scene.handle_chat
raise 'Unicode limit was not applied' unless scene.instance_variable_get(:@draft).size==100
Lunetile::UIInput.keys=[:backspace];scene.handle_chat
raise 'backspace split a character' unless scene.instance_variable_get(:@draft)=='가'*99
Lunetile::UIInput.value='ㄱ';Lunetile::UIInput.keys=[:escape];scene.handle_chat
raise 'cancel sent a message' unless messages.empty?
raise 'IME cancel committed its result' unless scene.instance_variable_get(:@draft)=='가'*99
""")

 def test_server_events_are_shown_once(self):
  self.run_ruby("""
scene.instance_variable_set(:@event_seq,0)
state={'event_seq'=>2,'events'=>[{'seq'=>1,'kind'=>'experience','amount'=>7},{'seq'=>2,'kind'=>'level_up','level'=>2}]}
2.times {scene.receive_events(state)}
raise 'events displayed repeatedly' unless scene.instance_variable_get(:@messages).size==2
""")

 def test_fast_drag_uses_press_position_and_clamps_window(self):
  self.run_ruby("""
Fake=Struct.new(:x,:y,:width,:height,:visible) do
 def hit?(px,py);visible&&px>=x&&py>=y&&px<x+width&&py<y+height;end
 def move(px,py);self.x=[[px,0].max,1280-width].min;self.y=[[py,0].max,720-height].min;end
end
panels={};[:menu,:dialogue,:character,:bag,:target,:map,:chat,:status].each{|k|panels[k]=Fake.new(882,218,382,366,k==:bag)}
scene.instance_variable_set(:@panels,panels);scene.instance_variable_set(:@inventory_open,true)
Lunetile::UIInput.pointer=[700,120];Lunetile::UIInput.press_pointer=[950,232]
scene.handle_mouse({})
raise 'fast drag lost its original position' unless [panels[:bag].x,panels[:bag].y]==[632,106]
panels[:bag].move(-100,1000)
raise 'window escaped the screen' unless [panels[:bag].x,panels[:bag].y]==[0,354]
""")

 def test_particle_cast_and_explosion_follow_deduplicated_server_events(self):
  self.run_ruby("""
emissions=[];particles=Object.new;particles.define_singleton_method(:emit){|name,position,**options|emissions<<[name,position,options]}
scene.instance_variable_set(:@particles,particles);scene.instance_variable_set(:@event_seq,0)
scene.instance_variable_set(:@effect_counts,{'attack'=>0});scene.instance_variable_set(:@sprites,{})
scene.define_singleton_method(:spawn_combat_effect){|*|}
position={'x'=>9,'y'=>7}
events=[{'seq'=>1,'kind'=>'attack','particles'=>'light','source'=>'player','position'=>position,'direction'=>6,'motion'=>'magic','motion_ms'=>360,'range'=>3},
 {'seq'=>2,'kind'=>'explosion','id'=>1,'particles'=>'fire','position'=>position,'radius'=>1}]
state={'event_seq'=>2,'events'=>events}
2.times{scene.receive_events(state)}
raise 'particles duplicated or missing' unless emissions.map(&:first)==['light','fire'] && emissions.map{|e|e[2][:seed]}==[1,2]
""")

 def test_level_up_has_one_field_notification(self):
  self.run_ruby("""
module LunetileMMO
 def self.now;1.0;end
end
class Sprite
 attr_accessor :z,:bitmap
end
class Bitmap
 attr_reader :font,:text
 def initialize(*);@font=Struct.new(:name,:size,:bold,:color).new;end
 def draw_text(*args);@text=args[-2];end
end
scene.instance_variable_set(:@event_seq,0)
scene.instance_variable_set(:@avatars,{'player'=>Struct.new(:real_x,:real_y).new(256,512)})
scene.instance_variable_set(:@floats,[])
state={'event_seq'=>1,'events'=>[{'seq'=>1,'kind'=>'level_up','level'=>2}]}
2.times {scene.receive_events(state)}
floats=scene.instance_variable_get(:@floats)
raise 'missing or duplicated level notification' unless floats.size==1 && floats[0][0].bitmap.text=='LEVEL UP!  Lv.2'
""")

 def test_hold_repeats_with_skill_priority_and_release_rearm(self):
  self.run_ruby("""
state={'self'=>{'hp'=>100,'mp'=>50,'direction'=>6},'skills'=>[{'id'=>'basic','mp_cost'=>0,'cooldown_ms'=>600},{'id'=>'burst','mp_cost'=>10,'cooldown_ms'=>1200}],'cooldowns'=>{}}
connection.define_singleton_method(:state){state}
Lunetile::UIInput.held=[:z,:x];$combat_clock=1.0
scene.repeat_combat;scene.repeat_combat
raise 'priority or duplicate send' unless messages.size==1 && messages.last['skill_id']=='burst' && !messages.last.key?('target_id')
$combat_clock=2.19;scene.repeat_combat;raise 'cooldown bypass' unless messages.size==1
$combat_clock=2.2;scene.repeat_combat;raise 'hold did not repeat' unless messages.size==2
scene.suspend_combat;$combat_clock=5;scene.repeat_combat;raise 'held key rearmed after interruption' unless messages.size==2
Lunetile::UIInput.held=[];scene.repeat_combat;Lunetile::UIInput.held=[:z];scene.repeat_combat
raise 'release did not rearm' unless messages.size==3 && messages.last['skill_id']=='basic'
$combat_clock=20;scene.repeat_combat;raise 'late frame burst' unless messages.size==4
""")

 def test_text_focus_and_resource_gates_never_cast(self):
  self.run_ruby("""
state={'self'=>{'hp'=>100,'mp'=>0,'direction'=>4},'skills'=>[{'id'=>'burst','mp_cost'=>10,'cooldown_ms'=>1200}],'cooldowns'=>{}}
connection.define_singleton_method(:state){state}
2.times {scene.attack('burst')}
raise 'insufficient MP cast or spammed notice' unless messages.empty? && scene.instance_variable_get(:@messages).size==1
state['self']['mp']=50;scene.instance_variable_set(:@form,{value:''});scene.attack('burst')
raise 'cast through text entry' unless messages.empty?
scene.instance_variable_set(:@form,nil);scene.instance_variable_set(:@fake_active,false)
Lunetile::UIInput.held=[:x];scene.handle_input(state);scene.instance_variable_set(:@fake_active,true);scene.repeat_combat
raise 'focus regain resumed a held key' unless messages.empty?
Lunetile::UIInput.held=[];scene.repeat_combat;Lunetile::UIInput.held=[:x];scene.repeat_combat
raise 'new key did not attack' unless messages.last['direction']==4
""")

 def test_attack_flushes_actual_movement_before_the_attack_request(self):
  self.run_ruby("""
state={'self'=>{'hp'=>100,'mp'=>50,'direction'=>6},'skills'=>[{'id'=>'basic','mp_cost'=>0,'cooldown_ms'=>600}],'cooldowns'=>{}}
connection.define_singleton_method(:state){state}
avatar=Object.new;avatar.define_singleton_method(:flush){|c,force|raise unless force;c.send_message({'type'=>'move'})}
scene.instance_variable_set(:@avatars,{'player'=>avatar})
scene.attack('basic');raise 'attack used stale coordinates' unless messages.map{|m|m['type']}==['move','attack']
""")

 def test_compact_quickslots_share_draw_bounds_and_ignore_gaps(self):
  self.run_ruby("""
Rect=Struct.new(:x,:y,:width,:height)
FakePanel=Struct.new(:x,:y,:width,:height,:visible) do
 def hit?(px,py);visible && px>=x && py>=y && px<x+width && py<y+height;end
end
panels={};[:menu,:dialogue,:character,:bag,:target,:map,:chat].each{|k|panels[k]=FakePanel.new(0,0,1,1,false)}
panels[:status]=FakePanel.new(16,656,1116,48,true);panels[:quicks]=FakePanel.new(1048,16,216,100,true);scene.instance_variable_set(:@panels,panels)
state={'self'=>{'hp'=>100},'skills'=>[{'id'=>'basic'},{'id'=>'burst'}],'items'=>[{'id'=>'potion'},{'id'=>'mana_potion'}]}
connection.define_singleton_method(:state){state}
actions=[];scene.define_singleton_method(:attack){|id|actions<<id};scene.define_singleton_method(:use_item){|id|actions<<id}
8.times do |i|
 r=scene.quickslot_rect(i);raise 'slot escaped panel' unless r.y==8+i/4*44 && r.width==40 && r.height==40 && r.x+40<=216 && r.y+40<=100
 raise 'slot spacing changed' if i%4>0 && r.x-scene.quickslot_rect(i-1).x!=44
 Lunetile::UIInput.pointer=Lunetile::UIInput.press_pointer=[1048+r.x+20,16+r.y+20];scene.handle_mouse(state)
end
raise 'wrong quickslot actions' unless actions==['basic','burst','potion','mana_potion']
r=scene.quickslot_rect(0)
[[r.x+40,20],[r.x+20,7],[r.x+20,48],[4,20]].each do |x,y|
 Lunetile::UIInput.pointer=Lunetile::UIInput.press_pointer=[1048+x,16+y];scene.handle_mouse(state)
end
raise 'padding or gap activated a slot' unless actions.size==4
cleared=[];scene.define_singleton_method(:assign_quickslot){|i,*_|cleared<<i}
Lunetile::UIInput.clicked=false;Lunetile::UIInput.right_clicked=true
r=scene.quickslot_rect(2);Lunetile::UIInput.pointer=[1048+r.x+20,16+r.y+20];scene.handle_mouse(state)
raise 'right click cast instead of clearing' unless cleared==[2] && actions.size==4
""")

 def test_learned_skills_bind_to_all_eight_keys_and_keep_shared_cooldowns(self):
  self.run_ruby("""
state={'self'=>{'hp'=>100,'mp'=>50,'direction'=>6},'skills'=>[{'id'=>'basic','mp_cost'=>0,'cooldown_ms'=>600},{'id'=>'burst','mp_cost'=>10,'cooldown_ms'=>1200},{'id'=>'grenade','mp_cost'=>10,'cooldown_ms'=>2000}],
 'items'=>[{'id'=>'potion'},{'id'=>'mana_potion'}],'inventory'=>{'potion'=>3,'mana_potion'=>3},'cooldowns'=>{},
 'progress'=>{'skills'=>{'burst'=>1,'grenade'=>1,'passive'=>1}},'progression'=>{'skills'=>[{'id'=>'burst','passive'=>false},{'id'=>'grenade','passive'=>false},{'id'=>'passive','passive'=>true}]}}
bindings=LunetileMMO.default_quickslots(state);saved=0
connection.define_singleton_method(:state){state}
connection.define_singleton_method(:quickslots){bindings}
connection.define_singleton_method(:save_quickslots){|slots|bindings=slots;saved+=1}
raise unless scene.assign_quickslot(1,'burst') && scene.assign_quickslot(2,'grenade')
Lunetile::UIInput.held=[];scene.repeat_combat
Lunetile::UIInput.held=[:x];$combat_clock=1.0;scene.repeat_combat
Lunetile::UIInput.held=[:v];$combat_clock=1.1;scene.repeat_combat
raise 'different keys lost a skill' unless messages.map{|m|m['skill_id']}==['burst','grenade']
raise unless scene.assign_quickslot(2,'burst')
scene.repeat_combat;raise 'rebind resumed held key' unless messages.size==2
Lunetile::UIInput.held=[];scene.repeat_combat
Lunetile::UIInput.held=[:v];$combat_clock=1.2;scene.repeat_combat
raise 'duplicate slot bypassed skill cooldown' unless messages.size==2
LunetileMMO::QUICK_KEYS.each_with_index do |key,i|
 raise 'slot assignment failed' unless scene.assign_quickslot(i,'grenade')
 Lunetile::UIInput.held=[];scene.repeat_combat
 Lunetile::UIInput.held=[key];$combat_clock=5+i*2.1;scene.repeat_combat
 raise 'mapped key cast wrong action' unless messages.size==3+i && messages.last['skill_id']=='grenade'
end
count=saved
raise if scene.assign_quickslot(2,'passive') || scene.assign_quickslot(2,'unknown') || scene.assign_quickslot(8,'burst')
raise 'invalid binding was saved' unless saved==count
raise unless scene.assign_quickslot(2) && bindings[2].nil?
Lunetile::UIInput.held=[];scene.repeat_combat
Lunetile::UIInput.held=[:v];$combat_clock=100;scene.repeat_combat
raise 'empty slot still attacked' unless messages.size==10
scene.chat_focus(true);scene.use_quickslot(1);raise 'click bypassed chat focus' unless messages.size==10
""")

 def test_profile_quickslots_survive_reconnect_and_failed_write_preserves_layout(self):
  self.run_ruby("""
require 'json';load 'example/client/mmo_network.rb'
Dir.mkdir(dir="build/quickslots-#{Process.pid}")
begin
 path=File.join(dir,'player.json');File.write(path,'CREDENTIALS_PRESERVED')
 make=->(id){c=LunetileMMO::Connection.allocate;c.instance_variable_set(:@profile_path,path);c.instance_variable_set(:@id,id);c.instance_variable_set(:@state,{'progress'=>{'quick_skill'=>'burst'}});c}
 c=make.call('player');layout=c.quickslots;layout[2]='skill:grenade';layout[7]='skill:burst';c.save_quickslots(layout)
 settings=path.sub('.json','.quicks.json');before=File.binread(settings)
 raise 'reconnect lost mapping' unless make.call('player').quickslots==layout
 raise 'another account inherited mapping' unless make.call('other').quickslots[2].nil?
 c=make.call('player');old=c.quickslots.dup;scene.instance_variable_set(:@connection,c)
 Dir.mkdir(settings+'.tmp')
 raise 'failed save accepted' if scene.save_quickslot_layout(Array.new(8))
 raise 'failed write changed layout or file' unless c.quickslots==old && File.binread(settings)==before
 Dir.rmdir(settings+'.tmp')
 [[],Array.new(7),Array.new(8,'bad:burst'),Array.new(8,1)].each{|bad|raise 'bad shape accepted' if c.valid_quickslots?(bad)}
 File.write(settings,JSON.generate({'id'=>'player','slots'=>['skill:burst']}))
 begin;make.call('player').quickslots;raise 'bad file accepted';rescue RuntimeError=>e;raise unless e.message.include?('퀵슬롯 설정');end
 File.write(settings,'x'*4097)
 begin;make.call('player').quickslots;raise 'oversized file accepted';rescue RuntimeError=>e;raise unless e.message.include?('너무 큽니다');end
 raise 'credential file changed' unless File.read(path)=='CREDENTIALS_PRESERVED'
ensure
 Dir.children(dir).each{|name|p=File.join(dir,name);File.directory?(p) ? Dir.rmdir(p) : File.delete(p)};Dir.rmdir(dir)
end
""")

 def test_skill_row_drag_copies_only_learned_active_skill_without_casting(self):
  self.run_ruby((ROOT/'tests/mmo_drag_fixture.rb').read_text(encoding='utf-8')+"""
scene.list_window(:skills,[['burst','Burst','burst'],['grenade','Grenade','grenade']],[]){}
u.pointer=u.press_pointer=[480,200];u.held=[:left_mouse];u.clicked=false
scene.window_click(:skills,20,90)
raise 'skill row did not start pending drag' unless scene.instance_variable_get(:@quick_drag)[:binding]=='skill:grenade'
move.call(point_for.call(2));drag=scene.instance_variable_get(:@quick_drag);cursor=drag[:cursor];target=drag[:target]
raise 'preview missing or saved early' unless drag[:active] && target.visible && [target.x,target.y]==[1158,24] && writes.empty?
release.call(point_for.call(2))
raise 'drop did not copy the skill' unless layout[1,2]==['skill:burst','skill:grenade'] && writes.size==1 && messages.empty?
raise 'drag resources leaked' unless cursor.disposed && target.disposed && target.bitmap.disposed && !cursor.bitmap.disposed
['passive','unknown'].each{|id|scene.begin_skill_drag(id);raise 'invalid skill drag began' if scene.instance_variable_get(:@quick_drag)}
raise 'shared cache disposed' if RPG::Cache.icons.any?(&:disposed)
""")

 def test_slot_drag_swaps_moves_to_empty_and_clicks_only_on_release(self):
  self.run_ruby((ROOT/'tests/mmo_drag_fixture.rb').read_text(encoding='utf-8')+"""
layout[2]='skill:grenade';press.call(1)
raise 'mouse down cast before drag decision' unless messages.empty?
move.call(point_for.call(2));release.call(point_for.call(2))
raise 'occupied slots did not swap' unless layout[1,2]==['skill:grenade','skill:burst'] && writes.size==1 && messages.empty?
press.call(0);move.call(point_for.call(3));release.call(point_for.call(3))
raise 'move to empty lost binding' unless layout[0].nil? && layout[3]=='skill:basic'
press.call(4);move.call(point_for.call(5));release.call(point_for.call(5))
raise 'item swap lost potion' unless layout[4,2]==['item:mana_potion','item:potion']
press.call(3);release.call(point_for.call(3))
raise 'click was not one release cast' unless messages.size==1 && messages[0]['skill_id']=='basic'
press.call(2);move.call([point_for.call(2)[0]+7,point_for.call(2)[1]]);release.call(point_for.call(2))
raise 'drag back to source cast or saved' unless messages.size==1 && writes.size==3
# A complete press/move/release between updates still uses the latched press point.
u.press_pointer=point_for.call(2);u.pointer=point_for.call(6);u.held=[];u.clicked=true;scene.handle_mouse(state)
raise 'fast gesture was read as destination click' unless layout[2].nil? && layout[6]=='skill:burst' && messages.size==1
""")

 @unittest.skipUnless(all((ROOT/f'example/server/data/{name}.json').is_file() for name in ('skills','progression')),'Local MMO skill database is excluded from Git')
 def test_elemental_skill_definitions_drag_to_distinct_slots_and_cast_their_own_ids(self):
  self.run_ruby((ROOT/'tests/mmo_drag_fixture.rb').read_text(encoding='utf-8')+"""
require 'json'
state['skills']=JSON.parse(File.read('example/server/data/skills.json'))
state['progression']=JSON.parse(File.read('example/server/data/progression.json'))
ids=%w[fire_wave light_wave water_wave]
ids.each{|id|scene.begin_skill_drag(id);raise 'unlearned elemental skill dragged' if scene.instance_variable_get(:@quick_drag)}
ids.each{|id|state['progress']['skills'][id]=1}
rows=state['progression']['skills'].map{|rule|d=state['skills'].find{|s|s['id']==rule['id']};[rule['id'],d['name'],d['icon']]}
scene.list_window(:skills,rows,[]){}
ids.each_with_index do |id,i|
 index=rows.index{|r|r[0]==id};raise 'elemental skill hidden on later page' unless index<7
 u.pointer=u.press_pointer=[480,110+48+index*34+15];u.held=[:left_mouse];u.clicked=false
 scene.window_click(:skills,30,48+index*34+15)
 move.call(point_for.call(i+1));release.call(point_for.call(i+1))
 raise 'wrong dragged binding' unless layout[i+1]=="skill:#{id}"
end
raise 'drag cast or failed to save' unless messages.empty? && writes.size==3
3.times{|i|scene.use_quickslot(i+1)}
raise 'slots did not cast separately' unless messages.map{|m|m['skill_id']}==ids
raise 'shared icon disposed' if RPG::Cache.icons.any?(&:disposed)
""")

 def test_drag_cancellation_occlusion_stale_source_and_save_failure_preserve_layout(self):
  self.run_ruby((ROOT/'tests/mmo_drag_fixture.rb').read_text(encoding='utf-8')+"""
before=layout.dup
press.call(1);move.call([900,50]);release.call([900,50]);raise unless layout==before && writes.empty? && messages.empty?
press.call(1);move.call(point_for.call(2));u.keys=[:escape];scene.handle_input(state);u.keys=[]
raise 'Escape closed source window or retained drag' unless panels[:skills].visible && !scene.instance_variable_get(:@quick_drag)
press.call(1);move.call(point_for.call(2));u.right_clicked=true;scene.handle_mouse(state);u.right_clicked=false
raise 'right cancel changed layout' unless layout==before && writes.empty?
press.call(1);move.call(point_for.call(2));scene.instance_variable_set(:@fake_active,false);scene.handle_input(state);scene.instance_variable_set(:@fake_active,true)
raise 'focus loss retained drag' if scene.instance_variable_get(:@quick_drag)
press.call(1);move.call(point_for.call(2));scene.close_window(:skills);panels[:skills].visible=true
raise 'window close retained drag' if scene.instance_variable_get(:@quick_drag)
press.call(1);move.call(point_for.call(2));state['self']['hp']=0;release.call(point_for.call(2));state['self']['hp']=100
raise 'death allowed drop' unless layout==before && writes.empty?
press.call(1);move.call(nil);release.call(nil)
raise 'outside release retained drag' if scene.instance_variable_get(:@quick_drag)
press.call(1);move.call(point_for.call(2));panels[:cover]=DragPanel.new(1048,16,216,100,true);scene.instance_variable_get(:@panel_order)<<:cover
release.call(point_for.call(2));panels[:cover].visible=false
raise 'drop went through covering window' unless layout==before && writes.empty?
press.call(1);move.call(point_for.call(2));layout[1]='skill:grenade';release.call(point_for.call(2))
raise 'stale source was moved' unless layout[1]=='skill:grenade' && layout[2].nil? && writes.empty?
layout=before.dup;fail_save=true;press.call(1);move.call(point_for.call(2));release.call(point_for.call(2))
raise 'failed save changed layout or leaked gesture' unless layout==before && writes.empty? && !scene.instance_variable_get(:@quick_drag)
raise 'cancelled gestures cast' unless messages.empty?
raise 'shared cache disposed' if RPG::Cache.icons.any?(&:disposed)
""")

 def test_chat_caret_tracks_the_repositioned_panel(self):
  self.run_ruby("""
Rect=Struct.new(:x,:y,:width,:height)
class << Lunetile::UIInput
 attr_accessor :caret_rect
 def ime_open?;false;end
end
painter=Object.new;painter.define_singleton_method(:width){420};painter.define_singleton_method(:label){|*_|};painter.define_singleton_method(:bar){|*_|}
panel=Object.new;panel.define_singleton_method(:x){16};panel.define_singleton_method(:y){452}
panel.define_singleton_method(:redraw){|_,&block|block.call(painter)}
scene.instance_variable_set(:@panels,{chat:panel});scene.instance_variable_set(:@chat_scroll,0)
scene.instance_variable_set(:@draft,'안녕');scene.chat_focus(true);scene.draw_chat
r=Lunetile::UIInput.caret_rect
raise 'IME remained at the old chat position' unless [r.x,r.y,r.width,r.height]==[58,612,1,22]
""")

 def test_hover_focus_leaves_foreground_opaque_and_keeps_chat_drag_focus(self):
  self.run_ruby("""
FakePanel=Struct.new(:x,:y,:width,:height,:visible,:alpha) do
 def hit?(px,py);visible && px>=x && py>=y && px<x+width && py<y+height;end
end
panels={chat:FakePanel.new(0,0,100,100,true),map:FakePanel.new(200,0,100,100,true),skills:FakePanel.new(0,0,100,100,true)}
scene.instance_variable_set(:@panels,panels);scene.instance_variable_set(:@panel_order,panels.keys)
Lunetile::UIInput.pointer=[20,20];scene.update_window_focus
raise 'topmost hover did not win' unless panels[:skills].alpha==238&&panels[:chat].alpha==144&&panels[:map].alpha==144
scene.instance_variable_set(:@chat_open,true);scene.update_window_focus;raise unless panels[:chat].alpha==208
scene.instance_variable_set(:@drag,[:map,0,0]);scene.update_window_focus;raise unless panels[:map].alpha==208
scene.instance_variable_set(:@fake_active,false);scene.update_window_focus;raise unless panels.values.all?{|p|p.alpha==144}
""")

 def test_invite_notice_once_and_repeated_command_notices_after_empty_state(self):
  self.run_ruby("""
scene.instance_variable_set(:@seen_chat,0)
s={'chat'=>[],'notice'=>'저장 완료','social'=>{'online'=>[{'id'=>'other','name'=>'친구'}],'invite'=>{'sender'=>'other','kind'=>'party_invite'}}}
scene.receive_chat(s);scene.receive_chat(s);raise unless scene.instance_variable_get(:@messages).size==2
s['notice']='';scene.receive_chat(s);s['notice']='저장 완료';scene.receive_chat(s);raise unless scene.instance_variable_get(:@messages).size==3
""")

 def test_chat_scrollbar_wheel_drag_bounds_and_new_messages_keep_history(self):
  self.run_ruby("""
PanelFixture=Struct.new(:x,:y,:width,:height,:visible) do
 def hit?(px,py);visible&&px>=x&&py>=y&&px<x+width&&py<y+height;end
end
chat=PanelFixture.new(0,0,420,190,true);scene.instance_variable_set(:@panels,{chat:chat})
20.times{|n|scene.push_message(n.to_s)}
Lunetile::UIInput.pointer=[406,80];Lunetile::UIInput.clicked=false;Lunetile::UIInput.wheel=2
scene.handle_chat_scroll;raise 'wheel not applied' unless scene.instance_variable_get(:@chat_scroll)==4
lines=scene.chat_lines;old=lines[0...lines.size-4].last(6)
scene.push_message('new '*15);lines=scene.chat_lines;offset=scene.instance_variable_get(:@chat_scroll)
raise 'new message jumped to bottom' unless lines[0...lines.size-offset].last(6)==old
Lunetile::UIInput.wheel=0;Lunetile::UIInput.clicked=true;Lunetile::UIInput.held=[:left_mouse]
top,height=scene.chat_scroll_thumb;Lunetile::UIInput.pointer=Lunetile::UIInput.press_pointer=[406,top+3];scene.handle_chat_scroll
Lunetile::UIInput.clicked=false;Lunetile::UIInput.pointer=[406,-200];scene.handle_chat_scroll
raise 'drag did not reach history start' unless scene.instance_variable_get(:@chat_scroll)==scene.chat_max_scroll
Lunetile::UIInput.pointer=[406,500];scene.handle_chat_scroll;raise 'drag did not reach latest' unless scene.instance_variable_get(:@chat_scroll)==0
Lunetile::UIInput.held=[];scene.handle_chat_scroll;raise 'drag not released' if scene.instance_variable_get(:@chat_drag_offset)
scene.instance_variable_set(:@messages,[]);scene.instance_variable_set(:@chat_scroll,99);scene.chat_scroll_thumb
raise 'empty chat overflow' unless scene.instance_variable_get(:@chat_scroll)==0
""")

 def test_nonmodal_windows_allow_motion_and_attacks_without_bag_arrow_navigation(self):
  self.run_ruby("""
PanelFixture=Struct.new(:x,:y,:width,:height,:visible,:z) do
 def hit?(px,py);visible&&px>=x&&py>=y&&px<x+width&&py<y+height;end
end
panels={};(scene.popup_keys+[:status,:quicks,:chat,:map,:menu_button]).each{|k|panels[k]=PanelFixture.new(0,0,100,100,false)}
[:bag,:skills,:dialogue,:menu].each{|k|panels[k].visible=true};panels[:chat].x=200
scene.instance_variable_set(:@panels,panels);scene.instance_variable_set(:@panel_order,panels.keys)
scene.instance_variable_set(:@inventory_open,true);scene.instance_variable_set(:@inventory_index,2);scene.instance_variable_set(:@avatars,{})
state={'self'=>{'hp'=>100,'mp'=>50,'direction'=>6},'skills'=>[{'id'=>'basic','mp_cost'=>0,'cooldown_ms'=>600}],'cooldowns'=>{},'monsters'=>[]}
connection.define_singleton_method(:state){state}
scene.define_singleton_method(:movement_input){[6,1.0]};moves=[];scene.define_singleton_method(:handle_movement){|input|moves<<input}
Lunetile::UIInput.held=[:z];Lunetile::UIInput.keys=[:right];Lunetile::UIInput.clicked=false;Lunetile::UIInput.pointer=[20,20]
scene.handle_input(state)
raise 'popup stopped movement' unless moves==[[6,1.0]]
raise 'popup stopped attack' unless messages.last['type']=='attack'
raise 'arrow moved inventory selection' unless scene.instance_variable_get(:@inventory_index)==2
scene.instance_variable_set(:@combat_blocked,{z:false,x:false});scene.open_window(:launcher)
raise 'opening menu interrupted attack' unless scene.instance_variable_get(:@combat_blocked)=={z:false,x:false}
raise 'dropup did not open' unless panels[:launcher].visible
scene.open_window(:skills);raise 'dropup stayed over selection' if panels[:launcher].visible
""")

 def test_self_hits_select_nearest_living_target_and_other_players_do_not_steal_it(self):
  self.run_ruby("""
scene.instance_variable_set(:@event_seq,0);scene.instance_variable_set(:@avatars,{});scene.instance_variable_set(:@floats,[])
monsters=[{'id'=>'far','hp'=>20,'position'=>{'x'=>13,'y'=>7}},{'id'=>'near','hp'=>10,'position'=>{'x'=>10,'y'=>7}}]
hit=->(seq,target,source){ {'seq'=>seq,'kind'=>'damage','monster'=>true,'source'=>source,'target'=>target,'amount'=>10} }
s={'self'=>{'position'=>{'x'=>9,'y'=>7}},'monsters'=>monsters,'event_seq'=>2,'events'=>[hit.call(1,'far','player'),hit.call(2,'near','player')]}
scene.receive_events(s);raise 'auto target not nearest' unless scene.instance_variable_get(:@target_id)=='near'
s['events']=[hit.call(3,'far','other')];s['event_seq']=3;scene.receive_events(s)
raise 'another player stole HP panel' unless scene.instance_variable_get(:@target_id)=='near'
s['events']=[hit.call(4,'far','player')];s['event_seq']=4;scene.receive_events(s)
raise 'new hit did not change HP panel' unless scene.instance_variable_get(:@target_id)=='far'
s['events']=[hit.call(5,'far','player')];s['event_seq']=5;s['monsters']=[];scene.receive_events(s)
raise 'dead target stayed selected' if scene.instance_variable_get(:@target_id)
scene.receive_events(s);raise 'duplicate hit reselected' if scene.instance_variable_get(:@target_id)
""")

 def test_names_have_a_complete_eight_neighbor_outline(self):
  self.run_ruby("""
bitmap=Object.new;font=Struct.new(:color).new;calls=[]
bitmap.define_singleton_method(:font){font};bitmap.define_singleton_method(:draw_text){|*args|calls<<[args,font.color]}
LunetileMMO::Theme.outlined_text(bitmap,2,2,176,24,'마을 안내인',LunetileMMO::Theme::GOLD,1)
raise 'outline incomplete' unless calls.size==9 && calls[0...-1].map{|args,_|args[0,2]}.sort==([1,2,3].product([1,2,3])-[[2,2]]).sort
raise 'outline not black' unless calls[0...-1].all?{|_,c|[c.r,c.g,c.b]==[0,0,0]}
raise 'text color changed' unless calls.last[0][0,2]==[2,2]&&calls.last[1]==LunetileMMO::Theme::GOLD
""")

 def test_throw_arc_starts_at_character_and_lands_after_400ms_in_every_direction(self):
  self.run_ruby("""
[[-3,0],[3,0],[0,-3],[0,3]].each do |dx,dy|
 d={'position'=>{'x'=>9,'y'=>7},'target'=>{'x'=>9+dx,'y'=>7+dy},'flight_ms'=>400}
 a=scene.projectile_pose(d,0);b=scene.projectile_pose(d,200);c=scene.projectile_pose(d,400);late=scene.projectile_pose(d,1000)
 raise 'throw start changed' unless a==[9.0,7.0,16.0]
 raise 'not an arc' unless b[2]>a[2]&&b[0,2]==[9+dx/2.0,7+dy/2.0]
 raise 'throw missed target or continued moving' unless c==[9+dx.to_f,7+dy.to_f,0.0]&&late==c
end
""")

 def test_projectile_sync_does_not_restart_flight_and_disposes_only_owned_warning(self):
  self.run_ruby("""
$combat_clock=1.0
class Bitmap
 attr_reader :width,:height
 def initialize(w,h);@width,@height=w,h;@disposed=false;end
 def fill_rect(*);end
 def dispose;@disposed=true;end
 def disposed?;@disposed;end
end
class Sprite
 attr_accessor :bitmap,:ox,:oy,:z
 def initialize(*);@disposed=false;end
 def dispose;@disposed=true;end
 def disposed?;@disposed;end
end
module RPG;module Cache;def self.icon(*);@icon||=Bitmap.new(24,24);end;end;end
scene.instance_variable_set(:@throw_effects,{})
d={'id'=>8,'position'=>{'x'=>9,'y'=>7},'target'=>{'x'=>12,'y'=>7},'flight_ms'=>400,'elapsed_ms'=>200,'radius'=>1,'icon'=>'032-Item01','cells'=>[{'x'=>12,'y'=>7}]}
scene.sync_projectiles({'projectiles'=>[d]});effect=scene.instance_variable_get(:@throw_effects)[8];first=effect[:began];marker=effect[:marker];icon=effect[:sprite].bitmap
$combat_clock=1.1;d['elapsed_ms']=200;scene.sync_projectiles({'projectiles'=>[d]})
raise 'flight rewound or restarted' unless effect[:began]==first
raise 'warning is not 3x3 tiles' unless [marker.bitmap.width,marker.bitmap.height]==[96,96]
scene.sync_projectiles({'projectiles'=>[]})
raise 'warning leaked' unless marker.disposed?&&marker.bitmap.disposed?&&effect[:sprite].disposed?
raise 'shared RTP icon was disposed' if icon.disposed?
""")
