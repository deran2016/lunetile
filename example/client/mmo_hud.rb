module LunetileMMO
  QUICK_KEYS=[:z,:x,:v,:f,:'1',:'2',:'3',:'4'].freeze
  def self.default_quickslots(state)
    ['skill:basic',"skill:#{state.dig('progress','quick_skill') || 'burst'}",nil,nil,'item:potion','item:mana_potion',nil,nil]
  end
  module Theme
    BG=Color.new(17,25,40,255); EDGE=Color.new(67,88,113); TEXT=Color.new(231,240,250)
    MUTED=Color.new(148,169,192); CYAN=Color.new(58,210,226); GOLD=Color.new(255,201,89)
    RED=Color.new(239,91,113); BLUE=Color.new(83,149,255); GREEN=Color.new(112,214,146)
    def self.outlined_text(bitmap,x,y,w,h,text,color,align=0)
      bitmap.font.color=Color.new(0,0,0)
      [-1,0,1].each{|dx|[-1,0,1].each{|dy|bitmap.draw_text(x+dx,y+dy,w,h,text,align) unless dx==0&&dy==0}}
      bitmap.font.color=color;bitmap.draw_text(x,y,w,h,text,align)
    end
  end
  class Panel
    attr_reader :sprite,:width,:height,:bitmap
    def initialize(x,y,w,h,title=nil,background:Theme::BG)
      @width,@height,@title=w,h,title
      @background=Bitmap.new(w,h)
      @background.fill_rect(0,0,w,h,Theme::EDGE)
      @background.fill_rect(1,1,w-2,h-2,background)
      @background.fill_rect(1,1,w-2,2,Theme::CYAN)
      @background.fill_rect(1,3,w-2,30,Color.new(26,39,58)) if title
      @background_sprite=Sprite.new;@background_sprite.bitmap=@background
      @sprite=Sprite.new;@sprite.x,@sprite.y=x,y;self.z=1500;self.alpha=238
      @background_sprite.x=x;@background_sprite.y=y
      @bitmap=Bitmap.new(w,h);@sprite.bitmap=@bitmap
      @bitmap.font.name='맑은 고딕';@bitmap.font.size=16
      redraw(nil) {}
    end
    def x;@sprite.x;end
    def y;@sprite.y;end
    def visible;@sprite.visible;end
    def visible=(v);@sprite.visible=v;@background_sprite.visible=v;@underlay.visible=v if @underlay;end
    def z=(v);@background_sprite.z=v;@sprite.z=v+2;@underlay.z=v+1 if @underlay;end
    def alpha=(v);@alpha=v;@background_sprite.opacity=v;@underlay.opacity=v if @underlay;end
    def underlay(bitmap,x,y)
      @underlay||=Sprite.new;@underlay.bitmap=bitmap;@underlay_offset=[x,y];@underlay.x=self.x+x;@underlay.y=self.y+y
      @underlay.z=@sprite.z-1;@underlay.opacity=@alpha;@underlay.visible=visible
    end
    def move(x,y)
      @sprite.x=[[x,0].max,Graphics.width-@width].min;@sprite.y=[[y,0].max,Graphics.height-@height].min
      @background_sprite.x=self.x;@background_sprite.y=self.y
      if @underlay;@underlay.x=self.x+@underlay_offset[0];@underlay.y=self.y+@underlay_offset[1];end
    end
    def hit?(x,y);visible && x>=self.x && y>=self.y && x<self.x+@width && y<self.y+@height;end
    def redraw(signature)
      return if signature && @signature==signature
      @signature=signature;@bitmap.clear
      if @title
        label(12,7,@width-48,22,@title,Theme::TEXT,16)
        label(@width-30,6,22,22,'×',Theme::MUTED,20)
      end
      yield self
    end
    def label(x,y,w,h,text,color=Theme::TEXT,size=16,align=0)
      @bitmap.font.color=color;@bitmap.font.size=size;@bitmap.draw_text(x,y,w,h,text,align)
    end
    def outlined_label(x,y,w,h,text,color=Theme::TEXT,size=16,align=0)
      @bitmap.font.size=size;Theme.outlined_text(@bitmap,x,y,w,h,text,color,align)
    end
    def bar(x,y,w,h,ratio,color)
      @bitmap.fill_rect(x,y,w,h,Color.new(8,14,25));@bitmap.fill_rect(x,y,(w*[[ratio,0].max,1].min).to_i,h,color)
    end
    def icon(x,y,name)
      return if name.to_s.empty?
      image=RPG::Cache.icon(name);@bitmap.blt(x,y,image,Rect.new(0,0,24,24))
    end
    def dispose;@underlay&.dispose;@background_sprite.dispose;@sprite.dispose;@bitmap.dispose;@background.dispose;end
  end

  class Minimap
    attr_reader :bitmap,:rect
    def initialize(map)
      @width,@height=map.width,map.height
      scale=[192.0/@width,106.0/@height].min
      w,h=[(@width*scale).round,1].max,[(@height*scale).round,1].max
      @rect=Rect.new(12+(192-w)/2,62+(106-h)/2,w,h)
      @bitmap=Bitmap.new(w,h)
      tileset=RPG::Cache.tileset(map.tileset_name)
      images=map.autotile_names.map{|name|name.empty? ? nil : RPG::Cache.autotile(name)}
      stamps={};groups={}
      @height.times do |y|
        @width.times do |x|
          left=x*w/@width;top=y*h/@height
          dest=Rect.new(left,top,(x+1)*w/@width-left,(y+1)*h/@height-top)
          next if dest.width==0 || dest.height==0
          map.data.zsize.times do |z|
            id=map.data[x,y,z];next unless id && id>=48
            priority=map.priorities[id] || 0
            (groups[priority>0 ? (y+priority+1)*32 : 0]||=[]) << [id,dest]
          end
        end
      end
      groups.keys.sort.each do |depth|
        groups[depth].each do |id,dest|
          if id>=384
            @bitmap.stretch_blt(dest,tileset,Rect.new((id-384)%8*32,(id-384)/8*32,32,32))
          elsif (image=images[id/48-1])
            if image.height==32
              @bitmap.stretch_blt(dest,image,Rect.new(0,0,32,32))
            else
              unless stamps[id]
                stamp=stamps[id]=Bitmap.new(32,32)
                RGSSXP::AUTOTILE_QUARTERS[id%48].each_with_index do |part,corner|
                  stamp.blt(corner%2*16,corner/2*16,image,Rect.new(part%6*16,part/6*16,16,16))
                end
              end
              @bitmap.stretch_blt(dest,stamps[id],stamps[id].rect)
            end
          end
        end
      end
    rescue StandardError
      @bitmap&.dispose;raise
    ensure
      stamps&.each_value(&:dispose)
    end
    def point(x,y)
      px=((x+0.5)*@rect.width/@width).floor;py=((y+0.5)*@rect.height/@height).floor
      [@rect.x+[[px,0].max,@rect.width-1].min,@rect.y+[[py,0].max,@rect.height-1].min]
    end
    def dispose;@bitmap.dispose;end
  end

  class Scene
    def setup_hud
      w,h=Graphics.width,Graphics.height
      @panels={status:Panel.new(16,h-64,w-164,48),chat:Panel.new(16,h-268,420,190,background:Color.new(17,25,40,255)),
        quicks:Panel.new(w-232,16,216,100),menu_button:Panel.new(w-132,h-64,116,48),
        map:Panel.new(w-232,124,216,184),target:Panel.new(w/2-160,16,320,76),
        bag:Panel.new(w-398,218,382,366,'인벤토리'),character:Panel.new(w/2-170,156,340,300,'캐릭터 정보'),
        dialogue:Panel.new(w/2-300,h-300,600,180,'마을 안내'),menu:Panel.new(w/2-150,210,300,198,'메뉴')}
      [:bag,:character,:dialogue,:menu,:target].each{|k|@panels[k].visible=false}
      @labels={};@floats=[];@messages=[];@draft='';@seen_chat=0;@chat_scroll=0
      @inventory_index=0;@inventory_open=false
      @status=@panels[:status];@hud=@status
    end
    def quickslot_rect(index)
      Rect.new(22+index%4*44,8+index/4*44,40,40)
    end
    def update_minimap
      map=$game_map;key=[map.map_id,map.width,map.height,map.data,map.tileset_name,map.autotile_names.dup]
      return if @minimap_key==key
      @minimap&.dispose;@minimap=nil
      @minimap=Minimap.new(map);@minimap_key=key
      @panels[:map].underlay(@minimap.bitmap,@minimap.rect.x,@minimap.rect.y)
    end
    def draw_hud
      return unless @panels
      now=LunetileMMO.now
      update_field_labels
      return if @last_hud && now-@last_hud<0.1
      @last_hud=now;s=@connection.state
      unless s
        @status.redraw('connecting'){|p|p.label(12,10,p.width-24,28,'서버에 접속하고 있습니다…',Theme::CYAN,16)}
        return
      end
      me=s['self'];@panels[:bag].visible=@inventory_open
      @status.redraw(me.values_at('name','level','hp','max_hp','mp','max_mp','exp','exp_next')) do |p|
        p.outlined_label(12,12,200,24,"Lv.#{me['level']}  #{me['name']}",Theme::TEXT,16)
        p.label(228,6,240,18,"HP  #{me['hp']} / #{me['max_hp']}",Theme::TEXT,12)
        p.bar(228,27,240,8,me['hp'].to_f/me['max_hp'],Theme::RED)
        p.label(484,6,240,18,"MP  #{me['mp']} / #{me['max_mp']}",Theme::TEXT,12)
        p.bar(484,27,240,8,me['mp'].to_f/me['max_mp'],Theme::BLUE)
        exp=me['exp_next'].to_i
        exp_width=p.width-756
        p.label(740,6,exp_width,18,exp==0 ? 'LEVEL MAX' : "EXP  #{me['exp']} / #{exp}",Theme::GOLD,12)
        p.bar(740,27,exp_width,8,exp==0 ? 1 : me['exp'].to_f/exp,Theme::GOLD)
      end
      @panels[:quicks].redraw([s['inventory'],s['cooldowns'],s['skills'],s.dig('progress','skills'),quickslot_bindings(s)]) do |p|
        QUICK_KEYS.each_with_index do |key,i|
          action=quickslot_action(i,s);kind,id=action
          definition=action && (kind=='skill' ? s['skills'] : s['items']).find{|d|d['id']==id}
          r=quickslot_rect(i);x=r.x;p.bar(x,r.y,40,40,1,Color.new(35,51,73));p.icon(x+8,r.y+8,definition && definition['icon'])
          p.label(x+3,r.y+1,16,12,key.to_s.upcase,Theme::CYAN,10)
          value=!action ? '' : kind=='skill' ? (s['cooldowns'][id].to_i>0 ? "#{(s['cooldowns'][id]/1000.0).round(1)}s" : '') : s['inventory'].fetch(id,0).to_s
          p.label(x+3,r.y+25,34,13,value,Theme::TEXT,10,2)
        end
      end
      update_minimap
      markers=[[s['npcs'],'npc_',Theme::GOLD],[s['monsters'],'monster_',Theme::RED],[s['players'],'',Theme::CYAN]].flat_map do |list,prefix,color|
        list.map do |e|
          avatar=@avatars[prefix+e['id']];x,y=avatar ? [avatar.real_x/128.0,avatar.real_y/128.0] : e['position'].values_at('x','y')
          [*@minimap.point(x,y),color]
        end
      end
      if respond_to?(:portal_entities)
        markers+=portal_entities(s).map{|_,p|[*@minimap.point(*p['position'].values_at('x','y')),Theme::GOLD]}
      end
      map_signature=[@minimap,s['map']['name'],s['players'].size,me['position'],markers]
      @panels[:map].redraw(map_signature) do |p|
        p.label(12,10,190,22,s['map']['name'],Theme::TEXT,17)
        p.label(12,34,190,18,"접속 #{s['players'].size}명   ·   #{me['position']['x']}, #{me['position']['y']}",Theme::MUTED,13)
        markers.each do |x,y,color|
          x=[[x-2,@minimap.rect.x].max,@minimap.rect.x+[@minimap.rect.width-5,0].max].min
          y=[[y-2,@minimap.rect.y].max,@minimap.rect.y+[@minimap.rect.height-5,0].max].min
          p.bar(x,y,[@minimap.rect.width,5].min,[@minimap.rect.height,5].min,1,color)
        end
      end
      target=s['monsters'].find{|m|m['id']==@target_id};@panels[:target].visible=!!target
      if target
        @panels[:target].redraw(target){|p|p.outlined_label(12,9,296,24,target['name'],Theme::TEXT,18);p.bar(12,39,296,9,target['hp'].to_f/target['max_hp'],Theme::RED);p.label(12,52,296,18,"#{target['hp']} / #{target['max_hp']}   Z 공격 · X 스킬",Theme::MUTED,12)}
      end
      draw_inventory(s);draw_chat;draw_windows(s) if @panel_order
      @panels[:character].redraw(me) do |p|
        ["#{me['name']}","초보자  ·  Lv.#{me['level']}","HP   #{me['hp']} / #{me['max_hp']}","MP   #{me['mp']} / #{me['max_mp']}","공격력   #{me['attack']}","경험치   #{me['exp']} / #{me['exp_next'].to_i==0 ? 'MAX' : me['exp_next']}"] .each_with_index{|text,i|p.label(22,54+i*34,296,28,text,i==1 ? Theme::CYAN : Theme::TEXT,18)}
      end
      @panels[:dialogue].redraw(@dialogue){|p|wrap_text(@dialogue.to_s,32).first(4).each_with_index{|line,i|p.label(20,48+i*24,560,24,line)};p.label(20,145,560,22,'Space / Esc 또는 × 로 닫기',Theme::MUTED,13)}
      @panels[:menu].redraw('menu'){|p|p.label(20,50,260,30,'온라인 세계는 계속 진행됩니다.',Theme::MUTED,15);p.bar(20,102,260,38,1,Color.new(42,76,96));p.label(20,108,260,26,'게임으로 돌아가기',Theme::TEXT,17,1);p.label(20,155,260,26,'게임 종료',Theme::RED,17,1)}
    end
    def wrap_text(text,limit)
      text.each_char.each_slice(limit).map(&:join)
    end
  end
end
