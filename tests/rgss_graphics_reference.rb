# Primitive graphics behavior observed locally; no original implementation is copied.
def norm(value)
  case value
  when Array then value.collect { |child| norm(child) }
  when Color then [value.red.to_s, value.green.to_s, value.blue.to_s, value.alpha.to_s]
  when Tone then [value.red.to_s, value.green.to_s, value.blue.to_s, value.gray.to_s]
  when Rect then [value.x, value.y, value.width, value.height]
  when Float then value.to_s
  when Integer, String, TrueClass, FalseClass, NilClass then value
  else value.class.name
  end
end
File.open('types-reference.txt', 'w') do |out|
  record = proc do |name, action|
    begin
      value = norm(action.call)
    rescue Exception => error
      value = ['error', error.class.name]
    end
    out.puts(name + "\t" + value.inspect)
    out.flush
  end
  record.call('font', proc { f=Font.new; [f.name,f.size,f.bold,f.italic,f.color] })
  record.call('font_bounds', proc {f=Font.new;f.size=1;a=f.size;f.size=999;[a,f.size]})
  record.call('font_copy', proc {f=Font.new;c=Color.new(1,2,3);f.color=c;c.red=9;f.color})
  record.call('font_defaults', proc {[Font.default_name,Font.default_size,Font.default_bold,Font.default_italic,Font.default_color]})
  record.call('bitmap_empty', proc {b=Bitmap.new(4,3);v=[b.width,b.height,b.rect,b.get_pixel(0,0),b.get_pixel(-1,0),b.font.name];b.dispose;v})
  record.call('set_pixel', proc {b=Bitmap.new(2,2);b.set_pixel(0,0,Color.new(201,101,51,128));v=b.get_pixel(0,0);b.dispose;v})
  record.call('fill_clip', proc {b=Bitmap.new(2,2);b.fill_rect(-1,0,2,1,Color.new(12,34,56,78));v=[b.get_pixel(0,0),b.get_pixel(1,0),b.get_pixel(0,1)];b.dispose;v})
  record.call('blt_transparent', proc {b=Bitmap.new(2,2);s=Bitmap.new(2,2);s.fill_rect(0,0,2,2,Color.new(200,100,50,128));b.blt(0,0,s,Rect.new(0,0,2,2));v=b.get_pixel(0,0);b.dispose;s.dispose;v})
  record.call('blt_opaque', proc {b=Bitmap.new(2,2);b.fill_rect(b.rect,Color.new(20,40,60));s=Bitmap.new(2,2);s.fill_rect(s.rect,Color.new(200,100,50,128));b.blt(0,0,s,s.rect,128);v=b.get_pixel(0,0);b.dispose;s.dispose;v})
  record.call('bitmap_clone', proc {b=Bitmap.new(2,2);b.set_pixel(0,0,Color.new(1,2,3));c=b.clone;c.set_pixel(0,0,Color.new(8,9,10));v=[b.get_pixel(0,0),c.get_pixel(0,0),c.font.object_id==b.font.object_id];b.dispose;c.dispose;v})
  record.call('bitmap_disposed', proc {b=Bitmap.new(1,1);b.dispose;b.width})
  record.call('sprite', proc {s=Sprite.new;v=[s.bitmap,s.src_rect,s.x,s.y,s.z,s.ox,s.oy,s.zoom_x,s.zoom_y,s.angle,s.mirror,s.bush_depth,s.opacity,s.blend_type,s.visible,s.color,s.tone];s.dispose;v})
  record.call('sprite_bitmap_rect', proc {s=Sprite.new;b=Bitmap.new(10,20);s.src_rect.set(2,3,4,5);s.bitmap=b;v=s.src_rect.clone;s.dispose;b.dispose;v})
  record.call('sprite_bounds', proc {s=Sprite.new;s.opacity=999;a=s.opacity;s.opacity=-9;s.blend_type=9;v=[a,s.opacity,s.blend_type];s.dispose;v})
  record.call('viewport', proc {v=Viewport.new(1,2,3,4);r=[v.rect,v.ox,v.oy,v.z,v.visible,v.color,v.tone];v.dispose;r})
  record.call('window', proc {w=Window.new;v=[w.x,w.y,w.z,w.width,w.height,w.ox,w.oy,w.opacity,w.back_opacity,w.contents_opacity,w.visible,w.active,w.pause,w.stretch,w.cursor_rect,w.windowskin,w.contents];w.dispose;v})
  record.call('plane', proc {p=Plane.new;v=[p.ox,p.oy,p.z,p.zoom_x,p.zoom_y,p.opacity,p.blend_type,p.visible,p.color,p.tone,p.bitmap];p.dispose;v})
  record.call('text_size', proc {b=Bitmap.new(100,50);v=[b.text_size('Hello'),b.text_size('')];b.dispose;v})
  record.call('opacity_clamp', proc {s=Sprite.new;s.opacity=999;a=s.opacity;s.opacity=-9;v=[a,s.opacity];s.dispose;v})
  [5,6,96,97].each {|size| record.call('font_size_'+size.to_s,proc {f=Font.new;f.size=size;f.size})}
end
