require 'json'
records=[]
def stock_edge_query(records,label,x,y)
 if STOCK_EXT=='rxdata'
  found=$game_map.check_event(x,y)
  records << [label,found.is_a?(Array) ? found.map(&:id) : found,[2,4,6,8].map { |d| $game_map.passable?(x,y,d) }]
 else
  records << [label,$game_map.events_xy(x,y).map(&:id),$game_map.events_xy_nt(x,y).map(&:id)]
 end
end
stock_map(32)
stock_edge_query(records,'build',9,4)
event=$game_map.events.values.first
event.instance_variable_set(:@through,true)
if STOCK_EXT=='rvdata2'
 $game_map.instance_variable_get(:@map).scroll_type=3
end
event.moveto(-1,-1);stock_edge_query(records,'negative-moveto',39,22)
STOCK_EXT=='rxdata' ? event.move_right : event.move_straight(6)
stock_edge_query(records,'edge-move',0,22)
event.jump(-1,-1)
140.times { Graphics.frame_count+=1;$game_map.update }
records << ['edge-position',event.x,event.y,event.real_x,event.real_y]
stock_edge_query(records,'jump-complete',event.x,event.y)
# Same collection size is supported through ordinary Script commands, which
# conservatively disable the index; collection replacement is detected directly.
replacement={};$game_map.events.each { |id,e| replacement[id]=e }
$game_map.instance_variable_set(:@events,replacement)
stock_edge_query(records,'collection-replacement',event.x,event.y)
nonstandard=Class.new(Hash).new
replacement.each { |id,e| nonstandard[id]=e }
$game_map.instance_variable_set(:@events,nonstandard)
stock_edge_query(records,'nonstandard-collection',event.x,event.y)
stock_map(32)
events=$game_map.events.values
first,second=events.first(2)
[first,second].each do |e|
 e.moveto(6,6)
 e.list << probe_object(RPG::EventCommand,{code:0,indent:0,parameters:[]})
end
if STOCK_EXT=='rxdata'
 $game_map.passages[384]|=0x80
else
 $game_map.tileset.flags[2816]|=0x80
end
$game_player.moveto(4,6)
$game_player.set_direction(6) if $game_player.respond_to?(:set_direction)
$game_player.instance_variable_set(:@direction,6)
$game_player.check_event_trigger_there([0])
records << ['counter-triggers',events.select(&:starting).map(&:id)]
events.each do |e|
 STOCK_EXT=='rxdata' ? e.clear_starting : e.clear_starting_flag
end
route=probe_object(RPG::MoveRoute,{repeat:false,skippable:true,wait:true,
 list:[probe_object(RPG::MoveCommand,{code:3,parameters:[]}),
       probe_object(RPG::MoveCommand,{code:15,parameters:[2]}),
       probe_object(RPG::MoveCommand,{code:14,parameters:[1,1]}),
       probe_object(RPG::MoveCommand,{code:0,parameters:[]})]})
first.instance_variable_set(:@through,true);first.force_move_route(route)
300.times do |i|
 Graphics.frame_count+=1
 STOCK_EXT=='rxdata' ? $game_map.update : $game_map.update(true)
 records << ['forced',i,first.x,first.y,first.real_x,first.real_y,first.instance_variable_get(:@wait_count),first.move_route_forcing] if i%10==0
end
records << ['forced-end',first.move_route_forcing]
File.write('stock-script-edges.json',JSON.generate(records))
File.write('runtime-complete.txt','stock script edges,false,false')
