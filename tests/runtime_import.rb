path = 'Saves/Import/Save1.rxdata'
stream = defined?(RGSSXP::Saves) ? RGSSXP::Saves.open_read(path) : File.open(path, 'rb')
objects = []
objects << Marshal.load(stream) until stream.eof?
stream.close
raise 'Empty original save' if objects.empty?
nodes = []
objects.each { |object| graph_lines(object, {}, nodes) }
File.open('types-reference.txt', 'a') { |file| file.puts('original-save' + "\t" + nodes.inspect) }

if defined?(RGSSXP::Saves)
  target = RGSSXP::Saves.filename(0, :write)
  RGSSXP::Saves.write(target) { |file| objects.each { |object| Marshal.dump(object, file) } }
  stream = RGSSXP::Saves.open_read(target)
  copies = []
  copies << Marshal.load(stream) until stream.eof?
  stream.close
  copied_nodes = []
  copies.each { |object| graph_lines(object, {}, copied_nodes) }
  raise 'Imported save changed after new-format reload' unless nodes == copied_nodes
end
File.open('runtime-complete.txt', 'w') { |file| file.write('import,false,false') }
