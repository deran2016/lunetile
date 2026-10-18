raise 'stock120 not active' unless Graphics.__stock120 && Graphics.logic_rate == 120 && Graphics.frame_rate == 120
bitmap = Bitmap.new(640,480)
bitmap.fill_rect(bitmap.rect,Color.new(30,60,90))
sprite = Sprite.new
sprite.bitmap = bitmap
6.times { Graphics.update }
records = []
[40,60,120].each do |rate|
  Graphics.render_rate = rate
  start = Process.clock_gettime(Process::CLOCK_MONOTONIC)
  before = Graphics.__refresh_stats
  frame = Graphics.frame_count
  240.times { Graphics.update }
  elapsed = Process.clock_gettime(Process::CLOCK_MONOTONIC) - start
  after = Graphics.__refresh_stats
  raise 'logic counter follows render rate' unless Graphics.frame_count - frame == 240
  raise 'presentation cadence wrong' unless after[0] - before[0] == rate * 2
  records << [rate, elapsed, after.zip(before).map { |a,b| a-b }]
end
begin
  Graphics.frame_rate = 60
  raise 'stock120 rate changed'
rescue ArgumentError
end
begin
  Graphics.render_rate = 90
  raise 'invalid output rate accepted'
rescue ArgumentError
end
raise 'output rate changed from another thread' unless Thread.new { begin;Graphics.render_rate=40;false;rescue ThreadError;true;end }.value
RGSSXP::Timing.save_settings(120)
Graphics.render_rate = 60
RGSSXP::Timing.load_settings
raise 'personal FPS did not persist' unless Graphics.render_rate == 120
saved = File.binread(RGSSXP::Timing.settings_path)
class << File
  alias_method :refresh_test_rename, :rename
  def rename(*args)
    raise IOError, 'injected settings write failure' if args.last == RGSSXP::Timing.settings_path
    refresh_test_rename(*args)
  end
end
begin
  RGSSXP::Timing.save_settings(40)
  raise 'failed save reported success'
rescue IOError
ensure
  class << File
    alias_method :rename, :refresh_test_rename
    remove_method :refresh_test_rename
  end
end
raise 'failed settings write destroyed settings' unless File.binread(RGSSXP::Timing.settings_path) == saved && Graphics.render_rate == 120
path = RGSSXP::Saves.filename(0,:write)
RGSSXP::Saves.write(path) { |file| Marshal.dump(123,file) }
raise 'high save version wrong' unless File.binread(path,RGSSXP::Saves::HIGH_MAGIC.bytesize) == RGSSXP::Saves::HIGH_MAGIC
file = RGSSXP::Saves.open_read(path)
raise 'high save read wrong' unless file.timing_rate == 120 && Marshal.load(file) == 123
file.close
File.open(RGSSXP::Saves.filename(1,:write),'wb') { |file| file.write(RGSSXP::Saves::MAGIC);Marshal.dump(456,file) }
file = RGSSXP::Saves.open_read(RGSSXP::Saves.filename(1))
raise 'legacy save version not recognized' unless file.timing_rate == 40 && Marshal.load(file) == 456
file.close
Graphics.freeze
frame = Graphics.frame_count
Graphics.transition(4)
raise 'transition accelerated' unless Graphics.frame_count - frame == 12
raise 'rendered image missing' unless Graphics.__scene_pixel(600,400) == [30,60,90,255]
File.write('refresh-results.txt',records.inspect)
bitmap.dispose;sprite.dispose
File.write('runtime-complete.txt','refresh,false,false')
