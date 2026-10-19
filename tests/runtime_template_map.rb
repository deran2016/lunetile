# Walk the packaged map through normal Game_Player updates before the stock story.
Graphics.render_rate = File.read('refresh-test-rate.txt').to_i if File.exist?('refresh-test-rate.txt')
module TemplateMapProbe
  @targets = [[0,0],[39,0],[39,22],[0,22],[9,7]]
  @direction,@index,@ticks,@settle = 0,0,0,0
  @samples = []
  class << self
    attr_reader :direction
    def check_large_map
      original_map = $game_map.instance_variable_get(:@map)
      original_display = [$game_map.display_x,$game_map.display_y]
      map = RPG::Map.new(80,45)
      colors = [[180,40,60,255],[40,180,60,255],[40,60,180,255]]
      45.times { |y| 80.times { |x| map.data[x,y,0] = 384+(x/20+y/15)%3 } }
      viewport = Viewport.new(0,0,1280,720)
      viewport.z = 10000
      tiles = Tilemap.new(viewport)
      bitmap = Bitmap.new(256,32)
      colors.each_with_index { |rgba,i| bitmap.fill_rect(i*32,0,32,32,Color.new(*rgba)) }
      tiles.tileset,tiles.map_data = bitmap,map.data
      $game_map.instance_variable_set(:@map,map)
      cameras = [[0,0],[79,44],[40,22]].map do |x,y|
        $game_player.center(x,y)
        tiles.ox,tiles.oy = $game_map.display_x/4,$game_map.display_y/4
        Graphics.__present(RGSSXP.scene_commands,-1.0,nil,0.0)
        [[0,0],[1279,719]].each do |px,py|
          expected = colors[((px+tiles.ox)/32/20+(py+tiles.oy)/32/15)%3]
          raise 'Large-map tile scroll mismatch' unless Graphics.__scene_pixel(px,py) == expected
        end
        [$game_map.display_x,$game_map.display_y]
      end
      raise 'Large-map camera limits changed' unless cameras.first(2) == [[0,0],[5120,2880]]
      File.write('template-large-map-checked.txt',cameras.inspect)
    ensure
      tiles&.dispose
      bitmap&.dispose
      viewport&.dispose
      $game_map.instance_variable_set(:@map,original_map)
      $game_map.display_x,$game_map.display_y = original_display
    end
    def step
      unless @large_checked
        check_large_map
        @large_checked = true
      end
      @ticks += 1
      raise 'Map walk timed out' if @ticks > 7000
      raise 'Template map/table dimensions changed' unless
        [$game_map.width,$game_map.height] == [40,23] &&
        [$game_map.data.xsize,$game_map.data.ysize,$game_map.data.zsize] == [40,23,3]
      raise 'Map viewport does not fill wide screen' unless Lunetile.map_rect == [0,0,1280,720]
      raise 'Camera left the 16px vertical scroll range' unless
        $game_map.display_x == 0 && $game_map.display_y.between?(0,64)
      raise 'Player escaped map' unless $game_player.x.between?(0,39) && $game_player.y.between?(0,22)
      @direction = 0
      return false if $game_player.moving?
      target = @targets[@index]
      if [$game_player.x,$game_player.y] != target
        @direction = if $game_player.x != target[0]
          $game_player.x < target[0] ? 6 : 4
        else
          $game_player.y < target[1] ? 2 : 8
        end
        return false
      end
      @settle += 1
      return false if @settle < 6 * RGSSXP::Timing.scale
      if @index < 4
        directions = [[4,8],[6,8],[6,2],[4,2]][@index]
        attempt = (@settle - 6 * RGSSXP::Timing.scale) / (8 * RGSSXP::Timing.scale)
        if attempt < 2
          @direction = directions[attempt]
          return false
        end
      end
      pixels = [[640,0],[1279,360],[640,719],[0,360]].map do |x,y|
        pixel = Graphics.__scene_pixel(x,y)
        tile = RPG::Cache.tileset($game_map.tileset_name).get_pixel(x%32,(y+$game_map.display_y/4)%32)
        expected = [tile.red,tile.green,tile.blue,tile.alpha].map(&:to_i)
        raise "Map edge is blank or misaligned at #{x},#{y}: #{pixel} != #{expected}" unless pixel == expected
        pixel
      end
      @samples << [target,[$game_map.display_x,$game_map.display_y],pixels]
      WideUIProbe.capture("Map_corner_#{@index}") if defined?(WideUIProbe)
      @index += 1
      @settle = 0
      return false if @index < @targets.size
      File.write('template-map-checked.txt',@samples.inspect)
      true
    end
  end
end
module TemplateMapDirections
  def dir4
    TemplateMapProbe.direction != 0 ? TemplateMapProbe.direction : super
  end
end
module TemplateMapScenario
  def step
    if !@template_map_checked && @phase == :map && $scene.is_a?(Scene_Map)
      @button = nil
      return unless TemplateMapProbe.step
      @template_map_checked = true
    end
    super
  end
end
Input.singleton_class.prepend(TemplateMapDirections)
ScenarioDriver.singleton_class.prepend(TemplateMapScenario)
