require 'json'
def check(value,message);raise message unless value;end
Graphics.resize_screen(160,128)
atlas=Bitmap.new(512,1024)
alternate=Bitmap.new(512,1024)
64.times { |y| 32.times { |x|
 atlas.fill_rect(x*16,y*16,16,16,Color.new(x*7%256,y*11%256,(x+y)*13%256,96+(x+y)%160))
 alternate.fill_rect(x*16,y*16,16,16,Color.new(y*13%256,x*9%256,(x+y)*17%256,128))
} }
map=Table.new(5,4,4);flags=Table.new(8192)
ids=[1536,1,256,512,768,2816]
4.times { |y| 5.times { |x|
 map[x,y,0]=ids[(x+y)%ids.size];map[x,y,1]=2816
 map[x,y,2]=256;map[x,y,3]=(x+y)%16
} }
flags[2816]=128;flags[256]=16
viewports=[Viewport.new(-3,5,112,96),Viewport.new(65,-4,82,110)]
tiles=viewports.map do |viewport|
 tile=Tilemap.new(viewport);tile.map_data=map;tile.flags=flags
 tile.bitmaps.replace(Array.new(9) { |i| i.even? ? atlas : alternate });tile
end
sprites=viewports.map do |viewport|
 sprite=Sprite.new(viewport);sprite.bitmap=alternate;sprite.src_rect.set(32,48,48,56)
 sprite.x=30;sprite.y=20;sprite.z=100;sprite.opacity=137;sprite.angle=17
 sprite.bush_depth=12;sprite.color=Color.new(180,20,50,65);sprite.tone=Tone.new(-12,18,7,45);sprite
end
root_sprite=Sprite.new;root_sprite.bitmap=atlas;root_sprite.src_rect.set(80,64,32,40)
root_sprite.x=130;root_sprite.y=70;root_sprite.z=300;root_sprite.mirror=true
capture=lambda do |commands|
 Graphics.__present(commands,-1.0,nil,0.0)
 bitmap=Graphics.snap_to_bitmap;bytes=bitmap.__pixel_bytes;bitmap.dispose;bytes
end
comparisons=0
3.times do |blend|
 3.times do |phase|
  sprites.each { |sprite| sprite.blend_type=blend;sprite.mirror=phase.odd? }
  viewports.each { |viewport| viewport.ox=phase*3;viewport.oy=phase;viewport.tone=Tone.new(phase*9,-7,5,23);viewport.color=Color.new(22,44,99,phase*37) }
  tiles.each { |tile| tile.ox=phase*17-25;tile.oy=phase*7;tile.instance_variable_set(:@updates,phase*30) }
  map[phase,1,0]=ids[(phase+blend)%ids.size]
  alternate.set_pixel(phase,phase,Color.new(10,200,30,140))
  commands=RGSSXP.scene_commands
  legacy=commands.flat_map { |command| command[0]==3 ? RGSSXP.__expand_tile_batch(command) : [command] }
  check(capture.call(commands)==capture.call(legacy),'mixed textures/alpha/sprite/viewport ordering pixels')
  comparisons+=1
 end
end
Graphics.freeze
Graphics.transition(3)
[root_sprite,*sprites,*tiles,*viewports].each(&:dispose)

def make_batch(count,bitmap,parts=1)
 cells=count/parts
 map=Table.new(cells,1,1);cells.times { |i| map[i,0,0]=1536 }
 cache=RGSSXP::TileCache.new
 cache.prepare(map,nil,0,0,cells,1,0)
 cache.shape(1536,4,Array.new(parts) { [0,0,0,0,1,1] });cache.commit
 images=Array.new(10);images[4]=bitmap
 [3,cache,0,images,0,0]
end
Graphics.__present([],-1.0,nil,0.0)
check(Graphics.__tile_batches[0,2]==[0,0] && Graphics.__tile_batches[4]==0,'empty instance frame')
capacities=[]
[1,1024,1025,4096,4097,100000].each do |count|
 command=make_batch(count,atlas,count==100000 ? 8 : 1)
 Graphics.__present([command],-1.0,nil,0.0)
 stats=Graphics.__tile_batches
 check(stats[0]==count && stats[1]==1 && stats[4]==1,'instance boundary/count')
 check(stats[5]>=count*32 && stats[5]<=100000*32,'instance storage bound')
 capacities<<stats[5]
 if count==1
  Graphics.__present([command,command],-1.0,nil,0.0)
  check(Graphics.__tile_batches[1]==2,'merged across native command boundary')
 end
 if count==100000
  extra=make_batch(1,atlas)
  begin
   Graphics.__present([command,extra],-1.0,nil,0.0)
   raise 'expanded 100001 commands accepted'
  rescue ArgumentError
  end
  extra[1].dispose
 end
 command[1].dispose
end
check(capacities==capacities.sort,'buffer capacity not reused')
weak=ObjectSpace::WeakMap.new
temporary=Bitmap.new(4,4);weak[temporary]=true
command=make_batch(1,temporary)
Graphics.__present([command],-1.0,nil,0.0)
command[3][4]=nil;temporary=nil
5.times { GC.start }
check(weak.keys.empty?,'instance storage retained bitmap')
Graphics.__present([command],-1.0,nil,0.0)
check(Graphics.__tile_batches[0]==0,'bitmap removal reused old draw')
command[1].dispose
atlas.dispose;alternate.dispose
File.write('d3d-result.json',JSON.generate({passed:true,pixel_comparisons:comparisons,instance_counts:[0,1,1024,1025,4096,4097,100000],capacity_bytes:capacities,expanded_limit:true,bitmap_released:true,transition:true}))
File.write('runtime-complete.txt','VXA ordered tile instancing PASS')
