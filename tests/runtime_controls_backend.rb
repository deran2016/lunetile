c = Lunetile::Controls
unless $comfort_probe_phase
  library = '__PROBE_DLL__'
  $probe_install = Win32API.new(library,'ProbeInstall','P','L')
  $probe_config = Win32API.new(library,'ProbeConfigure','LLLLLL','L')
  $probe_motor = Win32API.new(library,'ProbeMotor','L','L')
  $probe_reset = Win32API.new(library,'ProbeReset','','L')
  name = File.file?('LunetileVXA.dll') ? 'LunetileVXA.dll' : 'Lunetile.dll'
  raise 'Test imports not installed' unless $probe_install.call(name) == 3
  $probe_config.call(2,0,0,0,0,1)
  deadline = Process.clock_gettime(Process::CLOCK_MONOTONIC)+2
  until c.connected?
    Graphics.update;Input.update
    raise 'Simulated port 2 not found' if Process.clock_gettime(Process::CLOCK_MONOTONIC)>deadline
  end
  c.bind(:confirm,pad: :rt)
  $probe_config.call(2,4096,0,0,0,1);Input.update
  raise 'Old pad binding remained active' if Input.press?(Input::C)
  $probe_config.call(2,0,0,0,80<<8,1);Input.update
  raise 'RT mapping/device hint failed' unless Input.trigger?(Input::C) && c.device == :gamepad && c.prompt(:confirm) == 'RT'
  Input.update
  raise 'Held pad repeatedly triggered' if Input.trigger?(Input::C)
  c.rumble_enabled = true
  raise 'Simulated rumble start failed' unless c.rumble(0.25,0.5,35)
  raise 'Motor strengths wrong' unless $probe_motor.call(0)==16383 && $probe_motor.call(1)==32767
  deadline = Process.clock_gettime(Process::CLOCK_MONOTONIC)+0.2
  Graphics.update while Process.clock_gettime(Process::CLOCK_MONOTONIC)<deadline
  raise 'Graphics-only rumble timeout failed' unless $probe_motor.call(0)==0 && $probe_motor.call(1)==0
  c.rumble(0.25,0.5,1000)
  $probe_config.call(2,0,0,0,80<<8,0);Input.update
  raise 'Inactive rumble/input leaked' unless $probe_motor.call(0)==0 && !Input.press?(Input::C)
  $probe_config.call(2,0,0,0,80<<8,1);Input.update
  raise 'Held pad leaked on focus return' if Input.press?(Input::C)
  $probe_config.call(2,0,0,0,0,1);Input.update
  $probe_config.call(2,0,0,0,80<<8,1);Input.update
  raise 'Pad re-press lost' unless Input.trigger?(Input::C)
  $probe_config.call(2,0,20000,0,0,1);Input.update
  raise 'Stick direction missing' unless Input.dir4==6
  $probe_config.call(2,0,20000,0,0,0);Input.update
  $probe_config.call(2,0,20000,0,0,1);Input.update
  raise 'Held stick leaked on focus return' unless Input.dir4==0
  $probe_config.call(2,0,0,0,0,1);Input.update
  $probe_config.call(2,0,20000,0,0,1);Input.update
  raise 'Stick re-press lost' unless Input.dir4==6
  c.rumble(0.2,0.4,1000)
  c.rumble_enabled = false
  raise 'Rumble preference failed to stop' unless $probe_motor.call(0)==0
  c.rumble_enabled = true
  c.rumble(0.2,0.4,1000)
  $comfort_probe_phase = 1
  raise 'F12 test message failed' unless $probe_reset.call == 1
  deadline = Process.clock_gettime(Process::CLOCK_MONOTONIC)+1
  loop do
    Graphics.update;Input.update
    raise 'F12 did not reset' if Process.clock_gettime(Process::CLOCK_MONOTONIC)>deadline
  end
end
raise 'F12 did not stop vibration' unless $probe_motor.call(0)==0 && $probe_motor.call(1)==0
$probe_config.call(2,0,0,0,0,1);Input.update
raise 'Final shutdown rumble start failed' unless c.rumble(0.2,0.4,1000)
File.write('runtime-complete.txt','XInput simulated backend and F12,false,false')
