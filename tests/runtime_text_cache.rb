require 'json'
def check(value,message);raise message unless value;end
Bitmap.__text_cache_enabled=true
resources=Win32API.new('user32','GetGuiResources','LL','L')
process=Win32API.new('kernel32','GetCurrentProcess','','L').call
bitmap=Bitmap.new(640,480);bitmap.font.name='Arial'
bitmap.font.outline=false if bitmap.font.respond_to?(:outline=)
bitmap.draw_text(10,10,180,28,'cached text')
before=Bitmap.__text_cache_stats
bitmap.font.color=Color.new(255,30,40,120)
bitmap.draw_text(30,40,80,36,'cached text',2)
check(Bitmap.__text_cache_stats[0]>before[0] && Bitmap.__text_cache_stats[5]==before[5],'color/position/width did not share raster')
size=bitmap.text_size('cached text')
check(size.width>0 && Bitmap.__text_cache_stats[0]>before[0],'measure did not reuse cache')
snapshot=bitmap.__pixel_bytes
Bitmap.__text_cache_enabled=false
uncached=Bitmap.new(640,480);uncached.font=bitmap.font
uncached.font.color=Color.new(255,255,255);uncached.draw_text(10,10,180,28,'cached text')
uncached.font.color=bitmap.font.color;uncached.draw_text(30,40,80,36,'cached text',2)
check(uncached.__pixel_bytes==snapshot,'cached text pixels differ')
uncached.dispose;Bitmap.__text_cache_enabled=true
text='mutable';bitmap.draw_text(0,0,180,30,text);text.replace('changed');bitmap.draw_text(0,0,180,30,text)
check(Bitmap.__text_cache_stats[1]==2,'mutable text reused wrong key')
210.times { |i| bitmap.draw_text(0,0,180,30,format('unique-%04d',i)) }
stats=Bitmap.__text_cache_stats
check(stats[2]<=4*1024*1024 && stats[3]<=128 && stats[4]>0,'text LRU not bounded')
count=stats[3];bitmap.draw_text(0,0,20,20,'W'*513)
check(Bitmap.__text_cache_stats[3]==count && Bitmap.__text_cache_stats[6]>0,'long text not bypassed')
handles=resources.call(process,0)
1000.times { |i| bitmap.draw_text(0,0,180,30,format('resource-%04d',i)) }
check(resources.call(process,0)<=handles+2,'text GDI resources grew')
Bitmap.__text_cache_enabled=true;bitmap.font.size=48
30.times { |i| bitmap.draw_text(0,0,180,30,'W'*180+format('%03d',i)) }
budget=Bitmap.__text_cache_stats
check(budget[2]<=4*1024*1024 && budget[2]>3*1024*1024 && budget[3]<30 && budget[4]>0,'text byte budget not enforced')
bitmap.font.size=96;count=budget[3]
bitmap.draw_text(0,0,180,30,'W'*300)
check(Bitmap.__text_cache_stats[3]==count && Bitmap.__text_cache_stats[6]>0,'large mask not bypassed')
bitmap.font.size=22
Bitmap.__invalidate_text_cache
check(Bitmap.__text_cache_stats[2,2]==[0,0],'text invalidation failed')
sprite=Sprite.new;sprite.bitmap=bitmap
bitmap.clear;Graphics.update
initial=Graphics.__upload_stats
bitmap.draw_text(11,17,70,28,'A')
Graphics.update
upload=Graphics.__upload_stats.zip(initial).map { |a,b| a-b }
check(upload[0]==1 && upload[2]==0 && upload[1]>0 && upload[1]<70*28*4,'small text uploaded whole bitmap')
bitmap.clear;initial=Graphics.__upload_stats;Graphics.update
check(Graphics.__upload_stats[1]-initial[1]==640*480*4,'clear stopped uploading whole bitmap')
effects=[]
if bitmap.font.respond_to?(:outline=)
 [true,false].each do |outline|
  bitmap.font.outline=outline;bitmap.font.shadow=true
  initial=Graphics.__upload_stats;bitmap.draw_text(11,17,70,28,'A');Graphics.update
  bytes=Graphics.__upload_stats[1]-initial[1]
  check(bytes>=upload[1] && bytes<70*28*4,'outline/shadow upload did not include bounded written region')
  effects<<bytes
 end
end
sprite.dispose;bitmap.dispose
weak=ObjectSpace::WeakMap.new
def weak_bitmap(weak)
 temporary=Bitmap.new(128,32);weak[temporary]=true;temporary.draw_text(0,0,128,32,'weak text')
 nil
end
weak_bitmap(weak)
10.times { uncached=Bitmap.new(128,32);uncached.draw_text(0,0,128,32,'stack overwrite');uncached.dispose }
uncached=nil
5.times { GC.start }
check(weak.keys.empty?,'text cache retains Bitmap')
active=Win32API.new('user32','GetActiveWindow','','L')
post=Win32API.new('user32','PostMessageA','LLLL','L')
hwnd=active.call;check(hwnd!=0,'missing owned test window')
check(post.call(hwnd,0x1d,0,0)!=0,'font change message failed')
Graphics.update
check(Bitmap.__text_cache_stats[2,2]==[0,0],'font message did not invalidate text cache')
probe=Bitmap.new(160,48);probe.draw_text(0,0,160,32,'environment')
send_plain=Win32API.new('user32','SendMessageW','LLLL','L')
send_plain.call(hwnd,0x1a,0,0);Graphics.update
check(Bitmap.__text_cache_stats[2,2]==[0,0],'settings message did not invalidate text cache')
probe.draw_text(0,0,160,32,'environment')
outer=Win32API.new('user32','GetWindowRect','LP','I');rect=[0,0,0,0].pack('l4');outer.call(hwnd,rect)
send=Win32API.new('user32','SendMessageW','LILP','L');send.call(hwnd,0x2e0,96|(96<<16),rect);Graphics.update
check(Bitmap.__text_cache_stats[2,2]==[0,0],'DPI message did not invalidate text cache')
if defined?(RGSS_VERSION)
 Dir.mkdir('Fonts');File.binwrite('Fonts/probe.ttf',File.binread(File.join(ENV.fetch('WINDIR'),'Fonts','arial.ttf')))
 begin
  probe.draw_text(0,0,160,32,'private font')
  Win32API.new('LunetileVXA.dll','RGSSSetupFonts','','V').call
  check(Bitmap.__text_cache_stats[2,2]==[0,0],'private font registration did not invalidate text cache')
 ensure
  path=File.expand_path('Fonts/probe.ttf').encode('UTF-16LE').b+"\0\0".b
  Win32API.new('gdi32','RemoveFontResourceExW','PLL','I').call(path,16,0)
  File.delete('Fonts/probe.ttf');Dir.rmdir('Fonts')
 end
end
probe.dispose
File.write('text-cache-result.json',JSON.generate({passed:true,upload_bytes:upload[1],effect_upload_bytes:effects,full_bytes:640*480*4,lru:stats,budget:budget,bitmap_released:true,font_change:true,dpi_change:true,private_fonts:!!defined?(RGSS_VERSION),gdi_handles_before:handles,gdi_handles_after:resources.call(process,0)}))
File.write('runtime-complete.txt','text cache,false,false')
