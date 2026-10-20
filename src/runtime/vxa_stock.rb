# Installed before Main only after validating the complete VX Ace stock collection.
module LunetileVXA
  SAVE_ROOT = 'Saves/LunetileVXA'
  SAVE_MAGIC = "LUNETILE\0VXA\0".b + [1].pack('V')
  def self.slot(index, write = false)
    raise ArgumentError, 'Save slot must be 0..15' unless index.is_a?(Integer) && index.between?(0,15)
    name = format('Save%02d.rvdata2',index+1)
    own = File.join(SAVE_ROOT,name)
    write || File.file?(own) ? own : File.join('Saves/Import',name)
  end
  def self.read(index)
    path = slot(index)
    stream = StringIO.new(File.binread(path))
    rate = 60
    if path.start_with?(SAVE_ROOT+'/')
      raise ArgumentError, 'Invalid VX Ace save header' unless stream.read(SAVE_MAGIC.bytesize) == SAVE_MAGIC
      bytes = stream.read(4)
      raise ArgumentError, 'Truncated VX Ace save rate' unless bytes && bytes.bytesize == 4
      rate = bytes.unpack1('V')
      raise ArgumentError, 'Unsupported VX Ace save rate' unless [60,120].include?(rate)
    end
    header = Marshal.load(stream)
    contents = Marshal.load(stream)
    raise ArgumentError, 'Invalid VX Ace save data' unless header.is_a?(Hash) && contents.is_a?(Hash) && contents[:system].is_a?(Game_System)
    types = {system:Game_System,timer:Game_Timer,message:Game_Message,switches:Game_Switches,
      variables:Game_Variables,self_switches:Game_SelfSwitches,actors:Game_Actors,party:Game_Party,
      troop:Game_Troop,map:Game_Map,player:Game_Player}
    raise ArgumentError, 'Incomplete VX Ace save contents' unless types.all? { |key,type| contents[key].is_a?(type) }
    raise ArgumentError, 'Invalid VX Ace save display header' unless header[:characters].is_a?(Array) && header[:playtime_s].is_a?(String)
    raise ArgumentError, 'Trailing VX Ace save data' unless stream.eof?
    [header,contents,rate]
  ensure
    stream.close if stream
  end
end
module LunetileVXASaveManager
  def make_filename(index); LunetileVXA.slot(index); end
  def save_file_exists?; savefile_max.times.any? { |i| File.file?(make_filename(i)) }; end
  def save_game(index)
    save_game_without_rescue(index)
  rescue StandardError
    false
  end
  def save_game_without_rescue(index)
    path = LunetileVXA.slot(index,true)
    Dir.mkdir('Saves') unless Dir.exist?('Saves')
    Dir.mkdir(LunetileVXA::SAVE_ROOT) unless Dir.exist?(LunetileVXA::SAVE_ROOT)
    temporary = path + ".tmp-#{Process.pid}"
    $game_system.on_before_save
    bytes = LunetileVXA::SAVE_MAGIC + [Graphics.frame_rate].pack('V') + Marshal.dump(make_save_header) + Marshal.dump(make_save_contents)
    begin
      File.open(temporary,'wbx') { |file| file.write(bytes); file.flush; file.fsync }
      File.rename(temporary,path)
      @last_savefile_index = index
      true
    ensure
      File.delete(temporary) if File.file?(temporary)
    end
  end
  def load_game_without_rescue(index)
    _,contents,rate = LunetileVXA.read(index)
    if rate != Graphics.frame_rate
      system,timer = contents[:system],contents[:timer]
      frames = system.instance_variable_get(:@frames_on_save)
      system.instance_variable_set(:@frames_on_save,frames*Graphics.frame_rate/rate) if frames
      count = timer.instance_variable_get(:@count)
      timer.instance_variable_set(:@count,count*Graphics.frame_rate/rate) if count
    end
    extract_save_contents(contents)
    reload_map_if_updated
    @last_savefile_index = index
    true
  end
  def load_header_without_rescue(index); LunetileVXA.read(index)[0]; end
  def delete_save_file(index)
    path = LunetileVXA.slot(index,true)
    File.delete(path) if File.file?(path)
  end
end
DataManager.singleton_class.prepend(LunetileVXASaveManager)

# This stock method already converts milliseconds using the active logic rate.
module LunetileVXAFadeAll
  def fadeout_all(time = 1000)
    RPG::BGM.fade(time)
    RPG::BGS.fade(time)
    RPG::ME.fade(time)
    Graphics.vxa_fadeout(time * Graphics.frame_rate / 1000)
    RPG::BGM.stop
    RPG::BGS.stop
    RPG::ME.stop
  end
end
Scene_Base.prepend(LunetileVXAFadeAll)

