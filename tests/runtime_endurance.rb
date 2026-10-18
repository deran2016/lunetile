# Own endurance driver, appended to the short stock scenario in an isolated copy.
seconds, roundtrips = File.read('scenario-endurance.txt').split.map(&:to_i)
raise 'Invalid endurance parameters' unless seconds.between?(1,7200) && roundtrips.between?(1,1000)
ScenarioDriver.instance_variable_set(:@dur_seconds,seconds)
ScenarioDriver.instance_variable_set(:@dur_roundtrips,roundtrips)

map = load_data('Data/Map001.rxdata')
story = map.events[1].pages.first.list
story.insert(story.index { |command| command.code==201 },event_command(121,[7,7,0]))
map.autoplay_bgm = true
map.bgm = RPG::AudioFile.new('001-Battle01',20,100)
save_data(map,'Data/Map001.rxdata')
ending = load_data('Data/Map002.rxdata')
ending.events[1].pages.first.condition.switch1_valid = true
ending.events[1].pages.first.condition.switch1_id = 7
ending.autoplay_bgm = true
ending.bgm = RPG::AudioFile.new('001-Battle01',20,150)
save_data(ending,'Data/Map002.rxdata')

module EnduranceReady
  def update
    @rgssxp_endurance_ready = true
    super
  end
end
Scene_Title.prepend(EnduranceReady)
Scene_Map.prepend(EnduranceReady)

module EnduranceDriver
  def start_endurance
    @endurance_stage = :title
    @phase = :endurance
  end
  def direction
    @endurance_stage==:playing ? [6,2,4,8][(@dur_frames/40)%4] : nil
  end
  def endurance_record(path)
    values = {active_seconds:@dur_active,frames:@dur_frames,transfers:@dur_transfers,
              roundtrips:@dur_transfers/2,moves:@dur_moves,focus_pause_seconds:@dur_paused,
              gpu_valid:Graphics.__timings[3]}
    # A live Windows reader can briefly deny rename; telemetry may be partial, final data is read only after exit.
    File.write(path,values.map { |key,value| "#{key}=#{value}" }.join("\n"))
  end
  def step
    return super unless @endurance_stage
    @button = nil
    @tick += 1
    ready = $scene.instance_variable_get('@rgssxp_endurance_ready')
    if @endurance_stage==:title
      if $scene.is_a?(Scene_Title) && ready
        select(0)
        @endurance_stage = :map
      end
      return
    end
    return unless $scene.is_a?(Scene_Map) && ready
    stamp = Process.clock_gettime(Process::CLOCK_MONOTONIC)
    if @endurance_stage==:map
      @endurance_stage = :playing
      @dur_active,@dur_paused,@dur_frames,@dur_transfers,@dur_moves = 0.0,0.0,0,0,0
      @dur_previous_stamp = stamp
      @dur_previous_position = [$game_player.x,$game_player.y]
      @dur_previous_pause = Graphics.endurance_pause_seconds
      return
    end
    raise 'Endurance frame rate changed' unless Graphics.frame_rate==40
    paused = Graphics.endurance_pause_seconds
    pause = paused-@dur_previous_pause
    @dur_previous_pause = paused
    @dur_paused += pause
    @dur_active += [stamp-@dur_previous_stamp-pause,0].max
    @dur_previous_stamp = stamp
    @dur_frames += 1
    position = [$game_player.x,$game_player.y]
    @dur_moves += 1 if position!=@dur_previous_position
    @dur_previous_position = position
    if @dur_pending_map && $game_map.map_id==@dur_pending_map && !$game_temp.player_transferring
      @dur_transfers += 1
      @dur_pending_map = nil
    end
    if @dur_transfers < @dur_roundtrips*2 && !@dur_pending_map && @dur_frames%120==0
      @dur_pending_map = $game_map.map_id==1 ? 2 : 1
      $game_temp.player_new_map_id = @dur_pending_map
      $game_temp.player_new_x,$game_temp.player_new_y = 10,7
      $game_temp.player_new_direction = 2
      $game_temp.player_transferring = true
    end
    endurance_record('endurance-progress.txt') if @dur_frames%40==0
    if @dur_active>=@dur_seconds && @dur_frames>=@dur_seconds*40 && @dur_transfers>=@dur_roundtrips*2
      raise 'Player did not keep moving' if @dur_moves < [100,@dur_seconds*2].min
      raise 'Parallel events stopped advancing' unless $game_variables[2]>0
      endurance_record('endurance-result.txt')
      File.write('runtime-complete.txt','stock-endurance,false,false')
      exit
    end
  end
end
ScenarioDriver.singleton_class.prepend(EnduranceDriver)
module EnduranceInput
  def dir4
    ScenarioDriver.direction || super
  end
end
Input.singleton_class.prepend(EnduranceInput)
