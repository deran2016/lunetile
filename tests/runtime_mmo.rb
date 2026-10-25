# Runs only in isolated copies; the public Main remains the online entrypoint.
config=JSON.parse(File.read('client.json'))
config['host'],config['port'],config['display_name']='127.0.0.1',MMO_TEST_PORT,MMO_TEST_NAME
scene=LunetileMMO::Scene.new(config)
scene.define_singleton_method(:combat_active?){true}
module Input
  def self.trigger?(*);false;end
  def self.dir4;$mmo_direction||0;end
end
Graphics.transition
started=LunetileMMO.now;stage=0;peers=0;moving_at=nil;samples=0;max_step=0;max_camera=0
previous={};previous_camera=nil;identity=nil;final_motion=nil;ready_at=nil
schedule=[[1.4,6],[0.8,2],[0.7,4],[0.6,8],[0.035,6],[0.035,2],[0.035,4],[0.035,8],[0.4,4],[0.4,6],[1.0,0]]
begin
  loop do
    Graphics.update;Input.update
    if stage==3
      elapsed=LunetileMMO.now-moving_at;phase=0
      while phase<schedule.size && elapsed>=schedule[phase][0]
        elapsed-=schedule[phase][0];phase+=1
      end
      $mmo_direction=phase<schedule.size ? schedule[phase][1] : 0
    end
    scene.update;state=scene.connection.state
    raise "Native MMO deadline stage=#{stage}" if LunetileMMO.now-started>28
    next unless state
    peers=[peers,state['players'].size].max
    if stage==3
      scene.avatars.each do |id,avatar|
        current=[avatar.real_x,avatar.real_y];old=previous[id]
        if old
          dx=current[0]-old[0];dy=current[1]-old[1]
          raise 'Native scene cut a corner' if dx.abs>0.001 && dy.abs>0.001
          step=[dx.abs,dy.abs].max;max_step=[max_step,step].max
          raise "Native scene jumped #{step}" if step>6.001
        end
        previous[id]=current
      end
      camera=[$game_map.display_x,$game_map.display_y]
      max_camera=[max_camera,*(camera.zip(previous_camera).map{|a,b|(a-b).abs})].max if previous_camera
      previous_camera=camera;samples+=1
    end
    case stage
    when 0
      scene.connection.send_message({'type'=>'talk','npc_id'=>'guide'});stage=1
    when 1
      if state['inventory']['potion']==5
        scene.connection.send_message({'type'=>'use','item_id'=>'potion'});stage=2
      end
    when 2
      if state['self']['hp']==100 && peers>=2
        scene.instance_variable_get(:@panels)[:dialogue].visible=false
        moving_at=LunetileMMO.now;stage=3
      end
    when 3
      if LunetileMMO.now-moving_at>schedule.sum{|r|r[0]}+0.5
        avatar=scene.avatars.fetch(scene.connection.id);m=state['self']['motion']
        # Reconnection checks wait for committed state; movement timing has its own foreground probe.
        next unless avatar.pending_moves.empty? && (avatar.real_x-m['x']*0.128).abs<0.001 && (avatar.real_y-m['y']*0.128).abs<0.001
        identity=scene.connection.id;final_motion=m.values_at('x','y')
        scene.connection.send_message({'type'=>'chat','text'=>"#{MMO_TEST_NAME}: 실제 XP 접속"});stage=4
      end
    when 4
      if state['chat'].any?{|m|m['name']==MMO_TEST_NAME}
        scene.dispose;sleep 0.25;scene=LunetileMMO::Scene.new(config)
        scene.define_singleton_method(:combat_active?){true};stage=5
      end
    when 5
      raise 'Reconnect lost identity, inventory or fractional position' unless scene.connection.id==identity && state['inventory']['potion']==4 && state['self']['motion'].values_at('x','y')==final_motion
      scene.instance_variable_set(:@inventory_open,true);stage=6;ready_at=LunetileMMO.now
    when 6
      if LunetileMMO.now-ready_at>0.3
        pixel=Graphics.__scene_pixel(640,400);raise 'Empty rendered scene' unless pixel && pixel[3]==255 && pixel.first(3).any?{|v|v>0}
        File.write('mmo-native-result.json',JSON.generate({'name'=>MMO_TEST_NAME,'maximum_peers'=>peers,'stage'=>stage,
          'position'=>state['self']['position'],'motion'=>state['self']['motion'].slice('x','y'),
          'inventory'=>state['inventory'],'hp'=>state['self']['hp'],'movement_samples'=>samples,'max_step_real_units'=>max_step,
          'max_camera_step_real_units'=>max_camera,'sample_pixel'=>pixel,'logic_rate'=>Graphics.logic_rate,'render_rate'=>Graphics.render_rate}))
        File.write('runtime-complete.txt','mmo,false,false');break
      end
    end
  end
ensure
  scene.dispose
end
