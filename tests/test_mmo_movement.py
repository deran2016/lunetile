import subprocess,sys,unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from rxdata import read
from migrate_project import transform

RUBY=ROOT/'build/runtime-native/bin/Release/rgssxp-ruby.exe'

@unittest.skipUnless(RUBY.exists(),'Build the pinned Ruby helper first')
class MMOMovementTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  entries=read((ROOT/'template-xp/Data/Scripts.rxdata').read_bytes())
  replacements,_=transform(entries,widescreen=True)
  cls.stock=b'\n'.join(replacements.get(i,e.source()) for i,e in enumerate(entries)
   if e.name in (b'Game_Character 1',b'Game_Character 2',b'Game_Character 3',b'Game_Player')).decode('utf-8')

 def ruby(self,source):
  setup="""# encoding: UTF-8

module Graphics
  def self.width; 1280; end
  def self.height; 720; end
  def self.logic_rate; 120; end
end
module Input
  A=1; C=2; X=3
  def self.trigger?(*); false; end
  def self.dir4; 0; end
end
module Lunetile
 module UIInput
  class << self
   attr_accessor :move_held,:move_tap
   def direction4;@move_held||0;end
   def direction_trigger;@move_tap||0;end
  end
 end
end
class Sprite_Character;end
$game_map=Struct.new(:width,:height,:display_x,:display_y,:encounter_step).new(40,23,0,0,30)
def $game_map.valid?(x,y); x.between?(0,width-1) && y.between?(0,height-1); end
def $game_map.map_id; 1; end
def data(x,y,direction=6)
  {'id'=>'player','character'=>'001-Fighter01','position'=>{'map_id'=>1,'x'=>x,'y'=>y},'direction'=>direction}
end
def snapshot(x,y,seq=0,accepted=false)
  {'self'=>data(x,y).merge('hp'=>100,'motion'=>{'x'=>x*1000,'y'=>y*1000,'epoch'=>0,'path'=>[]}),'move_ack'=>{'seq'=>seq,'accepted'=>accepted},'npcs'=>[],
   'navigation'=>{'map_id'=>1,'x'=>7,'y'=>5,'passages'=>Array.new(5){Array.new(5,0)}}}
end
"""
  modules="\nmodule LunetileMMO;def self.now;$clock || Process.clock_gettime(Process::CLOCK_MONOTONIC);end;end\nload 'example/client/mmo_character.rb'\nload 'example/client/mmo_inventory.rb'\nload 'example/client/mmo_ui.rb'\nload 'example/client/mmo_windows.rb'\n"
  result=subprocess.run([str(RUBY),'--disable-gems','-'],input=setup+self.stock+modules+source,cwd=ROOT,capture_output=True,text=True,encoding='utf-8',timeout=10)
  self.assertEqual(result.returncode,0,result.stdout+result.stderr)

 def test_retarget_during_a_step_preserves_rendered_position(self):
  self.ruby("""
avatar=LunetileMMO::Avatar.new(data(9,7))
avatar.apply(data(10,7)); avatar.update
before=avatar.real_x
avatar.apply(data(11,7))
raise 'mid-step snapshot teleported the avatar' unless avatar.real_x==before && avatar.moving?
avatar.update
raise 'interpolation speed changed' unless avatar.real_x-before==16
raise 'walking animation was not resumed' unless avatar.instance_variable_get(:@stop_count)==0
""")

 def test_coalesced_positions_and_direction_reversal_do_not_snap(self):
  self.ruby("""
avatar=LunetileMMO::Avatar.new(data(9,7))
avatar.apply(data(12,7))
raise 'coalesced snapshot teleported' unless avatar.real_x==9*128
4.times { avatar.update }
before=avatar.real_x
avatar.apply(data(8,7,4))
raise 'direction reversal teleported' unless avatar.real_x==before
30.times do
  previous=avatar.real_x
  avatar.apply(data(8,7,4)); avatar.update
  raise 'exceeded stock per-tick motion' if (avatar.real_x-previous).abs>16
end
80.times { avatar.update }
raise 'did not settle on the server position' unless avatar.real_x==8*128 && !avatar.moving?
""")

 def test_camera_follows_interpolated_avatar(self):
  self.ruby("""
state={'self'=>data(9,12,2),'players'=>[data(9,12,2)],'npcs'=>[]}
avatar=LunetileMMO::Avatar.new(data(9,10,2))
connection=Object.new
connection.define_singleton_method(:update) {}
connection.define_singleton_method(:state) { state }
connection.define_singleton_method(:drain_states) { [state] }
connection.define_singleton_method(:id) { 'player' }
spriteset=Object.new; spriteset.define_singleton_method(:update) {}
spriteset.define_singleton_method(:appearance) { |*_| }
$game_player=Game_Player.new
scene=LunetileMMO::Scene.allocate
scene.instance_variable_set(:@connection,connection)
scene.instance_variable_set(:@map_id,1)
scene.instance_variable_set(:@avatars,{'player'=>avatar})
scene.instance_variable_set(:@sprites,{'player'=>spriteset})
scene.instance_variable_set(:@spriteset,spriteset)
scene.define_singleton_method(:draw_hud) {}
scene.define_singleton_method(:handle_input) { |_| }
20.times do
  previous=$game_map.display_y
  scene.update
  expected=[[avatar.real_y-(Graphics.height/2-16)*4,0].max,64].min
  raise 'camera followed a tile snapshot instead of the rendered avatar' unless $game_map.display_y==expected
  raise 'camera jumped' if ($game_map.display_y-previous).abs>16
end
""")

 def test_turns_wait_for_tile_center_and_duplicates_do_not_reset_animation(self):
  self.ruby("""
avatar=LunetileMMO::Avatar.new(data(9,7))
avatar.apply(data(10,7)); 3.times { avatar.update }
avatar.apply(data(10,8,2)); avatar.apply(data(9,8,4))
before=[avatar.real_x,avatar.real_y]
raise 'snapshot changed walking direction before the corner' unless avatar.direction==6
100.times do
  old=[avatar.real_x,avatar.real_y]
  avatar.apply(data(9,8,4)); avatar.update
  dx,dy=avatar.real_x-old[0],avatar.real_y-old[1]
  raise 'cut a corner diagonally' if dx!=0 && dy!=0
  raise 'turned away from a tile center' if dy!=0 && avatar.real_x%128!=0
end
raise 'lost queued reversal' unless [avatar.real_x,avatar.real_y]==[9*128,8*128]
stop_count=avatar.instance_variable_get(:@stop_count)
avatar.apply(data(9,8,4))
raise 'duplicate reset idle animation' unless avatar.instance_variable_get(:@stop_count)==stop_count
""")

 def test_network_keeps_coalesced_states_and_batches_poll_with_input(self):
  self.ruby("""
require 'json'
load 'example/client/mmo_network.rb'
module LunetileMMO
  def self.now; $clock; end
end
first={'type'=>'state','self'=>data(10,7),'notice'=>'','move_ack'=>{'seq'=>1,'accepted'=>true}}
second={'type'=>'state','self'=>data(10,8,2),'notice'=>'','move_ack'=>{'seq'=>1,'accepted'=>true}}
incoming=[first,second].map { |s| p=JSON.generate(s); [p.bytesize].pack('N')+p }.join
writes=[]
socket=Object.new
socket.define_singleton_method(:state) { :open }
socket.define_singleton_method(:read) { |_| bytes,incoming=incoming,nil; bytes }
socket.define_singleton_method(:write) { |bytes| writes << bytes }
connection=LunetileMMO::Connection.allocate
connection.instance_variable_set(:@catalog,{}) # These frames follow a completed v9 welcome.
{socket:socket,sent_login:true,buffer:''.b,outgoing:''.b,states:[],state:first,last_poll:0,last_response:0}.each do |key,value|
  connection.instance_variable_set(:"@#{key}",value)
end
$clock=0.11
connection.send_message({'type'=>'move','direction'=>6})
connection.update
raise 'coalesced states were lost or reordered' unless connection.drain_states==[first,second]
raise 'old states were applied twice' unless connection.drain_states.empty?
raise 'poll and input were written separately' unless writes.size==1
frame=writes.first;messages=[]
until frame.empty?
  size=frame.unpack1('N'); messages << JSON.parse(frame.byteslice(4,size)); frame=frame.byteslice(size+4..-1)
end
raise 'poll interval or command batch wrong' unless messages.map { |m| m['type'] }==['move','poll']
$clock=0.13; connection.update
raise 'polled faster than 30Hz' unless writes.size==1
connection.instance_variable_set(:@outgoing,'x'*65_536)
begin
  connection.send_message({'type'=>'poll'})
  raise 'unbounded outgoing buffer'
rescue RuntimeError => error
  raise unless error.message.encode('UTF-8').include?("\\uC1A1\\uC2E0 \\uBC84\\uD37C")
end
""")

 def test_explicit_respawn_discards_old_movement_targets(self):
  self.ruby("""
avatar=LunetileMMO::Avatar.new(data(9,7))
avatar.apply(data(10,7));avatar.update;avatar.apply(data(10,8,2))
avatar.reset_position({'x'=>1,'y'=>1})
avatar.apply(data(1,1));avatar.update
raise 'respawn continued an old path' unless [avatar.real_x,avatar.real_y]==[128,128] && !avatar.moving?
""")

 def test_network_rejects_future_or_regressing_acknowledgements(self):
  self.ruby("""
load 'example/client/mmo_network.rb'
c=LunetileMMO::Connection.allocate
c.instance_variable_set(:@catalog,{})
{states:[],move_seq:1,acked_move:0}.each{|key,value|c.instance_variable_set(:"@#{key}",value)}
s=snapshot(10,7,1,true).merge('type'=>'state','notice'=>'')
c.receive(s);c.receive(s)
raise 'duplicate ack lost state order' unless c.drain_states.size==2
[0,2].each do |seq|
 begin
  c.receive(snapshot(10,7,seq,true).merge('type'=>'state','notice'=>''))
  raise 'invalid ack was accepted'
 rescue RuntimeError=>e
  raise if e.message=='invalid ack was accepted'
 end
end
""")

 def test_mid_tile_turns_and_reversals_are_immediate_and_constant_speed(self):
  self.ruby("""
s=snapshot(9,7);a=LunetileMMO::LocalAvatar.new(s['self'])
[[6,35],[2,35],[4,35],[8,35]].each do |direction,ms|
 old=[a.real_x,a.real_y];raise unless a.advance(direction,s,ms)==:moved;a.update
 dx=a.real_x-old[0];dy=a.real_y-old[1]
 raise 'waited for a tile center' if dx==0 && dy==0
 raise 'diagonal movement' if dx!=0 && dy!=0
 raise 'speed changed' unless ((dx.abs+dy.abs)-35*0.64).abs<0.0001
 raise 'facing did not turn immediately' unless a.direction==direction
end
raise 'four directions lost distance' unless [a.real_x,a.real_y]==[9*128,7*128]
a.advance(6,s,40);old=a.real_x;a.advance(4,s,8)
raise 'reversal waited for center' unless a.real_x<old && a.real_x%128!=0
""")

 def test_input_changes_axis_in_the_same_logic_update_and_flushes_on_release(self):
  self.ruby("""
module LunetileMMO;def self.now;$clock;end;end
scene=LunetileMMO::Scene.allocate;s=snapshot(9,7);a=LunetileMMO::LocalAvatar.new(s['self']);messages=[]
c=Object.new;c.define_singleton_method(:id){'player'};c.define_singleton_method(:state){s}
c.define_singleton_method(:send_message){|m|messages<<m;messages.count{|p|p['type']=='move'}}
scene.instance_variable_set(:@connection,c);scene.instance_variable_set(:@avatars,{'player'=>a})
[6,2,4,8].each_with_index do |d,i|
 $clock=i/120.0;Lunetile::UIInput.move_held=d;Lunetile::UIInput.move_tap=d
 old=[a.real_x,a.real_y];scene.handle_movement
 raise 'turn waited' if old==[a.real_x,a.real_y]
 raise 'wrong direction' unless a.direction==d
end
raise 'sent frame-sized durable requests' unless messages.none?{|p|p['type']=='move'}
raise 'first observer preview missing' unless messages.first['type']=='preview'
$clock=0.04;Lunetile::UIInput.move_held=0;Lunetile::UIInput.move_tap=0;old=[a.real_x,a.real_y];scene.handle_movement
raise 'release continued movement' unless old==[a.real_x,a.real_y]
$clock=0.25;scene.handle_movement
raise 'short turn path was lost' unless messages.count{|p|p['type']=='move'}==1 && messages.last['parts'].map{|p|p['direction']}==[6,2,4,8]
""")

 def test_prediction_and_batched_ack_never_replay_approved_motion(self):
  self.ruby("""
s=snapshot(9,7);a=LunetileMMO::LocalAvatar.new(s['self']);messages=[]
c=Object.new;c.define_singleton_method(:send_message){|m|messages<<m;messages.count{|p|p['type']=='move'}}
a.advance(6,s,100);a.flush(c,true);before=[a.real_x,a.real_y]
raise 'waited for server' unless before==[9.5*128,7*128]
reply=snapshot(9,7,1,true);reply['self']['motion']['x']=9500;a.reconcile(reply)
20.times{a.update}
raise 'ack replayed or moved' unless before==[a.real_x,a.real_y] && a.pending_moves.empty?
raise 'fractional origin missing' unless messages.first['origin']==[9000,7000]
a.advance(2,s,100);a.flush(c,true)
raise 'next origin did not use acknowledged point' unless messages.last['origin']==[9500,7000]
""")

 def test_prediction_budget_is_distance_time_bounded_and_collision_does_not_delay_turn(self):
  self.ruby("""
s=snapshot(9,7);a=LunetileMMO::LocalAvatar.new(s['self'])
s['navigation']['passages'][2][3]=2
a.advance(6,s,100);raise 'crossed reverse passage' unless (a.real_x-9495*0.128).abs<0.0001
before=a.real_y;raise unless a.advance(2,s,8)==:moved
raise 'blocked direction delayed turn' unless a.real_y>before
a=LunetileMMO::LocalAvatar.new(s['self']);s['navigation']['passages'][2][3]=0
6.times{|i|raise unless a.advance(i.even? ? 6 : 4,s,100)==:moved}
raise 'unbounded speculative movement' unless a.advance(2,s,1)==:waiting
""")

 def test_collision_at_subtile_corners_npcs_map_edges_and_navigation_bounds(self):
  self.ruby("""
[1,2,3].each do |kind|
 s=snapshot(9,7);a=LunetileMMO::LocalAvatar.new(s['self'])
 s['navigation']['passages'][2][2]=4 if kind==1
 s['navigation']['passages'][2][3]=2 if kind==2
 s['npcs']=[{'position'=>{'x'=>10,'y'=>7}}] if kind==3
 a.advance(6,s,200);raise 'crossed collision' unless a.real_x<9.5*128
end
s=snapshot(9,7);s['navigation']['passages'][3][3]=15;a=LunetileMMO::LocalAvatar.new(s['self'])
a.advance(6,s,90);a.advance(2,s,90);a.advance(6,s,90);a.advance(2,s,90)
raise 'cut through a blocked corner' unless a.real_y<7.5*128
s=snapshot(9,7);s['navigation']['x']=10;a=LunetileMMO::LocalAvatar.new(s['self']);a.advance(4,s,200)
raise 'negative grid indexing escaped navigation' unless a.real_x>=8.5*128
""")

 def test_rejection_rolls_back_the_actual_turn_path_and_drains_inflight(self):
  self.ruby("""
s=snapshot(9,7);a=LunetileMMO::LocalAvatar.new(s['self']);seq=0
c=Object.new;c.define_singleton_method(:send_message){|m|seq+=1 if m['type']=='move'}
a.advance(6,s,100);a.flush(c,true);a.advance(2,s,100);a.flush(c,true)
before=[a.real_x,a.real_y];a.reconcile(snapshot(9,7,1,false))
raise 'rejection snapped' unless before==[a.real_x,a.real_y] && a.recovering?
raise 'predicted during recovery' unless a.advance(4,s,8)==:recovering
5.times{a.update};raise 'recovered before inflight drain' unless before==[a.real_x,a.real_y]
a.reconcile(snapshot(9,7,2,false))
100.times do
 old=[a.real_x,a.real_y];a.update;dx=a.real_x-old[0];dy=a.real_y-old[1]
 raise 'rollback shortcut' if dx!=0 && dy!=0
 raise 'rollback teleport' if [dx.abs,dy.abs].max>6
end
raise 'did not return to authority' unless [a.real_x,a.real_y]==[9*128,7*128] && !a.recovering?
""")

 def test_respawn_epoch_discards_inflight_and_preserves_new_fractional_position(self):
  self.ruby("""
s=snapshot(9,7);a=LunetileMMO::LocalAvatar.new(s['self']);c=Object.new;c.define_singleton_method(:send_message){|_|1}
a.advance(6,s,100);a.flush(c,true)
r=snapshot(1,1,1,false);r['self']['motion']['epoch']=1;a.reconcile(r);20.times{a.update}
raise 'respawn replayed old input' unless a.pending_moves.empty? && [a.real_x,a.real_y]==[128,128]
r['self']['hp']=0;raise unless a.advance(6,r,8)==:dead
""")

 def test_observer_uses_exact_subtile_turns_without_inventing_diagonal_paths(self):
  self.ruby("""
$clock=0;s=snapshot(9,7);a=LunetileMMO::Avatar.new(s['self'])
d=snapshot(9,7)['self'];d['motion']['path']=[{'seq'=>1,'x'=>9175,'y'=>7000},{'seq'=>2,'x'=>9175,'y'=>7175},{'seq'=>3,'x'=>9000,'y'=>7175}]
d['motion']['x']=9000;d['motion']['y']=7175;a.apply(d)
140.times do
 $clock+=1.0/120;old=[a.real_x,a.real_y];a.apply(d);a.update;dx=a.real_x-old[0];dy=a.real_y-old[1]
 raise 'observer cut corner' if dx!=0 && dy!=0
 raise 'observer snapped' if [dx.abs,dy.abs].max>6
end
raise 'observer lost turns' unless [a.real_x,a.real_y]==[9*128,7175*0.128]
""")

 def test_confirmed_history_stays_bounded_across_many_immediate_reversals(self):
  self.ruby("""
s=snapshot(9,7);a=LunetileMMO::LocalAvatar.new(s['self']);seq=0
c=Object.new;c.define_singleton_method(:send_message){|m|seq+=1 if m['type']=='move'}
200.times do |i|
 a.advance(i.even? ? 6 : 4,s,100);a.flush(c,true)
 point=a.instance_variable_get(:@trail).last
 r=snapshot(9,7,seq,true);r['self']['motion']['x'],r['self']['motion']['y']=point;a.reconcile(r)
 raise 'history leaked' if a.instance_variable_get(:@trail).size>2
end
""")


 def test_observer_starts_on_first_packet_and_predicts_only_short_validated_lead(self):
  self.ruby("""
$clock=0;s=snapshot(9,7);a=LunetileMMO::Avatar.new(s['self'])
d=s['self'].merge('relay'=>{'x'=>9200,'y'=>7000,'epoch'=>0,'direction'=>6,'moving'=>true,'lead_x'=>9500,'lead_y'=>7000,
 'path'=>[{'seq'=>1,'x'=>9000,'y'=>7000},{'seq'=>2,'x'=>9200,'y'=>7000}]})
a.apply(d);before=a.real_x;a.update
raise 'observer still buffers its first motion' unless a.real_x>before
100.times{$clock+=1.0/120;a.update}
raise 'unbounded dead reckoning' if a.real_x>9500*0.128+0.00001
raise 'moved after stale lead' if a.moving?
""")

 def test_observer_extrapolated_turn_stop_and_reversal_retrace_without_diagonals(self):
  self.ruby("""
[2,4,0].each do |direction|
 $clock=0;s=snapshot(9,7);a=LunetileMMO::Avatar.new(s['self'])
 r={'x'=>9200,'y'=>7000,'epoch'=>0,'direction'=>6,'moving'=>true,'lead_x'=>9500,'lead_y'=>7000,
  'path'=>[{'seq'=>1,'x'=>9000,'y'=>7000},{'seq'=>2,'x'=>9200,'y'=>7000}]}
 a.apply(s['self'].merge('relay'=>r));10.times{$clock+=1.0/120;a.update}
 target=direction==2 ? [9200,7200] : (direction==4 ? [9000,7000] : [9200,7000])
 r=r.merge('x'=>target[0],'y'=>target[1],'moving'=>false,'direction'=>direction==0 ? 6 : direction,
  'path'=>r['path']+(direction==0 ? [] : [{'seq'=>3,'x'=>target[0],'y'=>target[1]}]))
 a.apply(s['self'].merge('relay'=>r))
 80.times do
  $clock+=1.0/120;old=[a.real_x,a.real_y];a.update;dx=a.real_x-old[0];dy=a.real_y-old[1]
  raise 'remote corner teleport' if dx!=0 && dy!=0 || [dx.abs,dy.abs].max>6.00001
 end
 raise 'remote stop did not settle' unless (a.real_x-target[0]*0.128).abs<0.00001 && (a.real_y-target[1]*0.128).abs<0.00001
end
""")

 def test_observer_continuous_packets_have_no_waypoint_rounding_stalls(self):
  self.ruby("""
$clock=0;s=snapshot(9,7);a=LunetileMMO::Avatar.new(s['self']);x=9000;seq=0;stalls=0
120.times do |tick|
 if tick%4==0
  x+=165;seq+=1
  a.apply(s['self'].merge('relay'=>{'x'=>x,'y'=>7000,'epoch'=>0,'direction'=>6,'moving'=>true,'lead_x'=>x+300,'lead_y'=>7000,
   'path'=>[{'seq'=>seq,'x'=>x,'y'=>7000}]}))
 end
 old=a.real_x;a.update;stalls+=1 if a.real_x==old;$clock+=1.0/120
end
raise 'remote waypoint stalls' unless stalls==0
raise 'observer changed nominal speed' unless (a.real_x-9*128-640).abs<0.00001
""")

 def test_preview_uses_frame_steps_prunes_acks_and_precedes_durable_moves(self):
  self.ruby("""
$clock=0;s=snapshot(9,7);a=LunetileMMO::LocalAvatar.new(s['self']);messages=[];seq=0
c=Object.new;c.define_singleton_method(:send_message){|m|messages<<Marshal.load(Marshal.dump(m));seq+=1 if m['type']=='move'}
a.advance(6,s,8);a.preview(c,true);a.advance(2,s,8);a.flush(c,true)
raise 'latest route was not previewed before saving' unless messages.map{|m|m['type']}==['preview','preview','move']
raise 'lost per-frame step order' unless messages[1]['parts'].map{|p|p['step']}==[1,2]
r=snapshot(9,7,1,true);r['self']['motion']['x']=9040;r['self']['motion']['y']=7040;a.reconcile(r)
$clock=0.05;a.advance(4,s,8);a.preview(c,true)
raise 'replayed an acknowledged preview' unless messages.last['origin']==[9040,7040] && messages.last['parts'].map{|p|p['step']}==[3]
a.preview(c,false);$clock=0.1;a.preview(c,false)
raise 'release was not advertised' unless messages.last['moving']==false
""")

 def test_new_straight_packet_behind_extrapolation_never_walks_backwards(self):
  self.ruby("""
$clock=0;s=snapshot(9,7);a=LunetileMMO::Avatar.new(s['self'])
r={'x'=>9040,'y'=>7000,'epoch'=>0,'direction'=>6,'moving'=>true,'lead_x'=>9340,'lead_y'=>7000,'path'=>[{'seq'=>1,'x'=>9040,'y'=>7000}]}
a.apply(s['self'].merge('relay'=>r));8.times{$clock+=1.0/120;a.update}
r=r.merge('x'=>9165,'lead_x'=>9465,'path'=>[{'seq'=>2,'x'=>9165,'y'=>7000}]);old=a.real_x;a.apply(s['self'].merge('relay'=>r));a.update
raise 'rewound a continuing straight prediction' unless a.real_x>old
""")

 def test_portal_and_duplicate_respawn_keep_connection_ack_and_discard_old_requests(self):
  self.ruby("""
s=snapshot(9,7);a=LunetileMMO::LocalAvatar.new(s['self']);seq=0
connection=Object.new;connection.define_singleton_method(:send_message){|m|m['type']=='move' ? (seq+=1) : nil}
a.advance(6,s,20);a.flush(connection,true)
t=snapshot(9.1,7,1,true);a.reconcile(t)
a.advance(2,t,20);a.flush(connection,true)
portal=snapshot(3,14,1,true);portal['self']['position']['map_id']=2;portal['self']['motion']['epoch']=1
# A respawn event and the epoch can both reset the avatar before an old request ACK arrives.
a.reset_position(portal['self']['position']);a.reconcile(portal)
portal['move_ack']={'seq'=>2,'accepted'=>false};a.reconcile(portal)
raise 'old map prediction leaked' unless a.pending_moves.empty? && a.destination==[3.0,14.0] && !a.recovering?
portal['move_ack']={'seq'=>3,'accepted'=>true}
begin;a.reconcile(portal);raise 'invented ack accepted';rescue RuntimeError=>e;raise if e.message=='invented ack accepted';end
""")
