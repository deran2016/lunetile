background = Bitmap.new(640, 480)
background.fill_rect(background.rect, Color.new(20,40,60))
background.font.size = 28
background.draw_text(24,16,590,40,'Ruby 4.0.7 / Direct3D 11',0)
background.font.size = 22
background.draw_text(24,68,590,32,'Keyboard check: Enter, Down',0)
sprite = Sprite.new
sprite.bitmap = background
file = File.open('input-observed.txt', 'w')
active_window = Win32API.new('user32', 'GetActiveWindow', '', 'L')
window_rect = Win32API.new('user32', 'GetWindowRect', 'LP', 'I')
client_rect = Win32API.new('user32', 'GetClientRect', 'LP', 'I')
until File.exist?('finish-probe.txt')
  Graphics.update
  Input.update
  if Graphics.frame_count % 10 == 0
    File.write('last-frame.txt', Graphics.frame_count.to_s)
    outer = [0,0,0,0].pack('l4');inner = outer.dup
    window_rect.call(active_window.call, outer);client_rect.call(active_window.call, inner)
    File.write('window-observed.txt', [outer.unpack('l4'),inner.unpack('l4'),Graphics.__timings].inspect)
  end
  if Input.trigger?(Input::C)
    file.puts('ENTER');file.flush
    background.fill_rect(24,120,590,32,Color.new(20,40,60))
    background.draw_text(24,120,590,32,'Enter received',0)
  end
  if Input.trigger?(Input::DOWN)
    file.puts('DOWN');file.flush
    background.fill_rect(24,160,590,32,Color.new(20,40,60))
    background.draw_text(24,160,590,32,'Down received',0)
  end
end
file.close
sprite.dispose
background.dispose
