module Audio
  EXTENSIONS = %w[.ogg .wav .mp3 .wma .mid .midi].freeze
  class << self
    %i[bgm bgs me se].each_with_index do |name, channel|
      define_method("#{name}_play") do |filename, volume = 100, pitch = 100|
        filename = RGSSXP.text(filename)
        volume = [[volume.to_int, 0].max, 100].min
        pitch = [[pitch.to_int, 50].max, 150].min
        __play(channel, filename.tr('\\', '/').downcase, RGSSXP.read_file(filename, EXTENSIONS), volume, pitch)
      end
      define_method("#{name}_stop") { __stop(channel) }
      define_method("#{name}_fade") { |time| __fade(channel, [time.to_int, 0].max) } if channel < 3
    end
    def __voices
      __snapshot.lines.map do |line|
        kind, queued, samples, duration, channels, rate, volume, pitch, paused, fading, decoder, linear_gain, output_frequency = line.chomp.split(',')
        {channel: kind.to_i, queued: queued.to_i, samples: samples.to_i,
         duration_us: duration.to_i, channels: channels.to_i, sample_rate: rate.to_i,
         volume: volume.to_f, pitch: pitch.to_f, paused: paused == '1', fading: fading == '1', decoder: decoder,
         linear_gain: linear_gain && !linear_gain.empty? ? linear_gain.to_f : nil,
         output_frequency: output_frequency.to_i}
      end
    end
  end
end
