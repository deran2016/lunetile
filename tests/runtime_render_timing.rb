# A slow rendered frame must not slow the 120Hz simulation.
sprite = Sprite.new
sprite.bitmap = Bitmap.new(64,64)
sprite.bitmap.fill_rect(0,0,64,64,Color.new(255,255,255))
module RGSSXP
  class << self
    alias timing_scene_commands scene_commands
    def scene_commands
      sleep 0.020
      timing_scene_commands
    end
  end
end
30.times { Graphics.update }
Graphics.frame_reset
before = Graphics.__refresh_stats
started = Process.clock_gettime(Process::CLOCK_MONOTONIC)
120.times { Graphics.update }
elapsed = Process.clock_gettime(Process::CLOCK_MONOTONIC)-started
after = Graphics.__refresh_stats
raise "Simulation slowed by rendering: #{elapsed}s" unless elapsed.between?(0.9,1.6)
raise 'No frames presented' unless after[1] > before[1]
raise 'Overdue output frames were not dropped' unless after[2] > before[2]
File.write('render-timing.json',%Q({"seconds":#{elapsed},"logic_ticks":120,"render_rate":#{Graphics.render_rate},"presented":#{after[1]-before[1]},"dropped":#{after[2]-before[2]}}))
File.write('runtime-complete.txt',"render timing PASS,#{$DEBUG},#{$BTEST}")
