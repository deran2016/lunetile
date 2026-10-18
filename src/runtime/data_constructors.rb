class RPG::AudioFile
  def initialize(name = '', volume = 100, pitch = 100)
    @name, @volume, @pitch = name, volume, pitch
  end
end

class RPG::EventCommand
  def initialize(code = 0, indent = 0, parameters = [])
    @code, @indent, @parameters = code, indent, parameters
  end
end

class RPG::MoveCommand
  def initialize(code = 0, parameters = [])
    @code, @parameters = code, parameters
  end
end

class RPG::MoveRoute
  def initialize
    @repeat, @skippable, @list = true, false, [RPG::MoveCommand.new]
  end
end

class RPG::Map
  def initialize(width, height)
    @tileset_id, @width, @height = 1, width, height
    @autoplay_bgm = @autoplay_bgs = false
    @bgm, @bgs = RPG::AudioFile.new, RPG::AudioFile.new('',80)
    @encounter_list, @encounter_step, @events = [], 30, {}
    @data = Table.new(width, height, 3)
  end
end
class RPG::MapInfo
  def initialize
    @name, @parent_id, @order, @expanded, @scroll_x, @scroll_y = '', 0, 0, false, 0, 0
  end
end
class RPG::Event
  def initialize(x, y)
    @id, @name, @x, @y, @pages = 0, '', x, y, [RPG::Event::Page.new]
  end
end
class RPG::Event::Page
  def initialize
    @condition, @graphic = Condition.new, Graphic.new
    @move_type, @move_speed, @move_frequency, @move_route = 0, 3, 3, RPG::MoveRoute.new
    @walk_anime, @step_anime, @direction_fix, @through, @always_on_top = true, false, false, false, false
    @trigger, @list = 0, [RPG::EventCommand.new]
  end
end
class RPG::Event::Page::Condition
  def initialize
    @switch1_valid = @switch2_valid = @variable_valid = @self_switch_valid = false
    @switch1_id = @switch2_id = @variable_id = 1
    @variable_value, @self_switch_ch = 0, 'A'
  end
end
class RPG::Event::Page::Graphic
  def initialize
    @tile_id, @character_name, @character_hue, @direction, @pattern, @opacity, @blend_type = 0, '', 0, 2, 0, 255, 0
  end
end
class RPG::CommonEvent
  def initialize
    @id, @name, @trigger, @switch_id, @list = 0, '', 0, 1, [RPG::EventCommand.new]
  end
end
