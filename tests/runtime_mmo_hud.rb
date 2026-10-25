# Pixel checks use generated atlases in an isolated launcher, without original map edits.
def rgba(bitmap,x,y)
  c=bitmap.get_pixel(x,y);[c.red,c.green,c.blue,c.alpha].map(&:to_i)
end
def show_frames
  target=Graphics.__refresh_stats[1]+2
  120.times{Graphics.update;return if Graphics.__refresh_stats[1]>=target}
  raise 'HUD pixel probe did not present two frames'
end
atlas=Bitmap.new(192,128)
48.times{|i|atlas.fill_rect(i%6*16,i/6*16,16,16,Color.new(i%4*64+24,i/4%4*64+24,i/16*80+24))}
atlas.fill_rect(96,0,96,128,Color.new(0,255,255))
simple=Bitmap.new(64,32);simple.fill_rect(0,0,32,32,Color.new(240,220,20));simple.fill_rect(32,0,32,32,Color.new(10,10,10))
sheet=Bitmap.new(256,32)
sheet.fill_rect(0,0,32,32,Color.new(255,0,0));sheet.fill_rect(32,0,32,32,Color.new(0,255,0))
sheet.fill_rect(64,0,32,32,Color.new(0,0,255,128));sheet.fill_rect(112,0,16,32,Color.new(255,255,0))
sheet.fill_rect(128,0,32,32,Color.new(240,20,220))
icon=Bitmap.new(24,24);icon.fill_rect(icon.rect,Color.new(230,200,50))
RPG::Cache.define_singleton_method(:tileset){|_|sheet}
RPG::Cache.define_singleton_method(:autotile){|name|name=='atlas' ? atlas : simple}
RPG::Cache.define_singleton_method(:icon){|_|icon}
MapFixture=Struct.new(:map_id,:width,:height,:data,:tileset_name,:autotile_names,:priorities)
data=Table.new(8,6,3);48.times{|i|data[i%8,i/8,0]=48+i}
map=MapFixture.new(1,8,6,data,'sheet',['atlas','simple','','','','',''],Table.new(600))
preview=LunetileMMO::Minimap.new(map)
48.times do |i|
  x,y=i%8,i/8;left=x*preview.bitmap.width/8;top=y*preview.bitmap.height/6
  w=(x+1)*preview.bitmap.width/8-left;h=(y+1)*preview.bitmap.height/6-top
  RGSSXP::AUTOTILE_QUARTERS[i].each_with_index do |part,corner|
    expected=[part%4*64+24,part/4%4*64+24,part/16*80+24,255]
    actual=rgba(preview.bitmap,left+(w*(corner%2==0 ? 0.25 : 0.75)).to_i,top+(h*(corner/2==0 ? 0.25 : 0.75)).to_i)
    raise "Autotile #{i} quarter #{corner}: #{actual} != #{expected}" unless actual==expected
  end
end
preview.dispose
data=Table.new(3,1,3);data[0,0,0]=384;data[0,0,1]=386;data[0,0,2]=387
data[1,0,0]=388;data[1,0,1]=385;data[2,0,0]=96
map.data=data;map.width=3;map.height=1;map.priorities[388]=2
preview=LunetileMMO::Minimap.new(map)
viewport=Viewport.new(0,0,96,32);reference=Tilemap.new(viewport)
reference.map_data=data;reference.tileset=sheet;reference.autotiles[0]=atlas;reference.autotiles[1]=simple;reference.priorities=map.priorities
show_frames
[[8,8],[24,8],[40,8],[72,8]].each do |x,y|
  expected=Graphics.__scene_pixel(x,y);actual=rgba(preview.bitmap,x*2,y*2)
  raise "Layer/alpha/priority mismatch #{actual} != #{expected}" unless actual.zip(expected).all?{|a,b|(a-b).abs<=1}
