def io_assert_error(klass)
  begin
    yield
  rescue klass
    return
  end
  raise 'Expected '+klass.name
end
begin
  owner=Win32API.new('kernel32','GetCurrentThreadId',[],'L').call
  raise 'StringIO was not initialized before scripts' unless defined?(::StringIO)
  require 'stringio'
  raise 'Wrong bundled StringIO' unless StringIO::VERSION=='3.2.0'
  blob=(0..255).to_a.pack('C*')*9
  File.binwrite('binary.bin',blob)
  data,size,modified=RGSSXP.read_disk('binary.bin',0,nil,nil)
  raise 'Whole binary read changed bytes or encoding' unless data==blob && data.encoding==Encoding::BINARY && size==blob.bytesize
  raise 'File modification time precision lost' unless modified==File.mtime('binary.bin')
  [[0,0],[7,19],[blob.bytesize,1],[blob.bytesize+9,8]].each do |offset,length|
    actual,total=RGSSXP.read_disk('binary.bin',offset,length,size)
    expected=blob.byteslice(offset,length)||''.b
    raise 'Ranged read mismatch' unless actual==expected && total==size
  end
  File.binwrite('empty.bin','')
  raise 'Empty read mismatch' unless RGSSXP.read_disk('empty.bin',0,nil,nil)[0,2]==[''.b,0]
  File.binwrite('한글 파일.bin',blob)
  raise 'Korean path read failed' unless RGSSXP.read_file('한글 파일.bin')==blob
  long_path='Data/'+(0...5).map { |index| ('p'*60)+index.to_s }.join('/')+'/한글.bin'
  raise 'Native long path read failed' unless RGSSXP.read_disk(File.expand_path(long_path),0,nil,nil)[0]==blob
  io_assert_error(Errno::ENOENT) { RGSSXP.read_disk('missing.bin',0,nil,nil) }
  io_assert_error(ArgumentError) { RGSSXP.read_disk("bad\0name",0,nil,nil) }
  io_assert_error(TypeError) { RGSSXP.read_disk(123,0,nil,nil) }
  io_assert_error(ArgumentError) { RGSSXP.read_disk('binary.bin',-1,nil,nil) }
  io_assert_error(ArgumentError) { RGSSXP.read_disk('binary.bin',0,-1,nil) }
  io_assert_error(ArgumentError) { RGSSXP.read_disk('binary.bin',0,128*1024*1024+1,nil) }
  io_assert_error(ArgumentError) { RGSSXP.read_disk('binary.bin',0,nil,-1) }
  io_assert_error(IOError) { RGSSXP.read_disk('binary.bin',0,1,size+1) }
  File.open('large.bin','wb') { |file| file.seek(128*1024*1024);file.write('x') }
  io_assert_error(ArgumentError) { RGSSXP.read_disk('large.bin',0,nil,nil) }
  raise 'Large-file ranged read failed' unless RGSSXP.read_disk('large.bin',128*1024*1024,1,nil)[0,2]==['x'.b,128*1024*1024+1]
  count_before=RGSSXP.__io_threads[2]
  archive=RGSSXP::Archive.new('Data/fixture.rgssad')
  index_jobs=RGSSXP.__io_threads[2]-count_before
  raise 'Archive metadata cache ineffective' unless index_jobs>0 && index_jobs<100
  [0,999,1999].each do |index|
    expected=('entry:'+index.to_s+':')*(1+index%9)
    raise 'Archive seek/cache/key mismatch' unless archive.read('Data/entry'+index.to_s+'.bin')==expected
  end
  io_assert_error(Errno::ENOENT) { archive.read('missing.bin') }
  io_assert_error(NotImplementedError) { RGSSXP::Archive.new('Data/bad-version.rgssad') }
  ['truncated','bad-length','bad-name','duplicate'].each do |name|
    io_assert_error(ArgumentError) { RGSSXP::Archive.new('Data/'+name+'.rgssad') }
  end
  File.open('Data/fixture.rgssad','ab') { |file| file.write('x') }
  io_assert_error(IOError) { archive.read('Data/entry0.bin') }
  3.times { GC.start;raise 'Returned bytes lost after GC' unless RGSSXP.read_file('binary.bin')==blob }
  caller,worker,jobs=RGSSXP.__io_threads
  raise 'File I/O did not execute on another native thread' unless caller==owner && worker!=0 && worker!=owner && jobs>10
  File.write('file-io-result.txt',[caller,worker,jobs,index_jobs,long_path.length].join(','))
  File.write('runtime-complete.txt','io,false,false');sleep 0.3
rescue Exception => error
  File.open('file-io-error.txt','w') { |file| file.puts(error.full_message) }
  raise
end
