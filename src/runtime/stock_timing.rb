# Installed above Main only after the complete stock source collection is verified.
module RGSSXP::Timing
  SAVE_FIELDS = {
    'Game_System'=>%i[timer],
    'Interpreter'=>%i[wait_count],
    'Game_Map'=>%i[fog_tone_duration fog_opacity_duration],
    'Game_Character'=>%i[anime_count stop_count jump_count jump_peak wait_count],
    'Game_Screen'=>%i[tone_duration flash_duration shake_duration weather_duration],
    'Game_Picture'=>%i[duration tone_duration]
  }.freeze unless const_defined?(:SAVE_FIELDS, false)
  def self.import_save(file)
    return if file.timing_rate == 120
    seen = {}.compare_by_identity
    visit = lambda do |object|
      return if object.nil? || seen.key?(object)
      seen[object] = true
      SAVE_FIELDS.each do |name,fields|
        next unless object.is_a?(Object.const_get(name))
        fields.each do |field|
          key = :"@#{field}"
          value = object.instance_variable_get(key)
          object.instance_variable_set(key,value * 3) if value.is_a?(Numeric)
        end
      end
      case object
      when Array then object.each { |value| visit.call(value) }
      when Hash then object.each_value { |value| visit.call(value) }
      else
        if object.class.name&.start_with?('Game_', 'Interpreter')
          object.instance_variables.each { |field| visit.call(object.instance_variable_get(field)) }
        end
      end
    end
    [$game_system,$game_screen,$game_map,$game_player].each { |root| visit.call(root) }
    Graphics.frame_count *= 3
    file.timing_rate = 120
  end
end

module LunetileDisplayMenu
  def update_command
    if @command_window.index == 6 && !Input.trigger?(Input::B) && Input.trigger?(Input::C)
      $game_system.se_play($data_system.decision_se)
      $scene = Scene_LunetileDisplay.new
      return
    end
    super
  end
end
Scene_Menu.prepend(LunetileDisplayMenu) unless Scene_Menu.ancestors.include?(LunetileDisplayMenu)

class Scene_LunetileDisplay
  def main
    @help = Window_Help.new
    @help.set_text('화면 출력 FPS 선택 (게임 로직: 120Hz)')
    @command = Window_Command.new(320, ['40 FPS', '60 FPS', '120 FPS'])
    @command.x = (Graphics.width - @command.width) / 2
    @command.y = (Graphics.height - @command.height) / 2
    @command.index = [40,60,120].index(Graphics.render_rate)
    Graphics.transition
    loop do
      Graphics.update
      Input.update
      @command.update
      if Input.trigger?(Input::B)
        $scene = Scene_Menu.new(6)
      elsif Input.trigger?(Input::C)
        begin
          RGSSXP::Timing.save_settings([40,60,120][@command.index])
          $scene = Scene_Menu.new(6)
        rescue SystemCallError, IOError => error
          @help.set_text('설정을 저장하지 못했습니다: ' + error.message)
        end
      end
      break unless $scene.equal?(self)
    end
    Graphics.freeze
  ensure
    @command&.dispose
    @help&.dispose
  end
end
RGSSXP::Timing.load_settings
