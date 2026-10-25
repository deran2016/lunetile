# Installed only by the reviewed template packagers, after stock compatibility.
module Lunetile
  module StockScripts
    VERSION = 1 unless const_defined?(:VERSION, false)
    ORIGINALS = {} unless const_defined?(:ORIGINALS, false)
    EXPECTED = {} unless const_defined?(:EXPECTED, false)
    EMPTY = [].freeze unless const_defined?(:EMPTY, false)

    def self.enabled?; !@disabled; end
    def self.invalidate
      @map = @source = nil
      @records = {}.compare_by_identity
      @by_x = {}
      @valid = false
      @occupied = 0
      @invalidations = (@invalidations || 0) + 1
    end
    def self.disable!
      @disabled = true
      invalidate
    end
    def self.setup_begin
      @setup_depth = (@setup_depth || 0) + 1
      invalidate
    end
    def self.setup_end
      @setup_depth -= 1
      invalidate
    end
    def self.install(klass, name, key, source)
      current = klass.instance_method(name)
      return if current == EXPECTED[key]
      ORIGINALS[key] = current
      klass.class_eval(source, '(Lunetile stock scripts)', 1)
      EXPECTED[key] = klass.instance_method(name)
    end
    def self.candidates(map, x, y)
      return unless enabled? && !(@setup_depth && @setup_depth > 0) && map.equal?($game_map)
      return unless x.instance_of?(Integer) && y.instance_of?(Integer)
      events = map.events
      return unless events.instance_of?(Hash) ||
        (defined?(RGSSXP::IntegerMap) && events.instance_of?(RGSSXP::IntegerMap))
      return if events.size < 32
      unless @map.equal?(map) && @source.equal?(events) && @size == events.size
        invalidate
        @map, @source, @size = map, events, events.size
        @valid = true
        rank = 0
        events.each_value do |event|
          unless event.instance_of?(Game_Event) && event.x.instance_of?(Integer) &&
              event.y.instance_of?(Integer) && !@records.key?(event)
            @valid = false
            break
          end
          x0, y0 = event.x, event.y
          column = (@by_x[x0] ||= {})
          unless column.key?(y0)
            column[y0] = []
            @occupied += 1
          end
          column[y0] << event
          @records[event] = [x0, y0, rank]
          rank += 1
        end
        @builds = (@builds || 0) + 1
        unless @valid
          @records.clear
          @by_x.clear
          @occupied = 0
        end
      end
      return unless @valid
      @queries = (@queries || 0) + 1
      column = @by_x[x]
      column && column[y] || EMPTY
    end
    def self.moved(event)
      return unless enabled? && @valid && (record = @records[event])
      x, y = event.x, event.y
      return if record[0] == x && record[1] == y
      unless x.instance_of?(Integer) && y.instance_of?(Integer)
        disable!
        return
      end
      column = @by_x[record[0]]
      previous = column[record[1]]
      previous.delete(event)
      if previous.empty?
        column.delete(record[1])
        @occupied -= 1
        @by_x.delete(record[0]) if column.empty?
      end
      column = (@by_x[x] ||= {})
      bucket = column[y]
      unless bucket
        bucket = column[y] = []
        @occupied += 1
      end
      index = bucket.bsearch_index { |other| @records[other][2] > record[2] }
      index ? bucket.insert(index, event) : bucket.push(event)
      record[0], record[1] = x, y
      @moves = (@moves || 0) + 1
      nil
    end
    def self.stats
      {enabled:enabled?, active:!!(@map && @valid), events:@records.size,
       occupied:@occupied, queries:@queries || 0, builds:@builds || 0,
       moves:@moves || 0, invalidations:@invalidations || 0}
    end
    invalidate
  end
end
