require 'json'
# Only trusted, already converted XP files are loaded by the build tool.
module RPG; end
JSON.parse(File.read(ARGV.fetch(1))).each do |name,fields|
  eval('class '+name+'; attr_accessor '+fields.map { |f| ':'+f }.join(',')+'; end')
end
class Table
  def self._load(bytes)
    dim,x,y,z,count = bytes.unpack('V5')
    raise 'Invalid XP Table' unless (1..3).include?(dim) && x*y*z == count && bytes.bytesize == 20+count*2
    table = allocate
    table.instance_variable_set(:@size,[x,y,z])
    table.instance_variable_set(:@cells,bytes.byteslice(20..-1).unpack('v*'))
    table
  end
  def [](*coords)
    x,y,z = coords
    @cells[x+(y||0)*@size[0]+(z||0)*@size[0]*@size[1]]
  end
end
root = ARGV.fetch(0)
system = Marshal.load(File.binread(File.join(root,'Data/System.rxdata')))
map = Marshal.load(File.binread(File.join(root,format('Data/Map%03d.rxdata',system.start_map_id))))
tilesets = Marshal.load(File.binread(File.join(root,'Data/Tilesets.rxdata')))
actors = Marshal.load(File.binread(File.join(root,'Data/Actors.rxdata')))
tileset = tilesets.fetch(map.tileset_id)
raise 'Example requires a static starting map without XP events; convert events to server NPC definitions first' unless map.events.empty?
passages = Array.new(map.height) do |y|
  Array.new(map.width) do |x|
    [1,2,4,8].sum do |bit|
      blocked = false
      2.downto(0) do |z|
        tile = map.data[x,y,z]
        next if tile == 0
        passage = tileset.passages[tile]
        priority = tileset.priorities[tile]
        raise 'Invalid tileset table index' if passage.nil? || priority.nil?
        if passage & bit != 0
          blocked = true
          break
        end
        break if priority == 0
      end
      blocked ? bit : 0
    end
  end
end
spawn = {'map_id'=>system.start_map_id,'x'=>system.start_x,'y'=>system.start_y}
# Find an accessible tile next to the initial position for the introductory NPC.
candidates = [[0,1,1,8],[-1,0,2,4],[1,0,4,2],[0,-1,8,1]]
neighbor = candidates.find do |dx,dy,bit,reverse|
  x,y = system.start_x+dx,system.start_y+dy
  x.between?(0,map.width-1) && y.between?(0,map.height-1) &&
    passages[system.start_y][system.start_x]&bit == 0 && passages[y][x]&reverse == 0
end
raise 'Starting point has no accessible neighboring NPC tile' unless neighbor
npc_position = {'map_id'=>system.start_map_id,'x'=>system.start_x+neighbor[0],'y'=>system.start_y+neighbor[1]}
puts JSON.generate({
  'maps'=>[{'id'=>system.start_map_id,'name'=>'XP 시작 마을','width'=>map.width,'height'=>map.height,'passages'=>passages}],
  'server'=>{'bind'=>'127.0.0.1:4100','max_clients'=>32,'max_accounts'=>256,'spawn'=>spawn,
    'character'=>actors.fetch(system.party_members.first).character_name,'starting_items'=>{'potion'=>2}},
  'npcs'=>[{'id'=>'guide','name'=>'마을 안내인','character'=>actors.fetch(system.party_members.first).character_name,
    'position'=>npc_position,'dialogue'=>'이 마을의 위치와 가방은 서버가 기억해요. 물약과 기념 배지를 받아 가세요.',
    'reward'=>{'potion'=>3,'village_badge'=>1}}]
})
