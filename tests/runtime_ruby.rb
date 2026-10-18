raise 'wrong Ruby version' unless RUBY_VERSION == '4.0.7'
raise 'wrong pointer size' unless [0].pack('J').bytesize == 4
raise 'YJIT must be disabled' if defined?(RubyVM::YJIT) && RubyVM::YJIT.enabled?
raise 'ZJIT must be disabled' if defined?(RubyVM::ZJIT) && RubyVM::ZJIT.enabled?
data = 10000.times.map { |i| [i.to_s, i * i] }
GC.start
raise 'Marshal mismatch' unless Marshal.load(Marshal.dump(data)) == data
puts RUBY_DESCRIPTION
