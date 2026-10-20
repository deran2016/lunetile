# RGSS3-only API extensions. This file is loaded after the shared RGSS1 runtime.
RGSS_VERSION = '3.0.1'
class Reset < Exception; end unless defined?(Reset)
RGSSReset = Reset unless defined?(RGSSReset)
def rgss_main
  loop do
    begin
      yield
      break
    rescue RGSSReset
      RGSSXP.reset_display
      Graphics.__reset
      Audio.bgm_stop
      Audio.bgs_stop
      Audio.me_stop
      Audio.se_stop
      Graphics.frame_count = 0
      Graphics.brightness = 255
    end
  end
end
def rgss_stop
  loop { Graphics.update }
end
def msgbox(*values); print(*values); end
def msgbox_p(*values); print(*values.map(&:inspect)); end
module RGSSXP::Timing
  def self.scale; Graphics.__stock120 ? 2 : 1; end
  def self.settings_path; 'Saves/LunetileVXA/display.ini'; end
end
module Audio
  class << self
    %i[bgm bgs].each_with_index do |name, channel|
      define_method("#{name}_play") do |filename, volume = 100, pitch = 100, position = 0|
        filename = RGSSXP.text(filename)
        __play_at(channel, filename.tr('\\', '/').downcase, RGSSXP.read_file(filename, EXTENSIONS),
          [[volume.to_int, 0].max, 100].min, [[pitch.to_int, 50].max, 150].min, position.to_int)
      end
      define_method("#{name}_pos") { __position(channel) }
    end
    def setup_midi; __snapshot; nil; end
  end
end
class Color
  alias vxa_set set
  def set(*args)
    args = [args[0].red, args[0].green, args[0].blue, args[0].alpha] if args.size == 1
    vxa_set(*args)
  end
end
class Tone
  alias vxa_set set
  def set(*args)
    args = [args[0].red, args[0].green, args[0].blue, args[0].gray] if args.size == 1
    vxa_set(*args)
  end
end
class Rect
  alias vxa_set set
  def set(*args)
    args = [args[0].x, args[0].y, args[0].width, args[0].height] if args.size == 1
    vxa_set(*args)
  end
end
class Font
  class << self
    attr_accessor :default_shadow, :default_outline, :default_out_color
  end
  self.default_name, self.default_size = ['VL Gothic', 'Arial'], 24
  self.default_shadow, self.default_outline = false, true
  self.default_out_color = Color.new(0, 0, 0, 128)
  attr_accessor :shadow, :outline, :out_color
  alias vxa_initialize initialize
  def initialize(*args)
    vxa_initialize(*args)
    @shadow, @outline = self.class.default_shadow, self.class.default_outline
    @out_color = self.class.default_out_color.clone
  end
  def name=(value)
    candidates = value.is_a?(Array) ? value : [value]
    @name = RGSSXP.text(candidates.find { |name| Font.exist?(name) } || candidates.first || 'Arial')
  end
end
class Bitmap
  def clear_rect(*args)
    fill_rect(*args, Color.new(0,0,0,0))
  end
  def gradient_fill_rect(*args)
    if args[0].is_a?(Rect)
      rect, first, last, vertical = args
    else
      x,y,w,h,first,last,vertical = args
      rect = Rect.new(x,y,w,h)
    end
    length = vertical ? rect.height : rect.width
    length.times do |i|
      ratio = length > 1 ? i.to_f / (length - 1) : 0
      color = Color.new(*%i[red green blue alpha].map { |field| first.public_send(field) * (1-ratio) + last.public_send(field) * ratio })
      fill_rect(rect.x + (vertical ? 0 : i), rect.y + (vertical ? i : 0), vertical ? rect.width : 1, vertical ? 1 : rect.height, color)
    end
  end
end
class RGSSXP::DisplayObject
  def viewport=(value)
    raise TypeError, 'Expected Viewport or nil' unless value.nil? || value.is_a?(Viewport)
    @viewport = value
  end
