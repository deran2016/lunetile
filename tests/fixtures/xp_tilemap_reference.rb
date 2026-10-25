# Frozen alpha.14 geometry oracle; do not derive it from the optimized path.
class ReferenceTilemap < RGSSXP::DisplayObject
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
    @updates += 1 if RGSSXP::Timing.legacy_tick?
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
