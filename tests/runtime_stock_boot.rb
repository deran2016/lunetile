# This separate fixture injects logical button signals; it is not a physical input test.
module StockBootGraphics
  def update
    File.open('scene-states.txt','a') { |file| file.puts("#{frame_count}:#{$scene.class}") } if frame_count % 10 == 0
    if frame_count >= 180
      File.write('runtime-complete.txt','stock-boot,false,false')
      exit
    end
    super
  end
end
module StockBootInput
  def trigger?(key)
    return true if key == Input::C && Graphics.frame_count == 30
    return true if key == Input::B && Graphics.frame_count == 90
    super
  end
end
Graphics.singleton_class.prepend(StockBootGraphics)
Input.singleton_class.prepend(StockBootInput)
