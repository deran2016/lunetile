module RGSSXP::Saves
  class ReadStream < StringIO
    attr_accessor :timing_rate
    def initialize(bytes, modified)
      super(bytes, 'rb')
      @modified = modified
      @timing_rate = 40
    end
    def mtime
      raise IOError, 'closed stream' if closed?
      @modified.dup
    end
  end
  MAGIC = "RGSSXP\0SAVE\0".b + [1].pack('V')
  HIGH_MAGIC = "RGSSXP\0SAVE\0".b + [2].pack('V')
  ROOT = File.expand_path('Saves/RGSSXP').freeze
  IMPORT = File.expand_path('Saves/Import').freeze

  def self.slot(index)
    raise ArgumentError, 'Save slot must be 0..3' unless index.is_a?(Integer) && index.between?(0, 3)
    "Save#{index + 1}.rxdata"
  end

  def self.filename(index, mode = :read)
    raise ArgumentError, 'Invalid save access mode' unless mode == :read || mode == :write
    name = slot(index)
    own = File.join(ROOT, name)
    return own if mode == :write || File.file?(own)
    File.join(IMPORT, name)
  end

  def self.exist?(index)
    File.file?(filename(index))
  end

  def self.validate(path, write: false)
    expanded = File.expand_path(path)
    allowed = (0..3).any? do |index|
      expanded == File.join(ROOT, slot(index)) || (!write && expanded == File.join(IMPORT, slot(index)))
    end
    raise ArgumentError, 'Save access outside engine save directories' unless allowed
    expanded
  end

  def self.open_read(path)
    path = validate(path)
    bytes, _, modified = RGSSXP.read_disk(path, 0, nil, nil)
    file = ReadStream.new(bytes, modified)
    begin
      if File.dirname(path) == ROOT
        header = file.read(MAGIC.bytesize)
        if header == HIGH_MAGIC
          raise IOError, 'This save requires a stock120 converted project' unless RGSSXP::Timing.scale == 3
          file.timing_rate = 120
        elsif header != MAGIC
          raise IOError, 'Unsupported RGSSXP save header or version'
        end
      else
        raise IOError, 'Import requires an original RGSS save' if file.read(7) == "RGSSXP\0".b
        file.rewind
      end
      file
    rescue Exception
      file.close
      raise
    end
  end

  def self.write(path)
    path = validate(path, write: true)
    Dir.mkdir('Saves') unless Dir.exist?('Saves')
    Dir.mkdir(ROOT) unless Dir.exist?(ROOT)
    temporary = path + ".tmp-#{Process.pid}"
    begin
      File.open(temporary, 'wbx') do |file|
        file.write(RGSSXP::Timing.scale == 3 ? HIGH_MAGIC : MAGIC)
        yield file
        file.flush
        file.fsync
      end
      File.rename(temporary, path)
    ensure
      File.delete(temporary) if File.file?(temporary)
    end
    nil
  end
end
