raise 'wrong Ruby' unless RUBY_VERSION == '4.0.7'
raise 'wrong word size' unless [0].pack('J').bytesize == 4
at_exit { File.write('runtime-finalized.txt', 'at_exit completed') }
data = 10000.times.map { |i| [i.to_s, i*i] }
GC.start
raise 'Marshal mismatch' unless Marshal.load(Marshal.dump(data)) == data
File.write('runtime-ready.txt', RUBY_DESCRIPTION)
sleep 1.5
File.write('runtime-complete.txt', [RUBY_VERSION, RUBY_PLATFORM, !!$DEBUG, !!$BTEST].join(','))
