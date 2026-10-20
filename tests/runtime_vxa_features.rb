def check(value,message); raise message unless value; end
check(Rect.new == Rect.new(0,0,0,0),'Rect default')
check(Tone.new == Tone.new(0,0,0,0),'Tone default')
check(Color.new == Color.new(0,0,0,0),'Color default')
check(Color.new(1,2,3).alpha == 255,'Color three-component alpha')
viewport = Viewport.new
check(viewport.rect.width == Graphics.width,'viewport default')
window = Window.new(10,20,80,60)
check(window.contents.is_a?(Bitmap) && window.padding == 12,'window defaults')
window.openness = 0
check(window.close?,'window close')
window.openness = 999
check(window.open?,'window clamp')
bitmap = Bitmap.new(4,2)
bitmap.gradient_fill_rect(bitmap.rect,Color.new(0,0,0),Color.new(255,0,0))
check(bitmap.get_pixel(0,0).red == 0 && bitmap.get_pixel(3,0).red == 255,'gradient endpoints')
bitmap.clear_rect(0,0,1,1)
check(bitmap.get_pixel(0,0).alpha == 0,'clear rectangle')
bitmap.blur
bitmap.radial_blur(30,3)

# RGSS3 index and body encryption have different key schedules.
name = 'Data/Probe.rvdata2'.b
plain = 'archive round trip'.b
key = 27*9+3
body_key = 0x12345678
encrypted_name = name.bytes.each_with_index.map { |b,i| b ^ ([key].pack('V').getbyte(i%4)) }.pack('C*')
offset = 12+16+name.bytesize+4
header = "RGSSAD\0\x03".b+[27].pack('V')
entry = [offset^key,plain.bytesize^key,body_key^key,name.bytesize^key].pack('V4')+encrypted_name
bytes = header+entry+[key].pack('V')+RGSSXP.decode_archive(plain,body_key)
File.binwrite('test.rgss3a',bytes)
archive = RGSSXP::Archive.new('test.rgss3a')
check(archive.read('data/PROBE.rvdata2') == plain,'archive payload')
File.binwrite('bad.rgss3a',bytes.byteslice(0,bytes.bytesize-1))
begin
  RGSSXP::Archive.new('bad.rgss3a')
  raise 'accepted truncated archive'
rescue ArgumentError
end
bad = bytes.dup
bad[12,4] = [4^key].pack('V')
File.binwrite('bad.rgss3a',bad)
begin
  RGSSXP::Archive.new('bad.rgss3a')
  raise 'accepted directory overlap'
rescue ArgumentError
end
check(Tilemap::FLOOR.length == 48 && Tilemap::WALL.length == 16,'autotile shapes')
Graphics.update
File.write('runtime-complete.txt','VX Ace types, graphics and archive checks')
