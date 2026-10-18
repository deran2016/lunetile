def verify(condition,message)
  raise message unless condition
end
encoding = RGSSXP::SOURCE_ENCODING
expected = RGSSXP::DATA_ENCODING=='CP932' ? '日本語' : '한글'
encoded = expected.encode(encoding).b
root = [encoded,encoded]
root << root
changes = []
converted = RGSSXP.normalize_data(root,'fixture',{},changes)
verify(converted[0]==expected && converted[0].encoding==Encoding::UTF_8,'Legacy text did not become UTF-8')
verify(converted[0].equal?(converted[1]) && converted[2].equal?(converted),'Text conversion lost aliases/cycles')
verify(changes.size==1,'Aliased string was converted more than once')
key = expected.encode(encoding).b.freeze
value = {key=>[key]}
RGSSXP.normalize_data(value)
verify(value.keys.first.equal?(value[expected].first),'Frozen Hash-key alias was lost')
unless defined?(Table)
  class Table
    def initialize(*)
      @bytes="\xff\x00\x80".b
    end
    def _dump(*)
      @bytes
    end
  end
end
native = Table.new(1)
before = native._dump(0)
verify(RGSSXP.normalize_data(native).equal?(native) && native._dump(0)==before,'Native payload was transcoded')
begin
  RGSSXP.normalize_data("\xff".b)
  raise 'Invalid legacy byte sequence was accepted'
rescue EncodingError
end
begin
  RGSSXP.normalize_data(expected.encode('UTF-16LE'))
  raise 'Conflicting declared encoding was accepted'
rescue EncodingError
end
if RGSSXP::DATA_ENCODING=='CP932'
  keys=["\x81\xbe".b,"\x87\x9c".b]
  verify(keys.map { |s| s.dup.force_encoding(encoding).encode('UTF-8') }.uniq.size==1,'Collision fixture is invalid')
  begin
    RGSSXP.normalize_data({keys[0]=>1,keys[1]=>2})
    raise 'Decoded key collision lost data'
  rescue EncodingError
  end
end
