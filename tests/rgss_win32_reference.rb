File.open('types-reference.txt', 'w') do |out|
  pid = Win32API.new('kernel32', 'GetCurrentProcessId', [], 'L')
  out.puts('pid' + "\t" + (pid.call > 0).inspect)
  length = Win32API.new('kernel32', 'lstrlenA', 'p', 'i')
  out.puts('string' + "\t" + length.call("abc\0ignored").inspect)
  counter = Win32API.new('kernel32', 'QueryPerformanceCounter', 'p', 'i')
  bytes = "\0" * 8
  out.puts('counter' + "\t" + [counter.call(bytes) != 0, bytes != "\0" * 8].inspect)
  time = Win32API.new('kernel32', 'GetSystemTimeAsFileTime', ['P'], 'V')
  bytes = "\0" * 8
  value = time.call(bytes)
  out.puts('void' + "\t" + [value, bytes != "\0" * 8].inspect)
  handle = Win32API.new('kernel32', 'GetModuleHandleA', ['P'], 'L')
  out.puts('null' + "\t" + (handle.call(0) != 0).inspect)
  multiply = Win32API.new('kernel32', 'MulDiv', 'lll', 'l')
  out.puts('signed' + "\t" + multiply.call(-1, 1, 1).inspect)
end
File.open('runtime-complete.txt', 'w') { |file| file.write('win32,false,false') }
sleep 0.5
