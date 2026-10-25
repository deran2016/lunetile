config=JSON.parse(File.read('client.json'))
config['host'],config['port'],config['display_name']='127.0.0.1',GUI_TEST_PORT,"GUI#{GUI_TEST_INDEX}"
scene=LunetileMMO::Scene.new(config)
physical_active=scene.method(:combat_active?)
scene.define_singleton_method(:combat_active?){$gui_goal ? true : physical_active.call}
started=LunetileMMO.now;last_report=0;last_command=-1;composition_seen=false;events_seen={};projectile_history=[];projectile_events=[];drag_gestures=[];appearance_history=[]
original_cancel_drag=scene.method(:cancel_quick_drag)
scene.define_singleton_method(:cancel_quick_drag) do
  drag=instance_variable_get(:@quick_drag)
  if drag && drag[:active]
    icon=drag[:cursor].bitmap;marker=drag[:target].bitmap
    record={'binding'=>drag[:binding],'origin'=>drag[:origin],'target_visible'=>drag[:target].visible,
      'target_xy'=>[drag[:target].x,drag[:target].y]}
  end
  original_cancel_drag.call
  if record
    record['cursor_disposed']=drag[:cursor].disposed?;record['marker_disposed']=marker.disposed?;record['shared_icon_preserved']=!icon.disposed?
    drag_gestures<<record
  end
end
original_events=scene.method(:receive_events)
scene.define_singleton_method(:receive_events) do |state|
  seen=instance_variable_get(:@event_seq)||state['event_seq']
  state['events'].each do |e|
    next if e['seq']<=seen
    if e['kind']=='explosion'||e['projectile'];projectile_events<<{'kind'=>e['kind'],'id'=>e['projectile'] ? e['projectile']['id'] : e['id'],'at'=>LunetileMMO.now};end
  end
  original_events.call(state)
end
module Input
  class << self
    alias_method :gui_physical_dir4,:dir4
    def dir4
      return gui_physical_dir4 unless $gui_goal && $gui_scene.connection.state
      point=$gui_scene.avatars.fetch($gui_scene.connection.id).destination;p={'x'=>point[0],'y'=>point[1]};x,y=$gui_goal
      return p['x']<x ? 6 : 4 if (p['x']-x).abs>0.05
      return p['y']<y ? 2 : 8 if (p['y']-y).abs>0.05
      0
    end
  end
end
$gui_scene=scene
module Lunetile::UIInput
  class << self
    alias_method :gui_physical_key_press,:key_press?
    def key_press?(key)
      return $gui_attack_keys.include?(key) if $gui_attack_keys && LunetileMMO::QUICK_KEYS.include?(key)
      gui_physical_key_press(key)
    end
  end
