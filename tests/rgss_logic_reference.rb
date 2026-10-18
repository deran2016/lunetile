# Own deterministic logic probe, shared unchanged by Ruby 1.8 and 4. No rendering or audio oracle.
module Kernel
  def rand(limit=0)
    size=limit.to_i
    size>0 ? size*37/100 : 0.37
  end
  private :rand
end
module Input
  class << self
    def dir4;0;end
    def trigger?(key);false;end
    def press?(key);false;end
  end
end
%w[Actors Classes Skills Items Weapons Armors Enemies Troops States Animations Tilesets CommonEvents System].each do |name|
  eval('$data_'+name.gsub(/([a-z])([A-Z])/,'\\1_\\2').downcase+' = load_data("Data/'+name+'.rxdata")')
end
def logic_command(code,parameters=[],indent=0)
  RPG::EventCommand.new(code,indent,parameters)
end
def logic_event(id,x,y,trigger,variable)
  event=RPG::Event.new(x,y);event.id=id
  page=event.pages.first;page.trigger=trigger;page.graphic.character_name='Own fixture'
  page.list=[logic_command(122,[variable,variable,1,0,1]),logic_command(0)]
  event
end
unless File.exist?('Data/logic-fixtures-created.txt')
  map=load_data('Data/Map001.rxdata');map.width=20;map.height=15;map.data=Table.new(20,15,3)
  20.times { |x| 15.times { |y| map.data[x,y,0]=384 } };map.data[7,6,0]=385
  map.events={1=>logic_event(1,3,3,1,1),2=>logic_event(2,5,5,4,2),3=>logic_event(3,10,10,3,3),4=>logic_event(4,2,4,0,4)}
  parallel=map.events[2].pages.first.list;parallel.insert(1,logic_command(106,[2]))
  automatic=map.events[3].pages.first
  automatic.condition.switch1_valid=true;automatic.condition.switch1_id=5
  automatic.list.insert(1,logic_command(121,[5,5,1]))
  save_data(map,'Data/Map001.rxdata')
  other=Marshal.load(Marshal.dump(map));other.events={};save_data(other,'Data/Map002.rxdata')
  tilesets=load_data('Data/Tilesets.rxdata');tileset=tilesets[map.tileset_id]
  tileset.passages[384]=0;tileset.priorities[384]=0;tileset.terrain_tags[384]=0
  tileset.passages[385]=15;tileset.priorities[385]=0;tileset.terrain_tags[385]=0
  save_data(tilesets,'Data/Tilesets.rxdata')
  File.open('Data/logic-fixtures-created.txt','w'){|file|file.write('Own content, original Marshal bytes')}
end
$data_tilesets=load_data('Data/Tilesets.rxdata')
$game_temp=Game_Temp.new;$game_system=Game_System.new
$game_switches=Game_Switches.new;$game_variables=Game_Variables.new;$game_self_switches=Game_SelfSwitches.new
$game_screen=Game_Screen.new;$game_actors=Game_Actors.new;$game_party=Game_Party.new;$game_troop=Game_Troop.new
$game_map=Game_Map.new;$game_player=Game_Player.new;$game_party.setup_starting_members
$data_common_events=[nil]
Graphics.frame_rate=40;Graphics.frame_count=0
$game_map.setup(1);$game_player.moveto(2,3);$game_player.refresh
def logic_tick
  $game_system.map_interpreter.update;$game_map.update;$game_player.update;$game_system.update;$game_screen.update
  Graphics.frame_count+=1