# Continuous motion runs at 120Hz; authored animation counters retain their 60Hz units.
module LunetileVXAMotion
  def distance_per_frame; super / RGSSXP::Timing.scale.to_f; end
  def update_animation; super if RGSSXP::Timing.legacy_tick?; end
  def update_stop; super if RGSSXP::Timing.legacy_tick?; end
  def update_jump; super if RGSSXP::Timing.legacy_tick?; end
end
Game_CharacterBase.prepend(LunetileVXAMotion)
module LunetileVXARoute
  def update_routine_move
    return if @wait_count > 0 && !RGSSXP::Timing.legacy_tick?
    super
  end
end
Game_Character.prepend(LunetileVXARoute)
module LunetileVXAScroll
  def scroll_distance; super / RGSSXP::Timing.scale.to_f; end
  def update_parallax; super if RGSSXP::Timing.legacy_tick?; end
end
Game_Map.prepend(LunetileVXAScroll)
module LunetileVXAWait
  def wait(duration); super(duration*RGSSXP::Timing.scale); end
end
[Game_Interpreter,Window_Message,Scene_Battle].each { |klass| klass.prepend(LunetileVXAWait) }
{
  Game_Screen=>[:update], Sprite_Base=>[:update_animation],
  Sprite_Battler=>[:update_effect], Sprite_Character=>[:update_balloon],
  Window_Base=>[:update_open,:update_close], Spriteset_Weather=>[:update]
}.each do |klass,methods|
  patch = Module.new
  methods.each { |name| patch.define_method(name) { |*args| super(*args) if RGSSXP::Timing.legacy_tick? } }
  klass.prepend(patch)
end

module LunetileVXATitle
  def center_sprite(sprite)
    super
    return unless sprite.bitmap && Graphics.width > 544
    scale = [Graphics.width.to_f/sprite.bitmap.width,Graphics.height.to_f/sprite.bitmap.height].max
    sprite.zoom_x = sprite.zoom_y = scale
  end
end
Scene_Title.prepend(LunetileVXATitle)

# A compact native-resolution menu for the same output rates as the XP package.
class Window_LunetileVXADisplay < Window_Command
  def window_width; 240; end
  def make_command_list
    [40,60,120].each { |rate| add_command("#{rate} FPS",:"fps#{rate}") }
    add_command('Back',:cancel)
  end
end
class Scene_LunetileVXADisplay < Scene_MenuBase
  def start
    super
    @command_window = Window_LunetileVXADisplay.new((Graphics.width-240)/2,(Graphics.height-168)/2)
    [40,60,120].each { |rate| @command_window.set_handler(:"fps#{rate}",proc { select_rate(rate) }) }
    @command_window.set_handler(:cancel,method(:return_scene))
  end
  def select_rate(rate)
    Dir.mkdir('Saves') unless Dir.exist?('Saves')
    Dir.mkdir(LunetileVXA::SAVE_ROOT) unless Dir.exist?(LunetileVXA::SAVE_ROOT)
    path = RGSSXP::Timing.settings_path
    temporary = path + ".tmp-#{Process.pid}"
    begin
      File.open(temporary,'wbx') { |file| file.write("[Display]\nRenderRate=#{rate}\n"); file.flush; file.fsync }
      File.rename(temporary,path)
      Graphics.render_rate = rate
    ensure
      File.delete(temporary) if File.file?(temporary)
    end
    @command_window.activate
  end
end
module LunetileVXAMenuCommand
  def add_original_commands
    super
    add_command('Display',:lunetile_display) if Graphics.__stock120
  end
end
Window_MenuCommand.prepend(LunetileVXAMenuCommand)
module LunetileVXAMenu
  def create_command_window
    super
    @command_window.set_handler(:lunetile_display,proc { SceneManager.call(Scene_LunetileVXADisplay) })
  end
end
Scene_Menu.prepend(LunetileVXAMenu)
if Graphics.__stock120 && File.file?(RGSSXP::Timing.settings_path)
  text = File.binread(RGSSXP::Timing.settings_path)
  match = text.match(/\A\[Display\]\r?\nRenderRate=(40|60|120)\r?\n?\z/)
  Graphics.render_rate = match[1].to_i if match
end

module LunetileVXAMapFade
  def fade_loop(duration,&block); super(duration*RGSSXP::Timing.scale,&block); end
end
Scene_Map.prepend(LunetileVXAMapFade)
module LunetileVXABattleBackground
  def center_sprite(sprite)
    super
    return unless sprite.bitmap && Graphics.width > 544
    scale = [Graphics.width.to_f/sprite.bitmap.width,Graphics.height.to_f/sprite.bitmap.height].max
    sprite.zoom_x = sprite.zoom_y = scale
  end
end
Spriteset_Battle.prepend(LunetileVXABattleBackground)
module LunetileVXABattlePosition
  def screen_x; super + (Graphics.width-544)/2; end
  def screen_y; super + (Graphics.height-416)/2; end
end
Game_Enemy.prepend(LunetileVXABattlePosition)
