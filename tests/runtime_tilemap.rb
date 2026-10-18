viewport = Viewport.new(0, 0, 640, 480)
tilemap = Tilemap.new(viewport)
atlas = Bitmap.new(96, 128)
48.times do |index|
  atlas.fill_rect(index % 6 * 16, index / 6 * 16, 16, 16,
    Color.new(index % 4 * 64 + 24, index / 4 % 4 * 64 + 24, index / 16 * 80 + 24))
end
tilemap.autotiles[0] = atlas
tilemap.priorities = Table.new(400)
tilemap.map_data = Table.new(8, 6, 3)
48.times { |index| tilemap.map_data[index % 8, index / 8, 0] = index + 48 }
Graphics.update
48.times do |index|
  RGSSXP::AUTOTILE_QUARTERS[index].each_with_index do |part, corner|
    pixel = Graphics.__scene_pixel(index % 8 * 32 + corner % 2 * 16 + 8, index / 8 * 32 + corner / 2 * 16 + 8)
    expected = [part % 4 * 64 + 24, part / 4 % 4 * 64 + 24, part / 16 * 80 + 24, 255]
    raise "Autotile #{index} quarter #{corner}: #{pixel} != #{expected}" unless pixel == expected
  end
end
raise 'small map wrapping changed' unless Graphics.__scene_pixel(8, 8) == Graphics.__scene_pixel(264, 200)
tileset = Bitmap.new(256, 32)
tileset.fill_rect(0, 0, 32, 32, Color.new(255,0,0))
tileset.fill_rect(32, 0, 32, 32, Color.new(0,255,0))
tilemap.tileset = tileset
tilemap.map_data = Table.new(20, 15, 3)
tilemap.map_data[0,0,0], tilemap.map_data[1,0,0] = 384, 385
tilemap.priorities[384] = 2
actor_bitmap = Bitmap.new(32, 32)
actor_bitmap.fill_rect(actor_bitmap.rect, Color.new(0,0,255))
actor = Sprite.new(viewport)
actor.bitmap, actor.z = actor_bitmap, 64
Graphics.update
raise 'priority tile should cover actor' unless Graphics.__scene_pixel(8,8) == [255,0,0,255]
actor.z = 128
Graphics.update
raise 'foreground actor should cover tile' unless Graphics.__scene_pixel(8,8) == [0,0,255,255]
actor.dispose
tilemap.ox = 32
Graphics.update
raise 'tilemap scroll changed' unless Graphics.__scene_pixel(8,8) == [0,255,0,255]
tilemap.dispose
viewport.dispose
[atlas,tileset,actor_bitmap].each(&:dispose)
File.write('runtime-complete.txt', 'tilemap,false,false')
sleep 0.5
