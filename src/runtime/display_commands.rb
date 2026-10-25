module RGSSXP
  def self.__sprite_quad(commands, bitmap, x, y, source, zx, zy, angle, ox, oy, opacity, blend, color, tone, bush, mirror)
    return unless bitmap && !bitmap.disposed?
    width, height = source.width, source.height
    return unless width > 0 && height > 0
    commands << [0,bitmap,x,y,width,height,source.x,source.y,width,height,zx,zy,angle,ox,oy,opacity,blend,color,tone,bush,nil,mirror]
  end
  def self.__capture_display_methods
    @default_quad = method(:quad)
    @display_methods = {}
    [Viewport,Sprite,Window,Plane,Tilemap,Tilemap::Layer].each do |kind|
      names = %i[disposed? viewport z serial visible flash_hidden? emit effective_color screen_offset check_live is_a? class]
      names += [:y] if kind == Sprite
      names += %i[rect tone] if kind == Viewport
      names += [:layers] if kind == Tilemap
      @display_methods[kind] = names.filter_map { |name| [name,kind.instance_method(name)] if kind.method_defined?(name) }.to_h
    end
    nil
  end
  def self.__standard_display_class?(klass, kind)
    @display_methods.fetch(kind).all? { |name,original| klass.instance_method(name) == original }
  rescue NameError
    false
  end
  def self.__fast_sprite_emit?; @fast_sprite_emit; end
  def self.__viewport_changed; @viewport_generation += 1; end
  def self.__sort_display(nodes)
    ordered = __order_display(nodes)
    return ordered if ordered
    nodes.sort_by do |node|
      if node.is_a?(Tilemap::Layer)
        [node.z,0,node.serial]
      else
        node.check_live
        [node.instance_variable_get(:@z),node.is_a?(Sprite) ? node.instance_variable_get(:@y) : 0,node.serial]
      end
    end
  end
  def self.scene_commands
    previous = @fast_sprite_emit
    @fast_sprite_emit = false
    snapshot = @nodes.keys
    return __legacy_scene_commands(snapshot) unless method(:quad) == @default_quad
    checked = {}
    return __legacy_scene_commands(snapshot) unless __standard_display_class?(Tilemap::Layer,Tilemap::Layer)
    snapshot.each do |node|
      klass = __plain_display_class(node)
      return __legacy_scene_commands(snapshot) unless klass
      unless checked.key?(klass)
        kind = [Viewport,Sprite,Window,Plane,Tilemap].find { |base| node.is_a?(base) }
        checked[klass] = kind && __standard_display_class?(klass,kind)
      end
      return __legacy_scene_commands(snapshot) unless checked[klass]
    end
    nodes, roots = [], []
    children = {}.compare_by_identity
    snapshot.each do |node|
      next if node.disposed?
      expanded = node.is_a?(Tilemap) ? node.layers : nil
      if expanded
        expanded.each do |layer|
          nodes << layer
          layer.viewport ? (children[layer.viewport] ||= []) << layer : roots << layer
        end
      else
        nodes << node
        if node.is_a?(Viewport) || node.viewport.nil?
          roots << node
        else
          (children[node.viewport] ||= []) << node
        end
      end
    end
    generation = @viewport_generation
    commands = []
    @fast_sprite_emit = true
    __sort_display(roots).each do |node|
      next unless node.visible && !node.flash_hidden?
      if node.is_a?(Viewport)
        commands << [1,node.rect]
        group = if generation == @viewport_generation
          children[node] || []
        else
          nodes.select { |child| !child.is_a?(Viewport) && child.viewport.equal?(node) }
        end
        __sort_display(group).
          each { |child| child.emit(commands) if child.visible && !child.flash_hidden? }
        commands << [2,node.rect,node.effective_color,node.tone]
      else
        node.emit(commands)
      end
    end
    commands
  ensure
    @fast_sprite_emit = previous
  end
end
