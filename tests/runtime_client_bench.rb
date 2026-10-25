require 'json'
results=[]
counts=defined?(CLIENT_BENCH_COUNTS) ? CLIENT_BENCH_COUNTS : [0,100,300,1000]
counts.each do |count|
 [1,8,32].each do |views|
  RGSSXP.reset_display
  image=Bitmap.new(32,32);image.fill_rect(image.rect,Color.new(54,112,173,190))
  viewports=Array.new(views) { Viewport.new(0,0,Graphics.width,Graphics.height) }
  sprites=Array.new(count) do |i|
   sprite=Sprite.new(viewports[i%views]);sprite.bitmap=image;sprite.x=i*3%Graphics.width;sprite.y=i*7%Graphics.height;sprite.z=i%5;sprite
  end
  Graphics.update
  10.times { RGSSXP.scene_commands }
  GC.start
  before=GC.stat(:total_allocated_objects);samples=[]
  160.times do
   started=Process.clock_gettime(Process::CLOCK_MONOTONIC)
   RGSSXP.scene_commands
   samples << (Process.clock_gettime(Process::CLOCK_MONOTONIC)-started)*1000
  end
  allocated=GC.stat(:total_allocated_objects)-before;sorted=samples.sort
  results << {sprites:count,viewports:views,mean_ms:samples.sum/samples.size,p95_ms:sorted[((sorted.size-1)*0.95).ceil],allocated_per_frame:allocated.to_f/samples.size}
  sprites.each(&:dispose);viewports.each(&:dispose);image.dispose
 end
end
File.write('client-bench.json',JSON.generate(results))
File.write('runtime-complete.txt','client bench,false,false')
