require 'json'
$game_player.instance_variable_set(:@through,true)
$game_player.moveto(1,6)
module Input
  def self.dir4; 6; end
  def self.press?(key); false; end
end
records=[]
[40,60].each do |rate|
  Graphics.render_rate=rate
  30.times { scene.update }
  $game_player.moveto(1,6)
  before=Graphics.__refresh_stats
  frame=Graphics.frame_count
  started=Process.clock_gettime(Process::CLOCK_MONOTONIC)
  360.times { scene.update }
  elapsed=Process.clock_gettime(Process::CLOCK_MONOTONIC)-started
  delta=Graphics.__refresh_stats.zip(before).map { |a,b| a-b }
  raise 'Low-rate logic tick count changed' unless Graphics.frame_count-frame==360
  raise 'Low-rate presentation cadence changed' unless delta[0]==rate*3
  position=[$game_player.real_x,$game_player.real_y]
  records << {render_rate:rate,seconds:elapsed,logic_fps:360/elapsed,present_fps:delta[1]/elapsed,
    missing_fraction:[delta[0]-delta[1],0].max.to_f/delta[0],position:position}
end
raise 'Output rate changed movement speed' unless records[0][:position]==records[1][:position]
File.write('cadence.json',JSON.generate(records))
File.write('runtime-complete.txt','cadence,false,false')
