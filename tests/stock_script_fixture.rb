def probe_object(klass,fields)
 o=klass.allocate;fields.each { |k,v| o.instance_variable_set("@#{k}",v) };o
end
def probe_event(x,y)
 return RPG::Event.new(x,y) if STOCK_EXT=='rxdata'
 command=probe_object(RPG::EventCommand,{code:0,indent:0,parameters:[]})
 move=probe_object(RPG::MoveCommand,{code:0,parameters:[]})
 route=probe_object(RPG::MoveRoute,{repeat:true,skippable:false,wait:false,list:[move]})
 condition=probe_object(RPG::Event::Page::Condition,{switch1_valid:false,switch2_valid:false,variable_valid:false,self_switch_valid:false,item_valid:false,actor_valid:false})
 graphic=probe_object(RPG::Event::Page::Graphic,{tile_id:0,character_name:'',character_index:0,direction:2,pattern:1})
 page=probe_object(RPG::Event::Page,{condition:condition,graphic:graphic,move_type:0,move_speed:4,move_frequency:3,move_route:route,walk_anime:true,step_anime:false,direction_fix:false,through:false,priority_type:1,trigger:0,list:[command]})
 probe_object(RPG::Event,{id:0,name:'',x:x,y:y,pages:[page]})
end


def stock_map(count, dense=false, moving=false, blocked=false)
 data=Marshal.load(Marshal.dump($stock_base));data.events.clear
 unless blocked
  data.height.times { |y| data.width.times { |x| data.data.zsize.times { |z| data.data[x,y,z]=z==0 ? (STOCK_EXT=='rxdata' ? 384 : 2816) : 0 } } }
 end
 count.times do |i|
  event=probe_event(dense ? 7 : 9+i%20,dense ? 7 : 4+(i/20)%15)
  event.id=i+1;event.name='stock performance probe'
  event.pages.first.graphic.character_name=$game_player.character_name
  event.pages.first.move_type=moving ? 1 : 0
  event.pages.first.move_frequency=5
  data.events[i+1]=event
 end
 save_data(data,'Data/Map001.'+STOCK_EXT)
 $game_map.setup(1)
 $game_player.moveto(20,11)
 $stock_base
end
