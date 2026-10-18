raise 'default frame rate changed' unless Graphics.frame_rate == 40
properties = {x:1,y:2,z:3,ox:4,oy:5,bush_depth:6,zoom_x:1.25,zoom_y:1.5,angle:90.0,visible:false,mirror:true}
property_sprite = Sprite.new
properties.each { |field,value| property_sprite.public_send("#{field}=",value) }
properties.each { |field,value| raise "Display property #{field} aliased" unless property_sprite.public_send(field)==value }
property_sprite.dispose
properties.each_key do |field|
  begin
    property_sprite.public_send(field)
    raise 'Disposed property read succeeded'
  rescue RGSSError
  end
end
background = Bitmap.new(640, 480)
background.fill_rect(background.rect, Color.new(20, 40, 60))
base = Sprite.new
base.bitmap = background
overlay = Bitmap.new(64, 64)
overlay.fill_rect(overlay.rect, Color.new(200, 100, 50, 128))
sprite = Sprite.new
sprite.bitmap = overlay
sprite.x, sprite.y, sprite.z, sprite.opacity = 32, 48, 1, 128
File.write('renderer-stage.txt','before first frame')
Graphics.update
File.write('renderer-focus-pause-ms.txt',Graphics.__timings[10].to_s)
File.write('renderer-stage.txt','first frame returned')
raise 'background GPU pixel mismatch' unless Graphics.__scene_pixel(0, 0) == [20, 40, 60, 255]
actual = Graphics.__scene_pixel(40, 56)
raise "alpha GPU pixel mismatch #{actual.inspect}" unless actual.zip([65,55,57,255]).all? { |a,b| (a-b).abs <= 1 }
viewport = Viewport.new(100, 100, 20, 20)
viewport.z = 10
v_sprite = Sprite.new(viewport)
v_sprite.bitmap = overlay
Graphics.update
raise 'viewport clipping failed' unless Graphics.__scene_pixel(99, 100) == [20,40,60,255]
raise 'viewport draw failed' if Graphics.__scene_pixel(105, 105) == [20,40,60,255]
v_sprite.dispose
viewport.dispose
flash = Viewport.new(200, 100, 20, 20)
flash.z = 50
flash.color.set(255, 0, 0, 255)
Graphics.update
raise 'empty viewport flash missing' unless Graphics.__scene_pixel(205, 105) == [255, 0, 0, 255]
flash.dispose
text = Bitmap.new(200, 64)
text.draw_text(0, 0, 200, 32, 'Ruby 4.0.7')
text_sprite = Sprite.new
text_sprite.bitmap = text
text_sprite.y, text_sprite.z = 200, 20
before = Graphics.frame_count
30.times { Graphics.update }
raise 'frame counter mismatch' unless Graphics.frame_count == before + 30
timing = Graphics.__timings
raise 'GPU query unresolved' unless timing[3] > 0 && timing[2] && timing[2] >= 0
raise 'no deadline wait' unless timing[1] > 0
File.write('graphics-timings.txt', timing.inspect)
skin = Bitmap.new(192,128)
skin.fill_rect(128,64,2,2,Color.new(255,0,0))
skin.fill_rect(158,64,2,2,Color.new(0,255,0))
skin.fill_rect(128,94,2,2,Color.new(0,0,255))
skin.fill_rect(158,94,2,2,Color.new(255,255,0))
window = Window.new
window.windowskin = skin
window.x, window.y, window.z, window.width, window.height = 300,300,100,160,64
window.active = false
window.cursor_rect.set(0,0,100,32)
Graphics.update
[[316,316,0],[415,316,1],[316,347,2],[415,347,3]].each do |x,y,corner|
  expected = [[255,0,0],[0,255,0],[0,0,255],[255,255,0]][corner]
  pixel = Graphics.__scene_pixel(x,y)
  raise "Window cursor corner stretched away: #{pixel.inspect}" unless expected.each_with_index.all? { |value,i| value == 0 || pixel[i] > 120 }
end
window.dispose;skin.dispose
[base, sprite, text_sprite].each(&:dispose)
[background, overlay, text].each(&:dispose)
File.write('runtime-complete.txt', 'renderer,false,false')
sleep 0.5
