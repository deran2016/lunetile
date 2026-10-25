require 'json'
stock_map(32)
e=$game_map.events.values.first;e.instance_variable_set(:@through,true);e.instance_variable_set(:@move_speed,4);e.moveto(9,4)
Graphics.frame_count=0
STOCK_EXT=='rxdata' ? e.move_right : e.move_straight(6)
move=0
while e.moving?
 Graphics.frame_count+=1;e.update;move+=1
 raise 'Movement stalled' if move>300
end
raise 'Movement duration changed' unless move==(STOCK_EXT=='rxdata' ? 24 : 32)
e.jump(1,0);jump=0
while e.jumping?
 Graphics.frame_count+=1;e.update;jump+=1
 raise 'Jump stalled' if jump>300
end
interpreter=(STOCK_EXT=='rxdata' ? Interpreter : Game_Interpreter).new
code=STOCK_EXT=='rxdata' ? 106 : 230
commands=[probe_object(RPG::EventCommand,{code:code,indent:0,parameters:[10]}),
 probe_object(RPG::EventCommand,{code:122,indent:0,parameters:[1,1,0,0,801]}),
 probe_object(RPG::EventCommand,{code:0,indent:0,parameters:[]})]
$game_variables[1]=0;interpreter.setup(commands,0);wait=0
until $game_variables[1]==801
 Graphics.frame_count+=1;interpreter.update;wait+=1
 raise 'Event wait stalled' if wait>300
end
if STOCK_EXT=='rxdata'
 $game_system.timer=240;$game_system.timer_working=true
 240.times { Graphics.frame_count+=1;$game_system.update }
 timer=$game_system.timer
else
 $game_timer.start(240)
 240.times { Graphics.frame_count+=1;$game_timer.update }
 timer=$game_timer.instance_variable_get(:@count)
end
raise 'Timer duration changed' unless timer==0
result={move_ticks:move,jump_ticks:jump,wait_ticks:wait,timer:timer,x:e.x,y:e.y,real_x:e.real_x,real_y:e.real_y}
File.write('stock-script-speed.json',JSON.generate(result))
File.write('runtime-complete.txt','stock speed,false,false')
