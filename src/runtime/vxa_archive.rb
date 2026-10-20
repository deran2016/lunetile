# RGSS3 indexes use a fixed directory key; each payload has its own rolling key.
class RGSSXP::Archive
  alias vxa_v1_initialize initialize
  def initialize(path)
    header = RGSSXP.read_disk(path, 0, 8, nil)[0]
    return vxa_v1_initialize(path) unless header == "RGSSAD\0\x03".b
    @path, @entries = path, {}
    file = Reader.new(path)
    file.read(8)
    @size = file.size
    key = (word(file) * 9 + 3) & 0xffffffff
    ranges = []
    loop do
      offset = word(file) ^ key
      break if offset == 0
      length, data_key, name_length = word(file)^key, word(file)^key, word(file)^key
      raise ArgumentError, 'Invalid RGSS3 filename length' unless name_length.between?(1,4096)
      bytes = file.read(name_length)
      raise ArgumentError, 'Truncated RGSS3 filename' unless bytes && bytes.bytesize == name_length
      key_bytes = [key].pack('V').bytes
      name = self.class.normalize(bytes.bytes.each_with_index.map { |byte,i| byte ^ key_bytes[i%4] }.pack('C*'))
      if name.include?("\0") || name.include?(':') || name.split('/', -1).any? { |part| ['', '.', '..'].include?(part) }
        raise ArgumentError, 'Invalid relative RGSS3 filename'
      end
      raise ArgumentError, 'RGSS3 entry exceeds archive bounds' if offset > @size || length > @size-offset
      raise ArgumentError, 'Duplicate RGSS3 filename' if @entries.key?(name)
      raise ArgumentError, 'Too many RGSS3 entries' if @entries.size >= 100000
      @entries[name] = [offset,length,data_key]
      ranges << [offset, offset+length]
    end
    last = file.pos
    ranges.sort.each do |first,finish|
      raise ArgumentError, 'Overlapping RGSS3 directory or payload' if first < last
      last = finish
    end
  end
end
