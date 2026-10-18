deadline = Time.now.to_f + 60
until File.exist?('begin-trace.txt')
  raise 'Audio trace was not armed' if Time.now.to_f > deadline
  Graphics.update
end
File.open('audio-stages.txt','w') do |file|
  file.sync = true
  [50,100,150].each do |pitch|
    file.puts([pitch,Time.now.to_f].inspect)
    Audio.bgm_play('Data/tone.mid',50,pitch)
    60.times { Graphics.update }
    Audio.bgm_stop
    4.times { Graphics.update }
  end
end
File.open('runtime-complete.txt','w') { |file| file.write('Original MIDI pitch calls observed') }
120.times { Graphics.update }
