# Own fixtures: default damage text metadata/bounds and viewport-dependent animation placement.
def extended_cells(sprite)
  sprite.instance_variables.each do |name|
    value=sprite.instance_variable_get(name)
    return value if value.is_a?(Array) && value.length==16 && value.all? { |cell| cell.is_a?(Sprite) }
  end
  []
end
begin
File.open('types-reference.txt','w') do |file|
  [[123,false],[-123,true],['Miss',false]].each_with_index do |pair,index|
    sprite=RPG::Sprite.new;sprite.x=123;sprite.y=211;sprite.oy=20
    sprite.damage(pair[0],pair[1])
    child=nil
    sprite.instance_variables.each do |name|
      value=sprite.instance_variable_get(name)
      child=value if value.is_a?(Sprite) && value.bitmap && value.bitmap.width==160 && value.bitmap.height==48
    end
    raise 'Damage child not found' unless child
    bitmap=child.bitmap;font=bitmap.font;color=font.color
    metadata=[bitmap.width,bitmap.height,font.name,font.size,font.bold,font.italic,[color.red.to_i,color.green.to_i,color.blue.to_i,color.alpha.to_i]]
    file.puts('damage_font_'+index.to_s+"\t"+metadata.inspect)
    left,top,right,bottom=bitmap.width,bitmap.height,-1,-1
    digest=2166136261
    bitmap.height.times do |y|
      bitmap.width.times do |x|
        pixel=bitmap.get_pixel(x,y)
        packed=(pixel.red.to_i<<24)|(pixel.green.to_i<<16)|(pixel.blue.to_i<<8)|pixel.alpha.to_i
        digest=((digest*16777619)^packed)&0xffffffff
        if pixel.alpha>0
          left=[left,x].min;right=[right,x].max;top=[top,y].min;bottom=[bottom,y].max
        end
      end
    end
    file.puts('damage_bounds_'+index.to_s+"\t"+[left,top,right,bottom].inspect)
    file.puts('damage_pixels_'+index.to_s+"\t"+digest.inspect)
    sprite.dispose
  end
  [[17,23,320,240],[0,0,640,320],[0,0,640,480]].each_with_index do |rect,index|
    viewport=Viewport.new(*rect);viewport.ox=13;viewport.oy=19
    data=RPG::Animation.allocate;data.animation_name='';data.animation_hue=0;data.position=3;data.frame_max=1;data.timings=[]
    data.id=index+1;data.name='Own viewport fixture'
    frame=RPG::Animation::Frame.allocate;frame.cell_max=1;frame.cell_data=Table.new(16,8)
    16.times { |i| frame.cell_data[i,0]=-1 }
    [0,11,-7,100,0,0,255,0].each_with_index { |value,col| frame.cell_data[0,col]=value }
    data.frames=[frame]
    sprite=RPG::Sprite.new(viewport);sprite.bitmap=Bitmap.new(80,100)
    Graphics.frame_count=0;sprite.animation(data,true)
    cell=extended_cells(sprite).first;raise 'Animation child not found' unless cell
    file.puts('screen_animation_'+index.to_s+"\t"+[cell.x,cell.y,cell.z,cell.ox,cell.oy,cell.viewport.equal?(viewport)].inspect)
    sprite.animation(nil,true);sprite.loop_animation(data)
    cell=extended_cells(sprite).first;raise 'Loop child not found' unless cell
    file.puts('screen_loop_'+index.to_s+"\t"+[cell.x,cell.y,cell.z,cell.ox,cell.oy,cell.viewport.equal?(viewport)].inspect)
    sprite.bitmap.dispose;sprite.dispose;viewport.dispose
  end
end
rescue Exception => error
  File.open('extended-error.txt','w') { |file| file.puts(error.class.name+': '+error.message);file.puts(error.backtrace) }
  exit 1
end
