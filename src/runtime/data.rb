module RPG
end

module RGSSXP
  def self.text(value)
    string = String.try_convert(value)
    raise TypeError, 'Expected String or an object with to_str' unless string
    string = string.dup.force_encoding(SOURCE_ENCODING) if string.encoding == Encoding::BINARY
    raise EncodingError, 'Text is invalid in the declared project encoding' unless string.valid_encoding?
    string.encode(Encoding::UTF_8)
  end
  def self.define_data_class(path, fields)
    parts = path.split('::')
    name = parts.pop
    parent = parts.inject(Object) { |scope, part| scope.const_get(part, false) }
    klass = Class.new do
      # Deserialization does not call initialize. Unsupported constructors fail explicitly.
      define_method(:initialize) { |*| raise NotImplementedError, "#{path}.new is not implemented" }
      attr_accessor(*fields.map(&:to_sym))
    end
    parent.const_set(name, klass)
  end

  def self.resolve_file(name, extensions = [])
    name = text(name).tr('\\', '/')
    names = [name] + extensions.map { |extension| name + extension }
    [Dir.pwd, *RTP_PATHS].each do |base|
      names.each do |candidate|
        path = File.expand_path(candidate, base)
        return path if File.file?(path)
      end
    end
    raise Errno::ENOENT, name
  end
end

def load_data(filename)
  value = Marshal.load(RGSSXP.read_file(filename))
  # A script archive contains compressed binary strings, not project text.
  scripts = value.is_a?(Array) && value.all? { |entry| entry.is_a?(Array) && entry.size==3 && entry[0].is_a?(Integer) && entry[1].is_a?(String) && entry[2].is_a?(String) }
  scripts ? value : RGSSXP.normalize_data(value, filename)
end

def save_data(object, filename)
  File.binwrite(filename, Marshal.dump(object))
  nil
end
