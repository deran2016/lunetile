# Identical Ruby 1.8/4 source; generated tones, no microphone and no logical key injection.
Graphics.frame_rate=40;Graphics.update
background=File.read('audio-case.txt').split(',')[0]=='channels-repeat' ? 'Data/sustain.mid' : 'Data/held.mid'
File.open('game-ready.txt','w'){|file|file.write('Initial audio-test frame dispatched')}
deadline=Time.now.to_f+30
until File.exist?('capture-ready.txt')
  raise 'Process audio capture did not start' if Time.now.to_f>deadline
  sleep(0.02)
end
sleep(0.3)
def channel_stage(file,name,frames)
  started=Time.now.to_f;yield;played=Time.now.to_f
  frames.times { Graphics.update }
  file.puts([name,started,played,Time.now.to_f,frames].join(','))
end
File.open('audio-channel-stages.csv','w') do |file|
  file.sync=true;file.puts('stage,start,played,end,frames')
  channel_stage(file,'bgm',96){Audio.bgm_play(background,100,100)}
  channel_stage(file,'volume50',96){Audio.bgm_play(background,50,100)}
  channel_stage(file,'mix',80){Audio.bgm_play(background,100,100);Audio.bgs_play('Data/bgs.wav',100,100)}
  channel_stage(file,'me',64){Audio.me_play('Data/me.mid',100,100)}
  channel_stage(file,'resumed',64){}
  channel_stage(file,'bgs_stopped',64){Audio.bgs_stop}
  channel_stage(file,'all_stopped',96){Audio.bgm_stop}
  channel_stage(file,'me_solo',64){Audio.me_play('Data/me.mid',100,100)}
end
Audio.bgm_stop;Audio.bgs_stop;Audio.me_stop;Audio.se_stop
File.open('runtime-complete.txt','w'){|file|file.write('Owned channel PCM capture finished')}
sleep(0.3)
