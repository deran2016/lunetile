DataManager.init
DataManager.setup_new_game
SceneManager.goto(Scene_Map)
scene = SceneManager.scene
scene.start
scene.post_start
$game_player.instance_variable_set(:@through,true)
$game_player.moveto(1,6)
module Input
  def self.dir4; 6; end
  def self.press?(key); false; end
end
30.times { scene.update }
Graphics.frame_reset
started = Process.clock_gettime(Process::CLOCK_MONOTONIC)
start_x = $game_player.real_x
frames = Graphics.frame_rate*3
frames.times { scene.update }
elapsed = Process.clock_gettime(Process::CLOCK_MONOTONIC)-started
distance = $game_player.real_x-start_x
raise "Wrong movement distance: #{distance}" unless (distance-11.25).abs < 0.001
raise "Movement slowed in real time: #{elapsed}" unless elapsed.between?(2.7,3.6)
File.write('movement.json',%Q({"seconds":#{elapsed},"logic_rate":#{Graphics.frame_rate},"render_rate":#{Graphics.render_rate},"distance":#{distance},"frames":#{frames}}))
File.write('runtime-complete.txt','real-time movement PASS')
