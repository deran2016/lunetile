module RGSSXP
  # Only stock XP integer ID tables use this Ruby 1.8 bucket order.
  class IntegerMap < Hash
    SIZES = [11,19,37,67,131,283,521,1033,2053,4099,8219,16427,32771,
             65581,131101,262147,524309,1048583].freeze
    RAW_STORE = Hash.instance_method(:[]=)
    RAW_EACH = Hash.instance_method(:each_pair)

    def self.from_original(table)
      return table if table.is_a?(self)
      raise TypeError, 'Expected an integer ID Hash' unless table.is_a?(Hash)
      raise TypeError, 'Integer ID Hash defaults are unsupported' if table.default_proc || !table.default.nil?
      result = new
      # Ruby 4 preserves the pair order in the original Marshal stream.
      RAW_EACH.bind_call(table) { |key, value| result[key] = value }
      result
    end

    def initialize
      raise ArgumentError, 'ID table defaults are unsupported' if block_given?
      super
      @bins = Array.new(SIZES.first) { [] }
      @ordered_values = nil
    end

    def check_key(key)
      raise TypeError, 'ID must be an original 32-bit Fixnum' unless key.is_a?(Integer) && key.between?(-1073741824,1073741823)
      ((key << 1) | 1) & 0xffffffff
    end
    private :check_key

    def []=(key, value)
      raise FrozenError, 'Frozen integer ID table' if frozen?
      hash = check_key(key)
      unless key?(key)
        if size / @bins.size > 5
          count = SIZES.find { |candidate| candidate > @bins.size }
          raise RangeError, 'Integer ID table exceeds supported size' unless count
          expanded = Array.new(count) { [] }
          @bins.each { |bucket| bucket.each { |id| expanded[check_key(id) % count].unshift(id) } }
          @bins = expanded
        end
        @bins[hash % @bins.size].unshift(key)
      end
      @ordered_values = nil
      super
    end
    alias store []=

    def delete(key)
      raise FrozenError, 'Frozen integer ID table' if frozen?
      hash = check_key(key)
      return block_given? ? yield(key) : nil unless key?(key)
      @bins[hash % @bins.size].delete(key)
      @ordered_values = nil
      super
    end

    def clear
      super
      @bins.each(&:clear)
      @ordered_values = nil
      self
    end

    def keys
      @bins.flatten
    end
    def values
      # Collision checks need a fresh snapshot, but unchanged ID tables need not rebuild its order.
      ordered = @ordered_values
      unless ordered
        ordered = keys.map { |key| self[key] }
        @ordered_values = ordered unless frozen?
      end
      ordered.dup
    end
    def each
      return enum_for(:each) unless block_given?
      keys.each { |key| yield(key, self[key]) if key?(key) }
      self
    end
    alias each_pair each
    def each_key
      return enum_for(:each_key) unless block_given?
      keys.each { |key| yield(key) if key?(key) }
      self
    end
    def each_value
      return enum_for(:each_value) unless block_given?
      each { |_, value| yield(value) }
      self
    end

    def initialize_copy(other)
      super
      @bins = Array.new(SIZES.first) { [] }
      @ordered_values = nil
      Hash.instance_method(:clear).bind_call(self)
      other.each { |key, value| self[key] = value }
    end

    def marshal_dump
      [1, @bins, values]
    end
    def marshal_load(payload)
      unless payload.is_a?(Array) && payload.size == 3 && payload[0] == 1 && payload[1].is_a?(Array) && SIZES.include?(payload[1].size) && payload[1].all? { |bucket| bucket.is_a?(Array) } && payload[2].is_a?(Array)
        raise TypeError, 'Invalid integer ID table save data'
      end
      bins, entries = payload[1], payload[2]
      ids = bins.flatten
      raise TypeError, 'Invalid integer ID table entries' unless ids.size == entries.size && ids.uniq.size == ids.size
      bins.each_with_index do |bucket, index|
        bucket.each { |key| raise TypeError, 'Invalid integer ID bucket' unless check_key(key) % bins.size == index }
      end
      Hash.instance_method(:clear).bind_call(self)
      ids.zip(entries) { |key, value| RAW_STORE.bind_call(self, key, value) }
      @bins = bins
      @ordered_values = nil
    end

    # shortcut: stock scripts use only the mutators above; reject other inherited mutations before they can corrupt bucket order.
    %i[merge! update replace delete_if reject! keep_if select! filter! shift rehash transform_keys! transform_values! compact! compare_by_identity default= default_proc=].each do |name|
      define_method(name) { |*| raise NotImplementedError, "Integer ID table #{name} is outside stock XP support" }
    end
  end

  def self.original_integer_keys(table)
    IntegerMap.from_original(table).keys
  end

  def self.restore_integer_maps
    pending = [$game_map, $game_actors, $game_party, $game_troop]
    seen = {}
    until pending.empty?
      object = pending.pop
      next if object.nil? || seen[object.object_id]
      seen[object.object_id] = true
      if object.is_a?(Array)
        pending.concat(object)
      elsif object.is_a?(Hash)
        object.each_value { |child| pending << child }
      elsif object.class.name.start_with?('Game_')
        fields = object.is_a?(Game_Map) ? %i[@events @common_events] : object.is_a?(Game_Battler) ? %i[@states_turn] : []
        fields.each do |field|
          value = object.instance_variable_get(field)
          object.instance_variable_set(field, IntegerMap.from_original(value)) if value
        end
        object.instance_variables.each { |field| pending << object.instance_variable_get(field) }
      end
    end
  end
end
