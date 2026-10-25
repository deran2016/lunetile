module LunetileMMO
  class Scene
    def attack(skill)
      state=@connection.state
      return false if !state || @chat_open || combat_window_open? || state['self']['hp']==0
      definition=state['skills'].find{|s|s['id']==skill};return false unless definition
      now=LunetileMMO.now;@attack_ready_at||={}
      return false if now<@attack_ready_at.fetch(skill,0) || state['cooldowns'].fetch(skill,0)>0
      if state['self']['mp']<definition['mp_cost']
        push_message('MP가 부족합니다.',Theme::GOLD) unless @last_attack_notice==skill
        @last_attack_notice=skill;return false
      end
      @last_attack_notice=nil
      @avatars && @avatars[@connection.id]&.flush(@connection,true)
      @connection.send_message({'type'=>'attack','skill_id'=>skill,'direction'=>@aim_direction || state['self']['direction']})
      @attack_ready_at[skill]=now+definition['cooldown_ms']/1000.0
      true
    end
    def combat_window_open?
      !!@form || !!@chat_open
    end
    def combat_active?
      @active_window_api ||= Win32API.new('user32','GetActiveWindow',[],'L')
      @foreground_api ||= Win32API.new('user32','GetForegroundWindow',[],'L')
      window=@active_window_api.call
      window!=0 && window==@foreground_api.call
    end
    def physical_attack_down?(key)
      @physical_key_api ||= Win32API.new('user32','GetAsyncKeyState',['I'],'I')
      (@physical_key_api.call(key.to_s.upcase.ord)&0x8000)!=0
    end
    def suspend_combat
      cancel_quick_drag
      @combat_blocked=QUICK_KEYS.to_h{|key|[key,true]}
    end
    def quickslot_bindings(state=@connection.state)
      @connection.respond_to?(:quickslots) ? @connection.quickslots : LunetileMMO.default_quickslots(state)
    end
    def quickslot_action(index,state=@connection.state)
      binding=quickslot_bindings(state)[index];return unless binding
      kind,id=binding.split(':',2)
      if kind=='skill'
        return unless state['skills'].any?{|s|s['id']==id} && (id=='basic' || !state['progress'] || learned_active_skill?(id,state))
      else
        return unless state.fetch('items',[]).any?{|item|item['id']==id}
      end
      [kind,id]
    end
    def use_quickslot(index)
      return false if @chat_open || @form || @connection.state.dig('self','hp')==0
      kind,id=quickslot_action(index);return false unless id
      kind=='skill' ? attack(id) : use_item(id)
    end
    def assign_quickslot(index,id=nil)
      return false unless index.is_a?(Integer) && index.between?(0,QUICK_KEYS.size-1)
      state=@connection.state
      if id && !learned_active_skill?(id,state)
        push_message('습득한 액티브 스킬만 등록할 수 있습니다.',Theme::GOLD);return false
      end
      slots=quickslot_bindings(state).dup;slots[index]=id && "skill:#{id}"
      save_quickslot_layout(slots)
    end
    def learned_active_skill?(id,state)
      rule=state.dig('progression','skills').to_a.find{|s|s['id']==id}
      rule && !rule['passive'] && state.dig('progress','skills',id).to_i>0
    end
    def save_quickslot_layout(slots)
      @connection.save_quickslots(slots);suspend_combat
      push_message('퀵슬롯 배치를 저장했습니다.',Theme::CYAN);true
    rescue SystemCallError,IOError => error
      push_message("퀵슬롯 저장 실패: #{error.message}",Theme::GOLD);false
    end
    def repeat_combat
      @combat_blocked||={};u=Lunetile::UIInput
      QUICK_KEYS.each{|key|@combat_blocked[key]=false unless physical_attack_down?(key)}
      actions=QUICK_KEYS.each_index.map{|i|quickslot_action(i)}
      index=QUICK_KEYS.each_index.reverse_each.find{|i|actions[i]&.first=='skill' && (u.key_press?(QUICK_KEYS[i])||u.key_trigger?(QUICK_KEYS[i]))}
      use_quickslot(index) if index && !@combat_blocked[QUICK_KEYS[index]]
      QUICK_KEYS.each_with_index{|key,i|use_quickslot(i) if actions[i]&.first=='item' && u.key_trigger?(key) && !@combat_blocked[key]}
    end
    def setup_combat_effects
      @particles=ParticleSystem.new
      @combat_effects=[];@effect_counts={'attack'=>0,'hit'=>0,'ghost'=>0};@effect_cache={};@throw_effects={}
      ['slash','magic','spark','impact_magic','explosion'].each do |kind|
        @effect_cache[kind]=8.times.map do |frame|
          size=kind=='explosion' ? 128 : ['slash','magic'].include?(kind) ? 256 : 80;b=Bitmap.new(size,size);center=size/2;t=frame/7.0
          if kind=='slash' || kind=='magic'
            color=kind=='slash' ? Color.new(255,241,175,235) : Color.new(91,217,255,220)
            radii=kind=='slash' ? [30,35,40,45] : [20+60*t,28+65*t,36+70*t]
            radii.each do |radius|
              45.times do |i|
                angle=(-50+i*100.0/44+(kind=='slash' ? (t-0.5)*35 : 0))*Math::PI/180
                x=center+Math.cos(angle)*radius;y=center+Math.sin(angle)*radius
                b.fill_rect(x.to_i,y.to_i,kind=='slash' ? 4 : 3,kind=='slash' ? 4 : 3,color)
              end
            end
            if kind=='magic'
              5.times{|i|b.fill_rect(center+12+(i*17+t*35).to_i,center-3-i%2*4,12,3,Color.new(222,253,255,210))}
            end
          elsif kind=='explosion'
            80.times do |i|
              angle=i*Math::PI/40;radius=10+t*44
              b.fill_rect((center+Math.cos(angle)*radius).to_i,(center+Math.sin(angle)*radius).to_i,5,5,Color.new(255,90+(140*t).to_i,40,230))
            end
            b.fill_rect(center-8,center-8,16,16,Color.new(255,235,140,(255*(1-t)).to_i))
          else
            color=kind=='spark' ? Color.new(255,222,113,245) : Color.new(125,225,255,245)
            8.times do |i|
              angle=i*Math::PI/4;radius=5+t*22
              7.times{|j|x=center+Math.cos(angle)*(radius+j);y=center+Math.sin(angle)*(radius+j);b.fill_rect(x.to_i,y.to_i,3,3,color)}
            end
            b.fill_rect(center-3,center-3,7,7,Color.new(255,255,255,(235*(1-t)).to_i))
          end
          b
        end
      end
    end
    def spawn_combat_effect(kind,position,duration,direction=6,source=nil,icon=nil,range=1,shape='fan')
      frames=@effect_cache.fetch(kind);sprite=Sprite.new(@viewport);sprite.bitmap=frames.first
      sprite.ox=sprite.oy=frames.first.width/2;sprite.z=950;sprite.blend_type=1
      sprite.angle={6=>0,2=>270,4=>180,8=>90}.fetch(direction,0)
      sprite.zoom_x=sprite.zoom_y=range if kind=='slash'
      sprite.zoom_x=sprite.zoom_y=range if kind=='explosion'
      sprite.zoom_x=sprite.zoom_y=range/3.0 if kind=='magic'
      sprite.zoom_y=0.18 if shape=='line'
      @combat_effects << {sprite:sprite,weapon:nil,frames:frames,began:LunetileMMO.now,duration:duration,
        position:position,source:source,direction:direction,kind:kind}
    end
    def play_cast(event)
      @effect_counts['attack']+=1
      @sprites[event['source']]&.attack_motion(event)
      @particles&.emit(event['particles'],event['position'],direction:event['direction'],source:event['source'],seed:event['seq'])
      if event['projectile'];play_projectile(event['projectile']);return;end
      spawn_combat_effect(event['motion'],event['position'],event['motion_ms']/1000.0,event['direction'],event['source'],event['icon'],event['range'],event.fetch('shape','fan'))
    end
    def projectile_pose(data,elapsed_ms)
      t=(elapsed_ms.to_f/data['flight_ms']).clamp(0,1);a=data['position'];b=data['target']
      [a['x']+(b['x']-a['x'])*t,a['y']+(b['y']-a['y'])*t,16*(1-t)+192*t*(1-t)]
    end
    def play_projectile(data)
      began=LunetileMMO.now-data['elapsed_ms']/1000.0
      if (effect=@throw_effects[data['id']]);effect[:began]=[effect[:began],began].min;return;end
      radius=data['radius'];size=(radius*2+1)*32
      marker=Sprite.new(@viewport);marker.bitmap=Bitmap.new(size,size);marker.ox=marker.oy=size/2;marker.z=1
      data['cells'].each do |p|
        x=(p['x']-data['target']['x']+radius)*32;y=(p['y']-data['target']['y']+radius)*32
        marker.bitmap.fill_rect(x+1,y+1,30,30,Color.new(225,25,35,110))
        [[x,y,32,2],[x,y+30,32,2],[x,y,2,32],[x+30,y,2,32]].each{|r|marker.bitmap.fill_rect(*r,Color.new(255,45,55,210))}
      end
      sprite=Sprite.new(@viewport);sprite.bitmap=RPG::Cache.icon(data['icon']);sprite.ox=sprite.bitmap.width/2;sprite.oy=sprite.bitmap.height/2;sprite.z=950
      @throw_effects[data['id']]={sprite:sprite,marker:marker,data:data,began:began}
    end
    def remove_projectile(id)
      if effect=@throw_effects.delete(id);effect[:marker].bitmap.dispose;effect[:marker].dispose;effect[:sprite].dispose;end
    end
    def clear_projectiles
      @throw_effects&.keys&.each{|id|remove_projectile(id)}
    end
    def sync_projectiles(state)
      data=state.fetch('projectiles',[])
      data.each{|p|play_projectile(p)}
      (@throw_effects.keys-data.map{|p|p['id']}).each{|id|remove_projectile(id)}
    end
    def update_projectile_effects
      @throw_effects.each_value do |effect|
        data=effect[:data];elapsed=(LunetileMMO.now-effect[:began])*1000;x,y,height=projectile_pose(data,elapsed)
        sprite=effect[:sprite];sprite.x=(x*128-$game_map.display_x)/4+16;sprite.y=(y*128-$game_map.display_y)/4+16-height;sprite.angle=elapsed<data['flight_ms'] ? elapsed/data['flight_ms']*360 : 0
        marker=effect[:marker];marker.x=(data['target']['x']*128-$game_map.display_x)/4+16;marker.y=(data['target']['y']*128-$game_map.display_y)/4+16
        marker.opacity=(190+50*Math.sin(elapsed*Math::PI/160)).to_i
      end
    end
    def play_hit(event)
      @effect_counts['hit']+=1
      id=event['monster'] ? "monster_#{event['target']}" : event['target'];target=@sprites[id];avatar=@avatars[id]
      target&.flash(Color.new(255,255,255,210),6)
      position=event['position'] || (avatar && {'x'=>avatar.real_x/128.0,'y'=>avatar.real_y/128.0})
      return unless position
      @particles&.emit(event['particles'],position,intensity:0.3,scale:0.55,seed:event['seq'])
      spawn_combat_effect(event['hit_effect']=='magic' ? 'impact_magic' : 'spark',position,0.22)
      if event['killed'] && target && avatar
        ghost=Sprite.new(@viewport);ghost.bitmap=target.bitmap
        r=target.src_rect;ghost.src_rect.set(r.x,r.y,r.width,r.height);ghost.ox=target.ox;ghost.oy=target.oy;ghost.z=target.z
        ghost.color=Color.new(255,255,255,150)
        @combat_effects << {sprite:ghost,weapon:nil,frames:nil,began:LunetileMMO.now,duration:0.2,
          position:{'x'=>avatar.real_x/128.0,'y'=>avatar.real_y/128.0},direction:6,kind:'ghost'}
        @effect_counts['ghost']+=1
      end
    end
    def update_combat_effects
      now=LunetileMMO.now
      @particles&.update(@avatars)
      update_projectile_effects if @throw_effects
      @combat_effects.delete_if do |effect|
        t=(now-effect[:began])/effect[:duration];sprite=effect[:sprite];weapon=effect[:weapon]
        if t>=1
          weapon&.dispose;sprite.dispose;true
        else
          sprite.bitmap=effect[:frames][(t*8).to_i.clamp(0,7)] if effect[:frames]
          avatar=effect[:source] && @avatars[effect[:source]]
          position=effect[:position]
          x=avatar ? avatar.screen_x : (position['x']*128-$game_map.display_x)/4+16
          y=avatar ? avatar.screen_y : (position['y']*128-$game_map.display_y)/4+32
          sprite.x=x;sprite.y=y-(effect[:kind]=='ghost' ? 0 : effect[:kind]=='explosion' ? 16 : 20);sprite.opacity=(255*(1-t)).to_i
          if weapon
            fx,fy={2=>[0,1],4=>[-1,0],6=>[1,0],8=>[0,-1]}[effect[:direction]]
            weapon.x=x+fx*12;weapon.y=y-18+fy*8;weapon.angle=sprite.angle+90-t*160;weapon.opacity=sprite.opacity
          end
          false
        end
      end
    end
    def dispose_combat_effects
      @particles&.dispose
      clear_projectiles
      @combat_effects.each{|e|e[:weapon]&.dispose;e[:sprite].dispose};@combat_effects.clear
      @effect_cache.each_value{|frames|frames.each(&:dispose)};@effect_cache.clear
    end
    def use_item(id)
      @connection.send_message({'type'=>'use','item_id'=>id}) if @connection.state['inventory'].fetch(id,0)>0
    end
    def receive_events(state)
      @event_seq ||= state['event_seq']
      hits=state['events'].select{|e|e['seq']>@event_seq&&e['kind']=='damage'&&e['monster']&&e['source']==@connection.id}
      unless hits.empty?
        candidates=state.fetch('monsters',[]).select{|m|hits.any?{|e|e['target']==m['id']}&&m['hp']>0}
        origin=state['self']['position']
        @target_id=candidates.find{|m|m['id']==@target_id}&.fetch('id') || candidates.min_by{|m|p=m['position'];[(p['x']-origin['x']).abs+(p['y']-origin['y']).abs,m['id']]}&.fetch('id')
      end
      state['events'].each do |event|
        next if event['seq']<=@event_seq
        case event['kind']
        when 'attack';play_cast(event)
        when 'explosion'
          remove_projectile(event['id']) if @throw_effects
          @effect_counts['explosion']=@effect_counts.fetch('explosion',0)+1
          spawn_combat_effect('explosion',event['position'],0.35,6,nil,nil,event['radius'])
          @particles&.emit(event['particles'],event['position'],scale:event['radius'],seed:event['seq'])
        when 'respawn'
          avatar=@avatars[event['target']];avatar.reset_position(event['position']) if avatar
          suspend_movement if event['target']==@connection.id
        when 'damage'
          play_hit(event) if @combat_effects
          avatar=@avatars[event['monster'] ? "monster_#{event['target']}" : event['target']]
          if avatar || event['position']
            sprite=Sprite.new;sprite.z=1200;sprite.bitmap=Bitmap.new(100,36);sprite.bitmap.font.name='맑은 고딕';sprite.bitmap.font.size=24;sprite.bitmap.font.bold=true
            sprite.bitmap.font.color=event['monster'] ? Theme::GOLD : Theme::RED;sprite.bitmap.draw_text(0,0,100,36,event['amount'].to_s,1)
            @floats << [sprite,LunetileMMO.now,avatar ? avatar.real_x : event['position']['x']*128,avatar ? avatar.real_y : event['position']['y']*128]
          end
        when 'loot';push_message(event['text'],Theme::GOLD)
        when 'experience';push_message("경험치 +#{event['amount']}",Theme::GOLD)
        when 'level_up'
          text="LEVEL UP!  Lv.#{event['level']}";push_message(text,Theme::CYAN)
          avatar=@avatars && @avatars[@connection.id]
          if avatar
            sprite=Sprite.new;sprite.z=1200;sprite.bitmap=Bitmap.new(280,36);sprite.bitmap.font.name='맑은 고딕';sprite.bitmap.font.size=24;sprite.bitmap.font.bold=true
            sprite.bitmap.font.color=Theme::CYAN;sprite.bitmap.draw_text(0,0,280,36,text,1)
            @floats << [sprite,LunetileMMO.now,avatar.real_x,avatar.real_y]
          end
        when 'dialogue';@dialogue=event['text'];@panels[:dialogue].visible=true
        when 'death';push_message('쓰러졌습니다. 2초 후 마을에서 부활합니다.',Theme::RED) if event['target']==@connection.id
        end
      end
      @event_seq=state['event_seq']
    end
    def update_field_labels
      state=@connection.state;return unless state && @map_id
      entries=state['players'].map{|p|[p['id'],p]}+state['npcs'].map{|p|["npc_#{p['id']}",p]}+state['monsters'].map{|p|["monster_#{p['id']}",p]}
      entries+=portal_entities(state) if respond_to?(:portal_entities)
      ids=entries.map(&:first)
      (@labels.keys-ids).each{|id|sprite,_=@labels.delete(id);sprite.bitmap.dispose;sprite.dispose}
      entries.each do |id,data|
        avatar=@avatars[id];next unless avatar
        sprite,signature=@labels[id]
        unless sprite
          sprite=Sprite.new;sprite.z=900;sprite.bitmap=Bitmap.new(180,42);sprite.bitmap.font.name='맑은 고딕';sprite.bitmap.font.size=14
        end
        text="#{data['level'] ? "Lv.#{data['level']} " : ''}#{data['name']}"
        sig=[text,data['hp'],data['max_hp'],id=="monster_#{@target_id}"]
        if signature!=sig
          b=sprite.bitmap;b.clear
          Theme.outlined_text(b,2,2,176,24,text,id.start_with?('npc_') ? Theme::GOLD : sig[3] ? Theme::CYAN : Theme::TEXT,1)
          if data['hp']
            b.fill_rect(48,28,84,5,Color.new(15,20,30));b.fill_rect(48,28,(84*data['hp'].to_f/data['max_hp']).to_i,5,id.start_with?('monster_') ? Theme::RED : Theme::GREEN)
          end
          @labels[id]=[sprite,sig]
        end
        sprite.x=avatar.screen_x-90;sprite.y=avatar.screen_y-80
      end
      @floats.delete_if do |sprite,began,x,y|
        age=LunetileMMO.now-began
        if age>0.8;sprite.bitmap.dispose;sprite.dispose;true
        else;sprite.x=(x-$game_map.display_x)/4-sprite.bitmap.width/2;sprite.y=(y-$game_map.display_y)/4-55-age*35;sprite.opacity=(255*(1-age/0.8)).to_i;false
        end
      end
    end
  end
end
