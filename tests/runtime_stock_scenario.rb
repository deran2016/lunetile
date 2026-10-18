# Own test content, loaded after the 89 stock definitions and before stock Main.
def event_command(code, parameters = [], indent = 0)
  RPG::EventCommand.new(code, indent, parameters)
end
map = load_data('Data/Map001.rxdata')
event = RPG::Event.new(4,4)
event.id, event.name = 1, 'RGSSXP validation story'
page = event.pages.first
page.trigger = 3
page.condition.switch1_valid, page.condition.switch1_id = !File.exist?('scenario-manual.txt'), 2
route = RPG::MoveRoute.new
route.repeat = false
route.list = [RPG::MoveCommand.new(14,[1,0]),RPG::MoveCommand.new]
page.list = [
  event_command(101,['RGSSXP: dialogue and choice']),
  event_command(102,[['Continue','Wait'],0]),
  event_command(402,[0,'Continue']),
  event_command(121,[3,3,0],1),
  event_command(402,[1,'Wait']),
  event_command(121,[3,3,1],1),
  event_command(404),
  event_command(223,[Tone.new(10,-10,0,40),4]),
  event_command(224,[Color.new(255,255,255,100),4]),
  event_command(225,[3,4,4]),
  event_command(236,[1,3,4]),
  event_command(231,[1,'Validation',0,0,16,16,100,100,180,0]),
  event_command(106,[8]),
  event_command(235,[1]),
  event_command(209,[-1,route]),
  event_command(210),
  event_command(301,[1,false,false]),
  event_command(601),
  event_command(121,[4,4,0],1),
  event_command(604),
  event_command(201,[0,2,10,7,2,0]),
  event_command(0)
]
map.events = {1=>event}
parallel = RPG::Event.new(6,6)
parallel.id, parallel.name = 2, 'Parallel validation counter'
parallel.pages.first.trigger = 4
parallel.pages.first.list = [event_command(122,[2,2,1,0,1]),event_command(106,[5]),event_command(0)]
map.events[2] = parallel
save_data(map,'Data/Map001.rxdata')
ending_map = Marshal.load(Marshal.dump(map))
ending = RPG::Event.new(3,3)
ending.id, ending.name = 1, 'Validation ending'
ending.pages.first.trigger = 3
ending.pages.first.list = [event_command(236,[0,0,4]),event_command(101,['RGSSXP: ending reached']),event_command(121,[5,5,0]),event_command(354),event_command(0)]
ending_map.events = {1=>ending}
save_data(ending_map,'Data/Map002.rxdata')
infos=load_data('Data/MapInfos.rxdata');infos[2]=RPG::MapInfo.new;infos[2].name='Validation ending';save_data(infos,'Data/MapInfos.rxdata')
enemies = load_data('Data/Enemies.rxdata')
# A one-hit encounter keeps this rendering/scene integration test bounded.
enemies.compact.each { |enemy| enemy.maxhp = 1 }
save_data(enemies,'Data/Enemies.rxdata')

module ScenarioDriver
  @tick, @scene_tick, @phase, @last_scene, @button = 0, 0, :title, nil, nil
  @scenes = []
  class << self
    attr_reader :button
    def confirm
      @button = Input::C
    end
    def select(index)
      $scene.instance_variable_get('@command_window').index = index
      confirm
    end
    def step
      @tick += 1
      @button = nil
      if @last_scene != $scene
        @last_scene, @scene_tick = $scene, 0
        @scenes << $scene.class.name
        File.open('scenario-states.txt','a') { |file| file.puts("#{@tick}:#{@phase}:#{$scene.class}") }
      end
      @scene_tick += 1
      raise "Scenario timed out in #{@phase}, #{$scene.class}" if @tick > (@tick_limit || 2200)
      return if @scene_tick < 12
      case @phase
      when :title
        select(0);@phase = :map
      when :map
        if $scene.is_a?(Scene_Map)
          @button = Input::B;@phase = :menu
        end
      when :menu
        if $scene.is_a?(Scene_Menu)
          select(4);@phase = :save
        end
      when :save
        if $scene.is_a?(Scene_Save)
          $game_variables[1] = 345;confirm;@phase = :saved
        end
      when :saved
        if $scene.is_a?(Scene_Menu)
          raise 'Save missing' unless RGSSXP::Saves.exist?(0)
          $game_variables[1] = 999
          select(5);@phase = :end_menu
        end
      when :end_menu
        if $scene.is_a?(Scene_End)
          select(0);@phase = :continue
        end
      when :continue
        if $scene.is_a?(Scene_Title)
          select(1);@phase = :load
        end
      when :load
        if $scene.is_a?(Scene_Load)
          confirm;@phase = :loaded
        end
      when :loaded
        if $scene.is_a?(Scene_Map)
          raise 'Save did not restore game state' unless $game_variables[1] == 345
          raise 'Parallel event did not advance' unless $game_variables[2] > 0
          $game_switches[2] = true;$game_map.need_refresh = true
          @phase = :story
        end
      when :story
        story_step
      end
    end
    def story_step
      confirm if @tick % 8 == 0
      if $scene.is_a?(Scene_Title)
        raise 'Choice branch or battle/ending failed' unless [3,4,5].all? { |id| $game_switches[id] }
        raise 'Battle scene never ran' unless @scenes.include?('Scene_Battle')
        File.write('scenario-result.txt',@scenes.inspect)
        if File.exist?('scenario-endurance.txt')
          start_endurance
          return
        end
        File.write('runtime-complete.txt','stock-scenario,false,false')
        exit
      end
    end
  end
end
module ScenarioGraphics
  def update
    ScenarioDriver.step
    super
  end
end
module ScenarioInput
  def trigger?(key)
    key == ScenarioDriver.button || super
  end
end
if File.exist?('scenario-manual.txt')
  module ScenarioManualObserver
    def update
      if $scene.is_a?(Scene_Title) && $game_switches && $game_switches[5]
        raise 'Manual story did not complete the choice and battle' unless $game_switches[3] && $game_switches[4]
        File.write('manual-ending-reached.txt','Choice, battle victory, map transfer and ending switches observed')
      end
      super
    end
  end
  Graphics.singleton_class.prepend(ScenarioManualObserver)
else
  Graphics.singleton_class.prepend(ScenarioGraphics)
  Input.singleton_class.prepend(ScenarioInput)
end
