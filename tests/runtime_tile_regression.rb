require 'json'
Graphics.resize_screen(320,240)
clock=lambda { Process.clock_gettime(Process::CLOCK_MONOTONIC) }
summary=lambda { |v| s=v.sort;{mean:s.sum/s.size,p95:s[((s.size-1)*0.95).ceil]} }
atlas=Bitmap.new(256,512);atlas.fill_rect(atlas.rect,Color.new(87,139,183,141))
rows=[]
[:objects,:invalidated].each do |kind|
 nodes=[]
 if kind==:objects
  300.times { |i| s=Sprite.new;s.bitmap=atlas;s.src_rect.set(0,0,16,16);s.x=i%20*16;s.y=i/20*16;nodes<<s }
  plane=Plane.new;plane.bitmap=atlas;nodes<<plane
  window=Window.new;window.width=160;window.height=112;window.windowskin=atlas;window.contents=Bitmap.new(128,80);window.contents.fill_rect(0,0,128,80,Color.new(33,55,77));nodes<<window
 else
  map=Table.new(40,30,3);30.times { |y| 40.times { |x| map[x,y,0]=384 } }
  tile=Tilemap.new;tile.map_data=map
  if tile.respond_to?(:flags)
   map[0,0,0]=1536;30.times { |y| 40.times { |x| map[x,y,0]=1536 } }
   flags=Table.new(8192);tile.flags=flags;tile.bitmaps.fill(atlas);id=1536
  else
   flags=Table.new(8192);tile.priorities=flags;tile.tileset=atlas;id=384
  end
  nodes<<tile
 end
 values=[]
 200.times do |i|
  flags[id]=i%2 if kind==:invalidated
  started=clock.call;commands=RGSSXP.scene_commands;generation=(clock.call-started)*1000
  Graphics.__present(commands,-1.0,nil,0.0)
  values << generation+Graphics.__render_parts[0] if i>=40
 end
 rows << {kind:kind,timing_ms:summary.call(values)}
 nodes.each(&:dispose)
end
File.write('tile-regression.json',JSON.generate(rows))
File.write('runtime-complete.txt','tile regression,false,false')
