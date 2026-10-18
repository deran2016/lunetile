# Own content and checks; runs with locally supplied stock Game_/Interpreter definitions.
%w[Actors Classes Skills Items Weapons Armors Enemies Troops States Animations Tilesets CommonEvents System].each do |name|
  eval('$data_'+name.gsub(/([a-z])([A-Z])/,'\\1_\\2').downcase+' = load_data("Data/'+name+'.rxdata")')
end
unless File.exist?('Data/order-fixtures-created.txt')
  [10,12,66,67,100,300].each do |count|
    map = load_data('Data/Map001.rxdata')
    map.events = {}
    1.upto(count) do |id|
      event = RPG::Event.new(4,4)
      event.id = id
      event.pages.first.list = [RPG::EventCommand.new(122,0,[1,1,0,0,id]),RPG::EventCommand.new]
      map.events[id] = event
    end
    save_data(map,sprintf('Data/Map%03d.rxdata',count))
  end
  File.open('Data/order-fixtures-created.txt','w') { |file| file.write('Own content, original Marshal bytes') }
end

$game_temp = Game_Temp.new
$game_system = Game_System.new
$game_switches = Game_Switches.new
$game_variables = Game_Variables.new
$game_self_switches = Game_SelfSwitches.new
$game_screen = Game_Screen.new
$game_actors = Game_Actors.new
$game_party = Game_Party.new
$game_troop = Game_Troop.new
$game_map = Game_Map.new
$game_player = Game_Player.new
$game_party.setup_starting_members
$data_common_events = [nil]
1.upto(20) do |id|
  event = RPG::CommonEvent.new
  event.id,event.trigger,event.switch_id = id,2,1
  event.list = [RPG::EventCommand.new(122,0,[2,2,0,0,id]),RPG::EventCommand.new]
  $data_common_events[id] = event
end
$game_switches[1] = true
File.open('types-reference.txt','w') do |out|
  [10,12,66,67,100,300].each do |count|
    $game_map.setup(count)
    out.puts("events_#{count}\t#{$game_map.events.keys.inspect}")
    out.puts("common_#{count}\t#{$game_map.instance_variable_get('@common_events').keys.inspect}")
    $game_player.moveto(4,4)
    $game_player.check_event_trigger_here([0])
    interpreter=Interpreter.new(0,true)
    interpreter.setup_starting_event
    out.puts("decision_#{count}\t#{interpreter.instance_variable_get('@event_id')}")
    $game_map.events.each_value do |event|
      event.clear_starting
      event.instance_variable_set('@trigger',1)
      event.instance_variable_set('@character_name','Own overlap fixture')
      event.instance_variable_set('@through',false)
    end
    $game_player.check_event_trigger_touch(4,4)
    interpreter=Interpreter.new(0,true);interpreter.setup_starting_event
    out.puts("contact_#{count}\t#{interpreter.instance_variable_get('@event_id')}")
    $game_map.events.each_value do |event|
      event.clear_starting
      event.instance_variable_set('@trigger',4)
      event.instance_variable_set('@interpreter',Interpreter.new)
    end
    $game_map.update
    out.puts("parallel_#{count}\t#{[$game_variables[1],$game_variables[2]].inspect}")
  end
  if File.exist?('Data/original-order-save.rxdata')
    state=Marshal.load(File.open('Data/original-order-save.rxdata','rb'))
    $game_map,$game_actors,$game_party,$game_troop=state
    RGSSXP.restore_integer_maps if defined?(RGSSXP)
  else
    actor=$game_party.actors.first
    1.upto(100) { |id| actor.instance_variable_get('@states_turn')[id]=id }
    state=[$game_map,$game_actors,$game_party,$game_troop]
    save_data(state,'Data/original-order-save.rxdata')
    state=load_data('Data/original-order-save.rxdata')
    $game_map,$game_actors,$game_party,$game_troop=state
  end
  out.puts("import_events\t#{$game_map.events.keys.inspect}")
  out.puts("import_common\t#{$game_map.instance_variable_get('@common_events').keys.inspect}")
  out.puts("import_states\t#{$game_party.actors.first.instance_variable_get('@states_turn').keys.inspect}")
  if defined?(RGSSXP)
    raise 'Imported ID tables were not converted' unless $game_map.events.is_a?(RGSSXP::IntegerMap) && $game_party.actors.first.instance_variable_get('@states_turn').is_a?(RGSSXP::IntegerMap)
    reloaded=Marshal.load(Marshal.dump(state))
    raise 'New save changed imported event order' unless reloaded[0].events.keys==$game_map.events.keys
    raise 'New save changed imported state order' unless reloaded[2].actors.first.instance_variable_get('@states_turn').keys==$game_party.actors.first.instance_variable_get('@states_turn').keys
  end
end
