# Migration inspection only. Native Marshal values remain opaque; no engine API is emulated.
class RGSSXPOpaquePayload
  def initialize(bytes)
    @bytes = bytes
  end
end
%w[Table Color Tone Rect].each do |name|
  value_class = Class.new
  value_class.define_singleton_method(:_load) { |bytes| RGSSXPOpaquePayload.new(bytes) }
  Object.const_set(name, value_class)
end

def inspect_graph(value, location, seen, explicit_encoding)
  return if value.nil? || value.is_a?(Numeric) || value == true || value == false || value.is_a?(RGSSXPOpaquePayload)
  return if seen[value.object_id]
  seen[value.object_id] = true
  if value.is_a?(String)
    return if value.ascii_only?
    raise EncodingError, "#{location}: non-ASCII text requires explicit --data-encoding UTF-8, CP949 or CP932" unless explicit_encoding
  elsif value.is_a?(Array)
    value.each_with_index { |child, i| inspect_graph(child, "#{location}[#{i}]", seen, explicit_encoding) }
  elsif value.is_a?(Hash)
    value.each do |key, child|
      inspect_graph(key, "#{location}.key", seen, explicit_encoding)
      inspect_graph(child, "#{location}[#{key.inspect}]", seen, explicit_encoding)
    end
  else
    if value.is_a?(RPG::EventCommand) && ([355, 655].include?(value.code) || (value.code == 111 && value.parameters[0] == 12))
      raise ArgumentError, "#{location}, event script line 1: unreviewed Ruby code (command #{value.code})"
    end
    if value.is_a?(RPG::MoveCommand) && value.code == 45
      raise ArgumentError, "#{location}, movement script line 1: unreviewed Ruby code"
    end
    raise TypeError, "#{location}: unsupported data class #{value.class}" unless value.class.name.start_with?('RPG::')
    value.instance_variables.each do |field|
      inspect_graph(value.instance_variable_get(field), "#{location}.#{field}", seen, explicit_encoding)
    end
  end
end

files = Dir.glob(File.join(ARGV.fetch(0).tr('\\', '/'), '*.rxdata')).sort
raise ArgumentError, 'No project data files were inspected' if files.empty?
changes = []
files.each do |file|
  begin
    value = Marshal.load(File.binread(file))
    inspect_graph(value, File.basename(file), {}, ARGV[1] != 'ASCII')
    RGSSXP.normalize_data(value, File.basename(file), {}, changes)
  rescue StandardError => error
    raise error.class, "#{File.basename(file)}: #{error.message}"
  end
end
File.binwrite(ARGV.fetch(2),Marshal.dump(changes))
puts "#{files.size} project data files inspected: no unreviewed event Ruby; text encoding explicit or ASCII"
