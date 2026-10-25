require 'json'
DataManager.init
DataManager.setup_new_game
SceneManager.goto(Scene_Map)
scene = SceneManager.scene
scene.start
scene.post_start
if defined?(FPS_ALTERNATING) && FPS_ALTERNATING
  data=$game_map.data
  data.ysize.times { |y| data.xsize.times { |x| data.zsize.times { |z| data[x,y,z]=z==0 ? ((x+y).even? ? 1536 : 1) : 0 } } }
  tile=scene.instance_variable_get(:@spriteset).instance_variable_get(:@tilemap)
  tile.flags=Table.new(8192);tile.bitmaps.fill(nil)
  [4,5].each { |i| tile.bitmaps[i]=Bitmap.new(64,32);tile.bitmaps[i].fill_rect(0,0,64,32,Color.new(i*35,70,120)) }
end
$game_player.instance_variable_set(:@through,true)
$game_player.moveto(1,6)
$fps_direction = FPS_MOVING ? 6 : 0
module Input
  def self.dir4; $fps_direction; end
  def self.press?(key); false; end
end
$command_times = []
module RGSSXP
  class << self
    alias fps_original_commands scene_commands
    def scene_commands
      started = Process.clock_gettime(Process::CLOCK_MONOTONIC)
      result = fps_original_commands
      $command_times << (Process.clock_gettime(Process::CLOCK_MONOTONIC)-started)*1000
      result
    end
  end
end
advance = lambda do
  if FPS_MOVING
    $fps_direction = 4 if $game_player.real_x >= $game_map.width-2
    $fps_direction = 6 if $game_player.real_x <= 1
  end
  scene.update
end
120.times { advance.call }
native,parse,gpu,combined,total = [],[],[],[],[]
batch_totals = Array.new(5,0)
batch_frames,capacity = 0,0
scene_times,present_times = [],[]
parse_storage = []
cache_times = []
tilemaps = RGSSXP.instance_variable_get(:@nodes).keys.grep(Tilemap)
# Baseline XP emits one Draw per expanded native tile; count outside timed samples.
tile_reference_quads=tilemaps.sum do |tile|
 tile.layers.sum { |layer| layer.commands.sum { |c| c[0]==4 ? RGSSXP.__expand_xp_tile_batch(c).size : c[0]==3 ? RGSSXP.__expand_tile_batch(c).size : 0 } }
end
GC.start
Graphics.frame_reset
$command_times.clear
baseline = Graphics.__refresh_stats
sequence = Graphics.__timings[8]
gpu_sequence = Graphics.__timings[9]
allocated_before = GC.stat(:total_allocated_objects)
gc_before = GC.total_time
started = Process.clock_gettime(Process::CLOCK_MONOTONIC)
frames = Graphics.frame_rate*FPS_SECONDS
frames.times do
  advance.call
  timing = Graphics.__timings
  if timing[8] != sequence
    native << timing[0]
    cache_times << tilemaps.sum { |tile| tile.instance_variable_get(:@cache_prepare_ms).to_f }
    if Graphics.respond_to?(:__render_parts)
      parsed = Graphics.__render_parts[0]
      parse << parsed
      combined << $command_times.last+parsed
      total << $command_times.last+parsed+timing[0]
    end
    if timing[2] && timing[9] && timing[9] != gpu_sequence
      gpu << timing[2]
      gpu_sequence = timing[9]
    end
    if Graphics.respond_to?(:__tile_batches)
      batch = Graphics.__tile_batches
      5.times { |i| batch_totals[i] += batch[i] }
      capacity = [capacity,batch[5]].max
      scene_times << batch[6]; present_times << batch[7]
      batch_frames += 1
    end
    parse_storage << Graphics.__tile_parse_stats if Graphics.respond_to?(:__tile_parse_stats)
    sequence = timing[8]
  end
end
elapsed = Process.clock_gettime(Process::CLOCK_MONOTONIC)-started
allocated = GC.stat(:total_allocated_objects)-allocated_before
gc_ms = (GC.total_time-gc_before)/1_000_000.0
stats = Graphics.__refresh_stats.zip(baseline).map { |a,b| a-b }
summary = lambda do |values|
  next nil if values.empty?
  sorted = values.sort
  {mean:values.sum/values.size,p95:sorted[((sorted.size-1)*0.95).ceil],p99:sorted[((sorted.size-1)*0.99).ceil]}
end
result = {seconds:elapsed,logic_fps:frames/elapsed,present_fps:stats[1]/elapsed,
  missing_fraction:[stats[0]-stats[1],0].max.to_f/stats[0],stats:stats,
  command_ms:summary.call($command_times),parse_ms:summary.call(parse),combined_ms:summary.call(combined),total_ms:summary.call(total),submit_ms:summary.call(native),gpu_ms:summary.call(gpu),gpu_samples:gpu.size,
  cache_prepare_ms:summary.call(cache_times),tile_reference_quads:tile_reference_quads,
  allocated_per_present:allocated.to_f/stats[1],gc_ms:gc_ms,
  tile_caches:RGSSXP.instance_variable_get(:@nodes).keys.grep(Tilemap).filter_map { |tile| (tile.instance_variable_get(:@tile_cache)||tile.instance_variable_get(:@xp_tile_cache))&.stats },
  parse_storage:parse_storage.empty? ? nil : {used_bytes:parse_storage.map { |v| v[0] }.max,reserved_bytes:parse_storage.map { |v| v[1] }.max,tile_used_bytes:parse_storage.map { |v| v[2] }.max,tile_reserved_bytes:parse_storage.map { |v| v[3] }.max,expanded:parse_storage.map { |v| v[4] }.max,scene_ms:summary.call(parse_storage.map { |v| v[5] }),present_ms:summary.call(parse_storage.map { |v| v[6] })},
  map_size:[$game_map.width,$game_map.height],moving:FPS_MOVING,render_rate:Graphics.render_rate}
if batch_frames > 0
  result[:batches] = {frames:batch_frames,
    tile_quads:batch_totals[0].to_f/batch_frames,tile_draws:batch_totals[1].to_f/batch_frames,
    regular_draws:batch_totals[2].to_f/batch_frames,constant_maps:batch_totals[3].to_f/batch_frames,
    instance_maps:batch_totals[4].to_f/batch_frames,capacity_bytes_each:capacity,
    scene_ms:summary.call(scene_times),present_ms:summary.call(present_times)}
end
File.write('fps.json',JSON.generate(result))
File.write('runtime-complete.txt','FPS measured')
