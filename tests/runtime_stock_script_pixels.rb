require 'json'
Graphics.resize_screen(320,240)
stock_map(32)
viewport=Viewport.new(0,0,320,240)
events=$game_map.events.values.first(8)
events.each_with_index { |e,i| e.moveto(1+i%4,2+i/4) }
sprites=events.map { |e| Sprite_Character.new(viewport,e) }
raw=''.b;states=[]
capture=lambda do |name|
 Graphics.__present(RGSSXP.scene_commands,-1.0,nil,0.0)
 bitmap=Graphics.__snapshot;raw<<bitmap.__pixel_bytes;bitmap.dispose
 states<<[name,sprites.map { |s| [s.x,s.y,s.z,s.src_rect.x,s.src_rect.y,s.src_rect.width,s.src_rect.height,s.opacity,s.blend_type,s.visible] }]
end
advance=lambda do |count|
 count.times do
  Graphics.frame_count+=1
  events.each(&:update)
  sprites.each(&:update)
 end
end
advance.call(1);capture.call('initial')
$game_map.instance_variable_set(:@display_x,STOCK_EXT=='rxdata' ? 9 : 0.25)
$game_map.instance_variable_set(:@display_y,STOCK_EXT=='rxdata' ? -7 : -0.25)
advance.call(1);capture.call('scroll')
events.each_with_index { |e,i| e.instance_variable_set(:@pattern,i%3);e.instance_variable_set(:@direction,[2,4,6,8][i%4]) }
advance.call(1);capture.call('pattern-direction')
events[0].instance_variable_set(:@through,true);events[0].jump(1,1)
advance.call(8);capture.call('jump')
advance.call(140);capture.call('landed')
events.each_with_index { |e,i| e.instance_variable_set(:@opacity,64+i*20);e.instance_variable_set(:@blend_type,i%3);e.transparent=i==7 }
viewport.tone=Tone.new(5,-9,7,13);viewport.color=Color.new(22,40,60,17)
advance.call(1);capture.call('properties')
sprites[0].opacity=7;sprites[1].x+=29;sprites[2].y-=13
advance.call(1);capture.call('actual-sprite-values')
events[0].animation_id=1
advance.call(2);capture.call('animation')
advance.call(32);capture.call('animation-progress')
if STOCK_EXT=='rvdata2'
 events[1].balloon_id=1;advance.call(3);capture.call('balloon')
end
events[0].instance_variable_set(:@tile_id,STOCK_EXT=='rxdata' ? 384 : 1)
advance.call(1);capture.call('tile-graphic')
events[0].instance_variable_set(:@tile_id,0)
advance.call(1);capture.call('same-character-after-tile')
replacement=Marshal.load(Marshal.dump(events[1]));replacement.moveto(6,5)
sprites[1].character=replacement;events[1]=replacement
advance.call(1);capture.call('character-replacement')
old=sprites[2].bitmap
other=Bitmap.new(old.width,old.height);other.fill_rect(0,0,other.width,other.height,Color.new(91,143,197,113))
sprites[2].bitmap=other;advance.call(1);capture.call('bitmap-replacement')
GC.start;GC.compact if GC.respond_to?(:compact)
advance.call(1);capture.call('compact')
Graphics.resize_screen(384,256);viewport.rect=Rect.new(7,3,361,241)
advance.call(1);capture.call('resize-clip')
File.binwrite('stock-script-pixels.bin',raw)
File.write('stock-script-pixels.json',JSON.generate(states))
sprites.each(&:dispose);viewport.dispose;other.dispose
File.write('runtime-complete.txt','stock script pixels,false,false')
