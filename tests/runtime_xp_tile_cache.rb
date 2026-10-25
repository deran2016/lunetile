require 'json'
def check(v,m);raise m unless v;end
Graphics.resize_screen(192,128)
viewport=Viewport.new(-3,5,160,112)
viewport.color=Color.new(20,40,80,33);viewport.tone=Tone.new(12,-6,5,17)
tile=Tilemap.new(viewport);reference=ReferenceTilemap.new(viewport)
map=Table.new(8,6,3);priorities=Table.new(32768);flash=Table.new(8,6)
bitmaps=[Bitmap.new(256,512)]+Array.new(7) { Bitmap.new(288,128) }
bitmaps.each_with_index { |b,k| (b.height/16).times { |y| (b.width/16).times { |x| b.fill_rect(x*16,y*16,16,16,Color.new((x*37+k*29)%256,(y*41+k*13)%256,(x+y+k)*17%256,80+(x+y)%176)) } } }
tile.map_data=map;tile.priorities=priorities;tile.flash_data=flash;tile.tileset=bitmaps[0];tile.autotiles.replace(bitmaps[1,7])
sprite=Sprite.new(viewport);sprite.bitmap=bitmaps[0];sprite.src_rect.set(16,32,32,32);sprite.z=64;sprite.x=30;sprite.y=0;sprite.opacity=127
normalize=lambda do |layers,node|
 layers.map { |layer| [layer.z,layer.commands.flat_map { |c| c[0]==4 ? RGSSXP.__expand_xp_tile_batch(c) : [c] }.map { |c| c.map { |v| v.is_a?(Color) ? [v.red,v.green,v.blue,v.alpha] : v.equal?(node.instance_variable_get(:@flash_bitmap)) ? :flash : v } }] }
end
capture=lambda do |layers|
 out=[[1,viewport.rect]]
 (layers+[sprite]).sort_by { |v| [v.z,v.is_a?(Sprite) ? v.y : 0,v.serial] }.each { |v| v.emit(out) }
 out << [2,viewport.rect,viewport.effective_color,viewport.tone]
 Graphics.__present(out,-1.0,nil,0.0);b=Graphics.__snapshot;bytes=b.__pixel_bytes;b.dispose;bytes
end
comparisons=0
compare=lambda do |pixels=true|
 reference.map_data=tile.map_data;reference.priorities=tile.priorities;reference.flash_data=tile.flash_data;reference.tileset=tile.tileset;reference.autotiles.replace(tile.autotiles)
 reference.ox=tile.ox;reference.oy=tile.oy;reference.instance_variable_set(:@updates,tile.instance_variable_get(:@updates));reference.instance_variable_set(:@serial,tile.serial)
 a,b=tile.layers,reference.layers
 check(normalize.call(a,tile)==normalize.call(b,reference),'XP command geometry/order mismatch')
 if pixels
  check(capture.call(a)==capture.call(b),'XP full pixels mismatch');comparisons+=1
 end
end
7.times do |slot|
 6.times { |y| 8.times { |x| map[x,y,0]=48*(slot+1)+y*8+x;map[x,y,1]=384+(x+y)%32;map[x,y,2]=0;flash[x,y]=(x==y ? 0xa3f : 0) } }
 3.times do |phase|
  tile.instance_variable_set(:@updates,phase*16);tile.ox=phase*17-33;tile.oy=phase*9-65
  priorities[384]=1;priorities[385]=31;priorities[386]=2
  compare.call
 end
end
# Single-row strips, changing bitmap dimensions, negative/loop scroll and repeated aliases.
tile.autotiles[0]=Bitmap.new(96,32);tile.autotiles[0].fill_rect(0,0,96,32,Color.new(19,87,133,117))
tile.map_data=map=Table.new(2,1,3);tile.flash_data=flash=Table.new(2,1);map[0,0,0]=48;map[1,0,0]=49;flash[0,0]=0xf25
[0,16,32,48].each { |u| tile.instance_variable_set(:@updates,u);tile.ox=-65+u;compare.call }
cache=tile.instance_variable_get(:@xp_tile_cache);check(cache,'XP cache absent')
before=cache.stats;tile.layers;tile.layers;check(cache.stats[0]==before[0],'stationary map reread')
tile.ox+=1;tile.layers;check(cache.stats[0]==before[0],'pixel scroll reread')
# Use a larger map to prove one row/column and cell edits.
tile.map_data=map=Table.new(40,30,3);tile.flash_data=flash=Table.new(40,30)
30.times { |y| 40.times { |x| map[x,y,0]=384 } };tile.ox=tile.oy=0;tile.layers
before=cache.stats;tile.ox=32;tile.layers;check(cache.stats[0]-before[0]==5,'new column count')
before=cache.stats;tile.oy=32;tile.layers;check(cache.stats[0]-before[0]==6,'new row count')
before=cache.stats;map[2,2,0]=385;tile.layers;check(cache.stats[0]-before[0]==1,'single cell edit')
bytes=Marshal.dump(map);before=cache.stats;map[2,2,0]=385+65536;tile.layers;check(cache.stats[0]==before[0]&&Marshal.dump(map)==bytes,'identical normalized write')
flash[2,2]=0xf00;compare.call
priorities[385]=4;compare.call
65.times { |i| map[i%40,i/40,0]=700+i };before=cache.stats;tile.layers;check(cache.stats[0]-before[0]==30,'journal overflow');compare.call
map.send(:initialize_copy,map.clone);compare.call;map.resize(41,31,3);compare.call
tile.map_data=Marshal.load(Marshal.dump(map));compare.call
other=Tilemap.new(viewport);other.map_data=tile.map_data;other.priorities=priorities;other.tileset=bitmaps[0];other.layers
c2=other.instance_variable_get(:@xp_tile_cache);a,b=cache.stats,c2.stats;tile.map_data[2,2,0]=399;tile.layers;other.layers
check(cache.stats[0]-a[0]==1&&c2.stats[0]-b[0]==1,'shared table journal');other.dispose
bitmaps[0].set_pixel(0,0,Color.new(255,0,0,30));compare.call
tile.autotiles[1].dispose;compare.call
GC.start;GC.compact if GC.respond_to?(:compact);compare.call
old=tile.layers;old_dump=Marshal.dump(old.map { |l| [l.z,l.commands[0][2],l.commands[0][4,3]] });tile.ox+=1;tile.layers
check(Marshal.dump(old.map { |l| [l.z,l.commands[0][2],l.commands[0][4,3]] })==old_dump,'returned arrays overwritten')
# Public hooks retain Ruby behavior.
module RGSSXP
 class << self
  alias xp_saved_quad quad
  def quad(*a);$hook_calls=($hook_calls||0)+1;xp_saved_quad(*a);end
 end
