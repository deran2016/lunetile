class Font
  class << self
    attr_accessor :default_name, :default_size, :default_bold, :default_italic, :default_color
  end
  self.default_name, self.default_size = 'Arial', 22
  self.default_bold, self.default_italic = false, false
  self.default_color = Color.new(255, 255, 255)
  attr_reader :name, :size, :color
  attr_accessor :bold, :italic
  def initialize(name = self.class.default_name, size = self.class.default_size)
    self.name, self.size = name, size
    @bold, @italic, @color = self.class.default_bold, self.class.default_italic, self.class.default_color.clone
  end
  def name=(value)
    @name = RGSSXP.text(value).dup
  end
  def size=(value)
    value = value.to_int
    raise ArgumentError, 'Font size must be 6..96' unless value.between?(6, 96)
    @size = value
  end
  def color=(value)
    raise TypeError, 'Expected Color' unless value.is_a?(Color)
    @color.set(value.red, value.green, value.blue, value.alpha)
    value
  end
  def initialize_copy(other)
    super
    @name, @color = other.name.dup, other.color.clone
  end
end

class Bitmap
  attr_reader :font
  def initialize(*args)
    if args.size == 1 && args[0].is_a?(String)
      __decode(RGSSXP.read_file(args[0], %w[.png .jpg .jpeg .bmp]))
    elsif args.size == 2
      __empty(*args)
    else
      raise ArgumentError, 'Bitmap requires a filename or width, height'
    end
    @font = Font.new
  end
  def font=(value)
    raise TypeError, 'Expected Font' unless value.is_a?(Font)
    @font = value.clone
  end
  def rect
    Rect.new(0, 0, width, height)
  end
  def initialize_copy(other)
    __copy(other)
    @font = other.font.clone
  end
  def fill_rect(*args)
    args = [args[0].x, args[0].y, args[0].width, args[0].height, args[1]] if args.size == 2 && args[0].is_a?(Rect)
    __fill(*args)
  end
  def clear
    fill_rect(rect, Color.new(0, 0, 0, 0))
  end
  def blt(x, y, source, source_rect, opacity = 255)
    __blt([x, y, source_rect.width, source_rect.height, source, source_rect.x, source_rect.y, source_rect.width, source_rect.height, opacity])
  end
  def stretch_blt(target_rect, source, source_rect, opacity = 255)
    __blt([target_rect.x, target_rect.y, target_rect.width, target_rect.height, source, source_rect.x, source_rect.y, source_rect.width, source_rect.height, opacity])
  end
  def draw_text(*args)
    if args[0].is_a?(Rect)
      rect, text, align = args
      args = [rect.x, rect.y, rect.width, rect.height, text, align || 0]
    end
    raise ArgumentError, 'Invalid draw_text arguments' unless [5, 6].include?(args.size)
    x, y, w, h, text, align = args
    __text(RGSSXP.text(text.to_s), @font, [x, y, w, h, align || 0, false])
    nil
  end
  def text_size(text)
    w, h = __text(RGSSXP.text(text.to_s), @font, [0, 0, 0, 0, 0, true])
    Rect.new(0, 0, w, h)
  end
end

