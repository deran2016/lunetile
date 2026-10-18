raise 'legacy resolution changed' unless [Graphics.width, Graphics.height] == [640,480]
Graphics.resize_screen(1280,720)
raise 'resize not applied' unless [Graphics.width, Graphics.height] == [1280,720]
bitmap = Bitmap.new(1280,720)
bitmap.fill_rect(bitmap.rect, Color.new(20,40,60))
sprite = Sprite.new
sprite.bitmap = bitmap
viewport = Viewport.new(1248,688,32,32)
overlay = Sprite.new(viewport)
overlay.bitmap = Bitmap.new(32,32)
overlay.bitmap.fill_rect(overlay.bitmap.rect, Color.new(200,100,50))
overlay.z = 10
viewport.z = 10
Graphics.update
raise 'wide scene not rendered' unless Graphics.__scene_pixel(1000,600) == [20,40,60,255]
raise 'bottom-right clip failed' unless Graphics.__scene_pixel(1279,719) == [200,100,50,255]
raise 'viewport leaks' unless Graphics.__scene_pixel(1247,687) == [20,40,60,255]
sprite.visible = overlay.visible = false
plane = Plane.new
plane.bitmap = Bitmap.new(16,16)
plane.bitmap.fill_rect(plane.bitmap.rect, Color.new(30,90,150))
Graphics.update
raise 'plane does not cover wide canvas' unless Graphics.__scene_pixel(1279,719) == [30,90,150,255]
plane.bitmap.dispose
plane.dispose
tilemap = Tilemap.new
tilemap.tileset = Bitmap.new(256,32)
tilemap.tileset.fill_rect(tilemap.tileset.rect, Color.new(70,110,150))
tilemap.map_data = Table.new(40,23,1)
23.times { |y| 40.times { |x| tilemap.map_data[x,y,0] = 384 } }
Graphics.update
raise 'wide tilemap edge missing' unless Graphics.__scene_pixel(1279,719) == [70,110,150,255]
tilemap.tileset.dispose
tilemap.dispose
sprite.visible = overlay.visible = true
Graphics.update
Graphics.freeze
Graphics.resize_screen(640,480)
Graphics.transition(2)
raise 'legacy resize broke pixels' unless Graphics.__scene_pixel(639,479) == [20,40,60,255]
[[0,720],[-1,720],[4096,4096]].each do |size|
  begin
    Graphics.resize_screen(*size)
    raise 'invalid resolution accepted'
  rescue ArgumentError
  end
end
raise 'failed resize changed resolution' unless [Graphics.width,Graphics.height] == [640,480]
# Exercise the actual launcher window without changing system display settings.
active = Win32API.new('user32','GetActiveWindow','','L')
outer = Win32API.new('user32','GetWindowRect','LP','I')
client = Win32API.new('user32','GetClientRect','LP','I')
position = Win32API.new('user32','SetWindowPos','LLIIIII','I')
show = Win32API.new('user32','ShowWindow','LI','I')
send = Win32API.new('user32','SendMessageW','LILL','L')
hwnd = active.call
raise 'no active test window' if hwnd == 0
rect = [0,0,0,0].pack('l4')
outer.call(hwnd,rect)
original_rect = rect.dup
position.call(hwnd,0,40,40,1000,700,4)
Graphics.update
client.call(hwnd,rect)
raise 'window resize failed' unless rect.unpack('l4')[2] > 640
show.call(hwnd,3)
Graphics.update
outer.call(hwnd,rect)
maximized_rect = rect.dup
send.call(hwnd,0x104,13,0x20000001)
Graphics.update
send.call(hwnd,0x104,13,0x20000001)
Graphics.update
outer.call(hwnd,rect)
raise 'fullscreen did not restore maximized geometry' unless rect == maximized_rect
show.call(hwnd,9)
Graphics.update
outer.call(hwnd,rect)
normal_rect = rect.dup
send.call(hwnd,0x104,13,0x20000001)
Graphics.update
send.call(hwnd,0x104,13,0x20000001)
Graphics.update
outer.call(hwnd,rect)
raise 'fullscreen did not restore normal geometry' unless rect == normal_rect
send_dpi = Win32API.new('user32','SendMessageW','LILP','L')
send_dpi.call(hwnd,0x02e0,96 | (96 << 16),original_rect)
Graphics.update
File.write('window-checks.txt','resize,maximize,fullscreen restore,synthetic DPI message')
overlay.bitmap.dispose
overlay.dispose
viewport.dispose
sprite.dispose
bitmap.dispose
File.write('runtime-complete.txt','resolution,false,false')
