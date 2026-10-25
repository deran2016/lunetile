module LunetileMMO
  class Scene
    attr_reader :connection,:avatars
    def initialize(config,connection=nil)
      raise '새 Lunetile.dll과 Scripts.rxdata를 함께 업데이트하세요.' unless defined?(Lunetile::UIInput) && Lunetile::UIInput.respond_to?(:direction_trigger) && Lunetile::UIInput.respond_to?(:direction4)
      @previous_background=Graphics.background_update;Graphics.background_update=true
      Lunetile::UIInput.text_input=false
      @config=config;@avatars,@sprites={},{}
      $data_system=load_data('Data/System.rxdata');$game_system=Game_System.new
      setup_hud;setup_windows;setup_combat_effects;suspend_combat
      @connection=connection||Connection.new(config)
    end
    def main
      Graphics.transition
      until @quit
        Graphics.update;Input.update;update
      end
    ensure
      dispose
    end
    def update
      Lunetile::UIInput.text_input=!!(@chat_open||@form) if @panels
      update_window_focus if @panel_order
      handle_input(@connection.state) if @connection.state && @avatars.key?(@connection.id)
      @connection.update
      @connection.drain_states.each do |state|
        @particles&.configure(state.fetch('particle_presets',[]))
        if @map_id!=state['self']['position']['map_id']
          local=@avatars[@connection.id]
          @sprites.each_value(&:dispose);@sprites.clear;@avatars.clear;@spriteset&.dispose
          @avatars[@connection.id]=local if local
          @labels.each_value{|sprite,_|sprite.bitmap.dispose;sprite.dispose};@labels.clear
          @combat_effects.each{|e|e[:weapon]&.dispose;e[:sprite].dispose};@combat_effects.clear
          clear_projectiles
          @particles&.clear
          cancel_quick_drag
          @minimap&.dispose;@minimap=nil;@minimap_key=nil;@direction_buffer=nil;@next_move=nil;@pad_direction=0
          @map_id=state['self']['position']['map_id'];LunetileMMO.setup_game(@map_id)
          $game_player.transparent=true;@spriteset=Spriteset_Map.new;@viewport=@spriteset.instance_variable_get(:@viewport1)
        end
        receive_chat(state) if @panels
        receive_events(state) if @panels
        sync_projectiles(state) if @throw_effects
        @target_id=nil if @target_id && !state.fetch('monsters',[]).any?{|m|m['id']==@target_id}
        entities=state['players'].map{|p|[p['id'],p]}+state['npcs'].map{|n|["npc_#{n['id']}",n]}+state.fetch('monsters',[]).map{|m|["monster_#{m['id']}",m]}
        entities+=portal_entities(state)
        ids=entities.map(&:first)
        (@avatars.keys-ids).each{|id|@sprites.delete(id).dispose;@avatars.delete(id)}
        entities.each do |id,data|
          unless @sprites[id]
            @avatars[id]||=id==@connection.id ? LocalAvatar.new(data) : Avatar.new(data,id.start_with?('monster_') ? 3 : 4)
            @sprites[id]=CombatCharacter.new(@viewport,@avatars[id])
          end
          @sprites[id].appearance(data,state)
          id==@connection.id && @avatars[id].is_a?(LocalAvatar) ? @avatars[id].reconcile(state) : @avatars[id].apply(data)
          suspend_movement if id==@connection.id && @avatars[id].is_a?(LocalAvatar) && @avatars[id].recovering?
        end
      end
      if @connection.state
        @avatars.each_value(&:update)
        player=@avatars.fetch(@connection.id)
        $game_player.center(player.real_x/128.0,player.real_y/128.0)
        @spriteset.update;@sprites.each_value(&:update)
      end
      update_combat_effects if @combat_effects
      draw_hud
    end
    def handle_input(state)
      unless combat_active?;@drag=nil;@chat_drag_offset=nil;suspend_combat;suspend_movement;return;end
      if @form;handle_window_keys;suspend_combat;suspend_movement;return;end
      if handle_chat;suspend_combat;suspend_movement;return;end
      handle_window_keys
      input=movement_input;direction=@direction_buffer ? @direction_buffer[0] : input[0]
      @aim_direction=direction if direction!=0 && !combat_window_open?
      u=Lunetile::UIInput
      cancelled_quick_drag=u.key_trigger?(:escape) && @quick_drag
      if u.key_trigger?(:escape)
        if cancelled_quick_drag;cancel_quick_drag
        elsif (key=(@panel_order||@panels.keys).reverse.find{|k|popup_keys.include?(k)&&@panels[k].visible});close_window(key)
        else;open_window(:menu)
        end
      end
      open_window(:bag) if u.key_trigger?(:i)||u.key_trigger?(:shift)
      open_window(:character) if u.key_trigger?(:c)
      handle_mouse(state) unless cancelled_quick_drag
      if @chat_open || @form;suspend_combat;suspend_movement;return;end
      if u.key_trigger?(:enter);suspend_combat;chat_focus(true);return;end
      if state['self']['hp']==0;suspend_combat;suspend_movement;return;end
      repeat_combat
      if u.key_trigger?(:space)
        if @panels[:dialogue].visible;close_window(:dialogue);handle_movement(input);return;end
        avatar=@avatars.fetch(@connection.id);x,y=avatar.destination.map{|v|(v+0.5).floor}
        npc=state['npcs'].find{|n|(n['position']['x']-x).abs+(n['position']['y']-y).abs<=1}
        if npc
          avatar.flush(@connection,true)
          @connection.send_message({'type'=>'talk','npc_id'=>npc['id']})
        elsif (portal=state.dig('services','portals')&.find{|v|p=v['from'];p['map_id']==state['self']['position']['map_id']&&(p['x']-x).abs+(p['y']-y).abs<=1})
          suspend_movement
          window_command('service','portal',portal['id'])
          return
        end
      end
      handle_movement(input)
    end
    def quickslot_at(point)
      return unless point
      x,y=point;top=(@panel_order||@panels.keys).reverse.find{|key|@panels[key].hit?(x,y)}
      return unless top==:quicks
      panel=@panels[:quicks]
      QUICK_KEYS.each_index.find{|i|r=quickslot_rect(i);(x-panel.x).between?(r.x,r.x+r.width-1) && (y-panel.y).between?(r.y,r.y+r.height-1)}
    end
    def begin_skill_drag(id)
      return unless learned_active_skill?(id,@connection.state)
      begin_quick_drag("skill:#{id}")
    end
    def begin_quick_drag(binding,origin=nil)
      return unless binding && (point=Lunetile::UIInput.mouse_press_position || Lunetile::UIInput.mouse_position)
      cancel_quick_drag
      @quick_drag={binding:binding,origin:origin,point:point,active:false}
    end
    def cancel_quick_drag
      drag=@quick_drag;@quick_drag=nil;return unless drag
      drag[:cursor]&.dispose
      if (target=drag[:target]);target.bitmap&.dispose;target.dispose;end
    end
    def update_quick_drag(state,point)
      drag=@quick_drag;return false unless drag
      u=Lunetile::UIInput
      if u.mouse_trigger?(:right) || @chat_open || @form || state.dig('self','hp')==0;cancel_quick_drag;return true;end
      if !drag[:active] && point && point.zip(drag[:point]).any?{|a,b|(a-b).abs>=6}
        drag[:active]=true;kind,id=drag[:binding].split(':',2)
        definition=(kind=='skill' ? state['skills'] : state['items']).find{|s|s['id']==id}
        unless definition;cancel_quick_drag;return true;end
        cursor=drag[:cursor]=Sprite.new;cursor.bitmap=RPG::Cache.icon(definition['icon']);cursor.ox=cursor.oy=12;cursor.opacity=190;cursor.z=10000
        target=drag[:target]=Sprite.new;target.bitmap=Bitmap.new(40,40);target.z=9999
        [[0,0,40,3],[0,37,40,3],[0,0,3,40],[37,0,3,40]].each{|r|target.bitmap.fill_rect(*r,Theme::CYAN)}
      end
      destination=quickslot_at(point)
      if drag[:active]
        drag[:cursor].visible=!!point
        drag[:cursor].x,drag[:cursor].y=point if point
        drag[:target].visible=!destination.nil?
        if destination;r=quickslot_rect(destination);drag[:target].x=@panels[:quicks].x+r.x;drag[:target].y=@panels[:quicks].y+r.y;end
      end
      return true if u.key_press?(:left_mouse)
      cancel_quick_drag
      if drag[:active] && destination
        if drag[:origin].nil?;assign_quickslot(destination,drag[:binding].split(':',2).last)
        elsif destination!=drag[:origin]
          slots=quickslot_bindings(state).dup
          if slots[drag[:origin]]==drag[:binding]
            slots[drag[:origin]],slots[destination]=slots[destination],slots[drag[:origin]]
            save_quickslot_layout(slots)
          end
        end
      elsif !drag[:active] && destination==drag[:origin] && !destination.nil? && quickslot_bindings(state)[destination]==drag[:binding]
        use_quickslot(destination)
      end
      true
    end
    def handle_mouse(state)
      u=Lunetile::UIInput;point=u.mouse_position
      return true if update_quick_drag(state,point)
      unless u.key_press?(:left_mouse);@drag=nil;end
      if @drag && point
        key,dx,dy=@drag;@panels[key].move(point[0]-dx,point[1]-dy);@next_move=nil;return true
      end
      return false unless point
      x,y=point
      return true if handle_chat_scroll
      top=(@panel_order||@panels.keys).reverse.find{|key|@panels[key].hit?(x,y)}
      if top==:quicks && u.mouse_trigger?(:right)
        index=quickslot_at(point)
        assign_quickslot(index) if index
        return true
      end
      if @inventory_open && top==:bag && u.wheel_delta!=0
        @inventory_index=[[@inventory_index-u.wheel_delta*18,0].max,[inventory_entries(state).size-1,0].max].min
      end
      return false unless u.mouse_trigger?(:left)
      x,y=u.mouse_press_position || point
      @panels[:launcher].visible=false if @panels[:launcher] && ![:launcher,:menu_button].include?(top)
      @panels[:bag].visible=@inventory_open
      (@panel_order || @panels.keys).reverse.each do |key|
        p=@panels[key];next unless p.hit?(x,y)
        raise_panel(key) if @panel_order
        rx,ry=x-p.x,y-p.y
        if popup_keys.include?(key) && ry<34
          if rx>p.width-38
            close_window(key)
          elsif ([:bag,:character]+WINDOW_NAMES.keys).include?(key);@drag=[key,rx,ry];p.move(point[0]-rx,point[1]-ry)
          end
        elsif key==:bag;inventory_click(state,rx,ry)
        elsif WINDOW_NAMES.key?(key)||key==:launcher;window_click(key,rx,ry)
        elsif key==:chat && ry>=156
          chat_focus(true)
          u.ime_open=!u.ime_open? if rx>=364
        elsif key==:menu
          if ry>=148;@quit=true
          elsif ry>=100;p.visible=false
          end
        elsif key==:menu_button;open_window(:launcher)
        elsif key==:quicks
          index=QUICK_KEYS.each_index.find{|i|r=quickslot_rect(i);rx>=r.x && rx<r.x+r.width && ry>=r.y && ry<r.y+r.height}
          begin_quick_drag(quickslot_bindings(state)[index],index) if index && quickslot_action(index,state) && !@chat_open && !@form && state['self']['hp']>0
        end
        update_quick_drag(state,point) if @quick_drag
        @next_move=nil;return true
      end
      hit=state['monsters'].find do |m|
        a=@avatars["monster_#{m['id']}"];a && (x-a.screen_x).abs<24 && y.between?(a.screen_y-56,a.screen_y+8)
      end
      @target_id=hit['id'] if hit
      false
    end
    def suspend_movement
      @direction_buffer=nil;@next_move=nil;@pad_direction=0
      if @avatars && @connection && (avatar=@avatars[@connection.id])
        avatar.preview(@connection,false);avatar.flush(@connection,true)
      end
    end
    def movement_input
      u=Lunetile::UIInput;held=u.direction4;tap=u.direction_trigger
      pad=held==0 && tap==0 ? Input.dir4 : 0
      tap=pad if pad!=0 && pad!=(@pad_direction||0)
      @pad_direction=pad;held=pad if held==0
      now=LunetileMMO.now
      @direction_buffer=[tap,now] if tap!=0
      @direction_buffer=nil if @direction_buffer && now-@direction_buffer[1]>0.25
      [held,now]
    end
    def handle_movement(input=nil)
      held,now=input||movement_input
      direction=@direction_buffer ? @direction_buffer[0] : held
      avatar=@avatars.fetch(@connection.id)
      if direction==0;avatar.preview(@connection,false);avatar.flush(@connection);return;end
      @movement_fraction=(@movement_fraction||0)+1000.0/Graphics.logic_rate
      ms=@movement_fraction.floor;@movement_fraction-=ms
      status=avatar.advance(direction,@connection.state,ms)
      @direction_buffer=nil unless status==:waiting
      avatar.preview(@connection,status==:moved)
      avatar.flush(@connection)
      suspend_movement if [:recovering,:dead].include?(status)
    end
    def dispose
      return if @disposed;@disposed=true
      cancel_quick_drag
      Lunetile::UIInput.text_input=false if defined?(Lunetile::UIInput)
      dispose_combat_effects if @combat_effects
      @minimap&.dispose;@minimap=nil
      @connection&.close;@sprites&.each_value(&:dispose);@spriteset&.dispose
      @panels&.each_value(&:dispose)
      @labels&.each_value{|sprite,_|sprite.bitmap.dispose;sprite.dispose}
      @floats&.each{|sprite,*_|sprite.bitmap.dispose;sprite.dispose}
      Graphics.background_update=@previous_background unless @previous_background.nil?
    end
  end
  def self.run
    config=JSON.parse(File.read('client.json',encoding:'UTF-8'));connection=Entry.new(config).main
    return unless connection
    scene=Scene.new(config,connection);scene.main
  rescue StandardError => error
    scene&.dispose
    panel=Panel.new(Graphics.width/2-360,Graphics.height/2-80,720,160,'연결 안내')
    panel.redraw(error.message){|p|p.label(20,50,680,32,error.message,Theme::TEXT,16);p.label(20,110,680,24,'Esc로 종료하세요. 접속 프로필은 보존됩니다.',Theme::MUTED,14)}
    Graphics.transition
    loop {Graphics.update;Input.update;break if Input.trigger?(Input::B)}
    panel.dispose
  end
end
