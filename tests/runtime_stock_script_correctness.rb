require 'json'
records=[]
def stock_ids(value)
 value.is_a?(Array) ? value.map(&:id) : value
end
def stock_observe(records,tag)
 queries=[]
 [[9,4],[10,4],[7,7],[-1,0],[40,23],[9.0,4],[nil,4]].each do |x,y|
  if STOCK_EXT=='rxdata'
   found=$game_map.check_event(x,y)
   queries << [x,y,stock_ids(found)]
   queries.last << [2,4,6,8].map { |d| $game_map.passable?(x,y,d) } if x.is_a?(Integer) && y.is_a?(Integer)
  else
   a=$game_map.events_xy(x,y);b=$game_map.events_xy_nt(x,y)
   raise 'Shared public event array' if a.equal?($game_map.events_xy(x,y))
   queries << [x,y,a.map(&:id),b.map(&:id)]
  end
 end
 records << [tag,queries,$game_map.events.values.map { |e| [e.id,e.x,e.y,e.real_x,e.real_y,e.direction,e.pattern,e.through,e.instance_variable_get(:@jump_count),e.instance_variable_get(:@move_route_index)] }]
end
[0,1,31,32,100].each do |count|
 stock_map(count);stock_observe(records,"initial-#{count}")
 if defined?(Lunetile::StockScripts)
  raise 'Index threshold' unless Lunetile::StockScripts.stats[:active]==(count>=32)
 end
 next if count==0
 event=$game_map.events.values.first
 event.instance_variable_set(:@through,true)
 event.moveto(7,7);stock_observe(records,"moveto-#{count}")
 if count>1
  second=$game_map.events.values[1];second.moveto(7,7)
  event.moveto(8,7);event.moveto(7,7)
  stock_observe(records,"stable-order-#{count}")
 end
 if STOCK_EXT=='rxdata';event.move_down;event.move_left
 else;event.move_straight(2);event.move_straight(4);end
 if event.respond_to?(:move_diagonal);event.move_diagonal(6,8)
 else;event.move_upper_right;end
 stock_observe(records,"sequential-#{count}")
 event.jump(2,1);stock_observe(records,"jump-start-#{count}")
 140.times { Graphics.frame_count+=1;$game_map.update }
 stock_observe(records,"jump-end-#{count}")
 event.instance_variable_set(:@through,false);event.erase
 stock_observe(records,"erased-#{count}")
 restored=Marshal.load(Marshal.dump($game_map));$game_map=restored
 stock_observe(records,"reloaded-#{count}")
 records << ['save-ivars',count,$game_map.instance_variables.map(&:to_s).sort]
end
# A seeded autonomous trace checks processing/RNG order independently from timing.
stock_map(100,false,true);srand(731)
360.times do |i|
 Graphics.frame_count+=1
 STOCK_EXT=='rxdata' ? $game_map.update : $game_map.update(true)
 stock_observe(records,"trace-#{i}") if i%30==0
end
records << ['rng-after',Array.new(16) { rand(1_000_000) }]
GC.start;GC.compact if GC.respond_to?(:compact)
stock_observe(records,'after-gc')
# All public movement results keep their values, including chained assignments.
e=$game_map.events.values.first;e.instance_variable_set(:@through,true)
records << ['movement-returns',e.moveto(9,4),e.jump(1,0)]
if defined?(Lunetile::StockScripts)
 before=Lunetile::StockScripts.stats
 raise 'No actual indexed queries' unless before[:queries]>0 && before[:moves]>0
 # Use the real stock Script command, rather than toggling a test-only flag.
 interpreter=(STOCK_EXT=='rxdata' ? Interpreter : Game_Interpreter).new
 command=probe_object(RPG::EventCommand,{code:355,indent:0,parameters:['$stock_script_guard_seen=true']})
 ending=probe_object(RPG::EventCommand,{code:0,indent:0,parameters:[]})
 interpreter.setup([command,ending],0);interpreter.update
 raise 'Script guard did not execute' unless $stock_script_guard_seen
 raise 'Script guard left fast path enabled' if Lunetile::StockScripts.enabled?
 stock_map(32);$game_map.events.values.first.moveto(7,7)
 raise 'Script guard re-enabled by setup' if Lunetile::StockScripts.enabled?
end
File.write('stock-script-oracle.json',JSON.generate(records))
File.write('runtime-complete.txt','stock script correctness,false,false')
