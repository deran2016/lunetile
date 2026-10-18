# Checks actual stock windows after New Game has populated the database and party.
module WideUIProbe
  @checked = false
  @captured = {}
  def self.check
    raise 'wide config not loaded' unless [Graphics.width,Graphics.height] == [1280,720]
    actor = $game_party.actors.first
    windows = [Window_Help.new, Window_MenuStatus.new, Window_Item.new,
      Window_Skill.new(actor), Window_SkillStatus.new(actor), Window_Target.new,
      Window_EquipLeft.new(actor), Window_EquipRight.new(actor), Window_EquipItem.new(actor,0),
      Window_Status.new(actor), Window_ShopCommand.new, Window_ShopBuy.new([[0,1]]),
      Window_ShopSell.new, Window_ShopNumber.new, Window_ShopStatus.new,
      Window_NameEdit.new(actor,8), Window_NameInput.new, Window_Message.new,
      Window_PartyCommand.new, Window_BattleStatus.new, Window_DebugLeft.new,
      Window_DebugRight.new]
    windows += (0..3).map { |i| Window_SaveFile.new(i, 'Wide test') }
    windows.each do |window|
      raise "#{window.class}: outside screen" unless window.x >= 0 && window.y >= 0 &&
        window.x + window.width <= Graphics.width && window.y + window.height <= Graphics.height
    end
    item = windows.find { |window| window.is_a?(Window_Item) }
    raise 'list rows not expanded' unless item.page_row_max == (720-64-32)/32
    message = windows.find { |window| window.is_a?(Window_Message) }
    [0,1,2].each do |position|
      $game_system.message_position = position
      message.reset_window
      raise 'message outside screen' unless message.y >= 0 && message.y + message.height <= 720
    end
    $game_system.message_position = 2
    background = Sprite.new
    background.bitmap = Bitmap.new(640,480)
    Lunetile.cover(background)
    raise 'background aspect ratio/crop wrong' unless [background.zoom_x,background.zoom_y,background.x,background.y] == [2.0,2.0,0,-120]
    background.bitmap.dispose
    background.dispose
    rect = Lunetile.map_rect
    raise 'small map is not centered' unless rect[0] == (1280-rect[2])/2 && rect[1] == (720-rect[3])/2
    original_map = $game_map.instance_variable_get(:@map)
    original_display = [$game_map.display_x, $game_map.display_y]
    begin
      $game_map.instance_variable_set(:@map, RPG::Map.new(60,40))
      $game_player.center(59,39)
      raise 'large map camera boundary wrong' unless [$game_map.display_x,$game_map.display_y] == [2560,2240]
      $game_map.scroll_right(128);$game_map.scroll_down(128)
      raise 'camera scroll exceeded boundary' unless [$game_map.display_x,$game_map.display_y] == [2560,2240]
      $game_map.instance_variable_set(:@map, RPG::Map.new(10,8))
      $game_player.center(9,7)
      raise 'small map scroll or padding wrong' unless [$game_map.display_x,$game_map.display_y] == [0,0] && Lunetile.map_rect == [480,232,320,256]
    ensure
      $game_map.instance_variable_set(:@map,original_map)
      $game_map.display_x,$game_map.display_y = original_display
    end
    File.write('wide-ui-checked.txt', windows.map { |w| [w.class,w.x,w.y,w.width,w.height].join(',') }.join("\n"))
  ensure
    windows&.each { |window| window.dispose unless window.disposed? }
  end
  def self.step
    if !@checked && $scene.is_a?(Scene_Map)
      check
      @checked = true
    end
    return unless File.exist?('wide-capture-enabled.txt')
    name = $scene.class.name
    return if @captured[name] || !%w[Scene_Title Scene_Map Scene_Menu Scene_Save Scene_Load Scene_Battle Scene_LunetileDisplay].include?(name)
    return unless Graphics.frame_count % 12 == 0
    @captured[name] = true
    File.write('wide-capture-request.txt',name)
    deadline = Process.clock_gettime(Process::CLOCK_MONOTONIC) + 15
    until File.exist?("wide-capture-#{name}.done")
      raise 'screenshot observer timed out' if Process.clock_gettime(Process::CLOCK_MONOTONIC) > deadline
      Graphics.__present(RGSSXP.scene_commands,-1.0,nil,0.0) if Graphics.__should_render
      Graphics.__tick
    end
  end
end
module WideUIFrames
  def update
    super
    WideUIProbe.step
  end
end
Graphics.singleton_class.prepend(WideUIFrames)
