require 'json'
def check(condition,message); raise message unless condition; end
Graphics.resize_screen(160,128)
viewport = Viewport.new(3,5,128,96)
left,right = Tilemap.new(viewport),ReferenceTilemap.new(viewport)
flags = Table.new(8192)
left.flags = right.flags = flags
atlas = Bitmap.new(512,1024)
64.times { |y| 32.times { |x| atlas.fill_rect(x*16,y*16,16,16,Color.new(x*7%256,y*11%256,(x+y)*13%256)) } }
left.bitmaps.fill(atlas); right.bitmaps.fill(atlas)
comparisons = 0
[0,128].each do |flag|
  8192.times do |id|
    flags[id] = flag
    a,b = [],[]
    left.draw_tile(a,id,11,-7); right.draw_tile(b,id,11,-7)
    check(a == b,"tile geometry #{id}, #{flag}")
    comparisons += 1
  end
end
12.times do |phase|
  left.instance_variable_set(:@updates,phase*30)
  right.instance_variable_set(:@updates,phase*30)
  (2048...2816).each do |id|
    a,b = [],[]
    left.draw_tile(a,id,0,0); right.draw_tile(b,id,0,0)
    check(a == b,"animated geometry #{id}, #{phase}")
    comparisons += 1
  end
end
[[-0x40000000,0x3fffffff],[1.25,-2.75]].each do |x,y|
  a,b = [],[]
  left.draw_tile(a,2816,x,y);right.draw_tile(b,2816,x,y)
  check(a == b,'native coordinate addition')
end
[Array.new(9) { [0,0,0,0,16,16] },[[]]].each do |parts|
  begin
    RGSSXP.__tile_quads([],atlas,0,0,parts)
    raise 'malformed native tile accepted'
  rescue ArgumentError
  end
end
map = Table.new(5,4,4)
ids = [2048,2096,2240,2816,2863,4352,5888,6272,1536,1,256,512,768]
4.times { |y| 5.times { |x|
  map[x,y,0] = ids[(y*5+x)%ids.size]
  map[x,y,1] = x.even? ? 2816 : 0
  map[x,y,2] = x.odd? ? 512 : 0
  map[x,y,3] = (x+y)%16
} }
flags[2816] = 128
flags[512] = 16
left.map_data = right.map_data = map
# Compare layers after normalizing only independently allocated shadow bitmaps.
canonical = lambda { |tile|
  tile.layers.map { |layer| [layer.z,layer.commands.flat_map { |c| c[0]==3 ? RGSSXP.__expand_tile_batch(c) : [c] }.map { |c| c.map { |v| v.is_a?(Bitmap) && v.equal?(tile.instance_variable_get(:@vxa_shadow)) ? :shadow : v } }] }
}
pixels = lambda { |tile|
  commands = [[1,viewport.rect]]
  tile.layers.each { |layer| layer.emit(commands) }
  commands << [2,viewport.rect,Color.new,Tone.new]
  Graphics.__present(commands,-1.0,nil,0.0)
  bitmap = Graphics.snap_to_bitmap
  result = bitmap.__pixel_bytes
  bitmap.dispose
  result
}
12.times do |phase|
  [left,right].each { |tile| tile.ox=phase*17-60; tile.oy=phase*9-30; tile.instance_variable_set(:@updates,phase*30) }
  viewport.ox,viewport.oy = phase%3,phase%5
  map[phase%5,phase%4,0] = ids[phase%ids.size]
  flags[2816] = phase.odd? ? 128 : 0
  check(canonical.call(left) == canonical.call(right),"layer order/mutation #{phase}")
  check(pixels.call(left) == pixels.call(right),"rendered pixels #{phase}")
end
replacement = Bitmap.new(512,1024)
replacement.fill_rect(replacement.rect,Color.new(123,45,67))
left.bitmaps[0] = right.bitmaps[0] = replacement
check(pixels.call(left) == pixels.call(right),'bitmap replacement')
replacement.clear
check(pixels.call(left) == pixels.call(right),'bitmap edit')
replacement.dispose
check(canonical.call(left) == canonical.call(right),'disposed bitmap')
Graphics.resize_screen(192,128)
viewport.rect.set(0,0,192,128)
check(canonical.call(left) == canonical.call(right),'viewport resize')
check(pixels.call(left) == pixels.call(right),'resized pixels')
check(left.instance_variable_get(:@animated_shapes).size <= 768,'animated cache bounded')
check(left.instance_variable_get(:@tile_shapes).values.flatten.none? { |v| v.is_a?(Bitmap) },'geometry cache retains bitmap')
replacement = Bitmap.new(512,1024)
64.times { |y| 32.times { |x| replacement.fill_rect(x*16,y*16,16,16,Color.new((x+y)*17%256,x*19%256,y*23%256)) } }
left.bitmaps[0] = right.bitmaps[0] = replacement
Graphics.resize_screen(512,256);viewport.rect.set(0,0,512,256);viewport.ox=viewport.oy=0
mosaic=Table.new(16,8,4);left.map_data=right.map_data=mosaic
[left,right].each { |tile| tile.ox=tile.oy=0 }
native_comparisons=0;native_pixels=0
compare_mosaic=lambda do |ids,phase|
  128.times { |i| mosaic[i%16,i/16,0]=ids[i] || 0 }
  [left,right].each { |tile| tile.instance_variable_set(:@updates,phase*30) }
  check(canonical.call(left)==canonical.call(right),'exhaustive native batch geometry')
  check(pixels.call(left)==pixels.call(right),'exhaustive native batch pixels')
  native_comparisons+=ids.size;native_pixels+=1
end
[0,128].each do |table_flag|
  8192.times { |id| flags[id]=table_flag | (id%7==0 ? 16 : 0) }
  (0...8192).each_slice(128) { |ids| compare_mosaic.call(ids,0) }
end
12.times { |phase| (2048...2816).each_slice(128) { |ids| compare_mosaic.call(ids,phase) } }
[left,right,viewport,atlas].each(&:dispose)
replacement.dispose
File.write('tilemap-result.json',JSON.generate({geometry_comparisons:comparisons,pixel_comparisons:15,native_geometry_comparisons:native_comparisons,native_pixel_comparisons:native_pixels,mutations:true}))
File.write('runtime-complete.txt','VXA tilemap parity PASS')
