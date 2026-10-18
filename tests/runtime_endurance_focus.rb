module Graphics
  @pauses = [0,2500,0,1000,0]
  def self.__tick
    @last_pause = @pauses.shift
    :tick_result
  end
  def self.__timings
    [nil]*10+[@last_pause]
  end
end
load File.expand_path('endurance_focus.rb',__dir__)
raise 'Focus counter did not start at zero' unless Graphics.endurance_pause_seconds==0
raise 'Tick return changed' unless Graphics.__tick==:tick_result
before=Graphics.endurance_pause_seconds
3.times { Graphics.__tick }
raise 'Transition ticks lost a focus pause' unless Graphics.endurance_pause_seconds-before==3.5
Graphics.__tick
raise 'Last zero tick erased earlier pauses' unless Graphics.endurance_pause_seconds==3.5
puts 'Endurance focus: intermediate transition pauses counted once PASS'
