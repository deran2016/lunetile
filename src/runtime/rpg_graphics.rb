module RPG::Cache
  @cache = {}
  def self.load_bitmap(folder, filename, hue = 0)
    key = [folder, filename, hue]
    cached = @cache[key]
    return cached if cached && !cached.disposed?
    bitmap = filename.empty? ? Bitmap.new(32, 32) : Bitmap.new(folder + filename)
    bitmap.hue_change(hue) if hue != 0
    @cache[key] = bitmap
  end
  {animation: 'Animations', autotile: 'Autotiles', battleback: 'Battlebacks', battler: 'Battlers',
   character: 'Characters', fog: 'Fogs', gameover: 'Gameovers', icon: 'Icons', panorama: 'Panoramas',
   picture: 'Pictures', tileset: 'Tilesets', title: 'Titles', transition: 'Transitions', windowskin: 'Windowskins'}.each do |method, folder|
    define_singleton_method(method) { |filename, hue = 0| load_bitmap("Graphics/#{folder}/", filename, hue) }
  end
  def self.tile(filename, tile_id, hue)
    key = [:tile, filename, tile_id, hue]
    return @cache[key] if @cache[key] && !@cache[key].disposed?
    bitmap = Bitmap.new(32, 32)
    bitmap.blt(0, 0, tileset(filename), Rect.new((tile_id - 384) % 8 * 32, (tile_id - 384) / 8 * 32, 32, 32))
    bitmap.hue_change(hue) if hue != 0
    @cache[key] = bitmap
  end
  def self.clear
    @cache.clear
    GC.start
    nil
  end
end

