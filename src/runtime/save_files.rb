module Lunetile
  module SaveFiles
    LIMIT = 64 * 1024 * 1024
    def self.read(path)
      raise IOError, 'Save exceeds 64 MiB' if File.size(path) > LIMIT
      File.binread(path)
    end
    def self.replace(path, bytes)
      raise IOError, 'Save exceeds 64 MiB' if bytes.bytesize > LIMIT
      directory = File.dirname(path)
      Dir.mkdir('Saves') unless Dir.exist?('Saves')
      Dir.mkdir(directory) unless Dir.exist?(directory)
      temporary = path + ".tmp-#{Process.pid}-#{Process.clock_gettime(Process::CLOCK_MONOTONIC, :nanosecond)}"
      created = false
      begin
        File.open(temporary, 'wbx') do |file|
          created = true
          file.write(bytes)
          file.flush
          file.fsync
        end
        File.rename(temporary, path)
      ensure
        File.delete(temporary) if created && File.file?(temporary)
      end
      nil
    end
    def self.marshaled?(bytes, offset)
      stream = StringIO.new(bytes)
      stream.pos = offset
      count = 0
      until stream.eof?
        Marshal.load(stream)
        count += 1
      end
      raise ArgumentError, 'Empty save payload' if count.zero?
      true
    ensure
      stream&.close
    end
    def self.write(path, bytes, &validate)
      validate.call(bytes)
      # Copy verified generations before replacing the current save; a failed write keeps it intact.
      versions = [path, *1.upto(3).map { |n| path + ".bak#{n}" }].filter_map do |candidate|
        next unless File.file?(candidate)
        old = read(candidate)
        begin
          validate.call(old)
          old
        rescue ArgumentError, TypeError, EOFError, IOError, NameError, EncodingError, JSON::ParserError
          nil
        end
      end.first(3)
      versions.each_with_index.to_a.reverse_each { |old, i| replace(path + ".bak#{i+1}", old) }
      replace(path, bytes)
    end
  end
end
