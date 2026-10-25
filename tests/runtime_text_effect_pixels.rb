require 'json'
records=[];raw=''.b
[0,1,127,255].each do |background_alpha|
 [0,1,128,255].each do |alpha|
  [0,1,2,3].each do |effect|
   [-1000000,-7,3,1000000].each do |x|
    bitmap=Bitmap.new(96,48);bitmap.fill_rect(0,0,96,48,Color.new(23,47,83,background_alpha))
    bitmap.font.name='Arial';bitmap.font.size=20;bitmap.font.color=Color.new(181,73,129,alpha)
    if bitmap.font.respond_to?(:outline=)
     bitmap.font.outline=effect==1||effect==3;bitmap.font.shadow=effect>=2;bitmap.font.out_color=Color.new(13,31,59,alpha)
    end
    # Both the direct-width path and compressed path, with overlapping passes.
    bitmap.draw_text(x,-3,160,30,'Alpha 한글')
    bitmap.draw_text(11,17,[1,3,27,69][effect],21,'日本語ABC',effect%3)
    raw<<bitmap.__pixel_bytes;records << [background_alpha,alpha,effect,x]
    bitmap.dispose
   end
  end
 end
end
File.binwrite('effects-pixels.bin',raw)
File.write('effects-pixels.json',JSON.generate(records))
File.write('runtime-complete.txt','effects full RGBA,false,false')
