def verify(condition, message)
  raise message unless condition
end
def voices(channel)
  Audio.__voices.select { |voice| voice[:channel] == channel }
end
def delay(seconds)
  sleep(seconds)
end
def stage(name)
  File.open('audio-stages.txt','a') { |file| file.puts(name) }
end
stage('WAV')
%i[bgm bgs me se].each do |kind|
  ['', nil, 123].each do |invalid|
    begin
      Audio.public_send("#{kind}_play", invalid)
      raise 'Invalid filename accepted'
    rescue Errno::ENOENT
      verify(invalid == '', 'Wrong missing-file failure')
    rescue TypeError
      verify(invalid != '', 'Empty filename reported as a type error')
    end
  end
end
Audio.bgm_play('Data/tone.wav', 20, 100)
delay(0.08)
first = voices(0).first
verify(first && first[:samples] > 0 && first[:decoder] == 'wav', 'WAV did not reach XAudio2')
Audio.bgm_play('Data/tone.wav', 30, 100)
second = voices(0).first
verify(second[:samples] >= first[:samples], 'Same BGM/pitch restarted on a volume change')
Audio.bgm_play('Data/tone.wav', 30, 150)
third = voices(0).first
verify(third[:samples] < second[:samples] && third[:pitch] == 1.5, 'Changed BGM pitch did not restart')
%w[wav ogg mp3 wma].each do |format|
  {0=>-10000,1=>-3465,25=>-2625,50=>-1750,75=>-875,100=>0}.each do |volume, decibels|
    Audio.bgm_play('Data/tone.'+format, volume, 150)
    actual = voices(0).first[:linear_gain]
    expected = volume == 0 ? 0 : 10.0 ** (decibels/2000.0)
    verify((actual-expected).abs < 0.00001, "Original dB volume law mismatch for #{format} at #{volume}: #{actual}")
  end
end
Audio.bgm_play('Data/tone.wav', 30, 150)
stage('Vorbis')
Audio.bgs_play('Data/tone.ogg', 20, 100)
delay(0.08)
verify(voices(1).first[:decoder] == 'vorbis', 'Vorbis decoder was not used')
stage('ME')
Audio.me_play('Data/short.wav', 20, 100)
delay(0.03)
paused = voices(0).first
verify(paused[:paused], 'ME did not pause BGM')
delay(0.04)
verify(voices(0).first[:samples] == paused[:samples], 'Paused BGM advanced')
delay(0.16)
verify(voices(2).empty? && !voices(0).first[:paused], 'ME did not finish/resume BGM')
stage('MP3/WMA')
Audio.se_play('Data/tone.mp3', 15, 50)
Audio.se_play('Data/tone.wma', 15, 150)
delay(0.05)
effects = voices(3)
verify(effects.size == 2 && effects.all? { |voice| voice[:samples] > 0 && voice[:decoder] == 'media-foundation' }, 'MP3/WMA overlapping voices failed')
Audio.se_stop
verify(voices(3).empty?, 'SE stop did not release all voices')
stage('fade')
Audio.bgm_fade(160)
delay(0.07)
verify(voices(0).first[:volume] < 0.3, 'Fade gain did not decrease')
delay(0.15)
verify(voices(0).empty?, 'Fade did not release BGM')
delay(1.0)
verify(voices(1).first[:samples] > 11025, 'BGS did not loop past its end')
Audio.bgs_stop
stage('MIDI')
Audio.bgm_play('Data/tone.mid', 20, 100)
delay(0.05)
verify(voices(0).first[:decoder] == 'windows-midi-port' && voices(0).first[:samples] > 0, 'MIDI events did not play')
{50=>22050,100=>44100,150=>66150}.each do |pitch, frequency|
  Audio.bgm_play('Data/tone.mid', 50, pitch)
  verify(voices(0).first[:output_frequency] == frequency, 'MIDI output buffer frequency mismatch')
end
[0,1,25,50,75,100].each do |volume|
  Audio.bgm_play('Data/tone.mid', volume, 100)
  verify(voices(0).first[:linear_gain].nil?, 'AudioPath gain must not be reported as a buffer gain measurement')
end
Audio.me_play('Data/tone.mid', 10, 100)
delay(0.08)
verify(voices(0).first[:paused] && voices(2).first[:samples] > 0, 'Independent MIDI ME did not pause BGM')
Audio.me_stop
verify(!voices(0).first[:paused], 'MIDI BGM did not restore after ME')
delay(1.05)
verify(!voices(0).empty?, 'MIDI BGM did not loop')
Audio.bgm_stop
stage('independent MIDI percussion')
Audio.bgm_play('Data/drums.mid', 20, 50)
Audio.bgs_play('Data/drums.mid', 30, 100)
Audio.se_play('Data/drums.mid', 40, 150)
delay(0.05)
[0,1,3].zip([22050,44100,66150]).each do |channel, frequency|
  voice = voices(channel).first
  verify(voice && voice[:samples] > 0 && voice[:output_frequency] == frequency, 'MIDI percussion outputs interfered')
end
Audio.bgm_stop
Audio.bgs_stop
Audio.se_stop
%w[bad.wav bad.ogg bad.mid bad.mp3].each do |name|
  stage(name)
  begin
    Audio.se_play('Data/' + name)
    raise 'Invalid audio accepted: ' + name
  rescue RGSSError
  end
end
verify(Audio.__voices.empty?, 'Audio voices leaked after stop/end/errors')
File.write('audio-verified.txt', 'WAV/Vorbis/MP3/WMA/MIDI progression, overlap, pitch, fade, ME pause/resume, loops, corrupt-file rejection')
File.write('runtime-complete.txt', 'audio,false,false')
sleep 0.5