end
class Sprite
  attr_accessor :wave_amp, :wave_length, :wave_speed, :wave_phase, :bush_opacity
  alias vxa_initialize initialize
  def initialize(viewport = nil)
    vxa_initialize(viewport)
    @wave_amp, @wave_length, @wave_speed, @wave_phase, @bush_opacity = 0, 180, 360, 0.0, 128
  end
  alias vxa_update update
  def update
    vxa_update
    @wave_phase = (@wave_phase + @wave_speed.to_f / Graphics.frame_rate) % 360
  end
end
class Window
  attr_accessor :padding, :padding_bottom, :arrows_visible
  attr_reader :openness
  alias vxa_initialize initialize
  def initialize(x = 0, y = 0, width = 0, height = 0)
    vxa_initialize
    @x, @y, @width, @height = x, y, width, height
    @padding = @padding_bottom = 12
    @openness, @arrows_visible, @back_opacity = 255, true, 192
    @contents = Bitmap.new(1,1)
    @tone = Tone.new(0,0,0)
    @z = 100
  end
  def openness=(value); @openness = [[value.to_int,0].max,255].min; end
  def open?; @openness == 255; end
  def close?; @openness == 0; end
  def move(x,y,width,height); @x,@y,@width,@height=x,y,width,height; self; end
  def emit(commands)
    return if @width <= 0 || @height <= 0 || @openness == 0
    dx,dy = screen_offset
    x,y,w,h = @x+dx,@y+dy,@width,@height*@openness/255.0
    y += (@height-h)/2
    if @windowskin && !@windowskin.disposed?
      skin_quad(commands,0,0,64,64,x+2,y+2,w-4,h-4,@opacity*@back_opacity/255)
      [[64,0,x,y],[112,0,x+w-16,y],[64,48,x,y+h-16],[112,48,x+w-16,y+h-16]].each do |sx,sy,tx,ty|
        skin_quad(commands,sx,sy,16,16,tx,ty,16,16,@opacity)
      end
      [[80,0,32,16,x+16,y,w-32,16],[80,48,32,16,x+16,y+h-16,w-32,16],
       [64,16,16,32,x,y+16,16,h-32],[112,16,16,32,x+w-16,y+16,16,h-32]].each do |sx,sy,sw,sh,tx,ty,tw,th|
        skin_quad(commands,sx,sy,sw,sh,tx,ty,tw,th,@opacity)
      end
    end
    return unless open?
    area = Rect.new(x+@padding,y+@padding,[w-@padding*2,0].max,[@height-@padding-@padding_bottom,0].max)
    if @windowskin && @cursor_rect.width > 0 && @cursor_rect.height > 0
      pulse = @active ? 128 + ((@updates % 32 - 16).abs * 8) : 128
      RGSSXP.quad(commands,@windowskin,x+@padding+@cursor_rect.x-@ox,y+@padding+@cursor_rect.y-@oy,
        Rect.new(64,64,32,32),zoom_x:@cursor_rect.width/32.0,zoom_y:@cursor_rect.height/32.0,opacity:pulse*@opacity/255,clip:area)
    end
    if @contents && !@contents.disposed?
      RGSSXP.quad(commands,@contents,x+@padding-@ox,y+@padding-@oy,@contents.rect,opacity:@contents_opacity,clip:area)
      if @windowskin && @arrows_visible
        skin_quad(commands,88,16,16,8,x+w/2-8,y+4,16,8,@opacity) if @oy > 0
        skin_quad(commands,88,40,16,8,x+w/2-8,y+h-12,16,8,@opacity) if @contents.height-@oy > area.height
      end
    end
    skin_quad(commands,96+(@updates/8%2)*16,64+(@updates/16%2)*16,16,16,x+w/2-8,y+h-16,16,16,@opacity) if @pause && @windowskin
  end
end
module Graphics
  class << self
    def wait(duration); [duration.to_int,0].max.times { update }; end
    def fadeout(duration)
      start = brightness
      [duration.to_int,0].max.times { |i| self.brightness = start*(duration-i-1)/duration; update }
      self.brightness = 0
    end
    def fadein(duration)
      start = brightness
      [duration.to_int,0].max.times { |i| self.brightness = start+(255-start)*(i+1)/duration; update }
      self.brightness = 255
    end
    def play_movie(filename)
      __play_movie(RGSSXP.resolve_file(filename, ['.ogv']))
    end
  end