end
physical_attack=scene.method(:physical_attack_down?)
scene.define_singleton_method(:physical_attack_down?){|key|$gui_attack_keys ? $gui_attack_keys.include?(key) : physical_attack.call(key)}
Graphics.transition
begin
  loop do
    Graphics.update;Input.update
    if File.exist?('gui-control.json') && scene.connection.state
      command=begin
        JSON.parse(File.read('gui-control.json'))
      rescue Errno::EACCES,Errno::ENOENT,JSON::ParserError
        nil
      end
      if command && command['seq']!=last_command
        last_command=command['seq']
        case command['type']
        when 'walk';$gui_goal=command['position']
        when 'stop';$gui_goal=nil
        when 'buttons';$gui_attack_keys=command['keys']&.map(&:to_sym)
        when 'chat';scene.chat_focus(command['open'])
        when 'attack';scene.instance_variable_set(:@aim_direction,command['direction']) if command['direction'];scene.attack(command.fetch('skill','basic'))
        when 'use';scene.use_item(command['item'])
        when 'bind';scene.assign_quickslot(command['slot'],command['skill'])
        when 'quick';scene.use_quickslot(command['slot'])
        when 'system';scene.window_command(command['kind'],command['action'],command.fetch('key',''),command.fetch('amount',1),command.fetch('text',''),command.fetch('revision',0))
        when 'window';scene.open_window(command['key'].to_sym)
        when 'quit';scene.instance_variable_set(:@quit,true)
        when 'bag';scene.instance_variable_set(:@inventory_open,command['open'])
        when 'close';scene.popup_keys.each{|k|scene.close_window(k)}
        end
      end
    end
    scene.update
    composition_seen ||= Lunetile::UIInput.composing? || !Lunetile::UIInput.composition.empty?
    state=scene.connection.state
    if state && LunetileMMO.now-last_report>0.1
      scene.instance_variable_get(:@throw_effects).each do |id,e|
        d=e[:data];elapsed=(LunetileMMO.now-e[:began])*1000;p=d['cells'].last
        color=e[:marker].bitmap.get_pixel(16,16)
        projectile_history<<{'id'=>id,'elapsed_ms'=>elapsed,'pose'=>scene.projectile_pose(d,elapsed),
          'warning_bitmap_rgba'=>[color.red,color.green,color.blue,color.alpha],
          'warning_scene_rgba'=>p ? Graphics.__scene_pixel((p['x']*128-$game_map.display_x)/4+16,(p['y']*128-$game_map.display_y)/4+16) : nil}
      end
      projectile_history.shift while projectile_history.size>512
      state['events'].each{|e|events_seen[e['seq']]=e}
      data={'state'=>state,'command'=>last_command,'draft'=>scene.instance_variable_get(:@draft),'chat_open'=>scene.instance_variable_get(:@chat_open),'chat_scroll'=>scene.instance_variable_get(:@chat_scroll),'target_id'=>scene.instance_variable_get(:@target_id),
        'composition'=>Lunetile::UIInput.composition,'composition_seen'=>composition_seen,'events_seen'=>events_seen.values,'projectile_events'=>projectile_events,'projectile_history'=>projectile_history,
        'input_stats'=>Lunetile::UIInput.respond_to?(:__stats) ? Lunetile::UIInput.__stats : nil,'background_update'=>Graphics.background_update,'effect_counts'=>scene.instance_variable_get(:@effect_counts),'active_effects'=>scene.instance_variable_get(:@combat_effects).size,
        'panels'=>scene.instance_variable_get(:@panels).transform_values{|p|[p.x,p.y,p.visible]},'scene_pixel'=>Graphics.__scene_pixel(20,Graphics.height-85)}
      data['avatars']=scene.avatars.transform_values{|a|{'real_x'=>a.real_x,'real_y'=>a.real_y,'direction'=>a.direction}}
      data['prediction_pending']=scene.avatars.fetch(scene.connection.id).pending_moves.size
      data['direction_input']=[Lunetile::UIInput.direction4,Lunetile::UIInput.direction_trigger]
      data['reserved_direction']=scene.instance_variable_get(:@direction_buffer)
      panels=scene.instance_variable_get(:@panels)
      data['panel_bounds']=panels.transform_values{|p|[p.x,p.y,p.width,p.height,p.visible]}
      data['quickslots']=LunetileMMO::QUICK_KEYS.each_index.map{|i|r=scene.quickslot_rect(i);[panels[:quicks].x+r.x,panels[:quicks].y+r.y,r.width,r.height]}
      data['quickslot_bindings']=scene.quickslot_bindings(state);data['drag_gestures']=drag_gestures
      if (system=scene.instance_variable_get(:@particles))
        data['particles']=system.stats
        data['particle_samples']=system.instance_variable_get(:@active).first(8).map do |p|
          s=p.sprite;c=s.color
          {'xy'=>[s.x,s.y],'tint'=>[c.red,c.green,c.blue],'opacity'=>s.opacity,
            'pixel'=>s.x.between?(0,Graphics.width-1)&&s.y.between?(0,Graphics.height-1) ? Graphics.__scene_pixel(s.x,s.y) : nil}
        end
      end
      data['appearances']=scene.instance_variable_get(:@sprites).transform_values do |sprite|
        weapon=sprite.instance_variable_get(:@held_weapon);r=sprite.src_rect
        {'portal'=>!!sprite.instance_variable_get(:@portal),'frame'=>[r.x,r.y,r.width,r.height],
          'body'=>[sprite.x,sprite.y,sprite.z,sprite.zoom_x,sprite.oy],
          'weapon'=>weapon ? {'icon'=>sprite.instance_variable_get(:@weapon_icon),'pose'=>[weapon.x,weapon.y,weapon.z,weapon.angle],'visible'=>weapon.visible} : nil}
      end
      appearance_history<<{'at'=>LunetileMMO.now,'appearances'=>data['appearances']};appearance_history.shift while appearance_history.size>256
      data['appearance_history']=appearance_history
      if (minimap=scene.instance_variable_get(:@minimap))
        r=minimap.rect;b=minimap.bitmap
        data['minimap']={'rect'=>[r.x,r.y,r.width,r.height],'bitmap_id'=>b.object_id,
          'pixels'=>[[0.2,0.2],[0.5,0.5],[0.8,0.8]].map{|x,y|c=b.get_pixel((x*b.width).to_i,(y*b.height).to_i);[c.red,c.green,c.blue,c.alpha]}}
      end
      chat=panels[:chat];data['chat_background_pixel']=Graphics.__scene_pixel(chat.x+380,chat.y+140)
      File.write('gui-live.tmp',JSON.generate(data))
      begin
        File.rename('gui-live.tmp','gui-live.json')
      rescue Errno::EACCES
        # A Windows reader may temporarily hold the telemetry file without delete sharing.
      end
      last_report=LunetileMMO.now
    end
    break if scene.instance_variable_get(:@quit)||File.exist?('gui-exit.txt')||LunetileMMO.now-started>GUI_TEST_DURATION
  end
ensure
  scene.dispose
end
