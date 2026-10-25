# Instrumented input runs in an isolated client, never in the player's profile.
config = JSON.parse(File.read('client.json'))
config['host'],config['port'],config['display_name'] = '127.0.0.1',MMO_TEST_PORT,"Motion#{MMO_TEST_INDEX}"
scene = LunetileMMO::Scene.new(config)
Graphics.transition
physical_active=scene.method(:combat_active?)
scene.define_singleton_method(:combat_active?) {true}
module Input
  def self.trigger?(*); false; end
  def self.dir4; $motion_direction || 0; end
end
schedule = [[2.4,6],[1.6,2],[1.4,4],[1.2,8],[0.13,6],[0.4,4],[0.6,6],[0.5,0]]
schedule=([6,4,2,8]*10).flat_map{|d|[[0.05,d],[0.65,0]]} if MMO_TEST_LATENCY
rapid_expected=[]
if MMO_TEST_RAPID
  schedule=[]
  10.times do
    [[8,6,2,4],[2,4,8,6]].each do |directions|
      rapid_expected.concat(directions)
      directions.each{|d|schedule.concat([[0.035,d],[0.015,0]])}
      schedule << [0.4,0]
    end
  end
end
if MMO_TEST_COMBAT
  schedule.unshift([2.0,0]);scene.instance_variable_set(:@aim_direction,6)
  module Lunetile::UIInput
    class << self
      alias_method :motion_key_press,:key_press?
      def key_press?(key)
        return $motion_attack==key if [:z,:x].include?(key)
        motion_key_press(key)
      end
    end
  end
  scene.define_singleton_method(:physical_attack_down?){|key|$motion_attack==key}
end
started = nil
ready=false
samples = []
render_samples = []
presented = nil
sent = [];previews=[];state_events=[]
notices = []
max_effects=0;max_projectiles=0;max_held_weapons=0;max_particles=0
foreground_lost=0
latency_trials=[];last_direction=0;turn_trials=[]
connection = scene.connection
original_send = connection.method(:send_message)
connection.define_singleton_method(:send_message) do |message|
  sent << [LunetileMMO.now,message['parts'],samples.size] if message['type']=='move'
  previews << [LunetileMMO.now,message['elapsed'],message['parts'].last&.fetch('step'),message['moving'],message['origin']] if message['type']=='preview'
  original_send.call(message)
end
original_receive=connection.method(:receive)
connection.define_singleton_method(:receive) do |message|
 original_receive.call(message)
 if started && (mover=state['players'].find{|p|p['name']=='Motion0'})
  r=mover['relay'] || {};state_events << [LunetileMMO.now-started,state['move_ack']['seq'],mover['motion']['x'],mover['motion']['y'],r['x'],r['y'],r['moving'],r['step']]
 end
