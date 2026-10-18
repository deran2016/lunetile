# Own, bounded combat fixture; loaded only in a private test project.
enemies=load_data('Data/Enemies.rxdata')
enemies.compact.each do |enemy|
  enemy.maxhp=10000;enemy.atk=20;enemy.str=10;enemy.dex=999;enemy.agi=1;enemy.pdef=0;enemy.eva=0
  action=enemy.actions.first
  raise 'Fixture needs an existing enemy action' unless action
  action.kind=0;action.basic=0;action.rating=5
  action.condition_turn_a=0;action.condition_turn_b=1;action.condition_hp=100
  action.condition_level=1;action.condition_switch_id=0
  enemy.actions=[action]
end
save_data(enemies,'Data/Enemies.rxdata')
%w[Weapons Armors].each do |name|
  gear=load_data('Data/'+name+'.rxdata')
  gear.compact.each { |item| item.pdef=0;item.eva=0 if item.respond_to?(:eva=) }
  save_data(gear,'Data/'+name+'.rxdata')
end
troops=load_data('Data/Troops.rxdata')
troops.compact.each { |troop| troop.members=[troop.members.first] unless troop.members.empty? }
save_data(troops,'Data/Troops.rxdata')
ScenarioDriver.instance_variable_set(:@tick_limit,8000)
map=load_data('Data/Map001.rxdata')
map.events[1].pages.first.list.unshift(event_command(111,[12,'$rgssxp_fixture_gameover.nil?']),event_command(355,['$rgssxp_fixture_gameover = true'],1),event_command(353,[],1),event_command(412))
save_data(map,'Data/Map001.rxdata')

module FixtureGameoverRecovery
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
      super
    end
  end
end
ScenarioDriver.singleton_class.prepend(FixtureGameoverRecovery)

module FixtureCombatRandom
  def rand(limit=0)
    size=limit.to_i
    size>0 ? size*37/100 : 0.37
  end
  private :rand
end
Kernel.prepend(FixtureCombatRandom)

module FixtureCombatActions
  def make_basic_action_result
    actors=$game_party.actors.map(&:hp);enemies=$game_troop.enemies.map(&:hp)
    super
    @fixture_enemy_actions=(@fixture_enemy_actions || 0)+1 if @active_battler.is_a?(Game_Enemy) && @active_battler.current_action.basic==0
    @fixture_actor_damage=(@fixture_actor_damage || 0)+actors.zip($game_party.actors).sum { |hp,actor| [hp-actor.hp,0].max }
    @fixture_enemy_damage=(@fixture_enemy_damage || 0)+enemies.zip($game_troop.enemies).sum { |hp,enemy| [hp-enemy.hp,0].max }
  end
  def battle_end(result)
    values={turns:$game_temp.battle_turn,enemy_actions:@fixture_enemy_actions || 0,actor_damage:@fixture_actor_damage || 0,enemy_damage:@fixture_enemy_damage || 0}
    raise "Multi-turn combat failed: #{values}" unless result==0 && $rgssxp_fixture_gameover && values[:turns]>=3 && values[:enemy_actions]>=2 && values[:actor_damage]>0 && values[:enemy_damage]>=10000
    File.write('full-combat-result.txt',values.map { |key,value| "#{key}=#{value}" }.join("\n"))
    super
  end
end
Scene_Battle.prepend(FixtureCombatActions)
