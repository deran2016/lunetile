states = []
alphas = [0,1,64,127,128,192,254,255]
[0,1,64,127,128,192,254,255].each do |opacity|
  alphas.each do |source_alpha|
    alphas.each do |target_alpha|
      target, source = Bitmap.new(1,1), Bitmap.new(1,1)
      target.set_pixel(0,0,Color.new(20,90,180,target_alpha))
      source.set_pixel(0,0,Color.new(201,101,51,source_alpha))
      target.blt(0,0,source,Rect.new(0,0,1,1),opacity)
      color = target.get_pixel(0,0)
      states << [opacity,source_alpha,target_alpha,color.red.to_i,color.green.to_i,color.blue.to_i,color.alpha.to_i]
      target.dispose;source.dispose
    end
  end
end
File.open('types-reference.txt','w') { |file| file.puts('alpha' + "\t" + states.inspect) }
