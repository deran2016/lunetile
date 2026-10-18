# Identical Ruby 1.8/4 source; generated WMA only, actual PCM acquisition is PID-scoped.
Graphics.update
File.open('game-ready.txt','w') { |file| file.write('Owned WMA role fixture ready') }
deadline=Time.now.to_f+30
until File.exist?('capture-ready.txt')
 raise 'Process audio capture did not start' if Time.now.to_f>deadline
 sleep(0.02)
end
sleep(0.3)
File.open('wma-roles.csv','w') do |file|
 file.sync=true;file.puts('role,pitch,start,played,end')
 ['bgm','bgs','me','se'].each do |role|
  [50,100,150].each do |pitch|
   started=Time.now.to_f
   Audio.send(role+'_play','Data/sustain.wma',100,pitch)
   played=Time.now.to_f
   64.times { Graphics.update }
   Audio.send(role+'_stop')
   file.puts([role,pitch,started,played,Time.now.to_f].join(','))
   8.times { Graphics.update }
  end
 end
end
File.open('runtime-complete.txt','w') { |file| file.write('Owned WMA role pitch probe finished') }
sleep(0.3)
