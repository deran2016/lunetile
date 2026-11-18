module RGSSXP
  # Ruby 1.8 accepted `recv.meth (a, b)` with a warning; Ruby 4 rejects it.
  # Only lines the parser reports as failing are touched, and only when the
  # repaired source then compiles. Script data on disk is never changed.
  module LegacySyntax
    ROUNDS = 8
    KEYWORDS = %w[if elsif unless while until and or not when in return case then do def].freeze
    CALL = /([A-Za-z0-9_][?!]?)([ \t]+)\(/

    def self.compile(source, name)
      RubyVM::InstructionSequence.compile(source, name)
      nil
    rescue SyntaxError => error
      error
    end

    # Returns [repaired_source, edits] or nil when no bounded repair compiles.
    def self.repair(source, name, error = compile(source, name))
      return nil unless error
      lines = source.split(/(?<=\n)/)
      edits = []
      ROUNDS.times do
        failing = error.message.scan(/^>\s*(\d+) \|/).flatten.map(&:to_i).uniq
        changed = false
        failing.each do |number|
          line = lines[number - 1] or next
          fixed = repair_line(line)
          next if fixed == line
          edits << {line: number, before: line.chomp, after: fixed.chomp}
          lines[number - 1] = fixed
          changed = true
        end
        return nil unless changed
        error = compile(lines.join, name)
        return [lines.join, edits] unless error
      end
      nil
    end

    def self.repair_line(line)
      code = code_mask(line)
      result = line.dup
      # Right to left keeps earlier offsets valid.
      matches = []
      line.scan(CALL) { matches << Regexp.last_match }
      matches.reverse_each do |match|
        word_start = match.begin(1)
        word_start -= 1 while word_start > 0 && line[word_start - 1] =~ /[A-Za-z0-9_]/
        word = line[word_start...match.end(1)]
        next if KEYWORDS.include?(word) || word =~ /\A\d/
        next unless (match.begin(1)...match.end(0)).all? { |i| code[i] }
        open = match.end(0) - 1
        next unless top_level_comma?(line, code, open)
        result[match.begin(2)...match.end(2)] = ''
      end
      result
    end

    # true for characters outside string literals and comments on this line.
    def self.code_mask(line)
      mask = Array.new(line.length, true)
      quote = nil
      escaped = false
      line.each_char.with_index do |char, index|
        if quote
          mask[index] = false
          if escaped then escaped = false
          elsif char == '\\' then escaped = true
          elsif char == quote then quote = nil
          end
        elsif char == '"' || char == "'"
          quote = char
          mask[index] = false
        elsif char == '#'
          index.upto(line.length - 1) { |i| mask[i] = false }
          break
        end
      end
      mask
    end

    def self.top_level_comma?(line, code, open)
      depth = 0
      (open...line.length).each do |index|
        next unless code[index]
        case line[index]
        when '(', '[', '{' then depth += 1
        when ')', ']', '}'
          depth -= 1
          return false if depth.zero?
        when ','
          return true if depth == 1
        end
      end
      false
    end
  end
  # Reports custom scripts that bypass stock-only widescreen/stock120 source adaptations.
  module ScriptAudit
    STOCK_NAMES = [
      'Game_Temp', 'Game_System', 'Game_Switches', 'Game_Variables', 'Game_SelfSwitches', 'Game_Screen',
      'Game_Picture', 'Game_Battler 1', 'Game_Battler 2', 'Game_Battler 3', 'Game_BattleAction', 'Game_Actor',
      'Game_Enemy', 'Game_Actors', 'Game_Party', 'Game_Troop', 'Game_Map', 'Game_CommonEvent',
      'Game_Character 1', 'Game_Character 2', 'Game_Character 3', 'Game_Event', 'Game_Player',
      'Sprite_Character', 'Sprite_Battler', 'Sprite_Picture', 'Sprite_Timer', 'Spriteset_Map',
      'Spriteset_Battle', 'Window_Base', 'Window_Selectable', 'Window_Command', 'Window_Help', 'Window_Gold',
      'Window_PlayTime', 'Window_Steps', 'Window_MenuStatus', 'Window_Item', 'Window_Skill',
      'Window_SkillStatus', 'Window_Target', 'Window_EquipLeft', 'Window_EquipRight', 'Window_EquipItem',
      'Window_Status', 'Window_SaveFile', 'Window_ShopCommand', 'Window_ShopBuy', 'Window_ShopSell',
      'Window_ShopNumber', 'Window_ShopStatus', 'Window_NameEdit', 'Window_NameInput', 'Window_InputNumber',
      'Window_Message', 'Window_PartyCommand', 'Window_BattleStatus', 'Window_BattleResult',
      'Window_DebugLeft', 'Window_DebugRight', 'Arrow_Base', 'Arrow_Enemy', 'Arrow_Actor', 'Interpreter 1',
      'Interpreter 2', 'Interpreter 3', 'Interpreter 4', 'Interpreter 5', 'Interpreter 6', 'Interpreter 7',
      'Scene_Title', 'Scene_Map', 'Scene_Menu', 'Scene_Item', 'Scene_Skill', 'Scene_Equip', 'Scene_Status',
      'Scene_File', 'Scene_Save', 'Scene_Load', 'Scene_End', 'Scene_Battle 1', 'Scene_Battle 2',
      'Scene_Battle 3', 'Scene_Battle 4', 'Scene_Shop', 'Scene_Name', 'Scene_Gameover', 'Scene_Debug', 'Main'
    ].freeze
    # Stock methods changed by scripts/widescreen.py and scripts/high_refresh.py (see tests/test_custom_scripts.py).
    ADAPTED = {
      widescreen: {
        'Game_Actor' => %w[screen_x screen_y],
        'Game_Enemy' => %w[screen_x screen_y],
        'Game_Map' => %w[scroll_down scroll_right],
        'Game_Player' => %w[center update],
        'Scene_Battle' => %w[main phase3_setup_command_window],
        'Scene_Debug' => %w[main],
        'Scene_End' => %w[main],
        'Scene_Gameover' => %w[main],
        'Scene_Item' => %w[update_item],
        'Scene_Load' => %w[on_decision],
        'Scene_Menu' => %w[main],
        'Scene_Shop' => %w[main],
        'Scene_Skill' => %w[update_skill],
        'Scene_Title' => %w[main],
        'Sprite_Timer' => %w[initialize],
        'Spriteset_Battle' => %w[initialize update],
        'Spriteset_Map' => %w[initialize],
        'Window_BattleResult' => %w[initialize],
        'Window_BattleStatus' => %w[initialize refresh],
        'Window_DebugLeft' => %w[initialize],
        'Window_DebugRight' => %w[initialize],
        'Window_EquipItem' => %w[draw_item initialize],
        'Window_EquipRight' => %w[initialize],
        'Window_Help' => %w[initialize],
        'Window_Item' => %w[draw_item initialize],
        'Window_MenuStatus' => %w[initialize refresh update_cursor_rect],
        'Window_Message' => %w[initialize refresh reset_window],
        'Window_NameEdit' => %w[initialize refresh],
        'Window_NameInput' => %w[initialize refresh update_cursor_rect],
        'Window_PartyCommand' => %w[draw_item initialize],
        'Window_SaveFile' => %w[initialize],
        'Window_ShopBuy' => %w[initialize],
        'Window_ShopCommand' => %w[draw_item initialize],
        'Window_ShopNumber' => %w[initialize],
        'Window_ShopSell' => %w[draw_item initialize],
        'Window_ShopStatus' => %w[initialize],
        'Window_Skill' => %w[draw_item initialize],
        'Window_SkillStatus' => %w[initialize],
        'Window_Status' => %w[initialize refresh],
        'Window_Target' => %w[initialize]
      }.freeze,
      stock120: {
        'Arrow_Base' => %w[update],
        'Game_Character' => %w[jump move_type_custom screen_y update update_jump update_move],
        'Game_CommonEvent' => %w[update],
        'Game_Event' => %w[refresh update],
        'Game_Map' => %w[start_fog_opacity_change start_fog_tone_change update],
        'Game_Picture' => %w[move start_tone_change update],
        'Game_Screen' => %w[start_flash start_shake start_tone_change update weather],
        'Interpreter' => %w[command_106 setup_starting_event update],
        'Scene_Battle' => %w[start_phase5 update update_phase4_step4],
        'Scene_Load' => %w[read_save_data],
        'Scene_Menu' => %w[main],
        'Sprite_Battler' => %w[update],
        'Window_Message' => %w[update],
        'Window_SaveFile' => %w[initialize]
      }.freeze
    }.freeze
    LIMIT = 40

    def self.custom?(name)
      !STOCK_NAMES.include?(name)
    end

    def self.profiles
      return [] if defined?(LunetileVXA)
      result = []
      result << :widescreen if Graphics.width != 640 || Graphics.height != 480
      result << :stock120 if RGSSXP::Timing.scale != 1
      result
    rescue StandardError
      []
    end

    def self.adapted?(profile, name, method)
      ADAPTED[profile].fetch(name, []).include?(method.to_s)
    end

    # Method owners before the first custom script ran.
    def self.snapshot
      table = {}
      return table if profiles.empty?
      (ADAPTED[:widescreen].keys | ADAPTED[:stock120].keys).each do |name|
        next unless Object.const_defined?(name, false)
        klass = Object.const_get(name, false)
        next unless klass.is_a?(Class)
        (klass.instance_methods(false) + klass.private_instance_methods(false)).each do |method|
          next unless profiles.any? { |profile| adapted?(profile, name, method) }
          table[[name, method]] = klass.instance_method(method).source_location
        end
      end
      table
    end

    def self.report(before, custom_names)
      active = profiles
      return [] if active.empty? || custom_names.empty?
      lines = []
      lines << "Lunetile: custom scripts run under #{active.join('+')}: #{custom_names.join(', ')}; their frame counters and 640x480 coordinates are not adapted"
      before.each do |(name, method), original|
        next unless original && (klass = Object.const_get(name, false) rescue nil)
        location = (klass.instance_method(method).source_location rescue nil)
        next if location.nil? || location == original
        next unless custom?(location.first.sub(/\A\d+:/, ''))
        # An alias that still reaches the adapted stock body means the script wraps it.
        methods = klass.instance_methods(false) + klass.private_instance_methods(false)
        next if methods.any? { |other| other != method && (klass.instance_method(other).source_location rescue nil) == original }
        adapted = active.select { |profile| adapted?(profile, name, method) }
        next if adapted.empty?
        lines << "Lunetile: script #{location.first} overrides #{name}##{method}; #{adapted.join('+')} adaptation of the stock method is not applied"
        break if lines.size > LIMIT
      end
      lines
    end
  end
end
