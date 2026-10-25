require 'json'
raise 'Missing candidate helper' unless defined?(Lunetile::StockScripts)
raise 'Fast path disabled before test' unless Lunetile::StockScripts.enabled?
stock_map(32)
if STOCK_EXT=='rxdata';$game_map.check_event(9,4)
else;$game_map.events_xy(9,4);end
raise 'Index did not activate' unless Lunetile::StockScripts.stats[:active]
interpreter=(STOCK_EXT=='rxdata' ? Interpreter : Game_Interpreter).new
case STOCK_EVAL_KIND
when 'conditional'
 commands=[probe_object(RPG::EventCommand,{code:111,indent:0,parameters:[12,'$stock_eval_seen=true; true']}),
  probe_object(RPG::EventCommand,{code:412,indent:0,parameters:[]}),
  probe_object(RPG::EventCommand,{code:0,indent:0,parameters:[]})]
 interpreter.setup(commands,0);interpreter.update
when 'variable'
 raise 'Only VXA has variable Script operand' unless STOCK_EXT=='rvdata2'
 commands=[probe_object(RPG::EventCommand,{code:122,indent:0,parameters:[1,1,0,4,'$stock_eval_seen=true; 17']}),
  probe_object(RPG::EventCommand,{code:0,indent:0,parameters:[]})]
 interpreter.setup(commands,0);interpreter.update
 raise 'Script variable value changed' unless $game_variables[1]==17
when 'route'
 command=probe_object(RPG::MoveCommand,{code:45,parameters:['$stock_eval_seen=true']})
 ending=probe_object(RPG::MoveCommand,{code:0,parameters:[]})
 route=probe_object(RPG::MoveRoute,{repeat:false,skippable:true,wait:false,list:[command,ending]})
 $game_map.events.values.first.force_move_route(route)
 30.times { Graphics.frame_count+=1;$game_map.update }
when 'script'
 command=probe_object(RPG::EventCommand,{code:355,indent:0,parameters:['$stock_eval_seen=true']})
 ending=probe_object(RPG::EventCommand,{code:0,indent:0,parameters:[]})
 interpreter.setup([command,ending],0);interpreter.update
else
 raise 'Unknown Script fixture'
end
raise 'Script did not run' unless $stock_eval_seen
raise 'Fast path survived arbitrary Script' if Lunetile::StockScripts.enabled?
stock_map(32)
raise 'Setup re-enabled optimization' if Lunetile::StockScripts.enabled?
File.write('stock-script-eval.json',JSON.generate({passed:true,kind:STOCK_EVAL_KIND,index_disabled:!Lunetile::StockScripts.stats[:active]}))
File.write('runtime-complete.txt','stock Script fallback,false,false')
