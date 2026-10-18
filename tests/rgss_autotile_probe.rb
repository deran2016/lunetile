viewport = Viewport.new(0, 0, 640, 480)
tilemap = Tilemap.new(viewport)
atlas = Bitmap.new(96, 128)
48.times do |index|
  color = Color.new(index % 4 * 64 + 24, index / 4 % 4 * 64 + 24, index / 16 * 80 + 24)
  atlas.fill_rect(index % 6 * 16, index / 6 * 16, 16, 16, color)
end
tilemap.autotiles[0] = atlas
tilemap.priorities = Table.new(384)
tilemap.map_data = Table.new(8, 6, 3)
48.times { |index| tilemap.map_data[index % 8, index / 8, 0] = 48 + index }
File.open('ready.txt', 'w') { |file| file.write('atlas configured') }
until File.exist?('finish-probe.txt')
  tilemap.update
  Graphics.update
end
tilemap.dispose
atlas.dispose
viewport.dispose
