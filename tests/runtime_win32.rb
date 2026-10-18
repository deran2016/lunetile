def expect_failure(type)
  begin
    yield
  rescue type
    return
  end
  raise "Expected #{type}"
end
expect_failure(LoadError) { Win32API.new('kernel32', 'RGSSXP_Missing_Function_123', [], 'L') }
expect_failure(LoadError) { Win32API.new('RGSSXP_Missing_Library_123.dll', 'X', [], 'L') }
expect_failure(ArgumentError) { Win32API.new('kernel32', 'X', 'VL', 'L') }
expect_failure(NotImplementedError) { Win32API.new('kernel32', 'X', 'D', 'L') }
pid = Win32API.new('kernel32', 'GetCurrentProcessId', '', 'L')
expect_failure(ArgumentError) { pid.call(1) }
command = Win32API.new('kernel32', 'GetCommandLineA', '', 'P')
raise 'pointer result failed' unless command.call.is_a?(String) && command.call.include?('Game.exe')
length = Win32API.new('kernel32', 'lstrlenA', 'P', 'L')
1000.times do
  raise 'native stack corrupted' unless length.call('abc') == 3
end
GC.start
