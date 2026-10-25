require 'json'
process=Win32API.new('kernel32','GetCurrentProcess','','L').call
memory=Win32API.new('psapi','GetProcessMemoryInfo','LPL','I')
read_memory=lambda do
 bytes=[44,*Array.new(10,0)].pack('L11')
 raise 'Process memory counters failed' unless memory.call(process,bytes,bytes.bytesize)!=0
 fields=bytes.unpack('L11');{private_bytes:fields[10],working_set:fields[3],peak_working_set:fields[2]}
end
bitmap=Bitmap.new(640,480);bitmap.font.name='Arial'
viewports=Array.new(32) { Viewport.new(0,0,640,480) }
sprites=Array.new(300) { |i| sprite=Sprite.new(viewports[i%32]);sprite.bitmap=bitmap;sprite.y=i%40;sprite }
Graphics.update;GC.start
before=read_memory.call;gc=GC.total_time;allocated=GC.stat(:total_allocated_objects)
300.times do |i|
 RGSSXP.scene_commands
 bitmap.draw_text(0,0,300,32,format('Lunetile memory %04d',i))
end
after=read_memory.call
result={before:before,after:after,gc_ms:(GC.total_time-gc)/1_000_000.0,allocated:GC.stat(:total_allocated_objects)-allocated}
result[:text_cache]=Bitmap.__text_cache_stats if Bitmap.respond_to?(:__text_cache_stats)
File.write('client-memory.json',JSON.generate(result))
sprites.each(&:dispose);viewports.each(&:dispose);bitmap.dispose
File.write('runtime-complete.txt','memory,false,false')
