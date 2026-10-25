$text_resets=($text_resets||0)+1
raise 'text cache survived F12' unless Bitmap.__text_cache_stats[2,2]==[0,0]
bitmap=Bitmap.new(160,48);bitmap.draw_text(0,0,160,32,'F12 cache')
raise 'text cache did not populate' unless Bitmap.__text_cache_stats[3]>0
if $text_resets==1
 active=Win32API.new('user32','GetActiveWindow','','L')
 post=Win32API.new('user32','PostMessageA','LLLL','L')
 hwnd=active.call
 raise 'F12 post failed' if hwnd==0 || post.call(hwnd,0x100,0x7b,0)==0
 post.call(hwnd,0x101,0x7b,0);Graphics.update
 raise 'F12 did not reload scripts'
end
raise 'unexpected reset count' unless $text_resets==2
bitmap.dispose
File.write('runtime-complete.txt','text F12 reset,false,false')
