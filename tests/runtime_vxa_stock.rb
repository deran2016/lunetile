# Executed after the verified stock definitions and vxa_stock.rb, instead of Main.
def vxa_assert(condition, message)
  raise "VX Ace check: #{message}" unless condition
end
def vxa_pixels(label)
  # Read the presented GPU surface so opaque overlays cannot pass state-only checks.
  Graphics.update
  bitmap = Graphics.snap_to_bitmap
  colors = {}
  nonblack = 0
  (0...bitmap.height).step(16) do |y|
    (0...bitmap.width).step(16) do |x|
      color = bitmap.get_pixel(x,y)
      rgb = [color.red.to_i,color.green.to_i,color.blue.to_i]
      colors[rgb] = true
      nonblack += 1 if rgb.any? { |component| component > 8 }
    end
  end
  vxa_assert(nonblack > 10 && colors.length > 1,"#{label} GPU surface is visible")
  File.write("vxa-#{label}-pixels.json",%Q({"nonblack_samples":#{nonblack},"unique_colors":#{colors.length}}))
ensure
  bitmap.dispose if bitmap
end
DataManager.init
fade_start = Graphics.frame_count
Scene_Base.new.fadeout_all(100)
vxa_assert(Graphics.frame_count-fade_start == Graphics.frame_rate/10,'millisecond fade keeps duration')
vxa_assert($data_actors[1].is_a?(RPG::BaseItem), 'RPG inheritance')
vxa_assert($data_skills[1].is_a?(RPG::UsableItem), 'skill inheritance')
vxa_assert($data_weapons[1].is_a?(RPG::EquipItem), 'equipment inheritance')
vxa_assert(Graphics.width >= 544 && Graphics.height >= 416, 'dimensions')
Graphics.brightness = 255
SceneManager.goto(Scene_Title)
scene = SceneManager.scene
scene.start
scene.post_start
3.times { scene.update }
scene.command_new_game
scene.pre_terminate
scene.terminate
vxa_assert(SceneManager.scene_is?(Scene_Map),'title new game transition')
scene = SceneManager.scene
scene.start
scene.post_start
6.times { scene.update }
vxa_assert($game_map.map_id == $data_system.start_map_id,'start map')
vxa_pixels('map')
scene.call_menu
scene.pre_terminate
scene.terminate
scene = SceneManager.scene
scene.start
scene.post_start
3.times { scene.update }
SceneManager.return
scene.pre_terminate
scene.terminate
vxa_assert(SceneManager.scene_is?(Scene_Map),'menu return transition')

# Exercise stock menu scenes and their viewport-relative layout at both resolutions.
def vxa_window_bounds(window)
  return unless window.visible && window.width > 0 && window.height > 0
  vxa_assert(window.x >= 0 && window.y >= 0 && window.x+window.width <= Graphics.width && window.y+window.height <= Graphics.height,
    "#{window.class} fits screen")
end
def vxa_menu_scene(klass,*arguments)
  SceneManager.call(klass)
  current = SceneManager.scene
  current.prepare(*arguments) unless arguments.empty?
  current.start
  current.post_start
  4.times { current.update }
  current.instance_variables.each do |name|
    value = current.instance_variable_get(name)
    vxa_window_bounds(value) if value.is_a?(Window)
  end
  yield current if block_given?
  SceneManager.return if SceneManager.scene.equal?(current)
  current.pre_terminate
  current.terminate
end
actor = $game_party.members.first
$game_party.menu_actor = actor
vxa_menu_scene(Scene_Skill)
vxa_menu_scene(Scene_Status)
vxa_menu_scene(Scene_Equip) do |current|
  original = actor.equips[0]
  actor.change_equip(0,nil)
  vxa_assert(actor.equips[0].nil?,'unequip')
  actor.change_equip(0,original)
  vxa_assert(actor.equips[0] == original,'equip restored from inventory')
end
$game_party.gain_gold(1000)
item = $data_items[1]
quantity = $game_party.item_number(item)
gold = $game_party.gold
vxa_menu_scene(Scene_Shop,[[0,1,0,0]],false) do |current|
  current.command_buy
  current.instance_variable_get(:@buy_window).select(0)
  current.on_buy_ok
  current.on_number_ok
  vxa_assert($game_party.item_number(item) == quantity+1,'shop purchase inventory')
  vxa_assert($game_party.gold == gold-item.price,'shop purchase gold')
end
old_name = actor.name
vxa_menu_scene(Scene_Name,actor.id,8) do |current|
  edit = current.instance_variable_get(:@edit_window)
  edit.back until edit.name.empty?
  'Hero'.each_char { |letter| edit.add(letter) }
  current.on_input_ok
  vxa_assert(actor.name == 'Hero','name input confirmation')
end
actor.name = old_name

# Message text and choice selection use the stock Fiber and callback path.
message = Window_Message.new
$game_message.add('Lunetile VX Ace message\\^')
$game_message.choices.replace(['Continue','Cancel'])
selected = nil
$game_message.choice_proc = proc { |index| selected = index }
180.times { Graphics.update; message.update }
vxa_window_bounds(message)
choice = message.instance_variable_get(:@choice_window)
vxa_assert(choice.active && choice.open?,'choice window opens after message')
vxa_window_bounds(choice)
choice.select(0)
choice.call_ok_handler
10.times { Graphics.update; message.update }
vxa_assert(selected == 0,'choice callback')
$game_message.clear
message.dispose

# Movement retains authored speed at both logic profiles.
character = Game_Character.new
character.moveto(0,0)
character.instance_variable_set(:@x,1)
steps = (1.0 / character.distance_per_frame).round
steps.times { character.update_move }
vxa_assert((character.instance_variable_get(:@real_x)-1.0).abs < 0.00001, 'movement distance')
$game_timer.start(Graphics.frame_rate*2)
Graphics.frame_rate.times { $game_timer.update }
vxa_assert($game_timer.sec == 1, 'timer seconds')
$game_timer.stop

$game_variables[1] = 1977
vxa_assert(DataManager.save_game(15), 'save')
$game_variables[1] = 0
vxa_assert(DataManager.load_game(15), 'load')
vxa_assert($game_variables[1] == 1977, 'save round trip')
vxa_assert(DataManager.load_header(15)[:characters].is_a?(Array), 'header')
vxa_assert(File.binread(LunetileVXA.slot(15,true),LunetileVXA::SAVE_MAGIC.bytesize) == LunetileVXA::SAVE_MAGIC,'save version')

# Invalid input is rejected before replacing any live game global.
valid = File.binread(LunetileVXA.slot(15,true))
[valid.byteslice(0,12), 'wrong header', valid.byteslice(0,valid.bytesize-1)].each do |bad|
  File.binwrite(LunetileVXA.slot(0,true),bad)
  current = $game_system
  vxa_assert(!DataManager.load_game(0) && $game_system.equal?(current),'corrupt save leaves game intact')
end
File.delete(LunetileVXA.slot(0,true))
Dir.mkdir('Saves/Import') unless Dir.exist?('Saves/Import')
original = Marshal.dump(DataManager.make_save_header)+Marshal.dump(DataManager.make_save_contents)
File.binwrite('Saves/Import/Save01.rvdata2',original)
vxa_assert(DataManager.load_game(0),'original save import')
vxa_assert(DataManager.save_game(0),'imported game saved separately')
vxa_assert(File.binread('Saves/Import/Save01.rvdata2') == original,'original save unchanged')
BattleManager.setup(1,true,true)
BattleManager.save_bgm_and_bgs
SceneManager.call(Scene_Battle)
scene = SceneManager.scene
scene.define_singleton_method(:wait_for_message) { $game_message.clear }
scene.start
scene.post_start
40.times { scene.update }
party_commands = scene.instance_variable_get(:@party_command_window)
vxa_assert(party_commands.visible && party_commands.openness == 255,'battle party commands fully open')
scene.command_fight
40.times { scene.update }
actor_commands = scene.instance_variable_get(:@actor_command_window)
vxa_assert(actor_commands.active && actor_commands.open?,'battle actor command opens')
scene.command_attack
vxa_assert(scene.instance_variable_get(:@enemy_window).active,'attack target selection')
vxa_pixels('battle')
actor = $game_party.members.first
enemy = $game_troop.members.first
vxa_assert(actor && enemy,'battle participants')
action = Game_Action.new(actor)
action.set_attack
before = enemy.hp
20.times do
  enemy.item_apply(actor,action.item)
  break if enemy.hp < before
end
vxa_assert(enemy.hp < before,'battle attack applies damage')
BattleManager.method_wait_for_message = proc { $game_message.clear }
old_gold = $game_party.gold
$game_troop.members.each { |target| target.hp = 0 }
vxa_assert(BattleManager.judge_win_loss,'battle victory transition')
vxa_assert($game_party.gold >= old_gold,'battle reward')
vxa_assert(!$game_party.in_battle,'battle ended')
vxa_assert(SceneManager.scene_is?(Scene_Map),'battle return to map')
scene.pre_terminate
scene.terminate
Graphics.update
File.write('vxa-stock-result.json',%Q({"ok":true,"width":#{Graphics.width},"height":#{Graphics.height},"logic_rate":#{Graphics.frame_rate},"movement_steps":#{steps},"save_slot":16}))
File.write('runtime-complete.txt','VX Ace stock title, map, menu, battle, save and load completed')