module RGSSXP
  @nodes = ObjectSpace::WeakMap.new
  @serial = 0
  def self.register(node)
    @serial += 1
    @nodes[node] = @serial
    @serial
  end
  def self.quad(commands, bitmap, x, y, source, options = {})
    return unless bitmap && !bitmap.disposed? && source.width > 0 && source.height > 0
    commands << [0, bitmap, x, y, source.width, source.height, source.x, source.y, source.width, source.height,
      options.fetch(:zoom_x, 1.0), options.fetch(:zoom_y, 1.0), options.fetch(:angle, 0.0), options.fetch(:ox, 0), options.fetch(:oy, 0),
      options.fetch(:opacity, 255), options.fetch(:blend, 0), options[:color], options[:tone], options.fetch(:bush, 0), options[:clip], options.fetch(:mirror, false)]
  end
  def self.scene_commands
    nodes = @nodes.keys.reject(&:disposed?).flat_map { |node| node.is_a?(Tilemap) ? node.layers : [node] }
    roots = nodes.select { |node| node.is_a?(Viewport) || node.viewport.nil? }
    commands = []
    roots.sort_by { |node| [node.z, node.is_a?(Sprite) ? node.y : 0, node.serial] }.each do |node|
      next unless node.visible && !node.flash_hidden?
      if node.is_a?(Viewport)
        commands << [1, node.rect]
        nodes.select { |child| !child.is_a?(Viewport) && child.viewport.equal?(node) }.
          sort_by { |child| [child.z, child.is_a?(Sprite) ? child.y : 0, child.serial] }.
          each { |child| child.emit(commands) if child.visible && !child.flash_hidden? }
        commands << [2, node.rect, node.effective_color, node.tone]
      else
        node.emit(commands)
      end
    end
    commands
  end
  def self.reset_display
    @nodes.keys.each { |node| node.dispose unless node.disposed? }
    ObjectSpace.each_object(Bitmap) { |bitmap| bitmap.dispose unless bitmap.disposed? }
    @nodes = ObjectSpace::WeakMap.new
    @serial = 0
    nil
  end
end

class RGSSXP::DisplayObject
  attr_reader :serial, :viewport, :color, :tone
  def initialize(viewport = nil)
    raise TypeError, 'Expected Viewport or nil' unless viewport.nil? || viewport.is_a?(Viewport)
    @viewport, @disposed = viewport, false
    @serial = RGSSXP.register(self)
    @x = @y = @z = @ox = @oy = @bush_depth = @blend_type = 0
    @zoom_x = @zoom_y = 1.0
    @angle = 0.0
    @visible, @mirror, @opacity = true, false, 255
    @color, @tone = Color.new(0, 0, 0, 0), Tone.new(0, 0, 0, 0)
    @flash_left = @flash_total = 0
  end
  def dispose
    @disposed = true
    nil
  end
  def disposed?
    @disposed
  end
  def check_live
    raise RGSSError, "disposed #{self.class}" if @disposed
  end
  %i[x y z ox oy bush_depth].each do |field|
    variable = :"@#{field}"
    define_method(field) { check_live; instance_variable_get(variable) }
    define_method("#{field}=") { |value| check_live; instance_variable_set(variable, value.to_int) }
  end
  %i[zoom_x zoom_y angle].each do |field|
    variable = :"@#{field}"
    define_method(field) { check_live; instance_variable_get(variable) }
    define_method("#{field}=") do |value|
      check_live
      value = Float(value)
      raise ArgumentError, 'Non-finite display property' unless value.finite?
      instance_variable_set(variable, value)
    end
  end
  %i[visible mirror].each do |field|
    variable = :"@#{field}"
    define_method(field) { check_live; instance_variable_get(variable) }
    define_method("#{field}=") { |value| check_live; instance_variable_set(variable, !!value) }
  end
  def opacity
    check_live; @opacity
  end
  def opacity=(value)
    check_live; @opacity = [[value.to_int, 0].max, 255].min
  end
  def blend_type
    check_live; @blend_type
  end
  def blend_type=(value)
    check_live
    raise ArgumentError, 'Blend type must be 0, 1 or 2' unless (0..2).include?(value)
    @blend_type = value
  end
  def color=(value)
    check_live; @color.set(value.red, value.green, value.blue, value.alpha)
  end
  def tone=(value)
    check_live; @tone.set(value.red, value.green, value.blue, value.gray)
  end
  def flash(color, duration)
    check_live
    @flash_color, @flash_left, @flash_total = color && color.clone, duration.to_int, duration.to_int
    nil
  end
  def update
    check_live
    @flash_left -= 1 if @flash_left > 0
    nil
  end
  def flash_hidden?
    @flash_left > 0 && @flash_color.nil?
  end
  def effective_color
    @flash_left > 0 && @flash_color ? Color.new(@flash_color.red, @flash_color.green, @flash_color.blue, @flash_color.alpha * @flash_left / @flash_total) : @color
  end
  def screen_offset
    @viewport ? [@viewport.rect.x - @viewport.ox, @viewport.rect.y - @viewport.oy] : [0, 0]
  end
