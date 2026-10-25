require 'json'
def check(value,message);raise message unless value;end
[nil,true,false,1,:display].each { |value| check(RGSSXP.__plain_display_class(value).nil?,'immediate value entered native object header') }
bitmap=Bitmap.new(32,32);bitmap.fill_rect(bitmap.rect,Color.new(120,67,41,180))
Graphics.resize_screen(64,48)
viewports=Array.new(3) { |i| Viewport.new(i*11,i*7,120,90) }
sprites=Array.new(40) do |i|
 sprite=Sprite.new(i%4==0 ? nil : viewports[i%3]);sprite.bitmap=bitmap
 sprite.x=i*7;sprite.y=i%5;sprite.z=i%3;sprite.opacity=140+i
 sprite.angle=i;sprite.mirror=i.odd?;sprite.bush_depth=i%4;sprite
end
def compare_display
 reference=RGSSXP.__legacy_scene_commands
 actual=RGSSXP.scene_commands
 check(actual==reference,'display command order/content differs')
 actual
end
def display_pixels(commands)
 Graphics.__present(commands,-1.0,nil,0.0)
 capture=Graphics.__snapshot;pixels=capture.__pixel_bytes;capture.dispose;pixels
end
12.times do |i|
 sprites[i].y=i*3;sprites[i].z=4-i
 sprites[i+1].visible=i.even?
 sprites[i+2].flash(i.odd? ? nil : Color.new(13,27,61,180),3)
 viewports[i%3].z=i%2;viewports[i%3].ox=i;viewports[i%3].tone.set(i,-i,3,0)
 compare_display
 if i%4==0
  check(display_pixels(RGSSXP.__legacy_scene_commands)==display_pixels(RGSSXP.scene_commands),'full display pixels differ')
 end
end
snapshot=compare_display;quads=snapshot.select { |c| c[0]==0 };positions=quads.map { |c| c[2,2] }
sprites.each { |sprite| sprite.x+=100 }
compare_display
check(quads.map { |c| c[2,2] }==positions,'old commands overwritten by next frame')
direct=[];sprites.last.emit(direct)
check(direct==RGSSXP.__legacy_scene_commands.select { |c| c[0]==0 && c[2]==sprites.last.x+sprites.last.screen_offset[0] && c[3]==sprites.last.y+sprites.last.screen_offset[1] },'direct emit changed')
module RGSSXP
 class << self
  alias display_original_quad quad
  def quad(*args);$quad_calls+=1;display_original_quad(*args);end
 end
end
$quad_calls=0
compare_display
check($quad_calls>0,'custom quad bypassed')
class << RGSSXP;alias quad display_original_quad;remove_method :display_original_quad;end
sprites[0].define_singleton_method(:emit) { |output| GC.start;super(output) }
compare_display
sprites[0].singleton_class.remove_method(:emit)
class IdentityViewport < Viewport
 def hash;1;end
 def eql?(other);true;end
end
identity_views=Array.new(2) { IdentityViewport.new(0,0,32,32) }
identity_sprites=identity_views.map { |viewport| sprite=Sprite.new(viewport);sprite.bitmap=bitmap;sprite }
compare_display
identity_sprites.each(&:dispose);identity_views.each(&:dispose)
class DisplayHookSprite < Sprite
 def emit(output);$display_hook_calls+=1;super;end
end
$display_hook_calls=0;hook=DisplayHookSprite.new;hook.bitmap=bitmap
compare_display
check($display_hook_calls==2,'subclass rendering hook bypassed');hook.dispose
GC.verify_compaction_references(double_heap:true,toward: :empty)
GC.auto_compact=true
3.times { GC.start;compare_display }
GC.auto_compact=false
if defined?(RGSS_VERSION)
 sprites[2].viewport=viewports[2];compare_display
 class DisplayMovingColor < Color
  attr_accessor :target,:destination
  def red;target.viewport=destination;super;end
 end
 flasher=Sprite.new(viewports[0]);flasher.bitmap=bitmap;flasher.z=-10
 moving=sprites[3];color=DisplayMovingColor.new(30,50,70,150);color.target=moving;color.destination=viewports[1]
 moving.viewport=viewports[0];flasher.flash(color,3)
 expected=RGSSXP.__legacy_scene_commands
 moving.viewport=viewports[0];flasher.flash(color,3)
 check(RGSSXP.scene_commands==expected,'viewport change during emit lost membership update')
 flasher.dispose
end
sprites[5].dispose;viewports[2].dispose
compare_display
sprites.each(&:dispose);viewports.each(&:dispose);bitmap.dispose
Graphics.update
File.write('display-result.json',JSON.generate({passed:true,ordering:true,pixel_comparisons:3,immediate_inputs:true,quad_hook:true,singleton_hook:true,gc:true,retained_commands:true,viewport_mutation:defined?(RGSS_VERSION) ? true : nil}))
File.write('runtime-complete.txt','display commands,false,false')
