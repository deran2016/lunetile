# Applied above Main only to a verified stock project by --widescreen.
module Lunetile
  def self.map_rect
    width = [$game_map.width * 32, Graphics.width].min
    height = [$game_map.height * 32, Graphics.height].min
    [(Graphics.width - width) / 2, (Graphics.height - height) / 2, width, height]
  end
  def self.cover(sprite, width = Graphics.width, height = Graphics.height)
    bitmap = sprite.bitmap
    return unless bitmap && bitmap.width > 0 && bitmap.height > 0
    scale = [width.to_f / bitmap.width, height.to_f / bitmap.height].max
    sprite.zoom_x = sprite.zoom_y = scale
    sprite.x = ((width - bitmap.width * scale) / 2).round
    sprite.y = ((height - bitmap.height * scale) / 2).round
  end
end
