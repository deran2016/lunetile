module Lunetile
  class BrowserError < StandardError
    attr_reader :code, :native_code
    def initialize(code, native_code = 0)
      @code, @native_code = code, native_code
      super("Browser #{code} (native error #{native_code})")
    end
  end

  class Browser
    private :__create, :__navigate, :__load_file, :__rect, :__set_rect, :__error
    def initialize(rect)
      __create(*checked_rect(rect))
    end
    def navigate(url)
      __navigate(checked_string(url))
      self
    end
    def load_file(path)
      __load_file(checked_string(path))
      self
    end
    def rect
      Rect.new(*__rect)
    end
    def rect=(value)
      __set_rect(*checked_rect(value))
      value
    end
    def error
      value = __error
      value && BrowserError.new(*value)
    end
    private
    def checked_rect(value)
      raise TypeError, 'rect must be a Rect' unless value.is_a?(Rect)
      values = [value.x, value.y, value.width, value.height]
      unless values.all? { |v| v.is_a?(Integer) } &&
          values[0,2].all? { |v| v.between?(-4096,4096) } &&
          values[2,2].all? { |v| v.between?(32,4096) }
        raise ArgumentError, 'Browser rect requires coordinates -4096..4096 and size 32..4096'
      end
      values
    end
    def checked_string(value)
      raise TypeError, 'Browser URL/path must be a String' unless value.is_a?(String)
      text = value.encode(Encoding::UTF_8)
      raise ArgumentError, 'Invalid Browser URL/path' if text.empty? ||
        text.bytesize > 8192 || text.match?(/[\x00-\x1f\x7f]/)
      text
    end
  end
end
