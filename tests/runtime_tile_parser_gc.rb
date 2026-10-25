def check(v,m);raise m unless v;end
Graphics.resize_screen(64,48)
weak=ObjectSpace::WeakMap.new
make=lambda do
 bitmap=Bitmap.new(8,8);bitmap.fill_rect(0,0,8,8,Color.new(210,30,60));weak[bitmap]=true
 [0,bitmap,0,0,8,8,0,0,8,8,1,1,0,0,0,255,0,nil,nil,0,nil,false]
end
second=Bitmap.new(8,8);second.fill_rect(0,0,8,8,Color.new(20,130,70))
commands=[make.call,[0,second,16,0,8,8,0,0,8,8,1,1,0,0,0,255,0,nil,nil,0,nil,false]]
hook=Object.new
hook.define_singleton_method(:red) do
 commands[0]=nil;GC.start;GC.compact if GC.respond_to?(:compact)
 check(weak.keys.any?,'native parsed bitmap was collected during Ruby callback');0
end
%i[green blue alpha].each { |name| hook.define_singleton_method(name) { 0 } }
commands[1][17]=hook
Graphics.__present(commands,-1.0,nil,0.0)
check(Graphics.__scene_pixel(2,2)[0]>150,'GC-protected bitmap was not drawn')
commands[0]=make.call
hook.define_singleton_method(:red) { commands[0][1].dispose;0 }
sequence=Graphics.__timings[8]
begin
 Graphics.__present(commands,-1.0,nil,0.0);raise 'disposed bitmap accepted'
rescue RGSSError
end
check(Graphics.__timings[8]==sequence,'invalid frame partially submitted')
# Scalar conversion also completes before validating live bitmap references.
commands=[make.call]
progress=Object.new;progress.define_singleton_method(:to_f) { commands[0][1].dispose;-1.0 }
begin
 Graphics.__present(commands,progress,nil,0.0);raise 'scalar callback disposal accepted'
rescue RGSSError
end
File.write('runtime-complete.txt','parser roots and pre-submit validation,false,false')