end
module Graphics
  @brightness = 255
  class << self
    attr_reader :brightness
    def brightness=(value); @brightness = [[value.to_int,0].max,255].min; end
    def snap_to_bitmap; __snapshot; end
  end
end
module RGSSXP
  class << self
    alias vxa_scene_commands scene_commands
    def scene_commands
      commands = vxa_scene_commands
      if Graphics.brightness < 255
        if !@vxa_black || @vxa_black.disposed?
          @vxa_black = Bitmap.new(1,1)
          @vxa_black.fill_rect(0,0,1,1,Color.new(0,0,0))
        end
        quad(commands,@vxa_black,0,0,@vxa_black.rect,zoom_x:Graphics.width,zoom_y:Graphics.height,opacity:255-Graphics.brightness)
      end
      commands
    end
  end
end
class Sprite
  def width; @src_rect.width; end
  def height; @src_rect.height; end
end
class Bitmap
  def blur; __blur; end
  def radial_blur(angle, division); __radial_blur(angle,division); end
  alias vxa_draw_text draw_text
  def draw_text(*args)
    if args[0].is_a?(Rect)
      rect,text,align = args
      args = [rect.x,rect.y,rect.width,rect.height,text,align || 0]
    end
    x,y,w,h,text,align = args
    if @font.outline || @font.shadow
      color = @font.color.clone
      begin
        @font.color = @font.out_color
        offsets = @font.outline ? [[-1,0],[1,0],[0,-1],[0,1]] : [[1,1]]
        offsets.each { |dx,dy| __text(RGSSXP.text(text.to_s),@font,[x+dx,y+dy,w,h,align || 0,false]) }
      ensure
        @font.color = color
      end
    end
    vxa_draw_text(*args)
  end
end
class Rect
  def initialize(x = 0,y = 0,width = 0,height = 0); set(x,y,width,height); end
end
class Color
  def initialize(*components)
    components = [0,0,0,0] if components.empty?
    set(*components)
  end
end
class Tone
  def initialize(red = 0,green = 0,blue = 0,gray = 0); set(red,green,blue,gray); end
end
class Viewport
  alias vxa_initialize initialize
  def initialize(*args)
    args = [0,0,Graphics.width,Graphics.height] if args.empty?
    vxa_initialize(*args)
  end
end
module Graphics
  class << self
    alias vxa_wait wait
    alias vxa_fadein fadein
    alias vxa_fadeout fadeout
    def wait(duration); vxa_wait(duration*RGSSXP::Timing.scale); end
    def fadein(duration); vxa_fadein(duration*RGSSXP::Timing.scale); end
    def fadeout(duration); vxa_fadeout(duration*RGSSXP::Timing.scale); end
  end
end
class Sprite
  alias vxa_emit emit
  def emit(commands)
    return vxa_emit(commands) if @wave_amp == 0 || !@bitmap || @bitmap.disposed?
    dx,dy = screen_offset
    length = [@wave_length.to_f,1.0].max
    (0...@src_rect.height).step(8) do |row|
      offset = @wave_amp * Math.sin((@wave_phase + row*360.0/length)*Math::PI/180)
      source = Rect.new(@src_rect.x,@src_rect.y+row,@src_rect.width,[8,@src_rect.height-row].min)
      RGSSXP.quad(commands,@bitmap,@x+dx+offset,@y+dy+row*@zoom_y,source,
        zoom_x:@zoom_x,zoom_y:@zoom_y,angle:@angle,ox:@ox,oy:@oy,opacity:@opacity,
        blend:@blend_type,color:effective_color,tone:@tone,bush:@bush_depth,mirror:@mirror)
    end
  end
end
class Window
  def skin_quad(commands,sx,sy,sw,sh,x,y,w,h,opacity)
    return if w <= 0 || h <= 0
    RGSSXP.quad(commands,@windowskin,x,y,Rect.new(sx,sy,sw,sh),zoom_x:w.to_f/sw,zoom_y:h.to_f/sh,opacity:opacity,tone:@tone)
  end
end