end
begin
  loop do
    Graphics.update
    Input.update
    now = LunetileMMO.now
    state = connection.state
    if !ready && state && state['players'].size==2
      scene.open_window(:skills) if MMO_TEST_COMBAT && MMO_TEST_INDEX==0
      if MMO_TEST_COMBAT
        skill=MMO_TEST_PROJECTILE ? 'grenade' : 'burst'
        gear=state['progress']['gear'].find{|_,g|g['definition']=='weapon_1'}&.first
        connection.send_message({'type'=>'progress','action'=>'equip','key'=>gear}) if gear
        connection.send_message({'type'=>'progress','action'=>'learn','key'=>skill})
        connection.send_message({'type'=>'progress','action'=>'bind','key'=>skill})
      end
      File.write('motion-ready.txt','ready');ready=true
    end
    if !started && state && state['players'].size==2 && File.exist?('motion-start.txt')
      started = now
    end
    elapsed = started ? now-started : -1
    phase = 0
    remaining = elapsed
    while phase < schedule.size && remaining >= schedule[phase][0]
      remaining -= schedule[phase][0]
      phase += 1
    end
    $motion_direction = started && MMO_TEST_INDEX==0 && phase < schedule.size ? schedule[phase][1] : 0
    if MMO_TEST_LATENCY && $motion_direction!=0 && last_direction==0
      avatar=scene.avatars.fetch(connection.id)
      latency_trials << {'direction'=>$motion_direction,'input_at'=>elapsed,'origin'=>[avatar.real_x,avatar.real_y],
        'seq_before'=>connection.instance_variable_get(:@move_seq)||0}
    end
    if MMO_TEST_RAPID && $motion_direction!=0 && $motion_direction!=last_direction
      avatar=scene.avatars.fetch(connection.id)
      turn_trials << {'direction'=>$motion_direction,'input_at'=>elapsed,'origin'=>[avatar.real_x,avatar.real_y],
        'off_center'=>avatar.real_x%128!=0 || avatar.real_y%128!=0,'tick'=>samples.size}
    end
    last_direction=$motion_direction
    $motion_attack=MMO_TEST_COMBAT && started && MMO_TEST_INDEX==0 ? (elapsed<2 || (elapsed/1.2).to_i.even? ? :z : :x) : nil
    scene.update
    max_effects=[max_effects,scene.instance_variable_get(:@combat_effects).size].max
    max_projectiles=[max_projectiles,scene.instance_variable_get(:@throw_effects).size].max
    max_held_weapons=[max_held_weapons,scene.instance_variable_get(:@sprites).values.count{|s|s.instance_variable_get(:@held_weapon)}].max
    max_particles=[max_particles,scene.instance_variable_get(:@particles).stats[:active]].max
    if started
      foreground_lost+=1 if MMO_TEST_FOREGROUND && !physical_active.call
      notice=connection.state['notice']
      notices << [elapsed,notice] if notices.empty? || notices.last[1]!=notice
      mover = connection.state['players'].find { |p| p['name']=='Motion0' }
      avatar = mover && scene.avatars[mover['id']]
      if (trial=latency_trials.last)
        trial['logic_ms']||=(elapsed-trial['input_at'])*1000 if [avatar.real_x,avatar.real_y]!=trial['origin']
        trial['ack_ms']||=(elapsed-trial['input_at'])*1000 if connection.state['move_ack']['seq']>trial['seq_before']
      end
      if (turn=turn_trials.last) && !turn['logic_ms']
        dx=avatar.real_x-turn['origin'][0];dy=avatar.real_y-turn['origin'][1]
        if dx!=0 || dy!=0
          actual=dx!=0 ? (dx>0 ? 6 : 4) : (dy>0 ? 2 : 8)
          raise 'Mid-tile direction was delayed' unless actual==turn['direction']
          turn['logic_ms']=(elapsed-turn['input_at'])*1000;turn['wait_ticks']=samples.size-turn['tick']
        end
      end
      samples << [elapsed,phase,avatar.real_x,avatar.real_y,$game_map.display_x,$game_map.display_y,
                  mover['motion']['x']/1000.0,mover['motion']['y']/1000.0,avatar.direction] if avatar
      rendered = Graphics.__refresh_stats[1]
      if rendered != presented && samples.size > 1
        render_samples << [elapsed,*samples[-2][1..-1]]
        if trial && samples[-2][0]>=trial['input_at'] && samples[-2][2,2]!=trial['origin']
          trial['present_ms']||=(elapsed-trial['input_at'])*1000
        end
        if turn && samples[-2][0]>=turn['input_at'] && samples[-2][2,2]!=turn['origin']
          turn['present_ms']||=(elapsed-turn['input_at'])*1000
        end
        presented = rendered
      end
      if phase >= schedule.size && elapsed>schedule.sum{|row|row[0]}+1.5
        pixel=Graphics.__scene_pixel(640,400)
        File.write('motion-result.json',JSON.generate({'samples'=>samples,'moves'=>sent.map { |t,d| [t-started,d] },
          'started'=>started,'logic_rate'=>Graphics.logic_rate,'render_rate'=>Graphics.render_rate,'pixel'=>pixel,
          'refresh_stats'=>Graphics.__refresh_stats,'foreground_required'=>MMO_TEST_FOREGROUND,'notices'=>notices,
          'held_phases'=>MMO_TEST_LATENCY || MMO_TEST_RAPID ? [] : (MMO_TEST_COMBAT ? [1,2,3,4] : [0,1,2,3]),'movement_delay_ms'=>MMO_TEST_COMBAT ? 2000 : 0,
          'rapid_expected'=>rapid_expected,'turn_trials'=>turn_trials,
          'move_ticks'=>sent.map(&:last),'previews'=>previews.map{|row|[row[0]-started,*row[1..-1]]},'state_events'=>state_events,
          'latency_trials'=>latency_trials,
          'combat_counts'=>scene.instance_variable_get(:@effect_counts),'max_active_effects'=>max_effects,'max_projectiles'=>max_projectiles,'max_held_weapons'=>max_held_weapons,'max_particles'=>max_particles,
          'foreground_lost_ticks'=>foreground_lost,
          'render_samples'=>render_samples}))
        break
      end
    end
  end
ensure
  scene.dispose
end
