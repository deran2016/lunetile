def assert_raises(type)
  begin
    yield
  rescue type
    return
  end
  raise "Expected #{type}"
end

[Table.new(3), Table.new(2, 3), Table.new(2, 3, 4), Color.new(1, 2, 3, 4), Tone.new(-1, 2, 3, 4), Rect.new(1, 2, 3, 4)].each do |value|
  copy = Marshal.load(Marshal.dump(value))
  raise 'type changed' unless copy.class == value.class
  raise 'payload changed' unless copy._dump(0) == value._dump(0)
end
assert_raises(ArgumentError) { Table._load('') }
assert_raises(ArgumentError) { Table._load([3, 0x7fffffff, 0x7fffffff, 2, 0].pack('V5')) }
assert_raises(ArgumentError) { Table._load([1, 2, 1, 1, 1].pack('V5') + "\0\0") }
assert_raises(ArgumentError) { Table.new(-1) }
assert_raises(ArgumentError) { Color._load('') }
assert_raises(ArgumentError) { Rect._load('') }
assert_raises(FrozenError) { Table.new(1).freeze[0] = 2 }
assert_raises(FrozenError) { Color.new(1, 2, 3).freeze.red = 4 }
table = Table.new(4, 5, 6)
6.times { |z| 5.times { |y| 4.times { |x| table[x, y, z] = x + 10*y + 100*z } } }
table.resize(5, 4, 7)
raise 'resize lost coordinates' unless table[3, 3, 5] == 533 && table[4, 3, 5] == 0 && table[3, 3, 6] == 0
GC.start
# Pin Korean transcoding into the DLL, independent of external Ruby installations.
raise 'CP949 conversion failed' unless "한글".encode('CP949').encode('UTF-8') == "한글"
