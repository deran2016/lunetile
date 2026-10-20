# Migration-only Marshal validation; project data is never evaluated.
class Table
  def self._load(bytes)
    dimensions,x,y,z,count = bytes.unpack('V5')
    raise ArgumentError, 'Invalid Table payload' unless bytes.bytesize >= 20 &&
      dimensions.between?(1,3) && [x,y,z].all? { |v| v >= 0 } &&
      count == x*y*z && bytes.bytesize == 20+count*2
    new
  end
end
class Color
  def self._load(bytes)
    raise ArgumentError, 'Invalid color payload' unless bytes.bytesize == 32
    new
  end
end
class Tone < Color; end
def inspect_graph(value,seen)
  return if value.nil? || value == true || value == false || value.is_a?(Numeric) || value.is_a?(Table) || value.is_a?(Color)
  return if seen[value.object_id]
  seen[value.object_id] = true
  case value
  when String
    raise EncodingError, 'Invalid encoded text' unless value.valid_encoding?
    value.encode(Encoding::UTF_8) unless value.encoding == Encoding::ASCII_8BIT
    raise EncodingError, 'Ambiguous binary text' if value.encoding == Encoding::ASCII_8BIT && !value.ascii_only?
  when Array
    value.each { |child| inspect_graph(child,seen) }
  when Hash
    value.each { |key,child| inspect_graph(key,seen); inspect_graph(child,seen) }
  else
    if value.is_a?(RPG::EventCommand) && ([355,655].include?(value.code) || (value.code == 111 && value.parameters[0] == 12) || (value.code == 122 && value.parameters[3] == 4))
      raise ArgumentError, 'Unreviewed event Ruby code'
    end
    raise ArgumentError, 'Unreviewed movement Ruby code' if value.is_a?(RPG::MoveCommand) && value.code == 45
    raise TypeError, 'Unexpected project data class' unless value.class.name.start_with?('RPG::')
    value.instance_variables.each { |field| inspect_graph(value.instance_variable_get(field),seen) }
  end
end
files = Dir.glob(File.join(ARGV.fetch(0).tr('\\','/'),'*.rvdata2')).sort
raise ArgumentError, 'No project data files' if files.empty?
files.each do |path|
  File.open(path,'rb') do |stream|
    inspect_graph(Marshal.load(stream),{})
    raise ArgumentError, 'Trailing project data' unless stream.eof?
  end
end
puts "#{files.length} VX Ace data files inspected"
