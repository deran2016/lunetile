require 'json'
def check(value,message);raise message unless value;end
map=Table.new(40,30,4)
30.times { |y| 40.times { |x| map[x,y,0]=1536 } }
flags=Table.new(8192);flags[2816]=128
unchanged=map._dump(0)
map[1,1,0]=1537;map[1,1,0]=1536;map.resize(40,30,4)
check(map._dump(0)==unchanged && map.clone._dump(0)==unchanged,'tracking changed Marshal payload')
viewport=Viewport.new(0,0,128,96)
tile=Tilemap.new(viewport);tile.map_data=map;tile.flags=flags
reference=ReferenceTilemap.new(viewport)
def compare_cache(tile,reference)
  reference.map_data=tile.map_data;reference.flags=tile.flags
  reference.bitmaps.replace(tile.bitmaps);reference.ox=tile.ox;reference.oy=tile.oy
  reference.instance_variable_set(:@updates,tile.instance_variable_get(:@updates))
  normalize=lambda do |node|
    node.layers.map do |layer|
      [layer.z,layer.commands.flat_map { |c| c[0]==3 ? RGSSXP.__expand_tile_batch(c) : [c] }.map { |c|
        c.map { |v| v.is_a?(Bitmap) && v.equal?(node.instance_variable_get(:@vxa_shadow)) ? :shadow : v }
      }]
    end
  end
  check(normalize.call(tile)==normalize.call(reference),'incremental cache differs from legacy geometry')
end
atlas=Bitmap.new(512,1024);atlas.fill_rect(atlas.rect,Color.new(41,63,87))
tile.bitmaps.fill(atlas)
tile.layers
cache=tile.instance_variable_get(:@tile_cache)
check(cache,'native cache not used')
initial=cache.stats
10.times { tile.layers }
check(cache.stats[0,2]==initial[0,2],'stationary cache rebuilt')
tile.ox=1;tile.layers
check(cache.stats[0,2]==initial[0,2],'pixel scroll rebuilt')
tile.ox=32;tile.layers
check(cache.stats[0]-initial[0]==4,'new column not isolated')
before=cache.stats;tile.oy=32;tile.layers
check(cache.stats[0]-before[0]==5,'new row not isolated')
before=cache.stats;map[2,2,0]=1537;tile.layers
check(cache.stats[0]-before[0]==1,'one-cell edit not isolated')
bytes=Marshal.dump(map)
before=cache.stats;map[2,2,0]=1537+65536;tile.layers
check(cache.stats[0]==before[0] && Marshal.dump(map)==bytes,'unchanged normalized write invalidated')
before=cache.stats;map[2,2,1]=2816;tile.layers
check(cache.stats[0]-before[0]==2,'table edge dependency not refreshed')
compare_cache(tile,reference)
65.times { |i| map[i%40,i/40,0]=1600+i }
before=cache.stats;tile.layers
check(cache.stats[0]-before[0]==20,'journal overflow did not refresh visible range')
compare_cache(tile,reference)
before=cache.stats;flags[1536]=16;tile.layers
check(cache.stats[0]-before[0]==20,'flags change did not refresh')
compare_cache(tile,reference)
other=Tilemap.new(viewport);other.map_data=map;other.flags=flags;other.bitmaps.fill(atlas);other.ox=tile.ox;other.oy=tile.oy;other.layers
second=other.instance_variable_get(:@tile_cache)
a,b=cache.stats,second.stats;map[3,3,0]=1666;tile.layers;other.layers
check(cache.stats[0]-a[0]==1 && second.stats[0]-b[0]==1,'shared Table consumer lost change')
compare_cache(tile,reference)
before=cache.stats;map[30,20,0]=1700;tile.layers
check(cache.stats[0]==before[0],'offscreen edit rebuilt visible cells')
before=cache.stats;map.send(:initialize_copy,map.clone);tile.layers
check(cache.stats[0]-before[0]==20,'copy did not invalidate')
compare_cache(tile,reference)
before=cache.stats;map.resize(41,31,4);tile.layers
check(cache.stats[0]-before[0]==20,'resize did not invalidate')
compare_cache(tile,reference)
before=cache.stats;tile.map_data=Marshal.load(Marshal.dump(map));tile.layers
check(cache.stats[0]-before[0]==20,'loaded Table identity reused')
compare_cache(tile,reference)
map=tile.map_data;map[2,2,0]=2048;tile.layers
before=cache.stats;tile.instance_variable_set(:@updates,30);tile.layers
check(cache.stats[0]==before[0] && cache.stats[1]>before[1],'animation reread map or did not update')
compare_cache(tile,reference)
check(cache.stats[2]<=32*1024*1024,'cache memory exceeded limit')
# Native cache must not retain a replaced bitmap or its GPU pointer.
weak=ObjectSpace::WeakMap.new
replaced=Bitmap.new(32,32);weak[replaced]=true;tile.bitmaps[4]=replaced;tile.layers
tile.bitmaps[4]=nil;replaced=nil
5.times { GC.start }
check(weak.keys.empty?,'cache retained replaced Bitmap')
command=tile.layers.map { |layer| layer.commands[0] }.max_by { |batch| RGSSXP.__expand_tile_batch(batch).size }
check(command[0]==3,'native batch missing')
live_bytes=cache.stats[2]
begin
 Graphics.__present(Array.new(100000/RGSSXP.__expand_tile_batch(command).size+1,command),-1.0,nil,0.0)
 raise 'expanded command limit bypassed'
rescue ArgumentError
end
begin
 RGSSXP::TileCache.new.prepare(map,flags,0,0,1_000_000,1_000_000,0)
 raise 'memory bound bypassed'
rescue ArgumentError
end
begin
 Graphics.__present([[3,Object.new,0,Array.new(10),0,0]],-1.0,nil,0.0)
 raise 'forged native buffer accepted'
rescue TypeError
end
begin
 Graphics.__present([[3,cache,0,tile.bitmaps+[nil],Object.new,0]],-1.0,nil,0.0)
 raise 'nonprimitive batch origin accepted'
rescue TypeError
end
tile.dispose
begin
 Graphics.__present([command],-1.0,nil,0.0)
 raise 'disposed cache accepted'
rescue ArgumentError
end
class CustomCacheMap < Table;end
fallback=Tilemap.new(viewport);fallback.map_data=CustomCacheMap.new(2,2,4);fallback.map_data[0,0,0]=1536;fallback.bitmaps.fill(atlas)
check(fallback.layers[0].commands[0][0]==0,'custom Table did not fall back')
fallback.map_data=Table.new(2,2,0)
check(fallback.layers.all? { |layer| layer.commands.empty? },'zero-layer Table fallback')
fallback.map_data=map
viewport.rect.width=-40
check(fallback.layers.all? { |layer| layer.commands.empty? },'negative viewport fallback')
viewport.rect.width=128
fallback.dispose;other.dispose;reference.dispose;viewport.dispose;atlas.dispose
File.write('cache-result.json',JSON.generate({passed:true,stationary_reads:0,pixel_scroll_reads:0,new_column_reads:4,new_row_reads:5,changed_cell_reads:1,memory_bytes:live_bytes,released_bytes:cache.stats[2],shared_table:true,journal_overflow:true,marshal_preserved:true,bitmap_released:true}))
File.write('runtime-complete.txt','VXA native cache PASS')