end

class Viewport < RGSSXP::DisplayObject
  attr_reader :rect
  def initialize(*args)
    super(nil)
    args = [args[0].x, args[0].y, args[0].width, args[0].height] if args.size == 1 && args[0].is_a?(Rect)
    @rect = Rect.new(*args)
  end
  def rect=(value)
    check_live; @rect.set(value.x, value.y, value.width, value.height)
  end
end

class Sprite < RGSSXP::DisplayObject
  attr_reader :bitmap, :src_rect
  def initialize(viewport = nil)
    super(viewport)
    @bitmap, @src_rect = nil, Rect.new(0, 0, 0, 0)
  end
  def bitmap=(value)
    check_live
    raise TypeError, 'Expected Bitmap or nil' unless value.nil? || value.is_a?(Bitmap)
    @bitmap = value
    @src_rect.set(0, 0, value ? value.width : 0, value ? value.height : 0)
  end
  def src_rect=(value)
    check_live; @src_rect.set(value.x, value.y, value.width, value.height)
  end
  def emit(commands)
    dx, dy = screen_offset
    RGSSXP.quad(commands, @bitmap, @x + dx, @y + dy, @src_rect,
      zoom_x: @zoom_x, zoom_y: @zoom_y, angle: @angle, ox: @ox, oy: @oy, opacity: @opacity,
      blend: @blend_type, color: effective_color, tone: @tone, bush: @bush_depth, mirror: @mirror)
  end
end

class Plane < RGSSXP::DisplayObject
  attr_accessor :bitmap
  def emit(commands)
    return unless @bitmap && !@bitmap.disposed? && @zoom_x > 0 && @zoom_y > 0
    area = @viewport ? @viewport.rect : Rect.new(0, 0, Graphics.width, Graphics.height)
    w, h = @bitmap.width * @zoom_x, @bitmap.height * @zoom_y
    start_x, start_y = area.x - @ox % w, area.y - @oy % h
    y = start_y
    while y < area.y + area.height
      x = start_x
      while x < area.x + area.width
        RGSSXP.quad(commands, @bitmap, x, y, @bitmap.rect, zoom_x: @zoom_x, zoom_y: @zoom_y,
          opacity: @opacity, blend: @blend_type, color: @color, tone: @tone, clip: area)
        x += w
      end
      y += h
    end
  end
end

