# Own integer-key ordering probes for stock event/common-event/state tables.
File.open('types-reference.txt','w') do |out|
  table_class = defined?(RGSSXP::IntegerMap) ? RGSSXP::IntegerMap : Hash
  [0,1,2,10,11,12,55,56,57,60,66,67,68,114,115,116,222,223,224,100,300,999].each do |count|
    [false,true].each do |reverse|
      keys=(1..count).to_a
      keys.reverse! if reverse
      table=table_class.new
      keys.each { |key| table[key]=key }
      out.puts("#{count}_#{reverse}\t#{table.keys.inspect}")
      if defined?(RGSSXP::IntegerMap)
        raw={};table.each { |key,value| raw[key]=value }
        loaded=RGSSXP::IntegerMap.from_original(raw)
      else
        loaded=Marshal.load(Marshal.dump(table))
      end
      out.puts("#{count}_#{reverse}_loaded\t#{loaded.keys.inspect}")
      table[1]=99 if count>0
      out.puts("#{count}_#{reverse}_replaced\t#{table.keys.inspect}")
      keys.each { |key| table.delete(key) if key%3==0 }
      out.puts("#{count}_#{reverse}_deleted\t#{table.keys.inspect}")
      keys.each { |key| table[key]=key if key%3==0 }
      out.puts("#{count}_#{reverse}_reinserted\t#{table.keys.inspect}")
    end
  end
  table=table_class.new
  [0,-1,1,-11,11,1073741823,-1073741824].each { |key| table[key]=key }
  out.puts("signed_integer_keys\t#{table.keys.inspect}")
  seed=12345
  [150,300,999].each do |count|
    table=table_class.new
    (1..count).each { |key| table[key]=key }
    400.times do |i|
      seed=(seed*1103515245+12345)&0x7fffffff
      key=seed%1200-600
      if i%3==0 then table.delete(key) else table[key]=i end
    end
    out.puts("mixed_#{count}\t#{table.keys.inspect}")
    duplicate=table.dup
    duplicate[2000]=1;duplicate.delete(1)
    out.puts("mixed_#{count}_dup\t#{duplicate.keys.inspect}")
    table.clear
    (1..20).each { |key| table[key]=key }
    out.puts("mixed_#{count}_clear\t#{table.keys.inspect}")
  end
end
