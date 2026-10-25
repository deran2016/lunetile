require 'json'
def check(v,m);raise m unless v;end
Graphics.resize_screen(160,128)
atlas=Bitmap.new(256,256);atlas.fill_rect(0,0,256,256,Color.new(51,93,137,143))
other=Bitmap.new(256,256);other.fill_rect(0,0,256,256,Color.new(177,83,43,117))
flash=Bitmap.new(32,32);flash.fill_rect(0,0,32,32,Color.new(255,255,255))
def make_batch(count,atlas,other=nil,flashes=false)
 map=Table.new(count,1,1);count.times { |i| map[i,0,0]=other && i.odd? ? 48 : 384 }
 f=flashes ? Table.new(count,1) : nil;count.times { |i| f[i,0]=i%3==0 ? 0xf37 : 0 } if f
 cache=RGSSXP::XPTileCache.new;cache.prepare([map,nil,f],0,0,count,1,0,[atlas,other]+Array.new(6))
 cache.shape(384,0,[[0,0,0,0,32,32]]);cache.shape(48,1,[[0,0,0,0,32,32]]) if other
 cache.commit;groups=cache.groups(0)
 images=[atlas,other]+Array.new(6)+[nil]
 [cache,groups.map { |i,z| [z,[4,cache,i,images,-17,13,91]] }]
end
capture=lambda do |commands|
 Graphics.__present(commands,-1.0,nil,0.0);b=Graphics.__snapshot;bytes=b.__pixel_bytes;b.dispose;bytes
end
comparisons=0
[false,true].each do |flashes|
 cache,groups=make_batch(17,atlas,other,flashes)
 groups.each { |_,c| c[3][8]=flash }
 [0,23,-19].each do |offset|
  commands=[[1,Rect.new(3,7,139,109)]]
  groups.sort_by(&:first).each do |_,c|
   c[4]=offset;commands<<c
   commands<<[0,other,39,17,23,27,0,0,23,27,1,1,11,0,0,141,2,Color.new(30,70,110,41),Tone.new(9,-7,3,12),0,nil,false]
  end
  commands<<[2,Rect.new(3,7,139,109),Color.new(22,40,80,39),Tone.new(7,-11,3,23)]
  legacy=commands.flat_map { |c| c[0]==4 ? RGSSXP.__expand_xp_tile_batch(c) : [c] }
  check(capture.call(commands)==capture.call(legacy),'XP mixed atlas/flash/sprite/viewport pixels');comparisons+=1
 end
 cache.dispose
end
capacities=[]
Graphics.__present([],-1.0,nil,0.0);check(Graphics.__tile_batches[0,2]==[0,0]&&Graphics.__tile_batches[4]==0,'zero instances')
[1,1024,1025,4096,4097,100000].each do |count|
 cache,groups=make_batch(count,atlas);command=groups[0][1]
 Graphics.__present([command],-1.0,nil,0.0);s=Graphics.__tile_batches
 check(s[0]==count&&s[1]==1&&s[4]==1,'XP instance boundary')
 check(s[5]>=count*32&&s[5]<=100000*32,'XP buffer bound');capacities<<s[5]
 if count==1
  Graphics.__present([command,command],-1.0,nil,0.0);check(Graphics.__tile_batches[1]==2,'merged group boundaries')
 end
 if count==100000
  begin;Graphics.__present([command,command],-1.0,nil,0.0);raise 'expanded count limit bypassed';rescue ArgumentError;end
 end
 cache.dispose
end
# Every texture change must retain its own run.
cache,groups=make_batch(8,atlas,other);Graphics.__present([groups[0][1]],-1.0,nil,0.0)
check(Graphics.__tile_batches[0,2]==[8,8],'alternating texture order lost');cache.dispose
Graphics.freeze;Graphics.transition(2)
File.write('xp-d3d.json',JSON.generate({passed:true,pixel_comparisons:comparisons,counts:[0,1,1024,1025,4096,4097,100000],capacity_bytes:capacities,limits:true,alternating:true,flash:true,transition:true}))
File.write('runtime-complete.txt','XP ordered tile instancing,false,false')
