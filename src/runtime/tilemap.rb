class Tilemap < RGSSXP::DisplayObject
  attr_accessor :tileset, :map_data, :priorities, :flash_data
  attr_reader :autotiles
  Layer = Struct.new(:owner, :z, :commands) do
    def viewport; owner.viewport; end
    def serial; owner.serial; end
    def visible; owner.visible; end
    def disposed?; owner.disposed?; end
    def flash_hidden?; false; end
    def emit(output); output.concat(commands); end
  end
  def initialize(viewport = nil)
    super(viewport)
    @autotiles = Array.new(7)
    @tileset = @map_data = @priorities = @flash_data = nil
    @updates = 0
  end
  def update
    super
    @updates += 1
  end
  def layers
    return [] unless @map_data && @map_data.xsize > 0 && @map_data.ysize > 0 && visible
    rect = viewport ? viewport.rect : Rect.new(0, 0, Graphics.width, Graphics.height)
    vx, vy = viewport ? [viewport.ox, viewport.oy] : [0, 0]
    first_x, first_y = (@ox + vx).div(32), (@oy + vy).div(32)
    groups = {}
    ((rect.height + 31) / 32 + 1).times do |j|
      world_y = first_y + j
      ((rect.width + 31) / 32 + 1).times do |i|
        world_x = first_x + i
        map_x, map_y = world_x % @map_data.xsize, world_y % @map_data.ysize
        screen_x, screen_y = rect.x + world_x * 32 - @ox - vx, rect.y + world_y * 32 - @oy - vy
        @map_data.zsize.times do |level|
          tile_id = @map_data[map_x, map_y, level]
          next unless tile_id && tile_id >= 48
          priority = @priorities && @priorities[tile_id] || 0
          depth = priority > 0 ? screen_y - rect.y + (priority + 1) * 32 : 0
          commands = groups[depth] ||= []
          if tile_id >= 384
            next unless @tileset
            source = Rect.new((tile_id - 384) % 8 * 32, (tile_id - 384) / 8 * 32, 32, 32)
            RGSSXP.quad(commands, @tileset, screen_x, screen_y, source)
          else
            bitmap = @autotiles[tile_id / 48 - 1]
            next unless bitmap && !bitmap.disposed?
            if bitmap.height == 32
              frame = @updates / 16 % [bitmap.width / 32, 1].max
              RGSSXP.quad(commands, bitmap, screen_x, screen_y, Rect.new(frame * 32, 0, 32, 32))
            else
              frame = @updates / 16 % [bitmap.width / 96, 1].max
              RGSSXP::AUTOTILE_QUARTERS[tile_id % 48].each_with_index do |quarter, corner|
                source = Rect.new(frame * 96 + quarter % 6 * 16, quarter / 6 * 16, 16, 16)
                RGSSXP.quad(commands, bitmap, screen_x + corner % 2 * 16, screen_y + corner / 2 * 16, source)
              end
            end
          end
        end
        if @flash_data && (value = @flash_data[map_x, map_y]) && value != 0
          unless @flash_bitmap
            @flash_bitmap = Bitmap.new(32, 32)
            @flash_bitmap.fill_rect(@flash_bitmap.rect, Color.new(255,255,255))
          end
          color = Color.new((value >> 8 & 15) * 17, (value >> 4 & 15) * 17, (value & 15) * 17, 255)
          commands = groups[1000] ||= []
          RGSSXP.quad(commands,@flash_bitmap,screen_x,screen_y,@flash_bitmap.rect,color:color,opacity:(16-@updates%32).abs*8,blend:1)
        end
      end
    end
    groups.map { |depth, commands| Layer.new(self, depth, commands) }
  end
  def dispose
    @flash_bitmap.dispose if @flash_bitmap
    super
  end
end

class RPG::Weather
  attr_accessor :ox, :oy
  attr_reader :type, :max
  def initialize(viewport = nil)
    @ox = @oy = 0
    @type, @max = 0, 0
    @rain = Bitmap.new(7, 56)
    @storm = Bitmap.new(34, 64)
    @snow = Bitmap.new(6, 6)
    7.times { |x| @rain.fill_rect(x, (6-x)*8, 1, 8, Color.new(255,255,255,160)) }
    32.times { |x| @storm.fill_rect(x, (31-x)*2, 3, 2, Color.new(255,255,255,160)) }
    @snow.fill_rect(0,1,6,4,Color.new(255,255,255,192))
    @snow.fill_rect(1,0,4,6,Color.new(255,255,255,192))
    @sprites = Array.new(40) do
      sprite = ::Sprite.new(viewport)
      sprite.z, sprite.opacity, sprite.visible = 1000, 0, false
      sprite
    end
  end
  def type=(value)
    raise ArgumentError, 'Weather type must be 0..3' unless (0..3).include?(value)
    @type = value
    bitmap = [nil,@rain,@storm,@snow][value]
    @sprites.each { |sprite| sprite.bitmap = bitmap }
    value
  end
  def max=(value)
    @max = [[value.to_f, 0].max, 40].min
  end
  def update
    @sprites.each_with_index do |sprite,index|
      sprite.visible = @type != 0 && index < @max.to_i
      next unless sprite.visible
      case @type
      when 1 then sprite.x -= 2; sprite.y += 16; sprite.opacity -= 8
      when 2 then sprite.x -= 8; sprite.y += 16; sprite.opacity -= 12
      when 3 then sprite.x -= 2; sprite.y += 8; sprite.opacity -= 8
      end
      sprite.ox, sprite.oy = @ox, @oy
      if sprite.opacity < 64 || sprite.x - @ox < -50 || sprite.x - @ox > (Graphics.width + 110) || sprite.y - @oy < -200 || sprite.y - @oy > (Graphics.height + 120)
        sprite.x, sprite.y, sprite.opacity = rand(Graphics.width + 160)-50+@ox,rand(Graphics.height + 320)-200+@oy,rand(64)+160
      end
    end
  end
  def dispose
    @sprites.each(&:dispose)
    [@rain,@storm,@snow].each(&:dispose)
  end
end
