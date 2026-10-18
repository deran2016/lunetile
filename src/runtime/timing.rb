module RGSSXP::Timing
  def self.scale
    Graphics.__stock120 ? 3 : 1
  end
  def self.legacy_tick?
    Graphics.frame_count % scale == 0
  end
  def self.frames(count)
    count * scale
  end
  def self.step_distance(object, key, units)
    total = units + (object.instance_variable_get(key) || 0)
    distance, remainder = total.divmod(3)
    object.instance_variable_set(key, remainder)
    distance
  end
  def self.settings_path
    'Saves/Lunetile/display.ini'
  end
  def self.load_settings
    return unless scale == 3 && File.file?(settings_path)
    text = File.binread(settings_path)
    match = text.match(/\A\[Display\]\r?\nRenderRate=(40|60|120)\r?\n?\z/)
    Graphics.render_rate = match[1].to_i if match
  rescue SystemCallError, IOError
    # An unavailable personal settings file leaves the packaged default active.
  end
  def self.save_settings(rate)
    raise ArgumentError, 'Unsupported display rate' unless scale == 3 && [40,60,120].include?(rate)
    Dir.mkdir('Saves') unless Dir.exist?('Saves')
    Dir.mkdir('Saves/Lunetile') unless Dir.exist?('Saves/Lunetile')
    temporary = settings_path + ".tmp-#{Process.pid}"
    begin
      File.open(temporary, 'wbx') do |file|
        file.write("[Display]\nRenderRate=#{rate}\n")
        file.flush
        file.fsync
      end
      File.rename(temporary, settings_path)
      Graphics.render_rate = rate
    ensure
      File.delete(temporary) if File.file?(temporary)
    end
  end
end
