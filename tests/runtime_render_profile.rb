# Diagnostic pass only: split exactly the same update operations without changing the scene.
module RenderProfile
  CLOCK=Win32API.new('RGSSBenchMetrics','BenchClock','','L')
  ROWS=[]
end
module Graphics
  class << self
    def update
      __begin
      started=RenderProfile::CLOCK.call
      commands=RGSSXP.scene_commands
      built=RenderProfile::CLOCK.call
      __present(commands,-1.0,nil,0.0)
      submitted=RenderProfile::CLOCK.call
      __tick
      finished=RenderProfile::CLOCK.call
      if $bench_frame && $bench_frame>=80
        RenderProfile::ROWS << [$bench_phase,$bench_frame,commands.size,(built-started)/1000.0,(submitted-built)/1000.0,(finished-submitted)/1000.0]
      end
    end
  end
end
at_exit do
  File.open('render-parts.csv','w') do |file|
    file.puts('stage,frame,commands,command_build_ms,native_submit_ms,wait_ms')
    RenderProfile::ROWS.each { |row| file.puts(row.join(',')) }
  end
end
