# RPG classes/accessors are prepended from the runtime schema by package_template.py.
class Table
  def self._load(bytes)
    raise ArgumentError, 'Expected the original 20x15x3 template Table' unless
      bytes.bytesize == 1820 && bytes.unpack('V5') == [3,20,15,3,900]
    value = allocate
    value.instance_variable_set(:@cells, bytes.byteslice(20,1800).unpack('s<*'))
    value
  end
  def _dump(_depth)
    [3,40,23,3,2760].pack('V5') + @cells.pack('s<*')
  end
  def expand
    original = @cells
    @cells = Array.new(2760,0)
    920.times { |i| @cells[i] = 384 }
    3.times do |z|
      15.times do |y|
        @cells[z*920+y*40,20] = original[z*300+y*20,20]
      end
    end
  end
end

project = ARGV.fetch(0)
map_path = File.join(project,'Data/Map001.rxdata')
system_path = File.join(project,'Data/System.rxdata')
map = Marshal.load(File.binread(map_path))
system = Marshal.load(File.binread(system_path))
raise ArgumentError, 'Expected the original template map dimensions' unless
  map.is_a?(RPG::Map) && [map.width,map.height] == [20,15] && map.data.is_a?(Table)
raise ArgumentError, 'Invalid template starting position or data version' unless
  system.is_a?(RPG::System) && system.start_map_id == 1 &&
  system.start_x.is_a?(Integer) && system.start_x.between?(0,19) &&
  system.start_y.is_a?(Integer) && system.start_y.between?(0,14) &&
  system.magic_number.is_a?(Integer) && system.magic_number.between?(0,0x7fffffff)
previous_version = system.magic_number
map.data.expand
map.width,map.height = 40,23
system.magic_number = (previous_version+1) & 0x7fffffff
File.binwrite(map_path,Marshal.dump(map))
File.binwrite(system_path,Marshal.dump(system))
puts [previous_version,system.magic_number,system.start_x,system.start_y].inspect
