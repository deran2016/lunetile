$xp_tile_resets=($xp_tile_resets||0)+1
if $xp_tile_resets>1
 raise 'old tile cache survived F12' unless $xp_old_cache.stats[3]==0
 begin
  Graphics.__present([$xp_old_batch],-1.0,nil,0.0);raise 'old batch accepted after F12'
 rescue ArgumentError
 end
end
tile=Tilemap.new;tile.map_data=Table.new(4,4,1)
4.times { |y| 4.times { |x| tile.map_data[x,y,0]=384 } }
tile.tileset=Bitmap.new(256,32);tile.tileset.fill_rect(0,0,256,32,Color.new(100,140,180))
Graphics.update
raise 'tile cache not created' unless tile.instance_variable_get(:@xp_tile_cache)
if $xp_tile_resets==1
 $xp_old_cache=tile.instance_variable_get(:@xp_tile_cache);$xp_old_batch=tile.layers.first.commands.first
 active=Win32API.new('user32','GetActiveWindow','','L');post=Win32API.new('user32','PostMessageA','LLLL','L');hwnd=active.call
 raise 'F12 post failed' if hwnd==0||post.call(hwnd,0x100,0x7b,0)==0
 post.call(hwnd,0x101,0x7b,0);Graphics.update;raise 'F12 did not reload scripts'
end
raise 'reset loop' unless $xp_tile_resets==2
raise 'tile after F12' unless Graphics.__scene_pixel(10,10)==[100,140,180,255]
File.write('runtime-complete.txt','XP tile cache F12,false,false')
