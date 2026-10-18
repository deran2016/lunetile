# Own procedural visual fixture, identical Ruby 1.8/4 source; no game assets.
Graphics.frame_rate=40
Font.default_name='Arial';Font.default_size=18
bitmaps=[];sprites=[];viewports=[];planes=[];windows=[]
background=Bitmap.new(640,480);bitmaps << background
background.fill_rect(background.rect,Color.new(24,34,45))
background.draw_text(16,4,608,32,'RGSS 640 x 480 / sprites, viewport, plane, window',1)
background.draw_text(16,430,608,32,'C: freeze/transition   B: close review',1)
base=Sprite.new;base.bitmap=background;base.z=-100;sprites << base
texture=Bitmap.new(96,96);bitmaps << texture
[[0,0,Color.new(230,50,40)],[48,0,Color.new(40,210,70)],[0,48,Color.new(40,80,230)],[48,48,Color.new(250,240,220,128)]].each do |x,y,color|
  texture.fill_rect(x,y,48,48,color)
end
texture.fill_rect(24,24,48,48,Color.new(255,255,255,160))
4.times do |index|
  sprite=Sprite.new;sprite.bitmap=texture;sprite.x=24+index*108;sprite.y=88;sprite.z=20
  case index
  when 1
    sprite.tone=Tone.new(50,-30,80,40);sprite.opacity=180;sprite.mirror=true;sprite.angle=20
  when 2 then sprite.blend_type=1
  when 3 then sprite.blend_type=2
  end
  sprites << sprite
end
clip=Viewport.new(456,64,160,152);clip.z=30;clip.color=Color.new(30,60,160,70);viewports << clip
clipped=Sprite.new(clip);clipped.bitmap=texture;clipped.x=-24;clipped.y=24;clipped.zoom_x=2;clipped.zoom_y=1.5;sprites << clipped
pattern=Bitmap.new(16,16);bitmaps << pattern
pattern.fill_rect(pattern.rect,Color.new(65,100,85));pattern.fill_rect(0,0,8,8,Color.new(180,210,180,160));pattern.fill_rect(8,8,8,8,Color.new(180,210,180,160))
plane_view=Viewport.new(16,240,240,152);viewports << plane_view
plane=Plane.new(plane_view);plane.bitmap=pattern;plane.ox=12;plane.oy=5;plane.zoom_x=2;plane.opacity=180;planes << plane
skin=Bitmap.new(192,128);bitmaps << skin
skin.fill_rect(0,0,128,128,Color.new(30,55,110,230))
8.times { |index| skin.fill_rect(index*16,0,1,128,Color.new(100,140,180,100));skin.fill_rect(0,index*16,128,1,Color.new(100,140,180,100)) }
skin.fill_rect(128,0,64,64,Color.new(180,205,240));skin.fill_rect(144,16,32,32,Color.new(0,0,0,0))
skin.fill_rect(128,64,32,32,Color.new(130,170,230,150))
window=Window.new;window.x=280;window.y=240;window.width=336;window.height=152;window.z=100
window.windowskin=skin;window.opacity=220;window.back_opacity=180;window.active=false
window.contents=Bitmap.new(304,120);bitmaps << window.contents
window.contents.draw_text(4,4,296,28,'Window / cursor / clipping')
window.contents.draw_text(240,44,180,28,'Clipped at right edge')
window.contents.draw_text(4,84,296,28,'Right aligned',2)
window.cursor_rect=Rect.new(0,4,220,28);windows << window
phase=1
File.open('render-review-phase.txt','w'){|file|file.write(phase.to_s)}
Graphics.transition(0)
Graphics.update
File.open('render-review-pixels.txt','w') do |file|
  [[0,0],[30,100],[60,140],[500,100],[300,300]].each do |x,y|
    file.puts([x,y,Graphics.respond_to?(:__scene_pixel) ? Graphics.__scene_pixel(x,y) : nil].inspect)
  end
  file.puts(['source_background',background.get_pixel(0,0).red,background.get_pixel(0,0).green,background.get_pixel(0,0).blue].inspect)
end
until File.exist?('finish-probe.txt')
  Graphics.update;Input.update
  break if Input.trigger?(Input::B)
  if Input.trigger?(Input::C)
    Graphics.freeze
    phase=phase==1 ? 2 : 1
    sprites[1].opacity=phase==1 ? 255 : 80
    clipped.ox=phase==1 ? 0 : 24
    window.contents_opacity=phase==1 ? 255 : 100
    Graphics.transition(40)
    File.open('render-review-phase.txt','w'){|file|file.write(phase.to_s)}
  end
end
windows.each { |item| item.dispose };planes.each { |item| item.dispose };sprites.each { |item| item.dispose }
viewports.each { |item| item.dispose };bitmaps.each { |item| item.dispose unless item.disposed? }
File.open('runtime-complete.txt','w'){|file|file.write('visual-review,false,false')}
