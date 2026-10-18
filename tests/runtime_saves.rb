def expect_error(type)
  begin
    yield
  rescue type
    return
  end
  raise "Expected #{type}"
end

Dir.mkdir('Saves') unless File.directory?('Saves')
Dir.mkdir('Saves/Import') unless File.directory?('Saves/Import')
original = Marshal.dump([Color.new(1, 2, 3), Table.new(2, 3), "한글"])
File.binwrite('Saves/Import/Save1.rxdata', original)
File.binwrite('Save1.rxdata', 'root sentinel')
raise 'import path missing' unless RGSSXP::Saves.exist?(0)
raise 'import priority wrong' unless RGSSXP::Saves.filename(0).include?('/Import/')
reads_before = RGSSXP.__io_threads[2]
file = RGSSXP::Saves.open_read(RGSSXP::Saves.filename(0))
raise 'Import read bypassed native worker' unless RGSSXP.__io_threads[2] == reads_before + 1
raise 'Import mtime changed' unless file.mtime == File.mtime(RGSSXP::Saves.filename(0))
raise 'Import timestamp display timezone changed' unless file.mtime.strftime('%Y/%m/%d %H:%M:%S.%N %z') == File.mtime(RGSSXP::Saves.filename(0)).strftime('%Y/%m/%d %H:%M:%S.%N %z')
values = Marshal.load(file)
file.close
target = RGSSXP::Saves.filename(0, :write)
RGSSXP::Saves.write(target) { |file| Marshal.dump(values, file) }
raise 'new priority wrong' unless RGSSXP::Saves.filename(0) == target
raise 'new marker missing' unless File.binread(target).start_with?(RGSSXP::Saves::MAGIC)
reads_before = RGSSXP.__io_threads[2]
file = RGSSXP::Saves.open_read(target)
raise 'New save read bypassed native worker' unless RGSSXP.__io_threads[2] == reads_before + 1
copied = Marshal.load(file)
file.close
raise 'new save roundtrip failed' unless copied[0] == values[0] && copied[1]._dump(0) == values[1]._dump(0) && copied[2] == values[2]
previous = File.binread(target)
expect_error(RuntimeError) { RGSSXP::Saves.write(target) { |file| file.write('broken'); raise 'write interrupted' } }
raise 'failed write destroyed previous save' unless previous == File.binread(target)
raise 'temporary write leaked' unless Dir.glob(target + '.tmp-*').empty?
expect_error(ArgumentError) { RGSSXP::Saves.write('Saves/Import/Save1.rxdata') {} }
expect_error(ArgumentError) { RGSSXP::Saves.write('Save1.rxdata') {} }
expect_error(ArgumentError) { RGSSXP::Saves.filename(4) }
expect_error(ArgumentError) { RGSSXP::Saves.filename(0, :other) }
File.binwrite(RGSSXP::Saves.filename(1, :write), 'old or corrupt save')
expect_error(IOError) { RGSSXP::Saves.open_read(RGSSXP::Saves.filename(1)) }
second = RGSSXP::Saves.filename(2, :write)
RGSSXP::Saves.write(second) { |file| Marshal.dump(values, file) }
first_time = Time.at(1700000000, 123456700, :nanosecond)
second_time = Time.at(1700000000, 123456800, :nanosecond)
File.utime(first_time, first_time, target);File.utime(second_time, second_time, second)
first_stream = RGSSXP::Saves.open_read(target);second_stream = RGSSXP::Saves.open_read(second)
raise 'Subsecond save ordering lost' unless first_stream.mtime < second_stream.mtime && first_stream.mtime == File.mtime(target) && second_stream.mtime == File.mtime(second)
first_stream.close;second_stream.close
expect_error(IOError) { first_stream.mtime }
raise 'original import changed' unless File.binread('Saves/Import/Save1.rxdata') == original
raise 'root save changed' unless File.binread('Save1.rxdata') == 'root sentinel'
