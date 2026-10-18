entry = File.exist?('reset-run-count.txt') ? File.read('reset-run-count.txt').to_i + 1 : 1
File.open('reset-run-count.txt','w') { |file| file.write(entry.to_s) }
$reset_probe_count = ($reset_probe_count || 0) + 1
previous = defined?($reset_probe_bitmap) && $reset_probe_bitmap
File.open('types-reference.txt','a') do |file|
  file.sync = true
  nodes = defined?($reset_probe_nodes) && $reset_probe_nodes
  states = nodes && nodes.collect do |node|
    begin
      node.disposed?
    rescue Exception => error
      error.class.name
    end
  end
  file.puts('entry'+entry.to_s + "\t" + [$reset_probe_count,previous ? previous.disposed? : nil,Font.default_size,Graphics.frame_count,Graphics.frame_rate,states].inspect)
end
$reset_probe_bitmap = Bitmap.new(4,4)
Font.default_size = 30
Graphics.frame_rate = 60
5.times { Graphics.update }
$reset_probe_nodes = [Sprite.new, Viewport.new(0,0,640,480), Plane.new, Window.new]
unless File.exist?('reset-fired.txt')
  File.open('reset-fired.txt','w') { |file| file.write('Explicit Reset exception test, not physical F12') }
  class Reset < Exception
  end
  raise Reset
end
File.open('runtime-complete.txt','w') { |file| file.write('reset,false,false') }
sleep 0.5
