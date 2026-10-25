require 'json'
bitmap=Bitmap.new(640,480);bitmap.font.name='Arial';bitmap.font.size=22
results=[]
['repeated','unique'].each do |profile|
 texts=Array.new(1600) { |i| profile=='repeated' ? 'Lunetile 한글 이름표 0000' : format('Lunetile 한글 이름표 %04d',i) }
 100.times { |i| bitmap.draw_text(10,10,320,32,texts[i]) }
 GC.start;samples=[];allocated=GC.stat(:total_allocated_objects);gc=GC.total_time
 1500.times do |i|
  started=Process.clock_gettime(Process::CLOCK_MONOTONIC)
  bitmap.draw_text(10,10,320,32,texts[i+100])
  samples << (Process.clock_gettime(Process::CLOCK_MONOTONIC)-started)*1000
 end
 sorted=samples.sort
 results << {profile:profile,mean_ms:samples.sum/samples.size,p95_ms:sorted[((sorted.size-1)*0.95).ceil],allocated_per_call:(GC.stat(:total_allocated_objects)-allocated).to_f/samples.size,gc_ms:(GC.total_time-gc)/1_000_000.0}
end
File.write('text-bench.json',JSON.generate(results))
bitmap.dispose
File.write('runtime-complete.txt','text bench,false,false')
