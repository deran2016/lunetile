# RGSS3 tile IDs and quarter coordinates (32px cells, 16px quarters).
class Tilemap
  attr_accessor :flags
  attr_reader :bitmaps
  FLOOR = [
    [[2,4],[1,4],[2,3],[1,3]],[[2,0],[1,4],[2,3],[1,3]],
    [[2,4],[3,0],[2,3],[1,3]],[[2,0],[3,0],[2,3],[1,3]],
    [[2,4],[1,4],[2,3],[3,1]],[[2,0],[1,4],[2,3],[3,1]],
    [[2,4],[3,0],[2,3],[3,1]],[[2,0],[3,0],[2,3],[3,1]],
    [[2,4],[1,4],[2,1],[1,3]],[[2,0],[1,4],[2,1],[1,3]],
    [[2,4],[3,0],[2,1],[1,3]],[[2,0],[3,0],[2,1],[1,3]],
    [[2,4],[1,4],[2,1],[3,1]],[[2,0],[1,4],[2,1],[3,1]],
    [[2,4],[3,0],[2,1],[3,1]],[[2,0],[3,0],[2,1],[3,1]],
    [[0,4],[1,4],[0,3],[1,3]],[[0,4],[3,0],[0,3],[1,3]],
    [[0,4],[1,4],[0,3],[3,1]],[[0,4],[3,0],[0,3],[3,1]],
    [[2,2],[1,2],[2,3],[1,3]],[[2,2],[1,2],[2,3],[3,1]],
    [[2,2],[1,2],[2,1],[1,3]],[[2,2],[1,2],[2,1],[3,1]],
    [[2,4],[3,4],[2,3],[3,3]],[[2,4],[3,4],[2,1],[3,3]],
    [[2,0],[3,4],[2,3],[3,3]],[[2,0],[3,4],[2,1],[3,3]],
    [[2,4],[1,4],[2,5],[1,5]],[[2,0],[1,4],[2,5],[1,5]],
    [[2,4],[3,0],[2,5],[1,5]],[[2,0],[3,0],[2,5],[1,5]],
    [[0,4],[3,4],[0,3],[3,3]],[[2,2],[1,2],[2,5],[1,5]],
    [[0,2],[1,2],[0,3],[1,3]],[[0,2],[1,2],[0,3],[3,1]],
    [[2,2],[3,2],[2,3],[3,3]],[[2,2],[3,2],[2,1],[3,3]],
    [[2,4],[3,4],[2,5],[3,5]],[[2,0],[3,4],[2,5],[3,5]],
    [[0,4],[1,4],[0,5],[1,5]],[[0,4],[3,0],[0,5],[1,5]],
    [[0,2],[3,2],[0,3],[3,3]],[[0,2],[1,2],[0,5],[1,5]],
    [[0,4],[3,4],[0,5],[3,5]],[[2,2],[3,2],[2,5],[3,5]],
    [[0,2],[3,2],[0,5],[3,5]],[[0,0],[1,0],[0,1],[1,1]]
  ].freeze
  WALL = Array.new(16) do |shape|
    left,top,right,bottom = [1,2,4,8].map { |bit| (shape & bit) != 0 }
    [[left ? 0 : 2,top ? 0 : 2],[right ? 3 : 1,top ? 0 : 2],
     [left ? 0 : 2,bottom ? 3 : 1],[right ? 3 : 1,bottom ? 3 : 1]]
  end.freeze
  WATERFALL = Array.new(4) do |shape|
    [[shape&1 == 1 ? 0 : 2,0],[shape&2 == 2 ? 3 : 1,0],
     [shape&1 == 1 ? 0 : 2,1],[shape&2 == 2 ? 3 : 1,1]]
  end.freeze
  alias vxa_initialize initialize
  def initialize(viewport = nil)
    vxa_initialize(viewport)
    @bitmaps = Array.new(9)
    @flags = nil
    @tile_shapes = {}
    @animated_shapes = {}
  end
  def tile_quad(commands,bitmap,x,y,sx,sy,w,h)
    return unless bitmap && !bitmap.disposed?
    commands << [0,bitmap,x,y,w,h,sx,sy,w,h,1.0,1.0,0.0,0,0,255,0,nil,nil,0,nil,false]
  end
  def draw_tile(commands,id,x,y)
    return unless id && id > 0 && id < 8192
    table_flag = id.between?(2816,4351) && @flags && (@flags[id].to_i & 0x80) != 0
    key = id + (table_flag ? 8192 : 0)
    if id.between?(2048,2815)
      phase = @updates/30
      if @tile_phase != phase
        @animated_shapes.clear
        @tile_phase = phase
      end
      cache = @animated_shapes
    else
      cache = @tile_shapes
    end
    sheet,parts = cache[key] ||= tile_shape(id,table_flag)
    bitmap = @bitmaps[sheet]
    return unless bitmap && !bitmap.disposed?
    RGSSXP.__tile_quads(commands,bitmap,x,y,parts)
  end
  def tile_shape(id,table_flag)
    if id < 2048
      return [0,[]] if id.between?(1024,1535)
      sheet = id >= 1536 ? 4 : 5+id/256
      sx = (id/128%2*8+id%8)*32
      sy = id%256/8%16*32
      return [sheet,[[0,0,sx,sy,32,32]]]
    end
    kind, shape = (id-2048).divmod(48)
    tx,ty = kind%8,kind/8
    table = FLOOR
    if id < 2816
      sheet = 0
      water = [0,1,2,1][@updates/30%4]
      if kind < 4
        bx = kind < 2 ? water*2 : 6
        by = kind%2*3
      else
        bx,by = tx/4*8,ty*6+tx/2%2*3
        if kind.even?
          bx += water*2
        else
          bx += 6
          by += @updates/30%3
          table = WATERFALL
        end
      end
    elsif id < 4352
      sheet,bx,by = 1,tx*2,(ty-2)*3
    elsif id < 5888
      sheet,bx,by,table = 2,tx*2,(ty-6)*2,WALL
    else
      sheet,bx,by = 3,tx*2,((ty-10)*2.5+(ty.odd? ? 0.5 : 0)).floor
      table = WALL if ty.odd?
    end
    quarters = table[shape]
    return [sheet,[]] unless quarters
    parts = []
    quarters.each_with_index do |(qx,qy),corner|
      dx,dy = corner%2*16,corner/2*16
      if sheet == 1 && table_flag && [1,5].include?(qy)
        base_x = qy == 1 ? [0,3,2,1][qx] : qx
        parts << [dx,dy,(bx*2+base_x)*16,(by*2+3)*16,16,16]
        parts << [dx,dy+8,(bx*2+qx)*16,(by*2+qy)*16,16,8]
      else
        parts << [dx,dy,(bx*2+qx)*16,(by*2+qy)*16,16,16]
      end
    end
    [sheet,parts]
  end
  def legacy_layers
    map,flags = @map_data,@flags
    return [] unless map && map.xsize > 0 && map.ysize > 0 && visible
    rect = viewport ? viewport.rect : Rect.new(0,0,Graphics.width,Graphics.height)
    vx,vy = viewport ? [viewport.ox,viewport.oy] : [0,0]
    ox,oy = @ox+vx,@oy+vy
    first_x,first_y = ox.div(32),oy.div(32)
    width,height,levels = map.xsize,map.ysize,[3,map.zsize].min
    left,top,columns,rows = rect.x,rect.y,(rect.width+31)/32+1,(rect.height+31)/32+1
    lower,upper = [],[]
    shadows = map.zsize > 3
    j = 0
    while j < rows
      my = (first_y+j)%height
      above_y = (my-1)%height
      y = top+(first_y+j)*32-oy
      i = 0
      while i < columns
        mx = (first_x+i)%width
        x = left+(first_x+i)*32-ox
        level = 0
        while level < levels
          id = map[mx,my,level]
          if id && id > 0
            commands = flags && (flags[id].to_i & 0x10) != 0 ? upper : lower
            draw_tile(commands,id,x,y)
          end
          if level == 1 && flags
            above = map[mx,above_y,1]
            if above.between?(2816,4351) && (flags[above].to_i & 0x80) != 0 &&
                !(id.between?(2816,4351) && (flags[id].to_i & 0x80) != 0) && map[mx,my,0] < 4352
              kind,shape = (above-2048).divmod(48)
              FLOOR[shape][2,2].each_with_index do |(qx,qy),q|
                tile_quad(lower,@bitmaps[1],x+q*16,y,(kind%8*4+qx)*16,((kind/8-2)*6+qy)*16+8,16,8)
              end
            end
          end
          if level == 1 && shadows
            shadow = map[mx,my,3] & 15
            if shadow != 0
              unless @vxa_shadow
                @vxa_shadow = Bitmap.new(16,16)
                @vxa_shadow.fill_rect(0,0,16,16,Color.new(0,0,0,128))
              end
              4.times { |q| tile_quad(lower,@vxa_shadow,x+q%2*16,y+q/2*16,0,0,16,16) if shadow & (1<<q) != 0 }
            end
          end
          level += 1
        end
        i += 1
      end
      j += 1
    end
    [Layer.new(self,0,lower),Layer.new(self,200,upper)]
  end
  alias vxa_dispose dispose
  def dispose
    @tile_cache.dispose if @tile_cache
    @vxa_shadow.dispose if @vxa_shadow && !@vxa_shadow.disposed?
    @tile_shapes.clear
    @animated_shapes.clear
    vxa_dispose
  end
  CACHE_TABLE_READERS = %i[[] xsize ysize zsize].to_h { |name| [name,Table.instance_method(name)] }.freeze
  CACHE_SHAPE = instance_method(:tile_shape)
  CACHE_DRAW = instance_method(:draw_tile)
  def native_table?(value)
    value.instance_of?(Table) && CACHE_TABLE_READERS.all? { |name,original| value.method(name).unbind == original }
  end
  def layers
    return legacy_layers unless native_table?(@map_data) && (@flags.nil? || native_table?(@flags)) &&
      @bitmaps.instance_of?(Array) && @bitmaps.size == 9 && @bitmaps.all? { |bitmap| bitmap.nil? || bitmap.instance_of?(Bitmap) } &&
      method(:tile_shape).unbind == CACHE_SHAPE && method(:draw_tile).unbind == CACHE_DRAW
    return [] unless @map_data.xsize > 0 && @map_data.ysize > 0 && visible
    rect = viewport ? viewport.rect : Rect.new(0,0,Graphics.width,Graphics.height)
    ox,oy = @ox+(viewport ? viewport.ox : 0),@oy+(viewport ? viewport.oy : 0)
    return legacy_layers if rect.width<0 || rect.height<0
    @tile_cache ||= RGSSXP::TileCache.new
    cache_started = Process.clock_gettime(Process::CLOCK_MONOTONIC)
    keys = @tile_cache.prepare(@map_data,@flags,ox.div(32),oy.div(32),(rect.width+31)/32+1,(rect.height+31)/32+1,@updates/30)
    return legacy_layers unless keys
    keys.each do |key|
      sheet,parts = tile_shape(key%8192,key>=8192)
      @tile_cache.shape(key,sheet,parts)
    end
    @tile_cache.commit
    @cache_prepare_ms = (Process.clock_gettime(Process::CLOCK_MONOTONIC)-cache_started)*1000
    unless @vxa_shadow && !@vxa_shadow.disposed?
      @vxa_shadow = Bitmap.new(16,16)
      @vxa_shadow.fill_rect(0,0,16,16,Color.new(0,0,0,128))
    end
    images = @bitmaps+[@vxa_shadow]
    [Layer.new(self,0,[[3,@tile_cache,0,images,rect.x-ox,rect.y-oy]]),
     Layer.new(self,200,[[3,@tile_cache,1,images,rect.x-ox,rect.y-oy]])]
  end
end
