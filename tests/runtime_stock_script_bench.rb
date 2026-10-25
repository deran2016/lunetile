require 'json'
rows=[]
Graphics.update
def stock_measure(rows,count,kind)
  STOCK_WARMUP.times { |i| yield i }
  GC.start
  samples=[];allocated=GC.stat(:total_allocated_objects);gc=GC.total_time
  STOCK_SAMPLES.times do |i|
    start=Process.clock_gettime(Process::CLOCK_MONOTONIC)
    yield i
    samples << (Process.clock_gettime(Process::CLOCK_MONOTONIC)-start)*1000
  end
  elapsed_gc=(GC.total_time-gc)/1_000_000.0
  allocations=(GC.stat(:total_allocated_objects)-allocated).to_f/STOCK_SAMPLES
  sorted=samples.sort
  rows << {count:count,kind:kind,mean_ms:samples.sum/samples.size,
    p95_ms:sorted[((sorted.size-1)*0.95).ceil],p99_ms:sorted[((sorted.size-1)*0.99).ceil],
    allocated_per_call:allocations,gc_ms:elapsed_gc,
    index:defined?(Lunetile::StockScripts) ? Lunetile::StockScripts.stats : nil}
  File.write('stock-script-progress.json',JSON.generate(rows.map { |r| [r[:count],r[:kind],r[:mean_ms]] }))
end
[0,100,300,1000].each do |count|
  [false,true].each do |dense|
    next if dense && count<300
    stock_map(count,dense)
    stock_measure(rows,count,dense ? 'queries_dense' : 'queries') do
      8.times do |j|
        x,y=dense ? [7,7] : (j%4==0 ? [35,20] : j%4==1 ? [9,4] : j%4==2 ? [17,10] : [27,17])
        if STOCK_EXT=='rxdata';$game_map.passable?(x,y,2);$game_map.check_event(x,y)
        else;$game_map.events_xy(x,y);$game_map.events_xy_nt(x,y);end
      end
    end
  end
  [false,true].each do |moving|
    stock_map(count,false,moving);srand(731)
    stock_measure(rows,count,moving ? 'map_moving' : 'map_idle') do
      Graphics.frame_count+=1
      STOCK_EXT=='rxdata' ? $game_map.update : $game_map.update(true)
    end
  end
  if STOCK_EXT=='rvdata2'
    stock_map(count,false,true,true);srand(731)
    stock_measure(rows,count,'map_blocked') { Graphics.frame_count+=1;$game_map.update(true) }
  end
  ['idle','moving','effects'].each do |mode|
    stock_map(count)
    events=$game_map.events.values
    sprites=events.map { |e| Sprite_Character.new(nil,e) }
    stock_measure(rows,count,'characters_'+mode) do |i|
      if mode=='moving'
        events.each do |e|
          e.instance_variable_set(:@real_x,e.x*(STOCK_EXT=='rxdata' ? 128 : 1)+(i%32)/32.0)
          e.instance_variable_set(:@pattern,i/12%3)
        end
        $game_map.instance_variable_set(:@display_x,(i%128)/8.0)
      elsif mode=='effects'
        events.each { |e| e.instance_variable_set(:@opacity,128+i%128);e.instance_variable_set(:@blend_type,i%3);e.instance_variable_set(:@transparent,i%4==0) }
      end
      sprites.each(&:update)
    end
    sprites.each(&:dispose)
  end
end
File.write('stock-script-bench.json',JSON.generate(rows))
File.write('runtime-complete.txt','stock scripts measured,false,false')
