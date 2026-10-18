# Own conformance probes; run locally against an independently supplied RGSS1.
def normalized(value)
  case value
  when Array then value.collect {|v| normalized(v)}
  when Float then value.to_s
  when Integer, String, TrueClass, FalseClass, NilClass then value
  else value.class.name
  end
end
File.open('types-reference.txt','w') do |out|
  record = proc do |name, action|
    begin
      value=normalized(action.call)
    rescue Exception => error
      value=['error',error.class.name]
    end
    out.puts(name+"\t"+value.inspect)
    out.flush
  end
  record.call('table_shape',proc {t=Table.new(2,3,4);[t.xsize,t.ysize,t.zsize,t[0,0,0],t[2,0,0],t[-1,0,0]]})
  [-32769,-32768,32767,32768,65535,65536,2147483647,1.5].each do |v|
    record.call('table_value_'+v.to_s,proc {t=Table.new(1);t[0]=v;t[0]})
  end
  record.call('table_resize',proc {t=Table.new(2,2);t[0,0]=11;t[1,0]=12;t[0,1]=21;t[1,1]=22;t.resize(3,2);[t.xsize,t.ysize,t.zsize,t[0,0],t[1,0],t[2,0],t[0,1],t[1,1],t[2,1],t._dump(0).unpack('H*')[0]]})
  record.call('table_dimension_one',proc {t=Table.new(2);[t.xsize,t.ysize,t.zsize,t._dump(0).unpack('H*')[0]]})
  record.call('table_zero',proc {t=Table.new(0);[t.xsize,t.ysize,t.zsize,t[0]]})
  record.call('color_clamp',proc {c=Color.new(-20,256,1.5,-1);[c.red,c.green,c.blue,c.alpha]})
  record.call('color_dump',proc {Color.new(1,2,3,4)._dump(0).unpack('H*')[0]})
  record.call('color_default',proc {c=Color.new(1,2,3);[c.red,c.green,c.blue,c.alpha]})
  record.call('color_set',proc {c=Color.new(1,2,3);r=c.set(4,5,6,7);[r,c.red,c.green,c.blue,c.alpha]})
  record.call('tone_clamp',proc {c=Tone.new(-999,999,1.5,999);[c.red,c.green,c.blue,c.gray]})
  record.call('tone_dump',proc {Tone.new(-1,2,3,4)._dump(0).unpack('H*')[0]})
  record.call('rect_default',proc {r=Rect.new;[r.x,r.y,r.width,r.height]})
  record.call('rect_values',proc {r=Rect.new(1.8,-2.8,-3,4);[r.x,r.y,r.width,r.height]})
  record.call('rect_empty',proc {r=Rect.new(1,2,3,4);v=r.empty;[v,r.x,r.y,r.width,r.height]})
  record.call('rect_dump',proc {Rect.new(1,2,3,4)._dump(0).unpack('H*')[0]})
  record.call('table_arity',proc {t=Table.new(2,2);[t[0],t[0,0,0]]})
  record.call('table_bad_write',proc {t=Table.new(1);t.send(:[]=,4,9)})
  record.call('table_resize_return',proc {Table.new(1).resize(2)})
  record.call('table_clone',proc {t=Table.new(1);t[0]=3;c=t.clone;c[0]=8;[t[0],c[0]]})
  record.call('color_low',proc {c=Color.new(-999,-999,-999,-999);[c.red,c.green,c.blue,c.alpha]})
  record.call('color_setters',proc {c=Color.new(0,0,0);c.red=-999;c.green=-999;c.blue=-999;c.alpha=-999;[c.red,c.green,c.blue,c.alpha]})
  record.call('color_copy',proc {c=Color.new(1,2,3,4);d=Color.new(c);[d.red,d.green,d.blue,d.alpha]})
  record.call('color_set_copy',proc {c=Color.new(0,0,0);v=c.set(Color.new(1,2,3,4));[v,c.red,c.green,c.blue,c.alpha]})
  record.call('tone_default',proc {c=Tone.new(1,2,3);[c.red,c.green,c.blue,c.gray]})
  record.call('rect_set_copy',proc {r=Rect.new(0,0,0,0);v=r.set(Rect.new(1,2,3,4));[v,r.x,r.y,r.width,r.height]})
  record.call('rect_copy',proc {r=Rect.new(Rect.new(1,2,3,4));[r.x,r.y,r.width,r.height]})
  record.call('color_equality',proc {c=Color.new(1,2,3);[c==c.clone,c.eql?(c.clone)]})
end
