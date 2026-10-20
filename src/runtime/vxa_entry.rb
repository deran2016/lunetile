# VX Ace rewrites both Library and System/RGSS301.dll when saving in its editor.
unless defined?(RGSSXP::Timing)
  runtime = File.expand_path('LunetileVXA.dll')
  raise 'LunetileVXA.dll is missing from the game directory.' unless File.file?(runtime)
  wide = lambda { |text| (text + "\0").encode('UTF-16LE') }
  ini = wide.call(File.expand_path('Game.ini'))
  write = Win32API.new('kernel32', 'WritePrivateProfileStringW', 'pppp', 'i')
  ok = write.call(wide.call('Game'), wide.call('Library'),
                  wide.call('LunetileVXA.dll'), ini)
  raise 'Cannot restore LunetileVXA.dll in Game.ini.' if ok == 0
  arguments = $BTEST ? 'btest' : ($TEST ? 'test' : '')
  launch = Win32API.new('shell32', 'ShellExecuteW', 'lppppl', 'l')
  result = launch.call(0, wide.call('open'), wide.call(File.expand_path('Game.exe')),
                       wide.call(arguments), wide.call(Dir.pwd), 1)
  raise 'Cannot restart Game.exe with LunetileVXA.dll.' if result <= 32
  exit
end
