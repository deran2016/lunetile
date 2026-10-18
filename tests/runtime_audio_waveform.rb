# Identical Ruby 1.8/4 source; no keyboard injection and no microphone capture.
format,pitch=File.read('audio-case.txt').split(',')
raise 'Invalid owned audio fixture' unless ['wav','mid','sequence','compressed'].include?(format) && ['50','100','150'].include?(pitch)
pitch=pitch.to_i
sequence=['sequence','compressed'].include?(format)
phases=[]
if format=='compressed'
 ['ogg','mp3','wma'].each { |kind| [50,100,150].each { |rate| phases << [kind,rate] } }
elsif sequence
 phases=[['wav',50],['wav',100],['wav',150],['mid',50],['mid',100],['mid',150]]
else
 phases=[[format,pitch]]
end
Graphics.update if format=='mid' || sequence
File.open('game-ready.txt','w'){|file|file.write('Initial MIDI frame dispatched')}
deadline=Time.now.to_f+30
until File.exist?('capture-ready.txt')
 raise 'Process audio capture did not start' if Time.now.to_f>deadline
 sleep(0.02)
end
sleep(0.3)
File.open('audio-stages.csv','w') do |file|
 file.sync=true;file.puts('format,pitch,start,played,end')
 phases.each do |format,pitch|
   started=Time.now.to_f
   File.open('audio-current.txt','w'){|current|current.write([format,pitch,started].join(','))}
   if format=='mid'
    Audio.bgm_play('Data/sustain.mid',100,pitch)
    played=Time.now.to_f
    # BGM is the original engine's supported MIDI path; include multiple loop boundaries.
    216.times{Graphics.update}
    Audio.bgm_stop
   else
    Audio.se_play('Data/sustain.'+format,100,pitch)
    played=Time.now.to_f
    if sequence
     112.times{Graphics.update}
    else
     sleep(2.8)
    end
    Audio.se_stop
   end
   file.puts([format,pitch,started,played,Time.now.to_f].join(','))
   12.times{Graphics.update} if sequence
 end
end
File.open('runtime-complete.txt','w'){|file|file.write('Owned tone and MIDI output capture finished')}
sleep(0.3)
