def comfort_assert_error(*types)
  begin
    yield
  rescue *types
    return
  end
  raise 'Expected rejected controls/save operation'
end
c = Lunetile::Controls
s = Lunetile::SaveFiles
f = Lunetile::Comfort
raise 'Stock installer missing' unless f.installed?
Lunetile.install_stock
raise 'Duplicate stock hooks' unless Scene_Map.ancestors.count(Lunetile::Comfort::MapUpdate) == 1
raise 'Default controls' unless c.binding(:confirm) == [[32,90,13],:a]
c.bind(:confirm,keys:[86])
raise 'Remap missing' unless c.prompt(:confirm,:keyboard) == 'V'
saved_controls = File.binread(c::PATH)
comfort_assert_error(ArgumentError) { c.bind(:cancel,keys:[86]) }
comfort_assert_error(ArgumentError) { c.bind(:confirm,keys:[123]) }
comfort_assert_error(ArgumentError) { c.bind(:confirm,keys:[]) }
comfort_assert_error(ArgumentError) { c.bind(:confirm,pad: :b) }
raise 'Invalid remap changed settings' unless File.binread(c::PATH) == saved_controls && c.binding(:confirm)[0] == [86]
c.bind(:confirm,pad: :rt)
raise 'Pad remap/prompt' unless c.prompt(:confirm,:gamepad) == 'RT'
comfort_assert_error(ArgumentError) { c.__rumble(Float::NAN,0,10) }
comfort_assert_error(ArgumentError) { c.__rumble(1,0,5001) }
comfort_assert_error(ArgumentError) { c.__configure([[13,[86],4096]]) }
c.rumble_enabled = false
raise 'Rumble stop' unless c.rumble_enabled? == false && c.rumble(0.2,0.4,20)

path = 'Saves/Lunetile/transaction.json'
valid = lambda { |bytes| raise ArgumentError unless JSON.parse(bytes).is_a?(Integer) }
1.upto(5) { |i| s.write(path,JSON.generate(i),&valid) }
raise 'Backup order/count' unless 1.upto(3).map { |i| JSON.parse(File.binread(path+".bak#{i}")) } == [4,3,2] && !File.exist?(path+'.bak4')
File.binwrite(path,'broken')
s.write(path,'6',&valid)
raise 'Corrupt previous promoted to backup' unless File.binread(path+'.bak1') == '4'
comfort_assert_error(JSON::ParserError) { s.write(path,'broken',&valid) }
raise 'Rejected write replaced current' unless File.binread(path) == '6'
class << File
  alias_method :comfort_original_rename, :rename
  def rename(from,to)
    raise Errno::EACCES, 'injected final replacement failure' if to == 'Saves/Lunetile/transaction.json'
    comfort_original_rename(from,to)
  end
end
begin
  comfort_assert_error(Errno::EACCES) { s.write(path,'7',&valid) }
ensure
  class << File
    alias_method :rename, :comfort_original_rename
    remove_method :comfort_original_rename
  end
end
raise 'Failed replacement destroyed save or leaked temp' unless File.binread(path) == '6' && Dir.glob(path+'.tmp-*').empty?

if f.vxa?
  SceneManager.goto(Scene_Map)
  scene = SceneManager.scene
else
  $scene = scene = Scene_Map.new
end
$game_player.moveto(10,10)
raise 'Safe map rejected' unless f.safe?(scene)
$game_system.save_disabled = true
raise 'Save-disabled map accepted' if f.safe?(scene)
$game_system.save_disabled = false
if f.vxa?
  $game_message.add('pending message')
else
  $game_temp.message_window_showing = true
end
raise 'Message accepted for autosave' if f.safe?(scene)
f.vxa? ? $game_message.clear : $game_temp.message_window_showing = false
interpreter = f.vxa? ? $game_map.interpreter : $game_system.map_interpreter
interpreter.define_singleton_method(:running?) { true }
raise 'Running event accepted for autosave' if f.safe?(scene)
interpreter.singleton_class.remove_method(:running?)
common = $game_map.instance_variable_get(:@common_events)
parallel = Object.new
parallel.instance_variable_set(:@interpreter,Object.new)
parallel.instance_variable_get(:@interpreter).define_singleton_method(:running?) { true }
$game_map.instance_variable_set(:@common_events,[parallel])
raise 'Parallel event accepted for autosave' if f.safe?(scene)
$game_map.instance_variable_set(:@common_events,common)
comfort_assert_error(ArgumentError) { f.enabled = 'yes' }
f.enabled = false
f.request
f.instance_variable_set(:@pending_at,0)
f.update(scene)
raise 'Disabled autosave wrote a file' if File.exist?(f.auto_path)
f.enabled = true
$game_variables[1] = 910
f.instance_variable_set(:@pending_at,0)
f.update(scene)
raise "Autosave failed #{f.error}" unless File.file?(f.auto_path)
raise 'Autosave consumed a manual slot' if File.file?(f.vxa? ? LunetileVXA.slot(0,true) : RGSSXP::Saves.filename(0,:write))
before = File.binread(f.auto_path)
$game_variables[1] = 911
f.update(scene)
raise 'Autosave repeated every tick' unless File.binread(f.auto_path) == before
f.save_auto
raise 'Autosave backup missing' unless File.binread(f.auto_path+'.bak1') == before
1.upto(5) do |i|
  $game_variables[1] = i
  if f.vxa?
    raise 'Manual save failed' unless DataManager.save_game(0)
  else
    RGSSXP::Saves.write(RGSSXP::Saves.filename(0,:write)) { |file| Scene_Save.allocate.write_save_data(file) }
  end
end
manual = f.vxa? ? LunetileVXA.slot(0,true) : RGSSXP::Saves.filename(0,:write)
raise 'Manual backup missing' unless 1.upto(3).all? { |i| File.file?(manual+".bak#{i}") }
File.binwrite(manual,'truncated manual save')
f.load(manual+'.bak1')
raise 'Backup recovery state or source preservation' unless $game_variables[1] == 4 && File.binread(manual) == 'truncated manual save'
raise 'Recovery immediately autosaves' if f.instance_variable_get(:@pending_at)
old_variables = $game_variables
old_frame = Graphics.frame_count
File.binwrite(manual+'.bak2','corrupt backup')
comfort_assert_error(IOError,ArgumentError,EOFError,TypeError) { f.load(manual+'.bak2') }
raise 'Corrupt load changed game' unless $game_variables.equal?(old_variables) && Graphics.frame_count == old_frame
comfort_assert_error(ArgumentError) { f.load('../outside.rxdata') }
comfort_assert_error(RuntimeError) { f.transaction { $game_variables = nil; Graphics.frame_count = 99; raise 'injected apply failure' } }
raise 'Apply rollback failed' unless $game_variables.equal?(old_variables) && Graphics.frame_count == old_frame
f.load(f.auto_path+'.bak1')
raise 'Autosave recovery state' unless $game_variables[1] == 910
File.write('comfort-result.json',JSON.generate({passed:true,engine:f.vxa? ? 'vxa' : 'xp',physical_gamepad:false}))
File.write('runtime-complete.txt','comfort PASS,false,false')
