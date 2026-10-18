# Own UI fixture. Imported save's old magic number makes stock Scene_Load reload this edited map.
File.write('korean-path-diagnostics.txt',[
  ['pwd',Dir.pwd.encoding.name,Dir.pwd.b.unpack1('H*')],
  ['root',RGSSXP::Saves::ROOT.encoding.name,RGSSXP::Saves::ROOT.b.unpack1('H*')],
  ['import',RGSSXP::Saves::IMPORT.encoding.name,RGSSXP::Saves::IMPORT.b.unpack1('H*')],
  ['relative',File.file?('Saves/Import/Save1.rxdata')],
  ['absolute',File.file?(RGSSXP::Saves.filename(0))],
  ['slot',RGSSXP::Saves.exist?(0)]
].inspect)
message = '한글 대화가 정상적으로 표시됩니다.'
map = load_data('Data/Map001.rxdata')
event = RPG::Event.new(4,4)
event.id,event.name = 99,'Korean text review'
page = event.pages.first
page.trigger = 3
page.list = [RPG::EventCommand.new(101,0,[message.encode('CP949').b]),
             RPG::EventCommand.new(121,0,[9,9,0]),RPG::EventCommand.new]
done = RPG::Event::Page.new
done.condition.switch1_valid,done.condition.switch1_id = true,9
event.pages << done
map.events[99] = event
save_data(map,'Data/Map001.rxdata')
system = load_data('Data/System.rxdata')
system.magic_number += 1
save_data(system,'Data/System.rxdata')

module KoreanReviewObserver
  def update
    if $scene.is_a?(Scene_Map) && @korean_map_scene!=$scene
      @korean_map_scene = $scene
      raise 'Imported actor name is not Korean' unless $game_party.actors.first.name=='한글'
      raise 'Imported picture filename is not Korean' unless $game_screen.pictures[1].name=='한글'
      raise 'Imported state was not restored' unless $game_variables[5]==12345
      kind=File.file?(File.join(RGSSXP::Saves::ROOT,'Save1.rxdata')) ? 'own-save-present' : 'original-import'
      File.open('korean-review.txt','a') { |file| file.puts(kind+'|'+$game_party.actors.first.name+'|'+$game_screen.pictures[1].name+'|'+$game_variables[5].to_s) }
    end
    super
  end
end
Graphics.singleton_class.prepend(KoreanReviewObserver)
