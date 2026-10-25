require 'json'
%w[Actors Classes Skills Items Weapons Armors Enemies Troops States Animations Tilesets CommonEvents System].each do |name|
 eval('$data_'+name.gsub(/([a-z])([A-Z])/,'\\1_\\2').downcase+' = load_data("Data/'+name+'.rxdata")')
end
$game_temp=Game_Temp.new;$game_system=Game_System.new;$game_screen=Game_Screen.new
$game_switches=Game_Switches.new;$game_variables=Game_Variables.new;$game_self_switches=Game_SelfSwitches.new
$game_actors=Game_Actors.new;$game_party=Game_Party.new;$game_troop=Game_Troop.new
$game_map=Game_Map.new;$game_player=Game_Player.new;$game_party.setup_starting_members
$game_map.setup(1);$game_player.refresh
sprites=Spriteset_Map.new
scene=Object.new
scene.define_singleton_method(:update) do
 $game_system.map_interpreter.update;$game_map.update;$game_player.update
 $game_system.update;$game_screen.update;sprites.update;Graphics.update
end
