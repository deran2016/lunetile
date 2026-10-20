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
  end
  def draw_tile(commands,id,x,y)
    return unless id && id > 0 && id < 8192
    if id < 2048
      return if id.between?(1024,1535)
      sheet = id >= 1536 ? 4 : 5+id/256
      sx = (id/128%2*8+id%8)*32
      sy = id%256/8%16*32
      RGSSXP.quad(commands,@bitmaps[sheet],x,y,Rect.new(sx,sy,32,32))
      return
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
    return unless quarters
    quarters.each_with_index do |(qx,qy),corner|
      dx,dy = x+corner%2*16,y+corner/2*16
      if sheet == 1 && @flags && (@flags[id].to_i & 0x80) != 0 && [1,5].include?(qy)
        base_x = qy == 1 ? [0,3,2,1][qx] : qx
        RGSSXP.quad(commands,@bitmaps[sheet],dx,dy,Rect.new((bx*2+base_x)*16,(by*2+3)*16,16,16))
        RGSSXP.quad(commands,@bitmaps[sheet],dx,dy+8,Rect.new((bx*2+qx)*16,(by*2+qy)*16,16,8))
      else
        RGSSXP.quad(commands,@bitmaps[sheet],dx,dy,Rect.new((bx*2+qx)*16,(by*2+qy)*16,16,16))
      end
    end
  end
  def layers
    return [] unless @map_data && @map_data.xsize > 0 && @map_data.ysize > 0 && visible
    rect = viewport ? viewport.rect : Rect.new(0,0,Graphics.width,Graphics.height)
    vx,vy = viewport ? [viewport.ox,viewport.oy] : [0,0]
    first_x,first_y = (@ox+vx).div(32),(@oy+vy).div(32)
    lower,upper = [],[]
    ((rect.height+31)/32+1).times do |j|
      ((rect.width+31)/32+1).times do |i|
        mx,my = (first_x+i)%@map_data.xsize,(first_y+j)%@map_data.ysize
        x,y = rect.x+(first_x+i)*32-@ox-vx,rect.y+(first_y+j)*32-@oy-vy
        [3,@map_data.zsize].min.times do |level|
          id = @map_data[mx,my,level]
          commands = @flags && (@flags[id].to_i & 0x10) != 0 ? upper : lower
          draw_tile(commands,id,x,y)
          if level == 1 && @flags
            above = @map_data[mx,(my-1)%@map_data.ysize,1]
            current_table = id.between?(2816,4351) && (@flags[id].to_i & 0x80) != 0
            if above.between?(2816,4351) && (@flags[above].to_i & 0x80) != 0 && !current_table && @map_data[mx,my,0] < 4352
              kind,shape = (above-2048).divmod(48)
              FLOOR[shape][2,2].each_with_index do |(qx,qy),q|
                RGSSXP.quad(lower,@bitmaps[1],x+q*16,y,Rect.new((kind%8*4+qx)*16,((kind/8-2)*6+qy)*16+8,16,8))
              end
            end
          end
          if level == 1 && @map_data.zsize > 3
            shadow = @map_data[mx,my,3] & 15
            if shadow != 0
              unless @vxa_shadow
                @vxa_shadow = Bitmap.new(16,16)
                @vxa_shadow.fill_rect(0,0,16,16,Color.new(0,0,0,128))
              end
              4.times { |q| RGSSXP.quad(lower,@vxa_shadow,x+q%2*16,y+q/2*16,@vxa_shadow.rect) if shadow & (1<<q) != 0 }
            end
          end
        end
      end
    end
    [Layer.new(self,0,lower),Layer.new(self,200,upper)]
  end
  alias vxa_dispose dispose
  def dispose
    @vxa_shadow.dispose if @vxa_shadow && !@vxa_shadow.disposed?
    vxa_dispose
  end
end
