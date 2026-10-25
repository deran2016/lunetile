require 'json'
def check(v,m);raise m unless v;end
def plain_probe(bitmap,text,font)
 RGSSXP.instance_variable_get(:@display_methods)[Bitmap][:__text].bind_call(bitmap,text,font,[0,0,0,0,0,false,true])!=false
end
bitmap=Bitmap.new(160,64);bitmap.font.name='Arial';bitmap.font.size=20
check(plain_probe(bitmap,'guard',bitmap.font),'default text rejected')
30.times { bitmap.draw_text(1,2,140,32,'guard') };GC.start;GC.compact if GC.respond_to?(:compact)
check(plain_probe(bitmap,'guard',bitmap.font),'method roots lost during compact')
checks=0
frozen_bitmap=Bitmap.new(32,32);frozen_bitmap.font.color.freeze
check(!plain_probe(frozen_bitmap,'guard',frozen_bitmap.font),'frozen Color bypassed setter failure')
begin;frozen_bitmap.draw_text(0,0,32,32,'frozen');raise 'frozen Color accepted';rescue FrozenError;end
frozen_bitmap.dispose
# Every captured method must stop the fast path after redefine/remove/prepend.
[[Font,:size],[Color,:red],[Color,:red=],[Color,:clone],[String,:to_s],[Bitmap,:__text],[RGSSXP.singleton_class,:text]].each do |klass,name|
 original=klass.instance_method(name)
 klass.send(:define_method,name) { |*args| original.bind_call(self,*args) }
 check(!plain_probe(bitmap,'guard',bitmap.font),'redefinition missed: '+name.to_s)
 bitmap.draw_text(1,2,140,32,'guard')
 klass.send(:define_method,name,original)
 check(plain_probe(bitmap,'guard',bitmap.font),'restored method rejected: '+name.to_s);checks+=1
end
original=Font.instance_method(:size);Font.send(:remove_method,:size)
check(!plain_probe(bitmap,'guard',bitmap.font),'removed getter missed');Font.send(:define_method,:size,original)
color=bitmap.font.color
color.define_singleton_method(:red) { 77 }
check(!plain_probe(bitmap,'guard',bitmap.font),'singleton Color missed')
color.singleton_class.send(:remove_method,:red)
# Even an empty singleton class is conservative; use a new plain Font.
bitmap.font=Font.new('Arial',20)
class CustomTextFont < Font;end
bitmap.font=CustomTextFont.new('Arial',20);check(!plain_probe(bitmap,'guard',bitmap.font),'Font subclass bypassed hooks')
bitmap.font=Font.new('Arial',20)
string='dynamic';string.define_singleton_method(:to_s) { 'different' };check(!plain_probe(bitmap,string,bitmap.font),'singleton String missed')
converter=Object.new;def converter.to_s;$conversions=($conversions||0)+1;'converted';end
bitmap.draw_text(0,0,140,32,converter);check($conversions==5,'custom conversion no longer runs for all five passes')
# Old __text hooks still receive all passes and can dispose or raise safely.
original=Bitmap.instance_method(:__text);calls=0
Bitmap.send(:define_method,:__text) { |*args| calls+=1;original.bind_call(self,*args) }
bitmap.draw_text(0,0,140,32,'hook');check(calls==5,'__text hook bypassed');Bitmap.send(:define_method,:__text,original)
# Equal source definitions after alias restoration are accepted.
check(plain_probe(bitmap,'guard',bitmap.font),'alias restore guard')
mod=Module.new { def size;super;end };Font.prepend(mod)
check(!plain_probe(bitmap,'guard',bitmap.font),'prepend missed')
bitmap.draw_text(0,0,140,32,'prepend')
File.write('text-guard.json',JSON.generate({passed:true,method_mutations:checks,removed:true,singletons:true,subclass:true,custom_conversion:true,private_hook:true,gc_compact:true,prepend:true}))
File.write('runtime-complete.txt','VXA text guard')
