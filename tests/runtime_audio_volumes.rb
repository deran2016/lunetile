# Identical Ruby 1.8/4 fixture; process-specific PCM verifies AudioPath gain.
Graphics.frame_rate=40;Graphics.update
File.open('game-ready.txt','w'){|file|file.write('Initial volume-test frame dispatched')}
deadline=Time.now.to_f+30
until File.exist?('capture-ready.txt')
  raise 'Process audio capture did not start' if Time.now.to_f>deadline
  sleep(0.02)
end
sleep(0.3)
File.open('audio-volume-stages.csv','w') do |file|
  file.sync=true;file.puts('volume,start,played,end,frames')
  [100,0,1,25,50,75,100].each do |volume|
    started=Time.now.to_f
    Audio.bgm_play('Data/held.mid',volume,100)
    played=Time.now.to_f
    64.times { Graphics.update }
    file.puts([volume,started,played,Time.now.to_f,64].join(','))
  end
end
Audio.bgm_stop
File.open('runtime-complete.txt','w'){|file|file.write('Owned MIDI volume PCM capture finished')}
sleep(0.3)
