# Lunetile XP editor fix: RPG Maker XP resets Game.ini Library to RGSS104E.dll when saving.
# This block runs only under the original runtime and must stay Ruby 1.8 compatible.
unless defined?(RGSSXP)
  raise 'Lunetile.dll is missing from the game directory.' unless FileTest.exist?('Lunetile.dll')
  wide = lambda { |text| text.unpack('C*').pack('v*') + [0].pack('v') }
  module_name = Win32API.new('kernel32', 'GetModuleFileNameW', 'lpl', 'l')
  buffer = [0].pack('C') * 1040
  length = module_name.call(0, buffer, 520)
  raise 'Cannot locate Game.exe for Lunetile.dll.' if length <= 0 || length >= 520
  exe = buffer[0, length * 2]
  raise 'Cannot locate Game.ini for Lunetile.dll.' unless exe[-8, 8].downcase == '.exe'.unpack('C*').pack('v*')
  ini = exe[0, exe.size - 6] + wide.call('ini')
  library = wide.call('Lunetile.dll')
  write = Win32API.new('kernel32', 'WritePrivateProfileStringW', 'pppp', 'i')
  read = Win32API.new('kernel32', 'GetPrivateProfileStringW', 'pppplp', 'l')
  written = write.call(wide.call('Game'), wide.call('Library'), library, ini)
  value = [0].pack('C') * 128
  count = written == 0 ? 0 : read.call(wide.call('Game'), wide.call('Library'), wide.call(''), value, 64, ini)
  # A write that lands elsewhere would relaunch the original runtime forever.
  raise 'Cannot restore Lunetile.dll in Game.ini.' unless value[0, count * 2] + [0].pack('v') == library
  arguments = $BTEST ? 'btest' : ($DEBUG ? 'debug' : '')
  launch = Win32API.new('shell32', 'ShellExecuteW', 'lppppl', 'l')
  result = launch.call(0, wide.call('open'), exe + [0].pack('v'), wide.call(arguments), 0, 1)
  raise 'Cannot restart Game.exe with Lunetile.dll.' if result <= 32
  exit
end
