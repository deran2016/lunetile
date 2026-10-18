# Own original-save fixture; stock Game_/Interpreter definitions are supplied locally.
%w[Actors Classes Skills Items Weapons Armors Enemies Troops States Animations Tilesets CommonEvents System].each do |name|
  eval('$data_'+name.gsub(/([a-z])([A-Z])/,'\\1_\\2').downcase+' = load_data("Data/'+name+'.rxdata")')
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
$game_map.setup(1)
$game_player.refresh
$game_player.moveto(4,4)
$game_variables[5] = 12345
$game_system.magic_number = $data_system.magic_number
$game_screen.pictures[1].show($game_party.actors.first.name,0,16,16,100,100,255,0)
objects = [$game_party.actors.collect { |actor| [actor.character_name,actor.character_hue] },1234,
           $game_system,$game_switches,$game_variables,$game_self_switches,$game_screen,
           $game_actors,$game_party,$game_troop,$game_map,$game_player]
File.open('Save1.rxdata','wb') { |file| objects.each { |object| Marshal.dump(object,file) } }
File.open('types-reference.txt','w') { |file| file.puts('original_name_hex'+"\t"+$game_party.actors.first.name.unpack('H*')[0].inspect) }
