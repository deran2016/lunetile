# Corrupt indexes must fail before seeking/allocating untrusted sizes.
File.binwrite('invalid.rgssad', ['5247535341440003'].pack('H*'))
begin
  RGSSXP::Archive.new('invalid.rgssad')
  raise 'corrupt archive accepted: header'
rescue NotImplementedError
end
File.binwrite('invalid.rgssad', ['524753534144000100'].pack('H*'))
begin
  RGSSXP::Archive.new('invalid.rgssad')
  raise 'corrupt archive accepted: word'
rescue ArgumentError
end
File.binwrite('invalid.rgssad', ['5247535341440001013552a1'].pack('H*'))
begin
  RGSSXP::Archive.new('invalid.rgssad')
  raise 'corrupt archive accepted: name-length'
rescue ArgumentError
end
File.binwrite('invalid.rgssad', ['5247535341440001f8caaddeb1d7898faade8c03cc1f'].pack('H*'))
begin
  RGSSXP::Archive.new('invalid.rgssad')
  raise 'corrupt archive accepted: payload-bounds'
rescue ArgumentError
end
File.binwrite('invalid.rgssad', ['5247535341440001facaaddedb98a196840aea63c7'].pack('H*'))
begin
  RGSSXP::Archive.new('invalid.rgssad')
  raise 'corrupt archive accepted: path'
rescue ArgumentError
end
File.binwrite('invalid.rgssad', ['5247535341440001f8caaddeb1d7898faade8c03cc1fbfd81894de51d7498f8adeac264f39dc'].pack('H*'))
begin
  RGSSXP::Archive.new('invalid.rgssad')
  raise 'corrupt archive accepted: duplicate'
rescue ArgumentError
end
begin
  RGSSXP.inflate(['6e6f74207a6c6962'].pack('H*'))
  raise ArgumentError, 'Invalid zlib accepted: invalid'
rescue RuntimeError
end
begin
  RGSSXP.inflate(['789c3304000032003278'].pack('H*'))
  raise ArgumentError, 'Invalid zlib accepted: trailing'
rescue RuntimeError
end
begin
  RGSSXP.inflate(['789c330400003200'].pack('H*'))
  raise ArgumentError, 'Invalid zlib accepted: truncated'
rescue RuntimeError
end
File.write('runtime-complete.txt', 'input-errors,false,false')
sleep 0.5
