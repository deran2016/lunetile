require 'json'
Graphics.update
module StockSaveReads
 def load_header(*args);$stock_preview_reads+=1;super;end
end
DataManager.singleton_class.prepend(StockSaveReads)
rows=[]
[0,300].each do |count|
 stock_map(count)
 16.times { |i| raise 'Test save failed' unless DataManager.save_game_without_rescue(i) }
 $stock_preview_reads=0
 windows=Array.new(16) { |i| Window_SaveFile.new(180,i) };windows.each(&:dispose)
 samples=[];reads=[];allocation=[];gc=[]
 5.times do
  GC.start;$stock_preview_reads=0;before=GC.stat(:total_allocated_objects);before_gc=GC.total_time
  start=Process.clock_gettime(Process::CLOCK_MONOTONIC)
  windows=Array.new(16) { |i| Window_SaveFile.new(180,i) }
  samples << (Process.clock_gettime(Process::CLOCK_MONOTONIC)-start)*1000
  reads << $stock_preview_reads;allocation<<GC.stat(:total_allocated_objects)-before;gc<<(GC.total_time-before_gc)/1_000_000.0
  windows.each(&:dispose)
 end
 sorted=samples.sort
 rows << {count:count,mean_ms:samples.sum/samples.size,p95_ms:sorted[((sorted.size-1)*0.95).ceil],reads:reads,allocations:allocation,gc_ms:gc,save_bytes:File.size(LunetileVXA.slot(0))}
end
File.write('stock-script-save-bench.json',JSON.generate(rows))
File.write('runtime-complete.txt','stock save measured')
