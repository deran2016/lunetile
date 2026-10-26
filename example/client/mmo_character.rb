module LunetileMMO
  class CombatCharacter < Sprite_Character
    def appearance(data,state)
      @portal=!!data['portal']
      definition=state.dig('progression','equipment').to_a.find{|d|d['id']==data['weapon'] && d['slot']=='weapon'}
      icon=definition && definition['icon'];return if icon==@weapon_icon
      @weapon_icon=icon
      if icon
        @held_weapon ||= Sprite.new(self.viewport)
        @held_weapon.bitmap=RPG::Cache.icon(icon)
        @held_weapon.ox=@held_weapon.bitmap.width*0.75;@held_weapon.oy=@held_weapon.bitmap.height*0.75
      else
        @held_weapon&.dispose;@held_weapon=nil
      end
    end
    def attack_motion(event)
      @cast=[LunetileMMO.now,event]
    end
    def update
      # Attack poses override src_rect; let the stock cache restore it, including the final frame.
      @lunetile_bitmap=nil if @cast
      super
      self.angle=0;self.zoom_x=self.zoom_y=1.0
      if @portal
        self.src_rect.set((LunetileMMO.now*5).to_i%4*@cw,0,@cw,@ch)
        self.oy=(@ch*0.93).round;self.zoom_x=self.zoom_y=72.0/@ch
        return
      end
      t=nil;event=nil
      if @cast
        began,event=@cast;t=(LunetileMMO.now-began)/(event['motion_ms']/1000.0)
        if t>=1;@cast=nil;t=nil;event=nil
        else
          direction=event['direction'];pulse=Math.sin(t*Math::PI)
          fx,fy={2=>[0,1],4=>[-1,0],6=>[1,0],8=>[0,-1]}[direction]
          self.src_rect.set((t<0.65 ? 2 : 1)*@cw,(direction-2)/2*@ch,@cw,@ch)
          self.x+=fx*3*pulse;self.y+=fy*2*pulse
          self.angle=(direction==4 ? -1 : 1)*(event['motion']=='magic' ? 5 : 11)*pulse
          self.zoom_x=1+0.06*pulse;self.zoom_y=1-0.04*pulse
        end
      end
      update_held_weapon(t,event) if @held_weapon
    end
    def update_held_weapon(t,event)
      direction=event ? event['direction'] : @character.direction
      side=[4,8].include?(direction) ? -1 : 1
      bob=event ? 0 : [1,0,-1,0][@character.pattern%4]
      weapon=@held_weapon;weapon.x=self.x+side*@cw*0.22;weapon.y=self.y-@ch*0.35+bob
      weapon.z=self.z+(direction==8 ? -1 : 1);weapon.opacity=self.opacity;weapon.visible=self.visible
      weapon.zoom_x=weapon.zoom_y=1.15
      weapon.angle={2=>-85,4=>-10,6=>-80,8=>10}[direction]+self.angle
      if event
        pulse=Math.sin(t*Math::PI)
        if event['motion']=='slash'
          fx,fy={2=>[0,1],4=>[-1,0],6=>[1,0],8=>[0,-1]}[direction]
          weapon.x+=fx*7*pulse;weapon.y+=fy*7*pulse
          weapon.angle={2=>135,4=>45,6=>-135,8=>-45}[direction]+(1-2*t)*65
        else
          weapon.y-=4*pulse;weapon.angle+=20*pulse
        end
      end
    end
    def dispose
      @held_weapon&.dispose;@held_weapon=nil
      super
    end
  end

  class Avatar < Game_Character
    def initialize(data,speed=4)
      super()
      @character_name = data.fetch('character')
      @through = true
      @move_speed = speed
      moveto(data.fetch('position').fetch('x'),data.fetch('position').fetch('y'))
      @last_position = [@x,@y]
      @positions = []
      @direction = data.fetch('direction',2)
      if data['motion']
        @motion=true;@path_seq=0;@positions=[]
        source=data['relay'] || data['motion'];set_motion(source['x'],source['y'])
        @last_position=[@x,@y]
        @path_seq=(source['path']||[]).last&.fetch('seq') || 0
        @relay=!!data['relay'];@motion_credit=0
      end
    end
    def set_motion(x,y)
      @real_x=x*128.0/1000;@real_y=y*128.0/1000
      @x=x/1000.0;@y=y/1000.0
    end
    def reset_position(position)
      moveto(position.fetch('x'),position.fetch('y'))
      @positions.clear;@last_position=[@x,@y];@speculating=false;@lead=nil;@motion_credit=0
    end
    def apply(data)
      if @motion
        source=data['relay'] || data['motion']
        if source['epoch']!=(@remote_epoch||0)
          set_motion(source['x'],source['y']);@positions.clear;@last_position=[@x,@y]
          @path_seq=(source['path']||[]).last&.fetch('seq') || 0;@speculating=false;@motion_credit=0
        end
        @remote_epoch=source['epoch'];fresh=[]
        (source['path']||[]).each do |p|
          next if p['seq']<=@path_seq
          @path_seq=p['seq'];target=[p['x']/1000.0,p['y']/1000.0]
          fresh << target unless target==@last_position
          @last_position=target
        end
        if @speculating && (!fresh.empty? || !source['moving'])
          # Retain the real corner if a short extrapolation went past a turn or stop.
          anchor=@spec_origin;current=[@real_x/128.0,@real_y/128.0]
          while !fresh.empty? && on_segment?(fresh.first,anchor,current)
            anchor=fresh.shift
          end
          ahead=source['moving'] && [source['lead_x']/1000.0,source['lead_y']/1000.0]
          following=fresh.first || ahead
          if !following || !on_segment?(current,anchor,following)
            @positions << anchor unless anchor==current
          end
          @speculating=false
        end
        @positions.concat(fresh)
        raise '이동 경로 수신이 너무 늦습니다. 다시 접속하세요.' if @positions.size>256
        @relay=!!data['relay'];@lead=source['moving'] ? [source['lead_x']/1000.0,source['lead_y']/1000.0] : nil
        @relay_at=LunetileMMO.now
        @direction=source.fetch('direction',data['direction']) if @positions.empty? && !@lead
        return
      end
      p = data.fetch('position')
      target = [p.fetch('x'),p.fetch('y')]
      direction = data.fetch('direction',2)
      if target == @last_position
        @direction = direction if !moving? && @positions.empty?
        return
      end
      x,y = @last_position
      # shortcut: snapshots cannot recover unseen turns after a long stall; infer the last corner from facing.
      if x != target[0] && y != target[1]
        @positions << ([2,8].include?(direction) ? [target[0],y] : [x,target[1]])
      end
      @positions << target
      raise '이동 상태 수신이 너무 늦습니다. 다시 접속하세요.' if @positions.size > 64
      @last_position = target
    end

    def update
      if @motion
        old=[@real_x,@real_y];rate=Graphics.logic_rate
        @motion_credit=[(@motion_credit||0)+640.0/rate,1280.0/rate].min
        budget=[@motion_credit,720.0/rate].min;axis=nil
        loop do
          target=@positions.first
          if !target && @lead && LunetileMMO.now-@relay_at<0.15
            unless @speculating;@spec_origin=@last_position;@speculating=true;end
            target=@lead
          end
          break unless target
          x,y=target;dx=x*128-@real_x;dy=y*128-@real_y
          raise '서버 이동 경로가 대각선입니다.' if dx.abs>0.0001 && dy.abs>0.0001
          if dx.abs<0.0001 && dy.abs<0.0001
            break if @positions.empty?
            @positions.shift;next
          end
          direction=dx.abs>0.0001 ? (dx<0 ? 4 : 6) : (dy<0 ? 8 : 2)
          break if axis && axis!=direction || budget<0.0001
          axis=direction;@direction=direction
          distance=[dx.abs+dy.abs,budget].min
          @real_x+=dx<0 ? -distance : distance if dx.abs>0.0001
          @real_y+=dy<0 ? -distance : distance if dy.abs>0.0001
          budget-=distance;@motion_credit-=distance
        end
        @x=@real_x/128.0;@y=@real_y/128.0
        @motion_credit=0 if old==[@real_x,@real_y]
        animate_motion(old!=[@real_x,@real_y]);return
      end
      unless moving? || @positions.empty?
        x,y = @positions.shift
        @direction = x < @x ? 4 : 6 if x != @x
        @direction = y < @y ? 8 : 2 if y != @y
        @x,@y = x,y
        increase_steps
      end
      super
    end
    def on_segment?(p,a,b)
      e=0.00001
      (p[0]-a[0]).abs<e && (p[0]-b[0]).abs<e && p[1]>= [a[1],b[1]].min-e && p[1]<= [a[1],b[1]].max+e ||
        (p[1]-a[1]).abs<e && (p[1]-b[1]).abs<e && p[0]>= [a[0],b[0]].min-e && p[0]<= [a[0],b[0]].max+e
    end
    def animate_motion(walking)
      @walking=walking
      if walking
        @stop_count=0;@anime_count+=40.0/Graphics.logic_rate
        if @anime_count>=4;@pattern=(@pattern+1)%4;@anime_count-=4;end
      else
        @stop_count+=1;@pattern=@original_pattern
      end
    end
    def moving?;@motion ? !!@walking || !@positions.empty? : super;end
  end

  class LocalAvatar < Avatar
    attr_reader :pending_moves
    def destination;[@px/1000.0,@py/1000.0];end
    def initialize(data)
      super(data)
      @motion=true;@px=data.fetch('motion').fetch('x');@py=data['motion']['y']
      @epoch=data['motion']['epoch'];@pending_moves=[];@parts=[];@unsent_ms=0;@pending_ms=0;@ack=0
      @trail=[[@px,@py]];@trace=[];@preview_step=@preview_elapsed=0;@recovering=false;@recovery=[]
    end
    def recovering?;@recovering;end
    def passable_motion?(x,y,nx,ny,direction,state)
      tx=(x+500).div(1000);ty=(y+500).div(1000);ux=(nx+500).div(1000);uy=(ny+500).div(1000)
      return true if [tx,ty]==[ux,uy]
      n=state.fetch('navigation');return false unless n['map_id']==state['self']['position']['map_id']
      values=[[tx,ty],[ux,uy]].map do |cx,cy|
        row=n['passages'][cy-n['y']] if cy>=n['y']
        row[cx-n['x']] if row && cx>=n['x']
      end
      a,b=values;return false unless a && b
      bit,reverse={2=>[1,8],4=>[2,4],6=>[4,2],8=>[8,1]}.fetch(direction)
      a&bit==0 && b&reverse==0 && b!=15 && !state['npcs'].any?{|npc|p=npc['position'];p['x']==ux && p['y']==uy}
    end
    def advance(direction,state,ms)
      return :recovering if @recovering
      return :dead if state['self']['hp']==0
      return :waiting if @pending_ms+ms>600
      dx,dy={2=>[0,5],4=>[-5,0],6=>[5,0],8=>[0,-5]}.fetch(direction)
      before=[@px,@py];@direction=direction
      ms.times do
        nx,ny=@px+dx,@py+dy
        break unless passable_motion?(@px,@py,nx,ny,direction,state)
        @px,@py=nx,ny
      end
      @walked=before!=[@px,@py];set_motion(@px,@py)
      return :blocked unless @walked
      @trail << [@px,@py];@pending_ms+=ms;@unsent_ms+=ms
      @preview_step+=1;@preview_elapsed+=ms;@trace << {'step'=>@preview_step,'ms'=>ms,'direction'=>direction}
      if @parts.last && @parts.last['direction']==direction;@parts.last['ms']+=ms
      else;@parts << {'direction'=>direction,'ms'=>ms}
      end
      :moved
    end
    def preview(connection,moving,force=false)
      return if @recovering
      @preview_moving=moving
      signature=[@preview_step,moving,@direction]
      return if signature==@preview_signature
      return if !force && @preview_at && LunetileMMO.now-@preview_at<1.0/30
      connection.send_message({'type'=>'preview','origin'=>@trail.first,'epoch'=>@epoch,'elapsed'=>@preview_elapsed,
        'parts'=>@trace,'moving'=>moving,'direction'=>@direction})
      @preview_at=LunetileMMO.now;@preview_signature=signature;@preview_moving=moving
    end
    def flush(connection,force=false)
      return if @parts.empty?
      @flush_at||=LunetileMMO.now+0.2
      return unless force || @parts.size>=32 || @unsent_ms>=200-1000.0/Graphics.logic_rate || LunetileMMO.now>=@flush_at
      preview(connection,!!@preview_moving,true)
      origin=@pending_moves.empty? ? @trail.first : @pending_moves.last[1]
      seq=connection.send_message({'type'=>'move','origin'=>origin,'epoch'=>@epoch,'parts'=>@parts})
      @pending_moves << [seq,@trail.last,@unsent_ms]
      @parts=[];@unsent_ms=0;@flush_at=nil
    end
    def reset_position(position)
      @discard_until=[@discard_until||0,@pending_moves.last&.first || @ack].max
      @pending_moves.clear;@parts=[];@pending_ms=@unsent_ms=0;@flush_at=nil
      @px=position['x']*1000;@py=position['y']*1000;set_motion(@px,@py)
      @trail=[[@px,@py]];@trace=[];@preview_step=@preview_elapsed=0;@preview_signature=@preview_at=nil;@recovery=[];@positions=[];@walked=@walking=false;@recovering=false;@path_seq=0
    end
    def reconcile(state)
      data=state['self'];motion=data.fetch('motion');ack=state.fetch('move_ack');point=[motion['x'],motion['y']]
      if motion['epoch']!=@epoch
        reset_position(data['position']);@epoch=motion['epoch'];@px,@py=point;set_motion(*point);@trail=[point]
      end
      if ack['seq']>@ack
        expected=@pending_moves.find{|seq,*_|seq==ack['seq']}
        @pending_moves.reject!{|seq,*_|seq<=ack['seq']};@ack=ack['seq']
        if expected
          @pending_ms-=expected[2]
          if !@recovering && ack['accepted'] && expected[1]==point
            cut=@trail.index{|p|p.equal?(expected[1])};if cut;@trail.shift(cut);@trace.shift(cut);end
            @path_seq=(motion['path']||[]).last&.fetch('seq') || @path_seq
          elsif !@recovering
            @recovering=true;@recovery=@trail[0...-1].reverse
            @pending_ms-=@unsent_ms;@parts=[];@unsent_ms=0;@flush_at=nil
          end
        elsif ack['seq']>(@discard_until||0)
          raise '대기 중이지 않은 이동 응답입니다. 다시 접속하세요.'
        end
      end
      if @recovering
        (motion['path']||[]).each do |p|
          next if p['seq']<=@path_seq
          @path_seq=p['seq'];@recovery << [p['x'],p['y']]
        end
      end
      @direction=data['direction'] if @pending_moves.empty? && @parts.empty? && !@recovering
    end
    def update
      if @recovering && @pending_moves.empty?
        target=@recovery.first
        if target
          dx=target[0]-@px;dy=target[1]-@py
          raise '이동 복원 경로가 대각선입니다.' if dx!=0 && dy!=0
          step=5000.0/Graphics.logic_rate
          @direction=dx<0 ? 4 : 6 if dx!=0;@direction=dy<0 ? 8 : 2 if dy!=0
          @px+=[[dx,-step].max,step].min;@py+=[[dy,-step].max,step].min
          if (@px-target[0]).abs<0.001 && (@py-target[1]).abs<0.001
            @px,@py=target;@recovery.shift
          end
          set_motion(@px,@py);@walked=dx!=0 || dy!=0
        else
          @recovering=false;@trail=[[@px,@py]];@trace=[];@preview_signature=nil
        end
      end
      animate_motion(!!@walked);@walked=false
    end
  end

  def self.setup_game(map_id)
    $data_actors = load_data('Data/Actors.rxdata')
    $data_classes = load_data('Data/Classes.rxdata')
    $data_skills = load_data('Data/Skills.rxdata')
    $data_items = load_data('Data/Items.rxdata')
    $data_weapons = load_data('Data/Weapons.rxdata')
    $data_armors = load_data('Data/Armors.rxdata')
    $data_enemies = load_data('Data/Enemies.rxdata')
    $data_troops = load_data('Data/Troops.rxdata')
    $data_states = load_data('Data/States.rxdata')
    $data_animations = load_data('Data/Animations.rxdata')
    $data_tilesets = load_data('Data/Tilesets.rxdata')
    $data_common_events = load_data('Data/CommonEvents.rxdata')
    $data_system = load_data('Data/System.rxdata')
    $game_temp = Game_Temp.new
    $game_system = Game_System.new
    $game_switches = Game_Switches.new
    $game_variables = Game_Variables.new
    $game_self_switches = Game_SelfSwitches.new
    $game_screen = Game_Screen.new
    $game_actors = Game_Actors.new
    $game_party = Game_Party.new
    $game_troop = Game_Troop.new
    $game_map = Game_Map.new
    $game_map.setup(map_id)
    $game_map.events.clear
    $game_player = Game_Player.new
    $game_party.setup_starting_members
    $game_player.refresh
  end

end
