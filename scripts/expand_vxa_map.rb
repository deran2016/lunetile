# Declarations are prepended by package_template_vxa.py; preserve all event/data fields.
class Tone
  def self._load(bytes)
    allocate.tap { |value| value.instance_variable_set(:@bytes,bytes) }
  end
  def _dump(_depth); @bytes; end
end
class Color < Tone; end
class Table
  def self._load(bytes)
    header = bytes.unpack('V5')
    dimension, x, y, z, count = header
    raise ArgumentError, 'Invalid map Table' unless dimension == 3 && x > 0 && y > 0 && z == 4 &&
      count == x*y*z && bytes.bytesize == 20+count*2
    value = allocate
    value.instance_variable_set(:@header, header)
    value.instance_variable_set(:@cells, bytes.byteslice(20,count*2).unpack('v*'))
    value
  end
  def expand(width,height)
    _, x, y, z, = @header
    raise ArgumentError, 'Map/Table dimension mismatch' unless [x,y] == [width,height]
    nx,ny = [x,40].max,[y,23].max
    cells = Array.new(nx*ny*z,0)
    (nx*ny).times { |i| cells[i] = @cells[(y-1)*x+x-1] }
    z.times { |layer| y.times { |row| cells[layer*nx*ny+row*nx,x] = @cells[layer*x*y+row*x,x] } }
    @header,@cells = [3,nx,ny,z,nx*ny*z],cells
    [nx,ny]
  end
  def _dump(_depth)
    @header.pack('V5') + @cells.pack('v*')
  end
end
project = ARGV.fetch(0)
system = Marshal.load(File.binread(File.join(project,'Data/System.rvdata2')))
path = File.join(project,format('Data/Map%03d.rvdata2',system.start_map_id))
map = Marshal.load(File.binread(path))
before = [map.width,map.height]
raise ArgumentError, 'Invalid start position' unless system.start_x.between?(0,map.width-1) && system.start_y.between?(0,map.height-1)
map.width,map.height = map.data.expand(map.width,map.height)
File.binwrite(path,Marshal.dump(map))
puts [system.start_map_id,*before,map.width,map.height,system.start_x,system.start_y].inspect