end
compare.call(false);check($hook_calls>0,'custom quad bypassed')
module RGSSXP;class << self;alias quad xp_saved_quad;end;end
native=tile.layers.flat_map(&:commands).find { |c| c[0]==4 }
[[4,Object.new,0,Array.new(9),0,0,255],[4,cache,0,Array.new(9),Object.new,0,255]].each do |bad|
 begin;Graphics.__present([bad],-1.0,nil,0.0);raise 'forged batch accepted';rescue TypeError,ArgumentError;end
end
begin;Graphics.__present(Array.new(100001,native),-1.0,nil,0.0);raise 'expanded cap';rescue ArgumentError;end
# Depth zero and flash-depth collisions preserve the original group's insertion order.
tile.oy=24;tile.map_data[1,1,0]=385;priorities[385]=31;compare.call
# Table and bitmap singleton hooks must stay observable.
map=tile.map_data
class << map;alias raw_get [];def [](*a);$table_reads=($table_reads||0)+1;raw_get(*a);end;end
compare.call(false);check($table_reads>0,'custom Table reader bypassed')
class << map;alias [] raw_get;end
image=tile.autotiles[0]
class << image;alias raw_height height;def height;$height_reads=($height_reads||0)+1;raw_height;end;end
tile.map_data[2,2,0]=48;compare.call(false);check($height_reads>0,'custom Bitmap reader bypassed')
class << image;alias height raw_height;end
# A priority tile and flash share depth 1000 in the first partially visible row.
previous_map,previous_flash,previous_oy=tile.map_data,tile.flash_data,tile.oy
tile.map_data=Table.new(2,2,3);tile.flash_data=Table.new(2,2);tile.oy=24
2.times { |y| 2.times { |x| tile.map_data[x,y,0]=385;tile.map_data[x,y,1]=384;tile.flash_data[x,y]=0x5af } }
priorities[385]=31;priorities[384]=-1;sprite.z=1000
[-1,0,1].each { |y| sprite.y=y;compare.call }
check(tile.layers.any? { |layer| layer.z==1000 },'flash/priority depth collision fixture missing')
tile.map_data=previous_map;tile.flash_data=previous_flash;tile.oy=previous_oy
# Numeric caches do not retain an otherwise unused replacement Bitmap.
weak=ObjectSpace::WeakMap.new
replaced=Bitmap.new(96,128);weak[replaced]=true;tile.autotiles[6]=replaced;tile.layers
tile.autotiles[6]=nil;replaced=nil;5.times { GC.start }
check(weak.keys.empty?,'cache retained replaced XP Bitmap')
# Expanded cap applies to one internal batch, including the exact accepted boundary.
[100000,100001].each do |n|
 large=Table.new(n,1,1);n.times { |i| large[i,0,0]=384 }
 c=RGSSXP::XPTileCache.new;c.prepare([large,nil,nil],0,0,n,1,0,[bitmaps[0]]+Array.new(7));c.shape(384,0,[[0,0,0,0,1,1]]);c.commit;c.groups(0)
 command=[4,c,0,[bitmaps[0]]+Array.new(8),0,0,255]
 if n==100000;Graphics.__present([command],-1.0,nil,0.0)
 else;begin;Graphics.__present([command],-1.0,nil,0.0);raise 'expanded limit bypass';rescue ArgumentError;end;end
 c.dispose
end
check(cache.stats[2]<=32*1024*1024,'cache bound')
viewport.rect.set(0,0,1000000,1000000)
begin;tile.layers;raise 'oversized cache accepted';rescue ArgumentError;end
viewport.rect.set(0,0,160,112);tile.layers
live=cache.stats[2];tile.dispose;check(cache.stats[2]<live,'dispose cache memory')
begin;Graphics.__present([native],-1.0,nil,0.0);raise 'disposed cache accepted';rescue ArgumentError;end
File.write('xp-tile-cache.json',JSON.generate({passed:true,pixel_comparisons:comparisons,stats:cache.stats}))
File.write('runtime-complete.txt','XP tile cache,false,false')
