def verify(condition, message)
  raise message unless condition
end
map = RGSSXP::IntegerMap.new
verify(map.values == [], 'Empty value snapshot changed')
1.upto(300) { |key| map[key] = [key] }
snapshot = map.values
snapshot.clear
verify(map.values.size == 300, 'Caller changed the cached value snapshot')
before = map.values
map[1] = :replacement
verify(map.values == map.keys.map { |key| map[key] }, 'Value replacement left a stale snapshot')
verify(before.include?([1]) && !before.include?(:replacement), 'Earlier snapshot changed after replacement')
1.upto(250) { |key| map.delete(key) }
verify(map.values == map.keys.map { |key| map[key] }, 'Deletion left a stale value snapshot')
map[400] = map
map[401] = map[299]
copy = Marshal.load(Marshal.dump(map))
verify(copy.keys == map.keys, 'New-format save changed ID table order/capacity')
verify(copy[400].equal?(copy), 'ID table self-reference lost')
verify(copy[401].equal?(copy[299]), 'ID table shared value lost')
verify(copy.is_a?(Hash) && copy.size == map.size, 'Hash interface changed')
copy.each_value.to_a.zip(copy.values) { |a,b| verify(a.equal?(b), 'each_value order changed') }
copy.each_key.to_a.zip(copy.keys) { |a,b| verify(a == b, 'each_key order changed') }
cleared = copy.dup
cleared.values
cleared.clear
verify(cleared.values == [], 'Clear left a stale value snapshot')
uncached = RGSSXP::IntegerMap.new
uncached[1] = 2
uncached.freeze
verify(uncached.values == [2], 'Reading a frozen uncached table failed')
frozen = copy.dup.freeze
before = frozen.keys
begin
  frozen[999] = 1
  raise 'Frozen ID table mutated'
rescue FrozenError
end
verify(frozen.keys == before && !frozen.key?(999), 'Frozen failure corrupted buckets')
[nil,'1',1073741824].each do |key|
  begin
    map[key] = 0
    raise 'Unsupported ID accepted'
  rescue TypeError
  end
end
begin
  map.merge!(123=>0)
  raise 'Untracked mutation accepted'
rescue NotImplementedError
end
bad = RGSSXP::IntegerMap.allocate
begin
  bad.marshal_load([1,Array.new(11) { [] },[1]])
  raise 'Malformed ID table payload accepted'
rescue TypeError
end
File.write('runtime-complete.txt','integer-map,false,false')
sleep 0.5
