deadline = Time.now.to_f + 60
until File.exist?('begin-trace.txt')
  raise 'Audio trace was not armed' if Time.now.to_f > deadline
  Graphics.update
end
# Bind the shared DirectSound buffer methods through the typed MIDI audio path first.
Audio.bgm_play('Data/tone.mid',100,100)
16.times { Graphics.update }
Audio.bgm_stop
File.open('audio-stages.txt','w') do |file|
  file.sync = true
  ['wav','ogg','mp3','wma','mid'].each do |extension|
    [0,1,25,50,75,100].each do |volume|
      file.puts([extension,volume,Time.now.to_f].inspect)
      begin
        Audio.bgm_play('Data/tone.'+extension,volume,100)
        8.times { Graphics.update }
      rescue Exception => error
        file.puts(['error',error.class.name,error.message].inspect)
      end
    end
    Audio.bgm_stop
    2.times { Graphics.update }
  end
end
File.open('runtime-complete.txt','w') { |file| file.write('Original audio volume calls observed') }
80.times { Graphics.update }
