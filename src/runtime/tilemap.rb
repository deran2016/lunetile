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
    @updates += 1 if RGSSXP::Timing.legacy_tick?
  end
  def legacy_layers
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
          else
            bitmap = @autotiles[tile_id/48-1]
            next unless bitmap && !bitmap.disposed?
          end
          sheet,parts = tile_shape(tile_id)
          bitmap = sheet == 0 ? @tileset : @autotiles[sheet-1]
          parts.each do |dx,dy,sx,sy,w,h|
            RGSSXP.quad(commands,bitmap,screen_x+dx,screen_y+dy,Rect.new(sx,sy,w,h))
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
  def tile_shape(id)
    return [0,[[0,0,(id-384)%8*32,(id-384)/8*32,32,32]]] if id >= 384
    sheet = id/48
    bitmap = @autotiles[sheet-1]
    return [sheet,[]] unless bitmap && !bitmap.disposed?
    if bitmap.height == 32
      frame = @updates/16 % [bitmap.width/32,1].max
      [sheet,[[0,0,frame*32,0,32,32]]]
    else
      frame = @updates/16 % [bitmap.width/96,1].max
      [sheet,RGSSXP::AUTOTILE_QUARTERS[id%48].each_with_index.map { |q,c| [c%2*16,c/2*16,frame*96+q%6*16,q/6*16,16,16] }]
    end
  end
  XP_TABLE_READERS = %i[[] xsize ysize zsize].to_h { |name| [name,Table.instance_method(name)] }.freeze
  XP_BITMAP_READERS = %i[width height disposed?].to_h { |name| [name,Bitmap.instance_method(name)] }.freeze
  XP_QUAD = RGSSXP.method(:quad)
  XP_SHAPE = instance_method(:tile_shape)
  def layers
    tables = [@map_data,@priorities,@flash_data]
    return legacy_layers unless tables.each_with_index.all? { |v,i| (i>0 && v.nil?) || (v.instance_of?(Table) && XP_TABLE_READERS.all? { |n,m| v.method(n).unbind == m }) } &&
      @autotiles.instance_of?(Array) && @autotiles.size == 7 && RGSSXP.method(:quad) == XP_QUAD && method(:tile_shape).unbind == XP_SHAPE
    images = [@tileset]+@autotiles
    return legacy_layers unless images.all? { |v| v.nil? || (v.instance_of?(Bitmap) && XP_BITMAP_READERS.all? { |n,m| v.method(n).unbind == m }) }
    return [] unless @map_data.xsize>0 && @map_data.ysize>0 && visible
    rect = viewport ? viewport.rect : Rect.new(0,0,Graphics.width,Graphics.height)
    ox,oy = @ox+(viewport ? viewport.ox : 0),@oy+(viewport ? viewport.oy : 0)
    return legacy_layers unless rect.width>=0 && rect.height>=0 && ox.instance_of?(Integer) && oy.instance_of?(Integer)
    @xp_tile_cache ||= RGSSXP::XPTileCache.new
    cache_started = Process.clock_gettime(Process::CLOCK_MONOTONIC)
    keys = @xp_tile_cache.prepare(tables,ox.div(32),oy.div(32),(rect.width+31)/32+1,(rect.height+31)/32+1,@updates/16,images)
    return legacy_layers unless keys
    keys.each { |id| @xp_tile_cache.shape(id,*tile_shape(id)) }
    @xp_tile_cache.commit
    @cache_prepare_ms = (Process.clock_gettime(Process::CLOCK_MONOTONIC)-cache_started)*1000
    if @flash_data && !@flash_bitmap
      @flash_bitmap = Bitmap.new(32,32)
      @flash_bitmap.fill_rect(@flash_bitmap.rect,Color.new(255,255,255))
    end
    images << @flash_bitmap
    @xp_tile_cache.groups(oy).map { |index,depth| Layer.new(self,depth,[[4,@xp_tile_cache,index,images,rect.x-ox,rect.y-oy,(16-@updates%32).abs*8]]) }
  end
  def dispose
    @xp_tile_cache.dispose if @xp_tile_cache
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
      position = sprite.instance_variable_get(:@weather_position) || [sprite.x.to_f, sprite.y.to_f, sprite.opacity.to_f]
      dx,dy,fade = {1=>[-2,16,8],2=>[-8,16,12],3=>[-2,8,8]}.fetch(@type,[0,0,0])
      scale = RGSSXP::Timing.scale.to_f
      position[0] += dx / scale; position[1] += dy / scale; position[2] -= fade / scale
      sprite.x, sprite.y, sprite.opacity = position.map(&:round)
      sprite.ox, sprite.oy = @ox, @oy
      if sprite.opacity < 64 || sprite.x - @ox < -50 || sprite.x - @ox > (Graphics.width + 110) || sprite.y - @oy < -200 || sprite.y - @oy > (Graphics.height + 120)
        sprite.x, sprite.y, sprite.opacity = rand(Graphics.width + 160)-50+@ox,rand(Graphics.height + 320)-200+@oy,rand(64)+160
        position = [sprite.x.to_f,sprite.y.to_f,sprite.opacity.to_f]
      end
      sprite.instance_variable_set(:@weather_position,position)
    end
  end
  def dispose
    @sprites.each(&:dispose)
    [@rain,@storm,@snow].each(&:dispose)
  end
end
