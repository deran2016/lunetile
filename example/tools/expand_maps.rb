require 'json'
# Generate only the packaged copy; the supplied XP project remains untouched.
module RPG;end
JSON.parse(File.read(ARGV.fetch(2))).each do |name,fields|
  eval('class '+name+'; attr_accessor '+fields.map{|f|':'+f}.join(',')+'; end')
end
class Table
  def initialize(x,y,z);@dim=3;@size=[x,y,z];@cells=Array.new(x*y*z,0);end
  def self._load(bytes)
    dim,x,y,z,count=bytes.unpack('V5');raise 'Invalid Table' unless x*y*z==count&&bytes.bytesize==20+count*2
    t=new(x,y,z);t.instance_variable_set(:@dim,dim);t.instance_variable_set(:@cells,bytes.byteslice(20..-1).unpack('v*'));t
  end
  def _dump(*);[@dim,*@size,@cells.size].pack('V5')+@cells.pack('v*');end
  def []=(x,y,z,v);@cells[x+y*@size[0]+z*@size[0]*@size[1]]=v;end
end
root=ARGV.fetch(0);layouts=JSON.parse(File.read(ARGV.fetch(1)))
original=File.binread(File.join(root,'Data/Map001.rxdata'))
infos=Marshal.load(File.binread(File.join(root,'Data/MapInfos.rxdata')))
layouts.each do |layout|
  id=layout.fetch('id');path=File.join(root,format('Data/Map%03d.rxdata',id))
  raise 'Refusing to overwrite an existing map' if File.exist?(path)||infos.key?(id)
  map=Marshal.load(original);map.width=layout['width'];map.height=layout['height'];map.events={};map.data=Table.new(map.width,map.height,3)
  map.height.times{|y|map.width.times{|x|map.data[x,y,0]=layout['base_tile']}}
  layout['decals'].each{|d|map.data[d['x'],d['y'],1]=d['tile']}
  layout['structures'].each do |r|
    r['height'].times{|y|r['width'].times{|x|map.data[r['x']+x,r['y']+y,2]=384+(r['tile_y']+y)*8+r['tile_x']+x}}
  end
  File.binwrite(path,Marshal.dump(map));info=Marshal.load(Marshal.dump(infos.fetch(1)));info.name=layout['name'];info.parent_id=1;info.order=id;infos[id]=info
end
File.binwrite(File.join(root,'Data/MapInfos.rxdata'),Marshal.dump(infos))
