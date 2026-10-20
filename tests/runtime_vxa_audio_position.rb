# Run in the runtime; generate owned PCM so the test does not require RTP.
def audio_assert(condition, message)
  raise message unless condition
end
samples = Array.new(22050 * 2) { |index| (Math.sin(index * 440 * Math::PI * 2 / 22050) * 1000).to_i }.pack('s<*')
wave = 'RIFF' + [36 + samples.bytesize].pack('V') + 'WAVEfmt ' +
       [16, 1, 1, 22050, 44100, 2, 16].pack('VvvVVvv') +
       'data' + [samples.bytesize].pack('V') + samples
Audio.__play_at(0, 'owned-position.wav', wave, 0, 100, 500)
sleep 0.08
first = Audio.__position(0)
audio_assert(first.between?(500, 850), "Initial PCM offset missing: #{first}")
Audio.__play(2, 'owned-me.wav', wave, 0, 100)
sleep 0.05
paused = Audio.__position(0)
sleep 0.08
audio_assert(Audio.__position(0) == paused, 'Position advanced while ME paused BGM')
Audio.__stop(2)
sleep 0.08
audio_assert(Audio.__position(0) > paused, 'Position did not resume after ME')
Audio.__play_at(0, 'owned-position.wav', wave, 0, 100, 1200)
audio_assert(Audio.__position(0).between?(1200, 1400), 'Explicit seek did not replace same BGM')
Audio.__play_at(1, 'owned-loop.wav', wave, 0, 100, 3900)
audio_assert(Audio.__position(1).between?(1900, 1999), 'Seek beyond duration did not wrap')
sleep 0.2
audio_assert(Audio.__position(1) < 500, 'Playback position did not wrap at end')
loop_chunk = [0, 0, 0, 60, 0, 0, 0, 1, 0, 0, 0, 11025, 33074, 0, 0].pack('V*')
loop_wave = wave + 'smpl' + [loop_chunk.bytesize].pack('V') + loop_chunk
loop_wave[4, 4] = [loop_wave.bytesize - 8].pack('V')
Audio.__play_at(1, 'owned-tagged-loop.wav', loop_wave, 0, 100, 3900)
audio_assert(Audio.__position(1).between?(900, 1100), 'Seek ignored the tagged loop region')
sleep 0.7
audio_assert(Audio.__position(1).between?(500, 850), 'Position ignored the tagged loop region')
[-1, 2147483648].each do |position|
  begin
    Audio.__play_at(0, 'invalid.wav', wave, 0, 100, position)
    raise 'Invalid audio position accepted'
  rescue ArgumentError
  end
end
Audio.__stop(0)
Audio.__stop(1)
audio_assert(Audio.__position(0) == 0 && Audio.__position(1) == 0, 'Stopped position is not zero')
track = "\x00\xff\x51\x03\x07\xa1\x20\x00\xc0\x00\x00\x90\x45\x30\x87\x40\x80\x45\x00\x00\xff\x2f\x00".b
midi = 'MThd' + [6, 0, 1, 480].pack('Nnnn') + 'MTrk' + [track.bytesize].pack('N') + track
Audio.__play_at(0, 'owned-midi.mid', midi, 0, 100, 250)
sleep 0.05
audio_assert(Audio.__position(0).between?(250, 500), 'MIDI position ignored seek offset')
Audio.__play(2, 'owned-midi-pause.wav', wave, 0, 100)
sleep 0.03
paused = Audio.__position(0)
sleep 0.05
audio_assert(Audio.__position(0) == paused, 'MIDI position advanced during ME')
Audio.__stop(2)
sleep 0.05
audio_assert(Audio.__position(0) > paused, 'MIDI position did not resume')
Audio.__stop(0)
File.write('runtime-complete.txt', 'VX Ace native seek, position, looping and ME pause/resume passed')
