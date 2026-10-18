# Own Unicode filenames; bytes in the archive use the explicitly declared project encoding.
begin
  label = File.binread('Data/label.txt').force_encoding('UTF-8')
  archive = RGSSXP::Archive.new('Data/names.rgssad')
  raw = label.encode(RGSSXP::SOURCE_ENCODING).b
  raise 'Raw/decoded archive keys differ' unless RGSSXP::Archive.normalize(raw) == RGSSXP::Archive.normalize(label)
  begin
    RGSSXP::Archive.new('Data/invalid-name.rgssad')
    raise 'Invalid declared archive name was accepted'
  rescue EncodingError
  end
  RGSSXP.open_archive('Data/names.rgssad')
  text = load_data('Data/'+label+'.rxdata')
  raise 'Encoded archive data did not normalize' unless text == label+' payload'
  bitmap = Bitmap.new('Graphics/Pictures/'+label)
  color = bitmap.get_pixel(0,0)
  raise 'Encoded archive image lookup failed' unless [bitmap.width,bitmap.height,color.red.to_i,color.green.to_i,color.blue.to_i,color.alpha.to_i]==[2,2,17,31,47,255]
  bitmap.dispose
  audio = RGSSXP.read_file('Audio/BGM/'+label,['.wav'])
  raise 'Encoded archive audio lookup failed' unless audio=='own audio fixture'.b
  File.write('archive-names-result.txt',label)
  File.write('runtime-complete.txt','archive-names,false,false');sleep 0.3
rescue Exception => error
  File.write('archive-names-error.txt',error.full_message)
  raise
end
