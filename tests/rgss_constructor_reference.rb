classes = ['RPG::Map','RPG::MapInfo','RPG::Event','RPG::Event::Page','RPG::Event::Page::Condition','RPG::Event::Page::Graphic','RPG::CommonEvent']
convert = nil
convert = proc do |value|
  case value
  when Table
    [value.class.name,value.xsize,value.ysize,value.zsize,value._dump(0).unpack('H*')[0]]
  when Color,Tone,Rect
    [value.class.name,value._dump(0).unpack('H*')[0]]
  when Array
    value.collect { |item| convert.call(item) }
  when Hash
    value.keys.sort.collect { |key| [convert.call(key),convert.call(value[key])] }
  when Numeric,String,TrueClass,FalseClass,NilClass
    value
  else
    [value.class.name,value.instance_variables.collect { |name| name.to_s }.sort.collect { |name| [name,convert.call(value.instance_variable_get(name))] }]
  end
end
File.open('types-reference.txt','w') do |file|
  classes.each do |name|
    klass = name.split('::').inject(Object) { |parent,part| parent.const_get(part) }
    args = name == 'RPG::Map' ? [3,2] : name == 'RPG::Event' ? [2,3] : []
    file.puts(name + "\t" + convert.call(klass.new(*args)).inspect)
  end
end
