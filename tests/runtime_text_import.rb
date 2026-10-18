expected = RGSSXP::DATA_ENCODING=='CP932' ? '日本語' : '한글'
raise 'Project data did not decode' unless load_data('Data/Actors.rxdata')[1].name==expected
def restore_text_objects(objects,expected)
  raise 'Wrong original save record count' unless objects.size==12
  $game_system,$game_switches,$game_variables,$game_self_switches,$game_screen,
    $game_actors,$game_party,$game_troop,$game_map,$game_player = objects[2..-1]
  RGSSXP.restore_game_compatibility
  raise 'Actor import text is not UTF-8' unless $game_party.actors.first.name==expected && $game_party.actors.first.name.encoding==Encoding::UTF_8
  raise 'Picture import text did not decode' unless $game_screen.pictures[1].name==expected
  raise 'Game state changed during text import' unless $game_variables[5]==12345
  raise 'Map ID table import was skipped' unless $game_map.events.is_a?(RGSSXP::IntegerMap)
end
original = RGSSXP::Saves.filename(0)
stream = RGSSXP::Saves.open_read(original)
objects=[];objects << Marshal.load(stream) until stream.eof?;stream.close
restore_text_objects(objects,expected)
target = RGSSXP::Saves.filename(0,:write)
RGSSXP::Saves.write(target) { |file| objects.each { |object| Marshal.dump(object,file) } }
stream = RGSSXP::Saves.open_read(target)
copies=[];copies << Marshal.load(stream) until stream.eof?;stream.close
restore_text_objects(copies,expected)
File.write('runtime-complete.txt','legacy-text-import,false,false')
sleep 0.5
