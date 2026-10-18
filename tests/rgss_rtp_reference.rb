# Own fixture, valid in Ruby 1.8/4. No RTP asset is copied into the project.
raise 'RTP title accidentally exists locally' if File.exist?('Graphics/Titles/001-Title01.png')
raise 'RTP skin accidentally exists locally' if File.exist?('Graphics/Windowskins/001-Blue01.png')
if defined?(RGSSXP)
 expected=File.expand_path(File.open('rtp-root.txt','rb') { |file| file.read }).downcase
 raise 'Configured RTP path was not read' unless RGSSXP::RTP_PATHS.any? { |path| File.expand_path(path).downcase==expected }
end
File.open('types-reference.txt','w') do |file|
 [['rtp_title','Graphics/Titles/001-Title01'],['rtp_skin','Graphics/Windowskins/001-Blue01']].each do |label,path|
  bitmap=Bitmap.new(path)
  pixels=[[12,12],[32,32],[64,64]].collect do |x,y|
   color=bitmap.get_pixel(x,y)
   [color.red.to_i,color.green.to_i,color.blue.to_i,color.alpha.to_i]
  end
  file.puts(label+"\t"+[bitmap.width,bitmap.height,pixels].inspect)
  bitmap.dispose
 end
 # Same filename: project content must take precedence over the registered RTP.
 File.open('Graphics/Titles/001-Title01.png','wb') do |target|
  File.open('override.png','rb') { |source| target.write(source.read) }
 end
 bitmap=Bitmap.new('Graphics/Titles/001-Title01')
 color=bitmap.get_pixel(0,0)
 value=[bitmap.width,bitmap.height,color.red.to_i,color.green.to_i,color.blue.to_i,color.alpha.to_i]
 raise 'Project override did not win' unless value==[2,2,17,31,47,255]
 file.puts('project_priority'+"\t"+value.inspect);bitmap.dispose
 Audio.bgm_play('Audio/BGM/001-Battle01',1,100)
 40.times { Graphics.update;Input.update }
 if defined?(RGSSXP)
  voice=Audio.__voices.find { |item| item[:channel]==0 }
  raise 'RTP audio did not reach the scheduler' unless voice && voice[:samples]>0
 end
 Audio.bgm_stop
 file.puts('rtp_audio_loaded'+"\ttrue")
end
File.open('runtime-complete.txt','w') { |file| file.write('Registered RTP lookup, extension omission and project override completed') }
sleep(0.3)
