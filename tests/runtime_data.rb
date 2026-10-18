# Canonical object graph: compare values, identity, class names and native payloads.
def graph_lines(value, seen, out)
  case value
  when NilClass, TrueClass, FalseClass, Integer
    out << ['value', value]
  when Symbol
    out << ['symbol', value.to_s.unpack('H*')[0]]
  when Float
    out << ['double', [value].pack('d').unpack('H*')[0]]
  else
    if seen.has_key?(value.object_id)
      out << ['ref', seen[value.object_id]]
      return
    end
    seen[value.object_id] = seen.size
    out << ['object', value.class.name, seen.size - 1]
    case value
    when String
      out << ['bytes', value.unpack('H*')[0]]
    when Table, Color, Tone, Rect
      out << ['native', value._dump(0).unpack('H*')[0]]
    when Array
      out << ['array', value.size]
      value.each { |child| graph_lines(child, seen, out) }
    when Hash
      out << ['hash', value.size]
      value.keys.sort_by { |key| key.inspect }.each do |key|
        graph_lines(key, seen, out)
        graph_lines(value[key], seen, out)
      end
    else
      fields = value.instance_variables.collect { |field| field.to_s }.sort
      out << ['fields', fields]
      fields.each { |field| graph_lines(value.instance_variable_get(field), seen, out) }
    end
  end
end

File.open('types-reference.txt', 'w') do |out|
  Dir.glob('Data/*.rxdata').sort.each do |filename|
    next if filename == 'Data/Scripts.rxdata'
    value = load_data(filename)
    nodes = []
    graph_lines(value, {}, nodes)
    roundtrip = Marshal.load(Marshal.dump(value))
    copied = []
    graph_lines(roundtrip, {}, copied)
    raise "Marshal roundtrip changed #{filename}" unless nodes == copied
    out.puts(filename + "\t" + nodes.inspect)
  end
end
File.open('runtime-complete.txt', 'w') { |out| out.write('data,false,false') }
sleep 0.5
