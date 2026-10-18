module RGSSXP
  DATA_ENCODING = 'UTF-8' unless const_defined?(:DATA_ENCODING, false)
  SOURCE_ENCODING = Encoding.find(DATA_ENCODING)

  def self.normalize_data(value, location = 'data', seen = {}, changes = nil)
    return value if value.nil? || value.is_a?(Numeric) || value.is_a?(Symbol) || value == true || value == false
    return value if %w[Table Color Tone Rect].include?(value.class.name)
    return seen[value.object_id] if seen.key?(value.object_id)
    if value.is_a?(String)
      return value if value.ascii_only?
      encoding = value.encoding == Encoding::BINARY ? SOURCE_ENCODING : value.encoding
      unless encoding == SOURCE_ENCODING || encoding == Encoding::UTF_8
        raise EncodingError, "#{location}: declared string encoding conflicts with project encoding"
      end
      begin
        converted = value.dup.force_encoding(encoding).encode(Encoding::UTF_8)
        raise EncodingError, 'Invalid encoded text' unless converted.valid_encoding?
      rescue EncodingError => error
        raise EncodingError, "#{location}: #{error.message}"
      end
      converted.freeze if value.frozen?
      seen[value.object_id] = converted
      if changes && (value.encoding != Encoding::UTF_8 || converted.b != value.b)
        changes << [location.dup.b, value.encoding.name.b, value.b.unpack1('H*').b, converted.b.unpack1('H*').b]
      end
      return converted
    end
    seen[value.object_id] = value
    if value.is_a?(Array)
      value.each_index { |index| value[index] = normalize_data(value[index], "#{location}[#{index}]", seen, changes) }
    elsif value.is_a?(Hash)
      rebuilt = Hash.new(value.default)
      changed = false
      value.each_pair do |key, child|
        new_key = normalize_data(key, "#{location}.key", seen, changes)
        new_value = normalize_data(child, "#{location}[#{key.inspect}]", seen, changes)
        raise EncodingError, "#{location}: decoded Hash keys collide" if rebuilt.key?(new_key)
        rebuilt[new_key] = new_value
        changed ||= !new_key.equal?(key) || !new_value.equal?(child)
      end
      Hash.instance_method(:replace).bind_call(value, rebuilt) if changed
    elsif value.class.name&.start_with?('RPG::', 'Game_')
      value.instance_variables.each do |field|
        child = value.instance_variable_get(field)
        value.instance_variable_set(field, normalize_data(child, "#{location}.#{field}", seen, changes))
      end
    end
    value
  end

  def self.restore_game_compatibility
    normalize_data([$game_system,$game_switches,$game_variables,$game_self_switches,$game_screen,
                    $game_actors,$game_party,$game_troop,$game_map,$game_player], 'save')
    restore_integer_maps
  end
end