class Window < RGSSXP::DisplayObject
  attr_accessor :windowskin, :contents, :stretch, :active, :pause
  attr_reader :cursor_rect, :width, :height, :back_opacity, :contents_opacity
  def initialize
    super(nil)
    @width = @height = 0
    @windowskin = @contents = nil
    @stretch = @active = true
    @pause = false
    @cursor_rect = Rect.new(0, 0, 0, 0)
    @back_opacity = @contents_opacity = 255
    @updates = 0
  end
  %i[width height].each do |field|
    variable = :"@#{field}"
    define_method("#{field}=") { |value| check_live; instance_variable_set(variable, [value.to_int, 0].max) }
  end
  %i[back_opacity contents_opacity].each do |field|
    variable = :"@#{field}"
    define_method("#{field}=") { |value| check_live; instance_variable_set(variable, [[value.to_int, 0].max, 255].min) }
  end
  def cursor_rect=(value)
    @cursor_rect.set(value.x, value.y, value.width, value.height)
  end
  def update
    super
    @updates += 1
  end
  def skin_quad(commands, sx, sy, sw, sh, x, y, w, h, opacity)
    return if w <= 0 || h <= 0
    RGSSXP.quad(commands, @windowskin, x, y, Rect.new(sx, sy, sw, sh), zoom_x: w.to_f / sw, zoom_y: h.to_f / sh, opacity: opacity)
  end
  def emit(commands)
    return if @width <= 0 || @height <= 0
    x, y, w, h = @x, @y, @width, @height
    if @windowskin && !@windowskin.disposed?
      if @stretch
        skin_quad(commands, 0, 0, 128, 128, x+2, y+2, w-4, h-4, @opacity*@back_opacity/255)
      else
        (0...h-4).step(128) do |j|
          (0...w-4).step(128) do |i|
            pw, ph = [128,w-4-i].min, [128,h-4-j].min
            skin_quad(commands,0,0,pw,ph,x+2+i,y+2+j,pw,ph,@opacity*@back_opacity/255)
          end
        end
      end
      [[128,0,x,y],[176,0,x+w-16,y],[128,48,x,y+h-16],[176,48,x+w-16,y+h-16]].each do |sx,sy,dx,dy|
        skin_quad(commands,sx,sy,16,16,dx,dy,16,16,@opacity)
      end
      [[144,0,32,16,x+16,y,w-32,16],[144,48,32,16,x+16,y+h-16,w-32,16],
       [128,16,16,32,x,y+16,16,h-32],[176,16,16,32,x+w-16,y+16,16,h-32]].each do |sx,sy,sw,sh,dx,dy,dw,dh|
        skin_quad(commands,sx,sy,sw,sh,dx,dy,dw,dh,@opacity)
      end
      unless @cursor_rect.width <= 0 || @cursor_rect.height <= 0
        pulse = @active ? 128 + ((@updates % 32 - 16).abs * 8) : 128
        cw, ch = @cursor_rect.width, @cursor_rect.height
        opacity = @opacity*[pulse,255].min/255
        edge_x, edge_y = [2,cw/2].min, [2,ch/2].min
        source_x, source_y = [128,130,158], [64,66,94]
        target_x, target_y = [0,edge_x,cw-edge_x], [0,edge_y,ch-edge_y]
        [edge_y,ch-edge_y*2,edge_y].each_with_index do |height,row|
          [edge_x,cw-edge_x*2,edge_x].each_with_index do |width,col|
            skin_quad(commands,source_x[col],source_y[row],col==1 ? 28 : 2,row==1 ? 28 : 2,
              x+16+@cursor_rect.x+target_x[col],y+16+@cursor_rect.y+target_y[row],width,height,opacity)
          end
        end
      end
      if @contents && !@contents.disposed?
        skin_quad(commands,144,24,8,16,x+4,y+h/2-8,8,16,@opacity) if @ox > 0
        skin_quad(commands,168,24,8,16,x+w-12,y+h/2-8,8,16,@opacity) if @contents.width-@ox > w-32
        skin_quad(commands,152,16,16,8,x+w/2-8,y+4,16,8,@opacity) if @oy > 0
        skin_quad(commands,152,40,16,8,x+w/2-8,y+h-12,16,8,@opacity) if @contents.height-@oy > h-32
      end
      if @pause
        skin_quad(commands,160+(@updates/8%2)*16,64+(@updates/16%2)*16,16,16,x+w/2-8,y+h-16,16,16,@opacity)
      end
    end
    if @contents && !@contents.disposed?
      area = Rect.new(x+16,y+16,[w-32,0].max,[h-32,0].max)
      RGSSXP.quad(commands,@contents,x+16-@ox,y+16-@oy,@contents.rect,opacity:@contents_opacity,clip:area)
    end
  end
end

module Graphics
  def self.update
    __begin
    __present(RGSSXP.scene_commands, -1.0, nil, 0.0)
    __tick
  end
  def self.transition(duration = 8, filename = '', vague = 40)
    mask = filename.empty? ? nil : Bitmap.new(filename)
    duration = [duration.to_int, 0].max
    if duration.zero?
      __begin
      __present(RGSSXP.scene_commands, 1.0, mask, vague / 255.0)
    else
      duration.times do |i|
        __begin
        __present(RGSSXP.scene_commands, (i + 1).to_f / duration, mask, vague / 255.0)
        __tick
      end
    end
    nil
  ensure
    mask.dispose if mask
  end
end
