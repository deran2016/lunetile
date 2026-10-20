require 'json'
entries = 0
previous = nil
rgss_main do
  entries += 1
  raise 'instance counters survived reset' if entries > 1 && Graphics.__tile_batches[0,5] != [0,0,0,0,0]
  raise 'cache owners survived reset' if previous && previous.any? { |object| !object.disposed? }
  tile = Tilemap.new
  tile.map_data = Table.new(1,1,4)
  tile.map_data[0,0,0] = 2048
  bitmap = Bitmap.new(512,512)
  bitmap.fill_rect(bitmap.rect,Color.new(31,63,127))
  tile.bitmaps[0] = bitmap
  plane = Plane.new
  plane.bitmap = Bitmap.new(32,32)
  Graphics.update
  raise 'no geometry cached' unless tile.instance_variable_get(:@tile_cache).stats[1] > 0
  if entries == 1
    previous = [tile,bitmap,plane,plane.bitmap]
    active = Win32API.new('user32','GetActiveWindow','','L')
    post = Win32API.new('user32','PostMessageA','LLLL','L')
    hwnd = active.call
    raise 'missing game window' if hwnd == 0
    raise 'F12 keydown post' if post.call(hwnd,0x100,0x7b,0) == 0
    post.call(hwnd,0x101,0x7b,0)
    Graphics.update
    raise 'F12 did not reset'
  end
  raise 'wrong reset count' unless entries == 2
end
File.write('runtime-complete.txt','VXA F12 renderer reset PASS')
