# Runs after the reviewed definitions, without requiring RTP graphics or audio.
$data_tilesets = load_data('Data/Tilesets.rxdata')
$data_common_events = load_data('Data/CommonEvents.rxdata')
$game_temp = Game_Temp.new
$game_system = Game_System.new
$game_screen = Game_Screen.new
$game_switches = Game_Switches.new
$game_variables = Game_Variables.new
$game_self_switches = Game_SelfSwitches.new
$game_party = Game_Party.new
$game_map = Game_Map.new
$game_player = Game_Player.new
$game_map.setup(1)
scale = RGSSXP::Timing.scale
tick = 0
advance = lambda do
  tick += 1
  Graphics.frame_count = tick
end
character = Game_Character.new
character.moveto(4,4)
character.move_right
move_ticks = 0
while character.moving?
  advance.call;character.update;move_ticks += 1
  raise 'movement never ends' if move_ticks > 300
end
raise 'movement endpoint wrong' unless character.x == 5 && character.instance_variable_get(:@real_x) == 640
raise 'movement duration changed' unless move_ticks == 8 * scale
character.jump(1,0)
jump_ticks = 0
while character.jumping?
  advance.call;character.update;jump_ticks += 1
  raise 'jump never ends' if jump_ticks > 300
end
raise 'jump endpoint wrong' unless character.instance_variable_get(:@real_x) == character.x * 128
picture = Game_Picture.new(1)
picture.show('',0,0,0,100,100,255,0)
picture.move(20,0,100,80,120,130,100,0)
picture.rotate(4)
screen = Game_Screen.new
screen.start_tone_change(Tone.new(60,30,15,0),20)
20.times do
  scale.times { advance.call;picture.update;screen.update }
end
raise 'picture time wrong' unless (picture.x-100).abs < 0.001 && (picture.y-80).abs < 0.001 && (picture.angle-40).abs < 0.001
raise 'tone time wrong' unless screen.tone.red == 60 && screen.tone.green == 30
map = $game_map
map.start_fog_tone_change(Tone.new(20,30,40,0),20)
20.times { scale.times { advance.call;map.update } }
raise 'fog time wrong' unless map.fog_tone.red == 20
map_data = map.instance_variable_get(:@map)
original_size = [map_data.width,map_data.height]
map_data.width,map_data.height = 80,40
map.start_scroll(6,1,4)
scroll_ticks = 0
while map.scrolling?
  advance.call;map.update;scroll_ticks += 1
  raise 'scroll never ends' if scroll_ticks > 300
end
raise 'scroll duration changed' unless scroll_ticks == 8 * scale
map_data.width,map_data.height = original_size
map.display_x = map.display_y = 0
character.move_right
advance.call;character.update
restored = Marshal.load(Marshal.dump(character))
while character.moving?
  advance.call;character.update;restored.update
  raise 'moving save lost state/remainder' unless [character.instance_variable_get(:@real_x),character.instance_variable_get(:@lunetile_move_remainder)] == [restored.instance_variable_get(:@real_x),restored.instance_variable_get(:@lunetile_move_remainder)]
end
character.jump(1,0)
advance.call;character.update
restored = Marshal.load(Marshal.dump(character))
while character.jumping?
  advance.call;character.update;restored.update
  raise 'jumping save lost trajectory' unless character.screen_y == restored.screen_y && character.instance_variable_get(:@real_x) == restored.instance_variable_get(:@real_x)
end
effect = RPG::Sprite.new
effect.appear
effect_ticks = 0
while effect.effect?
  advance.call;effect.update;effect_ticks += 1
  raise 'effect never ends' if effect_ticks > 80
end
# Visual effects retain the 40 Hz cadence; start on its boundary for exact duration.
raise 'effect ran too fast' unless effect_ticks.between?(16*scale-(scale-1),16*scale)
effect.flash(nil,4)
(4*scale-1).times { advance.call;effect.update }
raise 'flash ended early' unless effect.flash_hidden?
advance.call;effect.update
raise 'flash duration changed' if effect.flash_hidden?
animation = Marshal.load(Marshal.dump(load_data('Data/Animations.rxdata').compact.find { |item| item.frame_max >= 3 }))
animation.frame_max = 3
animation.frames = animation.frames.first(3)
animation.animation_name = ''
animation.timings = []
Graphics.frame_count = 0
effect.animation(animation,true)
animation_ticks = 0
while effect.effect?
  Graphics.frame_count += 1;effect.update;animation_ticks += 1
  raise 'animation never ends' if animation_ticks > 30
end
raise 'animation duration changed' unless animation_ticks == 6 * scale
effect.dispose
system = Game_System.new
system.timer = Graphics.frame_rate * 2;system.timer_working = true
(Graphics.frame_rate * 2).times { advance.call;system.update }
raise 'timer duration changed' unless system.timer == 0
interpreter = Interpreter.new
interpreter.instance_variable_set(:@parameters,[10])
interpreter.command_106
wait = interpreter.instance_variable_get(:@wait_count)
raise 'event wait time changed' unless wait == 20 * scale
Graphics.frame_count = 0
route_character = Game_Character.new
route_character.moveto(4,4)
route = RPG::MoveRoute.new
route.repeat = false
route.list = [RPG::MoveCommand.new(15,[2]),RPG::MoveCommand.new(3),RPG::MoveCommand.new]
route_character.force_move_route(route)
route_wait = 0
until route_character.moving?
  Graphics.frame_count += 1;route_character.update;route_wait += 1
  raise 'forced route wait never ends' if route_wait > 50
end
raise 'forced route wait changed' unless route_wait == 4 * scale
Graphics.frame_count = 0
random_character = Game_Character.new
random_character.moveto(4,4)
random_character.instance_variable_set(:@test_random_calls,0)
def random_character.passable?(*); false; end
def random_character.check_event_trigger_touch(*); end
def random_character.move_random
  @test_random_calls += 1
  super
end
route = RPG::MoveRoute.new
route.repeat = route.skippable = true
route.list = [RPG::MoveCommand.new(9),RPG::MoveCommand.new]
random_character.force_move_route(route)
(40 * scale).times { Graphics.frame_count += 1;random_character.update }
raise 'blocked random route runs three times faster' unless random_character.instance_variable_get(:@test_random_calls) == 21
if scale == 3
  $game_system.timer = 80
  $game_player.instance_variable_set(:@jump_peak,7)
  $game_player.instance_variable_set(:@jump_count,9)
  $game_system.map_interpreter.instance_variable_set(:@wait_count,11)
  $game_screen.pictures[1].move(12,0,10,20,100,100,255,0)
  # Legacy serialized durations have not yet been scaled by the old runtime.
  $game_screen.pictures[1].instance_variable_set(:@duration,12)
  file = RGSSXP::Saves::ReadStream.new('',Time.now)
  Graphics.frame_count = 400
  RGSSXP::Timing.import_save(file)
  raise 'legacy play time not converted' unless Graphics.frame_count == 1200 && $game_system.timer == 240
  raise 'legacy active state not converted' unless $game_player.instance_variable_get(:@jump_count) == 27 && $game_player.instance_variable_get(:@jump_peak) == 21 && $game_system.map_interpreter.instance_variable_get(:@wait_count) == 33 && $game_screen.pictures[1].instance_variable_get(:@duration) == 36
  RGSSXP::Timing.import_save(file)
  raise 'save converted twice' unless Graphics.frame_count == 1200
end
File.write('timing-comparison.txt',[move_ticks,jump_ticks,scroll_ticks,wait,animation_ticks,picture.x,picture.y,picture.angle].inspect)
File.write('runtime-complete.txt','timing,false,false')
