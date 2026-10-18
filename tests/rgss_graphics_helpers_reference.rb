# Own finite fixtures; compare public child properties rather than private field names.
def helper_cells(sprite)
  sprite.instance_variables.each do |name|
    value = sprite.instance_variable_get(name)
    if value.is_a?(Array) && value.length == 16 && value.all? { |cell| cell.is_a?(Sprite) }
      return value
    end
  end
  []
end
def helper_state(sprite)
  cells = helper_cells(sprite)
  [sprite.effect?, cells.length, cells[0,2].collect do |cell|
    [cell.visible,cell.x,cell.y,cell.z,cell.ox,cell.oy,cell.zoom_x.to_f,cell.angle.to_f,
     cell.mirror,cell.opacity,cell.blend_type,
     [cell.src_rect.x,cell.src_rect.y,cell.src_rect.width,cell.src_rect.height]]
  end]
end
begin
File.open('types-reference.txt','w') do |file|
  bitmap = RPG::Cache.picture('')
  sprite = Sprite.new; sprite.bitmap = bitmap
  RPG::Cache.clear
  file.puts('cache_shared_lifetime'+"\t"+[bitmap.disposed?,sprite.bitmap.equal?(bitmap),bitmap.width].inspect)
  fresh = RPG::Cache.picture('')
  file.puts('cache_recreated'+"\t"+[fresh.equal?(bitmap),fresh.width].inspect)
  sprite.dispose;bitmap.dispose;RPG::Cache.clear
  colors = [[255,0,0,255],[20,100,200,128],[7,31,55,17],[101,101,101,255],[255,255,0,0],[230,17,91,254]]
  [-120,0,60,180,360,720].each do |hue|
    bitmap = Bitmap.new(colors.length,1)
    colors.each_with_index { |rgba,i| bitmap.set_pixel(i,0,Color.new(*rgba)) }
    bitmap.hue_change(hue)
    values = (0...colors.length).collect do |i|
      c=bitmap.get_pixel(i,0);[c.red.to_i,c.green.to_i,c.blue.to_i,c.alpha.to_i]
    end
    file.puts('hue_'+hue.to_s+"\t"+values.inspect);bitmap.dispose
  end
  2.times do |phase|
  prefix=phase==0 ? '' : 'odd_'
  4.times do |position|
    data=RPG::Animation.allocate
    data.animation_name='';data.animation_hue=0;data.position=position;data.frame_max=3;data.timings=[]
    data.frames=Array.new(3) do |index|
      frame=RPG::Animation::Frame.allocate;frame.cell_max=2;frame.cell_data=Table.new(16,8)
      16.times { |i| frame.cell_data[i,0]=-1 }
      2.times do |i|
        [index+i,11+i,-7-index,80+index*10,15+index, i,200-index*10,i].each_with_index do |value,col|
          frame.cell_data[i,col]=value
        end
      end
      frame
    end
    sprite=RPG::Sprite.new;sprite.bitmap=Bitmap.new(80,100)
    sprite.x=123;sprite.y=211;sprite.ox=12;sprite.oy=20;sprite.opacity=177
    Graphics.frame_count=phase
    sprite.animation(data,true)
    states=[];9.times { |tick| states << helper_state(sprite);Graphics.frame_count=phase+tick+1;sprite.update }
    file.puts(prefix+'animation_'+position.to_s+"\t"+states.inspect)
    sprite.animation(nil,true)
    file.puts(prefix+'animation_stopped_'+position.to_s+"\t"+helper_state(sprite).inspect)
    Graphics.frame_count=phase
    sprite.loop_animation(data)
    states=[];9.times { |tick| states << helper_state(sprite);Graphics.frame_count=phase+tick+1;sprite.update }
    file.puts(prefix+'loop_'+position.to_s+"\t"+states.inspect)
    sprite.loop_animation(nil)
    file.puts(prefix+'loop_stopped_'+position.to_s+"\t"+helper_state(sprite).inspect)
    sprite.bitmap.dispose;sprite.dispose
  end
  end
end
rescue Exception => error
  File.open('helper-error.txt','w') { |file| file.puts(error.class.name+': '+error.message);file.puts(error.backtrace) }
  exit 1
end