class RPG::Sprite < ::Sprite
  def initialize(viewport = nil)
    super(viewport)
    @effect = nil
    @effect_left = @damage_left = 0
    @blink = false
    @blink_count = 0
    @animation_data = @loop_data = nil
    @animation_cells = []
    @loop_cells = []
  end
  def whiten
    self.blend_type, self.opacity = 0, 255
    @effect, @effect_left = :whiten, 16
    self.color.set(255, 255, 255, 128)
  end
  def appear
    self.blend_type = 0
    self.color.set(0, 0, 0, 0)
    @effect, @effect_left = :appear, 16
    self.opacity = 0
  end
  def escape
    self.blend_type = 0
    self.color.set(0, 0, 0, 0)
    @effect, @effect_left = :escape, 32
    self.opacity = 255
  end
  def collapse
    self.opacity = 255
    @effect, @effect_left = :collapse, 48
    self.blend_type = 1
    self.color.set(255, 64, 64, 255)
  end
  def blink_on
    @blink = true
    @blink_count = 0
  end
  def blink_off
    @blink = false
    self.color.set(0, 0, 0, 0)
  end
  def effect?
    @effect_left > 0 || @damage_left > 0 || !!@animation_data
  end
  def damage(value, critical)
    dispose_damage
    text = value.is_a?(Numeric) ? value.abs.to_s : value.to_s
    bitmap = Bitmap.new(160, 48)
    bitmap.font.name, bitmap.font.size, bitmap.font.bold = 'Arial Black', 32, false
    bitmap.font.color = Color.new(0, 0, 0)
    [[-1,0],[1,0],[0,-1],[0,1]].each { |x,y| bitmap.draw_text(x, y + 12, 160, 36, text, 1) }
    bitmap.font.color = value.is_a?(Numeric) && value < 0 ? Color.new(176,255,144) : Color.new(255,255,255)
    bitmap.draw_text(0, 12, 160, 36, text, 1)
    if critical
      bitmap.font.size = 20
      bitmap.font.color = Color.new(0, 0, 0)
      [[-1,0],[1,0],[0,-1],[0,1]].each { |x,y| bitmap.draw_text(x, y, 160, 20, 'CRITICAL', 1) }
      bitmap.font.color = Color.new(255,255,255)
      bitmap.draw_text(0, 0, 160, 20, 'CRITICAL', 1)
    end
    @damage_sprite = ::Sprite.new(viewport)
    @damage_sprite.bitmap = bitmap
    @damage_sprite.ox, @damage_sprite.oy = 80, 20
    @damage_sprite.x, @damage_sprite.y, @damage_sprite.z = x, y - oy / 2, 3000
    @damage_left = 40
  end
  def dispose_damage
    if @damage_sprite
      @damage_sprite.bitmap.dispose
      @damage_sprite.dispose
      @damage_sprite = nil
    end
    @damage_left = 0
  end
  def animation(data, hit)
    @animation_cells.each(&:dispose)
    @animation_data, @animation_hit, @animation_tick = data, hit, 0
    @animation_cells = data ? Array.new(16) { ::Sprite.new(viewport) } : []
    update_animation(data, @animation_cells, 0, hit) if data
  end
  def loop_animation(data)
    return if @loop_data.equal?(data)
    @loop_cells.each(&:dispose)
    @loop_data, @loop_tick = data, 0
    @loop_cells = data ? Array.new(16) { ::Sprite.new(viewport) } : []
    update_animation(data, @loop_cells, 0, true) if data
  end
  def update_animation(data, cells, index, hit)
    frame = data.frames[index]
    sheet = RPG::Cache.animation(data.animation_name, data.animation_hue)
    cells.each_with_index do |cell, i|
      pattern = frame.cell_data[i,0]
      cell.visible = pattern && pattern >= 0
      next unless cell.visible
      cell.bitmap = sheet
      cell.src_rect.set(pattern % 5 * 192, pattern / 5 * 192, 192, 192)
      if data.position == 3
        cx, cy = viewport ? [viewport.rect.width / 2, ([Graphics.width, Graphics.height] == [640, 480] ? viewport.rect.height - 160 : viewport.rect.height / 2)] : [Graphics.width / 2, Graphics.height / 2]
      else
        cx, cy = x - ox + src_rect.width / 2, y - oy + src_rect.height / 2
        cy -= src_rect.height / 4 if data.position == 0
        cy += src_rect.height / 4 if data.position == 2
      end
      cell.x, cell.y, cell.z = cx + frame.cell_data[i,1], cy + frame.cell_data[i,2], 2000
      cell.ox = cell.oy = 96
      cell.zoom_x = cell.zoom_y = frame.cell_data[i,3] / 100.0
      cell.angle, cell.mirror = frame.cell_data[i,4], frame.cell_data[i,5] == 1
      cell.opacity, cell.blend_type = frame.cell_data[i,6] * opacity / 255, frame.cell_data[i,7]
    end
    data.timings.each do |timing|
      next unless timing.frame == index && (timing.condition == 0 || (timing.condition == 1 && hit) || (timing.condition == 2 && !hit))
      Audio.se_play('Audio/SE/' + timing.se.name, timing.se.volume, timing.se.pitch) unless timing.se.name.empty?
      case timing.flash_scope
      when 1 then flash(timing.flash_color, timing.flash_duration * 2)
      when 2 then viewport.flash(timing.flash_color, timing.flash_duration * 2) if viewport
      when 3 then flash(nil, timing.flash_duration * 2)
      end
    end
  end
  def update
    super
    return unless RGSSXP::Timing.legacy_tick?
    if @effect_left > 0
      @effect_left -= 1
      case @effect
      when :whiten then self.color.alpha = 128 - (16 - @effect_left) * 10
      when :appear then self.opacity = 256 - @effect_left * 16
      when :escape then self.opacity = 256 - (32 - @effect_left) * 10
      when :collapse then self.opacity = 256 - (48 - @effect_left) * 6
      end
    end
    if @blink
      @blink_count = (@blink_count + 1) % 32
      self.color.set(255, 255, 255, (16 - @blink_count).abs * 6)
    end
    if @damage_left > 0
      @damage_left -= 1
      @damage_sprite.y += @damage_left >= 38 ? -4 : @damage_left >= 36 ? -2 : @damage_left >= 34 ? 2 : @damage_left >= 28 ? 4 : 0
      @damage_sprite.opacity = 256 - (12 - @damage_left) * 32
      dispose_damage if @damage_left == 0
    end
    if @animation_data && (Graphics.frame_count / RGSSXP::Timing.scale).even?
      @animation_tick += 2
      if @animation_tick >= @animation_data.frame_max * 2
        @animation_cells.each(&:dispose)
        @animation_cells = []
        @animation_data = nil
      elsif @animation_tick.even?
        update_animation(@animation_data, @animation_cells, @animation_tick / 2, @animation_hit)
      end
    end
    if @loop_data && (Graphics.frame_count / RGSSXP::Timing.scale).even?
      @loop_tick = (@loop_tick + 2) % (@loop_data.frame_max * 2)
      update_animation(@loop_data, @loop_cells, (@loop_tick / 2 - 1) % @loop_data.frame_max, true) if @loop_tick.even?
    end
  end
  def dispose
    dispose_damage
    @animation_cells.each(&:dispose)
    @loop_cells.each(&:dispose)
    super
  end
end
