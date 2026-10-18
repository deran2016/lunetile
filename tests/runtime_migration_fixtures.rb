map = load_data('Data/Map001.rxdata')
event = RPG::Event.allocate
event.id, event.name, event.x, event.y = 1, 'inspection', 1, 1
page = RPG::Event::Page.allocate
event.pages = [page]
map.events[1] = event
page.list = [RPG::EventCommand.new(355, 0, ['$game_switches[1] = true'])]
File.binwrite('event-code.rxdata', Marshal.dump(map))
page.list = [RPG::EventCommand.new(111, 0, [12, '$game_switches[1]'])]
File.binwrite('condition-code.rxdata', Marshal.dump(map))
page.list = [RPG::EventCommand.new]
page.move_route = RPG::MoveRoute.new
page.move_route.list = [RPG::MoveCommand.new(45, ['$game_player.move_down'])]
File.binwrite('movement-code.rxdata', Marshal.dump(map))
page.move_route = RPG::MoveRoute.new
event.name = '한글'
File.binwrite('utf8-text.rxdata', Marshal.dump(map))
File.write('runtime-complete.txt', 'migration-fixtures,false,false')
sleep 0.5
