# Exercises the shipped settings scene with injected logical input, then resumes the stock story.
module RefreshScenarioDriver
  def step
    if @phase == :menu && $scene.is_a?(Scene_Menu) && !@refresh_selected && @scene_tick >= 10 * RGSSXP::Timing.scale
      @button = nil
      select(6)
      @phase = :refresh_settings
      @refresh_wait = 0
      return
    end
    if @phase == :refresh_settings
      @button = nil
      if $scene.is_a?(Scene_LunetileDisplay)
        @refresh_wait += 1
        if @refresh_wait >= 12 * RGSSXP::Timing.scale
          rate = File.read('refresh-test-rate.txt').to_i
          $scene.instance_variable_get(:@command).index = [40,60,120].index(rate)
          confirm
          @phase = :refresh_return
        end
      end
      return
    end
    if @phase == :refresh_return
      @button = nil
      if $scene.is_a?(Scene_Menu)
        rate = File.read('refresh-test-rate.txt').to_i
        raise 'settings UI did not apply output rate' unless Graphics.render_rate == rate
        raise 'settings UI did not save output rate' unless File.read(RGSSXP::Timing.settings_path).include?("RenderRate=#{rate}")
        File.write('refresh-settings-selected.txt',rate.to_s)
        @refresh_selected = true
        @phase = :menu
      else
        return
      end
    end
    super
  end
end
ScenarioDriver.singleton_class.prepend(RefreshScenarioDriver)
