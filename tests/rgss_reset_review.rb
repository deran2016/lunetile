$reset_probe_count = ($reset_probe_count || 0) + 1
previous = defined?($reset_probe_bitmap) && $reset_probe_bitmap
File.open('reset-observed.txt','a') do |file|
  file.puts(['entry',$reset_probe_count,previous ? previous.disposed? : nil,Font.default_size,Graphics.frame_count,Graphics.frame_rate,Object.constants.collect { |v| v.to_s }.grep(/Reset/) ].inspect)
end
$reset_probe_bitmap = Bitmap.new(4,4)
Font.default_size = 30
Graphics.frame_rate = 40
background = Bitmap.new(640,480)
background.fill_rect(background.rect,Color.new(20,40,60))
background.draw_text(24,24,590,40,'F12 reset probe: '+$reset_probe_count.to_s)
sprite = Sprite.new
sprite.bitmap = background
begin
  until File.exist?('finish-probe.txt')
    Graphics.update
    Input.update
  end
rescue Exception => error
  File.open('reset-observed.txt','a') { |file| file.puts(['caught',error.class.name,error.class.ancestors.collect { |klass| klass.name }].inspect) }
  raise
end
sprite.dispose
background.dispose
