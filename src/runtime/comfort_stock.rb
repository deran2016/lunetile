module Lunetile
  module Comfort
    PATH = 'Saves/Lunetile/comfort.json'
    class << self
      attr_reader :error
      def installed?; !!@installed; end
      def vxa?; defined?(DataManager) && defined?(LunetileVXA); end
      def root; vxa? ? LunetileVXA::SAVE_ROOT : RGSSXP::Saves::ROOT; end
      def auto_path; File.join(root, vxa? ? 'Autosave.rvdata2' : 'Autosave.rxdata'); end
      def enabled?; @enabled != false; end
      def enabled=(value)
        raise ArgumentError, 'Autosave setting must be boolean' unless [true,false].include?(value)
        SaveFiles.replace(PATH, JSON.generate({'version'=>1, 'autosave'=>value}))
        @enabled = value
        request if value
      end
      def request
        @pending_at = Process.clock_gettime(Process::CLOCK_MONOTONIC)
        @next_attempt_at = 0
      end
      def validate_xp(stream)
        position = stream.pos
        values = 12.times.map { Marshal.load(stream) }
        types = [Array,Integer,Game_System,Game_Switches,Game_Variables,Game_SelfSwitches,
                 Game_Screen,Game_Actors,Game_Party,Game_Troop,Game_Map,Game_Player]
        raise ArgumentError, 'Invalid XP save objects' unless types.zip(values).all? { |type,value| value.is_a?(type) }
        raise ArgumentError, 'Invalid XP save metadata' unless values[1] >= 0 && values[0].all? { |v| v.is_a?(Array) && v.size == 2 && v[0].is_a?(String) && v[1].is_a?(Numeric) }
        raise ArgumentError, 'Trailing XP save data' unless stream.eof?
        values
      ensure
        stream.pos = position if position
      end
      def decode_xp(bytes)
        header = bytes.byteslice(0, RGSSXP::Saves::MAGIC.bytesize)
        raise IOError, 'Invalid XP save header' unless [RGSSXP::Saves::MAGIC, RGSSXP::Saves::HIGH_MAGIC].include?(header)
        rate = header == RGSSXP::Saves::HIGH_MAGIC ? 120 : 40
        raise IOError, 'This save requires stock120' if rate == 120 && RGSSXP::Timing.scale != 3
        stream = RGSSXP::Saves::ReadStream.new(bytes, Time.now)
        stream.pos = header.bytesize
        stream.timing_rate = rate
        validate_xp(stream)
        stream
      rescue Exception
        stream&.close
        raise
      end
      def validate(bytes)
        if vxa?
          LunetileVXA.decode(bytes)
        else
          stream = decode_xp(bytes)
          stream.close
        end
        true
      end
      def safe?(scene)
        return false unless enabled? && $game_system && !$game_system.save_disabled && $game_player && $game_map
        return false if $game_player.moving? || $game_player.jumping? || $game_player.move_route_forcing
        common = $game_map.instance_variable_get(:@common_events)
        events = $game_map.events.values + (common.is_a?(Hash) ? common.values : Array(common))
        return false if events.any? { |event| event.instance_variable_get(:@interpreter)&.running? }
        if vxa?
          SceneManager.scene.equal?(scene) && !$game_party.in_battle && !$game_map.interpreter.running? &&
            !$game_message.busy? && !$game_player.transfer? && !$game_temp.common_event_reserved?
        else
          $scene.equal?(scene) && !$game_temp.in_battle && !$game_system.map_interpreter.running? &&
            !$game_temp.message_window_showing && !$game_temp.player_transferring && $game_temp.common_event_id == 0 &&
            !$game_temp.battle_calling && !$game_temp.gameover
        end
      end
      def update(scene)
        return unless @pending_at
        now = Process.clock_gettime(Process::CLOCK_MONOTONIC)
        return if now - @pending_at < 1.0 || now < (@next_attempt_at || 0)
        @next_attempt_at = now + 0.25
        return unless safe?(scene)
        @pending_at = nil
        save_auto
      rescue StandardError => failure
        @error = "자동 저장 실패 (#{failure.class}). 수동 저장을 사용하세요."
      end
      def save_auto
        if vxa?
          $game_system.on_before_save
          bytes = LunetileVXA::SAVE_MAGIC + [Graphics.frame_rate].pack('V') + Marshal.dump(DataManager.make_save_header) + Marshal.dump(DataManager.make_save_contents)
        else
          stream = StringIO.new(''.b)
          stream.write(RGSSXP::Timing.scale == 3 ? RGSSXP::Saves::HIGH_MAGIC : RGSSXP::Saves::MAGIC)
          Scene_Save.allocate.write_save_data(stream)
          bytes = stream.string
          stream.close
        end
        SaveFiles.write(auto_path, bytes) { |data| validate(data) }
        @error = nil
        true
      end
      def candidates
        result = [[auto_path, '자동 저장 · 최신']]
        1.upto(3) { |n| result << [auto_path + ".bak#{n}", "자동 저장 · 백업 #{n}"] }
        (vxa? ? 16 : 4).times do |index|
          path = vxa? ? LunetileVXA.slot(index,true) : RGSSXP::Saves.filename(index,:write)
          1.upto(3) { |n| result << [path + ".bak#{n}", "수동 #{index+1} · 백업 #{n}"] }
        end
        result.select { |path,_| File.file?(path) }.sort_by { |path,_| -File.mtime(path).to_f }
      end
      def load(path)
        raise ArgumentError, 'Unknown recovery save' unless candidates.any? { |name,_| name == path }
        bytes = SaveFiles.read(path)
        validate(bytes)
        stream = nil
        transaction do
        if vxa?
          _,contents,rate = LunetileVXA.decode(bytes)
          if rate != Graphics.frame_rate
            system,timer = contents[:system],contents[:timer]
            frames = system.instance_variable_get(:@frames_on_save)
            system.instance_variable_set(:@frames_on_save, frames*Graphics.frame_rate/rate) if frames
            count = timer.instance_variable_get(:@count)
            timer.instance_variable_set(:@count, count*Graphics.frame_rate/rate) if count
          end
          DataManager.extract_save_contents(contents)
          DataManager.reload_map_if_updated
          $game_system.on_after_load
          SceneManager.goto(Scene_Map)
          SceneManager.clear
        else
          stream = decode_xp(bytes)
          $game_temp = Game_Temp.new
          Scene_Load.allocate.read_save_data(stream)
          RGSSXP.restore_game_compatibility
          stream.close
          $game_system.bgm_play($game_system.playing_bgm)
          $game_system.bgs_play($game_system.playing_bgs)
          $scene = Scene_Map.new
        end
        # Loading a backup must not immediately overwrite the autosave it came from.
        @pending_at = nil
        true
        end
      ensure
        stream&.close unless stream&.closed?
      end
      def transaction
        state = [$game_temp,$game_system,$game_timer,$game_message,$game_switches,$game_variables,
                 $game_self_switches,$game_screen,$game_actors,$game_party,$game_troop,$game_map,$game_player]
        frame = Graphics.frame_count
        yield
      rescue StandardError
        $game_temp,$game_system,$game_timer,$game_message,$game_switches,$game_variables,
          $game_self_switches,$game_screen,$game_actors,$game_party,$game_troop,$game_map,$game_player = state
        Graphics.frame_count = frame
        raise
      end
      def open(origin)
        Scene.instance_variable_set(:@origin, origin)
        vxa? ? SceneManager.call(Scene) : $scene = Scene.new
      end
      def install
        return if installed?
        raise 'Reviewed stock scripts are required' unless defined?(Scene_Map) && defined?(Scene_Menu) && defined?(Game_Actor)
        raise 'Reconvert this VX Ace project with the current converter before installing comfort menus' if vxa? && !LunetileVXA.respond_to?(:decode)
        if vxa?
          Window_MenuCommand.prepend(VXAMenuCommand)
          Scene_Menu.prepend(VXAMenu)
          Window_TitleCommand.prepend(VXATitleCommand)
          Scene_Title.prepend(VXATitle)
          BattleManager.singleton_class.prepend(BattleResult)
        else
          Window_Command.prepend(XPCommands)
          Scene_Menu.prepend(XPMenu)
          Scene_Title.prepend(XPTitle)
          Scene_Battle.prepend(BattleResult)
          Scene_Load.prepend(XPLoad)
          Window_SaveFile.prepend(XPPreview)
        end
        Game_Map.prepend(MapSetup)
        Scene_Map.prepend(MapUpdate)
        Game_Actor.prepend(HitRumble)
        @installed = true
        if File.file?(PATH)
          raise ArgumentError, 'Comfort settings exceed 4 KiB' if File.size(PATH) > 4096
          value = JSON.parse(File.binread(PATH), create_additions:false, max_nesting:4)
          raise ArgumentError, 'Invalid comfort settings' unless value.is_a?(Hash) && value.keys.sort == %w[autosave version] && value['version'] == 1 && [true,false].include?(value['autosave'])
          @enabled = value['autosave']
        end
      rescue StandardError => failure
        raise unless @installed
        @error = "자동 저장 설정을 읽지 못해 기본값을 사용합니다 (#{failure.class})"
      end
    end
    module MapSetup
      def setup(*args)
        result = super
        Comfort.request
        result
      end
    end
    module MapUpdate
      def update
        result = super
        Comfort.update(self)
        result
      end
    end
    module BattleResult
      def battle_end(result)
        value = super
        Comfort.request if result != 2
        value
      end
    end
    module HitRumble
      def hp=(value)
        old = hp
        result = super
        in_battle = Comfort.vxa? ? $game_party&.in_battle : $game_temp&.in_battle
        Controls.rumble if hp < old && in_battle
        result
      end
    end
    module XPLoad
      def read_save_data(file)
        Comfort.validate_xp(file)
        Comfort.transaction { super }
      end
      def on_decision(filename)
        super
      rescue StandardError
        Comfort.instance_variable_set(:@error,'저장을 불러오지 못했습니다. 자동 저장 / 백업 불러오기를 사용하세요.')
        Scene.instance_variable_set(:@origin,:title)
        $scene = Scene.new
      end
    end
    module XPPreview
      def initialize(*args)
        super
      rescue StandardError
        @file_exist = false
        @selected = false
        @name_width = 180
        contents.clear
        contents.draw_text(4,0,contents.width-8,32,'손상된 저장 · 조작/저장 메뉴에서 복구')
      end
    end
    module XPCommands
      def initialize(width, commands)
        if $scene.is_a?(Scene_Menu) || $scene.is_a?(Scene_Title)
          @lunetile_index = commands.size
          commands = commands + ['조작·저장']
        end
        super(width,commands)
      end
    end
    module XPMenu
      def update_command
        if @command_window.index == @command_window.instance_variable_get(:@lunetile_index) && Input.trigger?(Input::C) && !Input.trigger?(Input::B)
          Comfort.open(:menu)
        else
          super
        end
      end
    end
    module XPTitle
      def update
        if @command_window.index == @command_window.instance_variable_get(:@lunetile_index) && Input.trigger?(Input::C)
          Comfort.open(:title)
        else
          super
        end
      end
    end
    module VXAMenuCommand
      def add_original_commands
        super
        add_command('조작·저장',:lunetile_comfort)
      end
    end
    module VXAMenu
      def create_command_window
        super
        @command_window.set_handler(:lunetile_comfort,proc { Comfort.open(:menu) })
      end
    end
    module VXATitleCommand
      def make_command_list
        super
        add_command('조작·저장',:lunetile_comfort)
      end
    end
    module VXATitle
      def create_command_window
        super
        @command_window.set_handler(:lunetile_comfort,proc { close_command_window; Comfort.open(:title) })
      end
    end
  end
  def self.install_stock
    Comfort.install
  end
end
