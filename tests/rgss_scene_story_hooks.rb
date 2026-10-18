# Own hooks shared by Ruby 1.8 and 4; actual default scene code remains unchanged.
$scene_counter_trace=[]
class << Graphics
  alias rgssxp_scene_graphics_base update
  def update
    before=frame_count
    ScenarioDriver.step
    rgssxp_scene_graphics_base
    $scene_counter_trace << ['update',ScenarioDriver.instance_variable_get('@tick'),before,frame_count]
  end
  alias rgssxp_scene_transition_base transition
  def transition(*args)
    before=frame_count
    result=rgssxp_scene_transition_base(*args)
    $scene_counter_trace << ['transition',ScenarioDriver.instance_variable_get('@tick'),args,before,frame_count]
    result
  end
  alias rgssxp_scene_reset_base frame_reset
  def frame_reset
    before=frame_count
    result=rgssxp_scene_reset_base
    $scene_counter_trace << ['reset',ScenarioDriver.instance_variable_get('@tick'),before,frame_count]
    result
  end
  alias rgssxp_scene_set_count_base frame_count=
  def frame_count=(value)
    before=frame_count
    result=rgssxp_scene_set_count_base(value)
    $scene_counter_trace << ['set',ScenarioDriver.instance_variable_get('@tick'),value,before,frame_count]
    result
  end
end
class << Input
  def trigger?(key)
    key == ScenarioDriver.button
  end
  def repeat?(key);key == ScenarioDriver.button;end
  def press?(key);false;end
  def dir4;0;end
  def dir8;0;end
end
class << ScenarioDriver
  alias rgssxp_scene_story_base story_step
  def story_step
    if $scene.is_a?(Scene_Gameover)
      @fixture_returning=true
      confirm if @tick%8==0
    elsif @fixture_returning
      if $scene.is_a?(Scene_Title) && $scene.instance_variable_get('@command_window')
        select(0)
      elsif $scene.is_a?(Scene_Map)
        $game_switches[2]=true;$game_map.need_refresh=true;@fixture_returning=false
      end
    else
      rgssxp_scene_story_base
    end
  end
end
module Kernel
  def rand(limit=0)
    size=limit.to_i
    size>0 ? size*37/100 : 0.37
  end
  private :rand
end
class Scene_Battle
  alias rgssxp_scene_action_base make_basic_action_result
  alias rgssxp_scene_battle_end_base battle_end
  def make_basic_action_result
    actors=$game_party.actors.collect { |actor| actor.hp }
    enemies=$game_troop.enemies.collect { |enemy| enemy.hp }
    rgssxp_scene_action_base
    @fixture_enemy_actions=(@fixture_enemy_actions || 0)+1 if @active_battler.is_a?(Game_Enemy) && @active_battler.current_action.basic==0
    @fixture_actor_damage=(@fixture_actor_damage || 0)+actors.zip($game_party.actors).collect { |pair| [pair[0]-pair[1].hp,0].max }.inject(0) { |sum,value| sum+value }
    @fixture_enemy_damage=(@fixture_enemy_damage || 0)+enemies.zip($game_troop.enemies).collect { |pair| [pair[0]-pair[1].hp,0].max }.inject(0) { |sum,value| sum+value }
  end
  def battle_end(result)
    values=[['turns',$game_temp.battle_turn],['enemy_actions',@fixture_enemy_actions || 0],['actor_damage',@fixture_actor_damage || 0],['enemy_damage',@fixture_enemy_damage || 0]]
    raise 'Full-scene combat fixture did not exercise battle' unless result==0 && $rgssxp_fixture_gameover && values[0][1]>=3 && values[1][1]>=2 && values[2][1]>0 && values[3][1]>=10000
    File.open('full-combat-result.txt','w') { |file| values.each { |pair| file.puts(pair.join('=')) } }
    rgssxp_scene_battle_end_base(result)
  end
end
def scene_save_exists
  defined?(RGSSXP::Saves) ? RGSSXP::Saves.exist?(0) : File.file?('Save1.rxdata')
end
def scene_write_oracle
  File.open('counter-trace.txt','w') { |file| $scene_counter_trace.each { |row| file.puts(row.inspect) } }
  File.open('types-reference.txt','w') do |file|
    file.puts('switches'+"\t"+(1..5).collect { |index| $game_switches[index] }.inspect)
    file.puts('variables'+"\t"+(1..2).collect { |index| $game_variables[index] }.inspect)
    actors=$game_party.actors.collect { |actor| [actor.id,actor.hp,actor.sp,actor.level,actor.exp,actor.states,actor.skills] }
    file.puts('party'+"\t"+[$game_party.gold,actors].inspect)
    file.puts('items'+"\t"+(1...$data_items.size).collect { |index| $game_party.item_number(index) }.inspect)
    file.puts('player'+"\t"+[$game_map.map_id,$game_player.x,$game_player.y,$game_player.real_x,$game_player.real_y,$game_player.direction].inspect)
    file.puts('timer'+"\t"+[$game_system.timer,$game_system.timer_working].inspect)
    file.puts('frame_rate'+"\t"+Graphics.frame_rate.inspect)
    file.puts('frame_count'+"\t"+Graphics.frame_count.inspect)
    file.puts('driver_tick'+"\t"+ScenarioDriver.instance_variable_get('@tick').inspect)
  end
end
