# Count every native tick, including ticks inside transitions without a driver step.
module EnduranceFocus
  def __tick
    result = super
    @endurance_pause_seconds = endurance_pause_seconds + __timings[10] / 1000.0
    result
  end
  def endurance_pause_seconds
    @endurance_pause_seconds || 0.0
  end
end
Graphics.singleton_class.prepend(EnduranceFocus)
