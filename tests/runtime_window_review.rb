# Read-only telemetry for this game's own HWND; UI actions are performed by the desktop test.
active=Win32API.new('user32','GetActiveWindow','','I')
client=Win32API.new('user32','GetClientRect','IP','I')
rectangle=Win32API.new('user32','GetWindowRect','IP','I')
style=Win32API.new('user32','GetWindowLongA','II','I')
placement=Win32API.new('user32','GetWindowPlacement','IP','I')
monitor=Win32API.new('user32','MonitorFromWindow','II','I')
monitor_info=Win32API.new('user32','GetMonitorInfoW','IP','I')
pid=Win32API.new('kernel32','GetCurrentProcessId','','I')
owner=Win32API.new('user32','GetWindowThreadProcessId','IP','I')
clock=Win32API.new('kernel32','GetTickCount','','L')
bitmap=Bitmap.new(640,480)
[[0,0,Color.new(220,40,40)],[320,0,Color.new(40,180,40)],[0,240,Color.new(40,40,220)],[320,240,Color.new(230,230,230)]].each do |x,y,color|
 bitmap.fill_rect(x,y,320,240,color)
end
bitmap.draw_text(0,0,640,48,'RGSSXP window review: 640 x 480',1)
sprite=Sprite.new;sprite.bitmap=bitmap
Graphics.frame_rate=40;Graphics.transition(0)
window=active.call;owned=[0].pack('L');owner.call(window,owned)
raise 'Window probe must own its HWND' unless window!=0 && owned.unpack('L')[0]==pid.call
started=clock.call
File.open('window-trace.csv','w') { |file| file.puts('ms,frame,style,client_w,client_h,x,y,w,h,show,monitor_x,monitor_y,monitor_w,monitor_h') }
loop do
 Input.update;Graphics.update
 next unless Graphics.frame_count%20==0
 c=[0]*4;c=c.pack('l*');r=c.dup;p=[44,0,0,0,0,0,0,0,0,0,0].pack('l*');m=[40,0,0,0,0,0,0,0,0,0].pack('l*')
 raise 'Window query failed' unless client.call(window,c)!=0 && rectangle.call(window,r)!=0 && placement.call(window,p)!=0 && monitor_info.call(monitor.call(window,2),m)!=0
 c=c.unpack('l*');r=r.unpack('l*');p=p.unpack('l*');m=m.unpack('l*')
 values=[clock.call-started,Graphics.frame_count,style.call(window,-16)&0xffffffff,c[2]-c[0],c[3]-c[1],r[0],r[1],r[2]-r[0],r[3]-r[1],p[2],m[1],m[2],m[3]-m[1],m[4]-m[2]]
 File.open('window-trace.csv','a') { |file| file.puts(values.join(',')) }
end
