# The harness supplies owned Theora/Vorbis movies in MOVIE_PATHS.
Graphics.update
MOVIE_PATHS.each do |path|
  started = Process.clock_gettime(Process::CLOCK_MONOTONIC)
  Graphics.__play_movie(path)
  elapsed = Process.clock_gettime(Process::CLOCK_MONOTONIC) - started
  raise "Movie returned without playback: #{elapsed}" if elapsed < 0.5
  Graphics.update
end
BAD_MOVIE_PATHS.each do |path|
  begin
    Graphics.__play_movie(path)
    raise "Bad movie was silently accepted: #{path}"
  rescue RGSSError
  end
end
File.write('runtime-complete.txt', 'Theora/Vorbis and silent video playback; missing/corrupt/truncated rejection passed')
