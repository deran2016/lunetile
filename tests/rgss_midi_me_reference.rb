# Own generated MIDI cases; API trace must be armed before playback.
Graphics.frame_rate=40
until File.exist?('begin-trace.txt');Graphics.update;end
Audio.bgm_play('Data/sustain.mid',100,100)
File.open('me-reference-stages.csv','w') do |file|
  file.sync=true;file.puts('name,start,played,end')
  [['me',136],['me-long',216],['me-3-4',136],['me-tempo',176]].each do |name,frames|
    started=Time.now.to_f;Audio.me_play('Data/'+name+'.mid',100,100);played=Time.now.to_f
    frames.times{Graphics.update}
    file.puts([name,started,played,Time.now.to_f].join(','))
  end
end
Audio.bgm_stop;Audio.me_stop
File.open('runtime-complete.txt','w'){|file|file.write('Owned MIDI length references completed')}