end
File.open('types-reference.txt','w') do |out|
  $game_player.move_right
  out.puts("contact_started\t#{[$game_player.x,$game_player.y,$game_map.events[1].starting].inspect}")
  8.times { logic_tick }
  raise 'Contact or parallel fixture did not execute' unless $game_variables[1]==1 && $game_variables[2]>0
  out.puts("contact_result\t#{[$game_variables[1],$game_variables[2]].inspect}")
  $game_player.turn_down;$game_player.check_event_trigger_there([0])
  8.times { logic_tick }
  raise 'Decision fixture did not execute' unless $game_variables[4]==1
  out.puts("decision_result\t#{$game_variables[4]}")
  $game_switches[5]=true;$game_map.need_refresh=true
  12.times { logic_tick }
  raise 'Autorun fixture did not finish' unless $game_variables[3]==1 && !$game_switches[5]
  out.puts("autorun_result\t#{[$game_variables[3],$game_switches[5]].inspect}")
  $game_player.moveto(6,6);$game_player.move_right
  raise 'Blocked fixture tile was passable' unless [$game_player.x,$game_player.y]==[6,6]
  out.puts("blocked_tile\t#{[$game_player.x,$game_player.y].inspect}")
  $game_player.instance_variable_set('@through',true);$game_player.move_right
  raise 'Through fixture did not move' unless [$game_player.x,$game_player.y]==[7,6]
  out.puts("through_tile\t#{[$game_player.x,$game_player.y].inspect}")
  $game_player.instance_variable_set('@through',false);$game_player.moveto(1,1)
  route=RPG::MoveRoute.new;route.repeat=false
  route.list=[RPG::MoveCommand.new(37),RPG::MoveCommand.new(3),RPG::MoveCommand.new(14,[1,-1]),RPG::MoveCommand.new(38),RPG::MoveCommand.new]
  event=$game_map.events[1];event.force_move_route(route);jumped=false
  120.times do |index|
    logic_tick;jumped=true if event.jumping?
    out.puts("forced_route_#{index}\t#{[event.x,event.y,event.moving?,event.jumping?,event.move_route_forcing].inspect}") if index%10==0
  end
  raise 'Forced route did not jump or finish' unless jumped && !event.move_route_forcing && event.x==5 && event.y==2
  $game_system.timer=2;$game_system.timer_working=true;$game_temp.in_battle=true
  3.times { $game_system.update }
  raise 'Timer did not expire' unless $game_system.timer==0
  out.puts("timer_state\t#{[$game_system.timer,$game_temp.battle_abort].inspect}")
  $game_temp.in_battle=false;$game_temp.battle_abort=false
  $game_screen.start_tone_change(Tone.new(20,-10,30,40),4)
  $game_screen.start_flash(Color.new(200,100,50,160),4);$game_screen.start_shake(3,4,4);$game_screen.weather(1,3,4)
  6.times do |index|
    $game_screen.update;tone=$game_screen.tone
    out.puts("screen_#{index}\t#{[tone.red,tone.green,tone.blue,tone.gray,$game_screen.flash_color.alpha,$game_screen.shake,$game_screen.weather_type,$game_screen.weather_max].inspect}")
  end
  $game_map.setup(2);$game_player.moveto(10,7)
  out.puts("map_setup\t#{[$game_map.map_id,$game_player.x,$game_player.y,$game_map.events.size].inspect}")
  $game_troop.setup(1);actor=$game_party.actors.first;enemy=$game_troop.enemies.first
  raise 'Combat fixture is empty' unless actor && enemy
  $game_temp.in_battle=true
  6.times do |index|
    $game_temp.battle_turn=index+1;enemy.make_action
    action=enemy.current_action
    out.puts("enemy_action_#{index}\t#{[action.kind,action.basic,action.skill_id,action.target_index].inspect}")
    enemy.recover_all;enemy.attack_effect(actor)
    out.puts("actor_attack_#{index}\t#{[enemy.hp,enemy.damage,enemy.states].inspect}")
    enemy.recover_all;actor.recover_all;actor.attack_effect(enemy)
    out.puts("enemy_attack_#{index}\t#{[actor.hp,actor.damage,actor.states].inspect}")
    scene=Scene_Battle.new;scene.make_action_orders
    order=scene.instance_variable_get('@action_battlers').collect { |battler| [battler.is_a?(Game_Actor) ? 'actor' : 'enemy',battler.index,battler.current_action.speed] }
    out.puts("battle_order_#{index}\t#{order.inspect}")
  end
  members=$data_troops[1].members
  $data_troops[1].members=Array.new(8){members.first.dup};$game_troop.setup(1)
  ($game_party.actors+$game_troop.enemies).each { |battler| battler.instance_variable_set('@agi_plus',999) }
  scene=Scene_Battle.new;scene.make_action_orders
  order=scene.instance_variable_get('@action_battlers').collect { |battler| [battler.is_a?(Game_Actor) ? 'actor' : 'enemy',battler.index,battler.current_action.speed] }
  raise 'Tied-speed fixture did not create twelve equal actions' unless order.size==12 && order.collect { |row| row[2] }.uniq.size==1
  out.puts("tied_battle_order\t#{order.inspect}")
  enemy=$game_troop.enemies.first;actor.recover_all
  skill=$data_skills.compact.find { |item| item.scope==1 && item.power>0 }
  raise 'No damage skill in stock fixture' unless skill
  enemy.recover_all;enemy.skill_effect(actor,skill)
  out.puts("skill_result\t#{[skill.id,enemy.hp,enemy.damage,enemy.states].inspect}")
  item=$data_items.compact.find { |entry| entry.scope==3 && entry.recover_hp>0 }
  raise 'No recovery item in stock fixture' unless item
  actor.hp=actor.maxhp/2;actor.item_effect(item)
  out.puts("item_result\t#{[item.id,actor.hp,actor.damage,actor.states].inspect}")
  state=$data_states.compact.find { |entry| entry.slip_damage }
  raise 'No slip state in stock fixture' unless state
  actor.recover_all;actor.add_state(state.id);actor.slip_damage_effect;actor.remove_states_auto
  out.puts("state_result\t#{[state.id,actor.hp,actor.damage,actor.states].inspect}")
end
