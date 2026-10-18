# Serializable RGSS1 value types, implemented from observable API behavior.
class Color
  attr_reader :red, :green, :blue, :alpha

  def initialize(red, green, blue, alpha = 255)
    set(red, green, blue, alpha)
  end

  def set(red, green, blue, alpha = 255)
    self.red, self.green, self.blue, self.alpha = red, green, blue, alpha
    self
  end

  [:red, :green, :blue, :alpha].each do |field|
    define_method("#{field}=") do |value|
      raise TypeError, 'expected a Numeric' unless value.is_a?(Numeric)
      instance_variable_set("@#{field}", [[value.to_f, field == :alpha ? 0.0 : -255.0].max, 255.0].min)
    end
  end

  def ==(other)
    other.instance_of?(self.class) && [red, green, blue, alpha] == [other.red, other.green, other.blue, other.alpha]
  end
  alias eql? ==

  def _dump(_depth)
    [red, green, blue, alpha].pack('E4')
  end

  def self._load(bytes)
    raise ArgumentError, 'Invalid Color payload' unless bytes.bytesize == 32
    new(*bytes.unpack('E4'))
  end
end

class Tone
  attr_reader :red, :green, :blue, :gray

  def initialize(red, green, blue, gray = 0)
    set(red, green, blue, gray)
  end

  def set(red, green, blue, gray = 0)
    self.red, self.green, self.blue, self.gray = red, green, blue, gray
    self
  end

  [:red, :green, :blue, :gray].each do |field|
    define_method("#{field}=") do |value|
      raise TypeError, 'expected a Numeric' unless value.is_a?(Numeric)
      instance_variable_set("@#{field}", [[value.to_f, field == :gray ? 0.0 : -255.0].max, 255.0].min)
    end
  end

  def ==(other)
    other.instance_of?(self.class) && [red, green, blue, gray] == [other.red, other.green, other.blue, other.gray]
  end
  alias eql? ==

  def _dump(_depth)
    [red, green, blue, gray].pack('E4')
  end

  def self._load(bytes)
    raise ArgumentError, 'Invalid Tone payload' unless bytes.bytesize == 32
    new(*bytes.unpack('E4'))
  end
end

class Rect
  attr_reader :x, :y, :width, :height

  def initialize(x, y, width, height)
    set(x, y, width, height)
  end

  def set(x, y, width, height)
    self.x, self.y, self.width, self.height = x, y, width, height
    self
  end

  def empty
    set(0, 0, 0, 0)
  end

  [:x, :y, :width, :height].each do |field|
    define_method("#{field}=") do |value|
      raise TypeError, 'expected a Numeric' unless value.is_a?(Numeric)
      integer = value.to_int
      raise RangeError, 'Rect component exceeds int32' unless integer.between?(-0x80000000, 0x7fffffff)
      instance_variable_set("@#{field}", integer)
    end
  end

  def ==(other)
    other.instance_of?(self.class) && [x, y, width, height] == [other.x, other.y, other.width, other.height]
  end
  alias eql? ==

  def _dump(_depth)
    [x, y, width, height].pack('l<4')
  end

  def self._load(bytes)
    raise ArgumentError, 'Invalid Rect payload' unless bytes.bytesize == 16
    new(*bytes.unpack('l<4'))
  end
end
