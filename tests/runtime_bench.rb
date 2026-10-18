# Identical logical input; rendering and stock map/sprite updates remain enabled.
module Input
  class << self
    def dir4;0;end
    def trigger?(key);false;end
    def press?(key);false;end
  end
end
%w[Actors Classes Skills Items Weapons Armors Enemies Troops States Animations Tilesets CommonEvents System].each do |name|
  eval('$data_'+name.gsub(/([a-z])([A-Z])/,'\\1_\\2').downcase+' = load_data("Data/'+name+'.rxdata")')
end
$game_temp=Game_Temp.new;$game_system=Game_System.new
$game_switches=Game_Switches.new;$game_variables=Game_Variables.new;$game_self_switches=Game_SelfSwitches.new
$game_screen=Game_Screen.new;$game_actors=Game_Actors.new;$game_party=Game_Party.new;$game_troop=Game_Troop.new
$game_map=Game_Map.new;$game_player=Game_Player.new;$game_party.setup_starting_members
reset=Win32API.new('RGSSBenchMetrics','BenchReset','I','I')
stage=Win32API.new('RGSSBenchMetrics','BenchStage','I','I')
begin_frame=Win32API.new('RGSSBenchMetrics','BenchBegin','','I')
logic_done=Win32API.new('RGSSBenchMetrics','BenchLogic','','I')
end_frame=Win32API.new('RGSSBenchMetrics','BenchEnd','','I')
clock=Win32API.new('RGSSBenchMetrics','BenchClock','','L')
write=Win32API.new('RGSSBenchMetrics','BenchWrite','P','I')
raise 'Metrics initialization failed' unless reset.call(1)==1
start=clock.call;3000.times { };empty=clock.call-start
start=clock.call;3000.times { begin_frame.call;logic_done.call;end_frame.call };cost=clock.call-start
File.open('instrumentation.txt','w') { |file| file.puts(((cost-empty)/3000.0).to_s) }
raise 'Metrics reset failed' unless reset.call(1)==1
frames=File.read('bench-frames.txt').to_i
raise 'Invalid benchmark duration' unless frames>=60 && frames<=1800
Graphics.frame_rate=40
foreground=Win32API.new('user32','GetForegroundWindow','','L')
window_pid=Win32API.new('user32','GetWindowThreadProcessId','LP','L')
process_pid=Win32API.new('kernel32','GetCurrentProcessId','','L').call
pid_buffer=[0].pack('L');initial_frame=Graphics.frame_count;deadline=Time.now.to_f+120
File.open('bench-ready.txt','w'){|file|file.write('Waiting for foreground before warmup and measurement')}
loop do
  window_pid.call(foreground.call,pid_buffer)
  break if pid_buffer.unpack('L')[0]==process_pid
  raise 'Benchmark foreground setup timed out' if Time.now.to_f>deadline
  Graphics.update
end
Graphics.frame_count=initial_frame;Graphics.frame_reset
gpu=[];last_gpu=-1;oracles=[]
4.times do |phase|
  $bench_phase=phase
  $game_variables[2]=0
  $game_map.setup(phase*100+1);$game_player.moveto(10,7);$game_player.refresh
  $game_system.timer=frames+80;$game_system.timer_working=true
  sprites=Spriteset_Map.new
  Graphics.transition(0);Graphics.frame_reset
  raise 'Metrics stage failed' unless stage.call(phase)==1
  File.open('bench-progress.txt','w') { |file| file.puts(phase) }
  (frames+80).times do |index|
    $bench_frame=index
    raise 'Metrics begin failed' if index>=80 && begin_frame.call!=1
    if index%16==0 && !$game_player.moving?
      direction=[6,2,4,8][index/64%4]
        case direction
        when 6 then $game_player.move_right
        when 2 then $game_player.move_down
        when 4 then $game_player.move_left
        when 8 then $game_player.move_up
        end
    end
    $game_system.map_interpreter.update;$game_map.update;$game_player.update;$game_system.update;$game_screen.update;sprites.update
    raise 'Metrics logic failed' if index>=80 && logic_done.call!=1
    Graphics.update
    raise 'Metrics end failed' if index>=80 && end_frame.call!=1
    if File.exist?('bench-gpu.txt') && index>=80
      timing=Graphics.__timings
      if timing[9] && timing[9]!=last_gpu
        last_gpu=timing[9];gpu << [phase,timing[8],timing[9],timing[2],timing[3],timing[4],timing[10]]
      end
    end
  end
  oracles << [$game_player.x,$game_player.y,$game_system.timer,$game_variables[2],$game_map.events.values.collect { |event| [event.id,event.x,event.y,event.direction,event.pattern] }.sort]
  sprites.dispose
end
raise 'Missing measured frames' unless write.call('frames.csv')==frames*4
File.open('oracle.txt','w') { |file| file.write(oracles.inspect) }
File.open('gpu.csv','w') { |file| gpu.each { |row| file.puts(row.join(',')) } }
File.open('runtime-complete.txt','w') { |file| file.write('rendered-benchmark,false,false') }
sleep 0.3
