module RGSSXP
  class Archive
    class Reader
      attr_reader :size, :pos
      def initialize(path)
        @path, @pos, @start = path, 0, 0
        @buffer, @size = RGSSXP.read_disk(path, 0, 65536, nil)
      end
      def read(length)
        return nil if @pos >= @size && length > 0
        if @pos < @start || @pos + length > @start + @buffer.bytesize
          @start = @pos
          @buffer = RGSSXP.read_disk(@path, @pos, [65536, length].max, @size)[0]
        end
        value = @buffer.byteslice(@pos - @start, length)
        @pos += value.bytesize
        value
      end
      def seek(length, origin)
        raise ArgumentError, 'Only forward relative archive seeks are supported' unless origin == IO::SEEK_CUR && length >= 0
        @pos += length
      end
    end
    def self.step(key)
      (key * 7 + 3) & 0xffffffff
    end

    def self.normalize(name)
      RGSSXP.text(name).tr('\\', '/').b.downcase
    end

    def word(file)
      bytes = file.read(4)
      raise ArgumentError, 'Truncated RGSSAD word' unless bytes && bytes.bytesize == 4
      bytes.unpack1('V')
    end

    def initialize(path)
      @path, @entries = path, {}
      file = Reader.new(path)
        raise NotImplementedError, 'Only RPG Maker XP RGSSAD version 1 is supported' unless file.read(8) == "RGSSAD\0\x01".b
        @size = file.size
        key = 0xdeadcafe
        while file.pos < @size
          length = word(file) ^ key
          key = self.class.step(key)
          raise ArgumentError, 'Invalid RGSSAD filename length' unless length.between?(1, 4096)
          bytes = file.read(length)
          raise ArgumentError, 'Truncated RGSSAD filename' unless bytes && bytes.bytesize == length
          name = bytes.bytes.map do |byte|
            plain = byte ^ (key & 255)
            key = self.class.step(key)
            plain
          end.pack('C*')
          name = self.class.normalize(name)
          if name.include?("\0") || name.include?(':') || name.split('/', -1).any? { |part| ['', '.', '..'].include?(part) }
            raise ArgumentError, 'Invalid relative RGSSAD filename'
          end
          length = word(file) ^ key
          key = self.class.step(key)
          raise ArgumentError, 'RGSSAD entry exceeds archive bounds' if length > @size - file.pos
          raise ArgumentError, 'Duplicate RGSSAD filename' if @entries.key?(name)
          raise ArgumentError, 'Too many RGSSAD entries' if @entries.size >= 100000
          @entries[name] = [file.pos, length, key]
          file.seek(length, IO::SEEK_CUR)
        end
    end

    def include?(name)
      @entries.key?(self.class.normalize(name))
    end

    def read(name)
      entry = @entries.fetch(self.class.normalize(name)) { raise Errno::ENOENT, name }
      offset, length, key = entry
      raise ArgumentError, 'RGSSAD entry exceeds 128 MiB limit' if length > 128 * 1024 * 1024
      encrypted = RGSSXP.read_disk(@path, offset, length, @size)[0]
      raise IOError, 'Truncated RGSSAD data' unless encrypted && encrypted.bytesize == length
      RGSSXP.decode_archive(encrypted, key)
    end
  end

  def self.open_archive(path)
    @archive = path ? Archive.new(path) : nil
  end

  def self.read_file(name, extensions = [])
    if @archive
      ([name] + extensions.map { |extension| name + extension }).each do |candidate|
        return @archive.read(candidate) if @archive.include?(candidate)
      end
    end
    read_disk(resolve_file(name, extensions), 0, nil, nil)[0]
  end
end
