require 'json'
records=[];raw=''.b
['Arial','Malgun Gothic','Missing Lunetile Font'].each do |face|
 ['Lunetile AV 0123','한글 테스트','日本語とABC',"A\0B",''].each_with_index do |text,index|
  [0,1,2].each do |align|
   bitmap=Bitmap.new(128,64);bitmap.fill_rect(bitmap.rect,Color.new(23,47,83,index*40))
   bitmap.font.name=face;bitmap.font.size=14+index*3;bitmap.font.bold=index.odd?;bitmap.font.italic=index%3==0
   bitmap.font.color=Color.new(173,61,129,index*60%256)
   if bitmap.font.respond_to?(:outline=)
    bitmap.font.outline=index.odd?;bitmap.font.shadow=index==2;bitmap.font.out_color=Color.new(12,43,76,140)
   end
   x,y,w,h=align==0 ? [-9,-4,112,27] : align==1 ? [11,7,49,22] : [93,40,90,35]
   bitmap.draw_text(x,y,w,h,text,align)
   size=bitmap.text_size(text)
   pixels=if bitmap.respond_to?(:__pixel_bytes)
    bitmap.__pixel_bytes
   else
    output=''.b
    64.times { |py| 128.times { |px| c=bitmap.get_pixel(px,py);output<<[c.red,c.green,c.blue,c.alpha].map(&:to_i).pack('C4') } }
    output
   end
   raw<<pixels;records<<{face:face,index:index,align:align,size:[size.width,size.height],bytes:pixels.bytesize}
   bitmap.dispose
  end
 end
end
File.binwrite('text-pixels.bin',raw)
File.write('text-pixels.json',JSON.generate(records))
File.write('runtime-complete.txt','text pixel oracle,false,false')