end
reference.dispose;viewport.dispose;preview.dispose
scene=LunetileMMO::Scene.allocate;scene.setup_hud
panels=scene.instance_variable_get(:@panels);chat=panels[:chat];status=panels[:status]
raise 'HUD geometry' unless [status.x,status.y,status.width,status.height]==[16,656,1116,48]
raise 'Top-right quickslots' unless [panels[:quicks].x,panels[:quicks].y,panels[:quicks].width,panels[:quicks].height]==[1048,16,216,100]
raise 'Bottom-right menu button' unless [panels[:menu_button].x,panels[:menu_button].y]==[1148,656]
raise 'Chat anchor' unless chat.y+chat.height+14==status.y
field=Sprite.new;field.z=1200;field.bitmap=Bitmap.new(1280,720)
chat.alpha=144
chat.redraw(:probe){|p|p.bitmap.fill_rect(350,100,8,8,Color.new(230,200,50))}
opaque=[];foreground=[]
[Color.new(255,0,0),Color.new(0,255,0)].each do |color|
  field.bitmap.fill_rect(field.bitmap.rect,color);show_frames
  opaque<<Graphics.__scene_pixel(chat.x+380,chat.y+140)
  foreground<<Graphics.__scene_pixel(chat.x+352,chat.y+102)
end
raise "Chat did not blend field graphics: #{opaque}" unless opaque[0]!=opaque[1] && opaque.all?{|v|v[3]==255}
raise "Foreground faded: #{foreground}" unless foreground==[[230,200,50,255]]*2
raise 'HUD does not cover field text' unless chat.sprite.z>field.z
name=Bitmap.new(200,40);name.font.name='맑은 고딕';name.font.size=20
LunetileMMO::Theme.outlined_text(name,4,4,192,32,'NPC 이름',Color.new(255,255,255))
ink=[];black=[]
40.times{|y|200.times{|x|c=rgba(name,x,y);next if c[3]<64;(c[0..2].min>200 ? ink : black)<<[x,y]}}
raise 'Name outline has no pixels' if ink.empty?||black.empty?
[0,1].each do |axis|
  raise 'Name outline missing a side' unless black.map{|p|p[axis]}.min<ink.map{|p|p[axis]}.min && black.map{|p|p[axis]}.max>ink.map{|p|p[axis]}.max
end
name.dispose
$game_map=map;scene.update_minimap;cached=scene.instance_variable_get(:@minimap)
10.times{scene.update_minimap;raise 'Minimap rebuilt on an unchanged map' unless scene.instance_variable_get(:@minimap).equal?(cached)}
map.map_id=2;scene.update_minimap
raise 'Old map cache not released' unless cached.bitmap.disposed?
raise 'Shared RTP images disposed' if sheet.disposed? || atlas.disposed? || simple.disposed?
[[1,1],[1,500],[500,1],[40,23]].each do |w,h|
  m=MapFixture.new(3,w,h,Table.new(w,h,3),'sheet',['','','','','','',''],map.priorities)
  p=LunetileMMO::Minimap.new(m);r=p.rect
  raise 'Unbounded minimap' unless r.width.between?(1,192) && r.height.between?(1,106)
  [[-100,-100],[0,0],[w-1,h-1],[w+100,h+100]].each do |x,y|
    px,py=p.point(x,y);raise 'Marker escaped map' unless px>=r.x && px<r.x+r.width && py>=r.y && py<r.y+r.height
  end
  p.dispose
end
last=scene.instance_variable_get(:@minimap);scene.dispose
raise 'Scene leaked minimap bitmap' unless last.bitmap.disposed?
raise 'Scene disposed shared RTP images' if sheet.disposed? || atlas.disposed? || simple.disposed?
field_bitmap=field.bitmap;field.dispose;field_bitmap.dispose
[atlas,simple,sheet,icon].each(&:dispose)
File.write('hud-pixels.json',JSON.generate({'passed'=>true,'autotile_quarters'=>192,'layers_alpha_priority'=>true,'chat_rgba'=>opaque,'hud_height'=>48,'top_right_quickslots'=>true,'bottom_right_menu'=>true,'name_outline_all_sides'=>true,'map_cache_reused_and_released'=>true,'rtp_cache_preserved'=>true,'marker_bounds'=>true}))
File.write('runtime-complete.txt','hud,false,false')
sleep 0.5
