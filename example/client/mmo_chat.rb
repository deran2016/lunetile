module LunetileMMO
  class Scene
    def chat_focus(value)
      @chat_open=value;suspend_movement
      Lunetile::UIInput.text_input=value
    end
    def push_message(text,color=Theme::MUTED)
      @chat_scroll+=wrap_text(text,26).size if @chat_scroll.to_i>0
      @messages << [text,color];@messages.shift while @messages.size>100
      @chat_scroll=(@chat_scroll||0).clamp(0,chat_max_scroll)
    end
    def chat_lines
      @messages.flat_map{|text,color|wrap_text(text,26).map{|line|[line,color]}}
    end
    def chat_max_scroll;[chat_lines.size-6,0].max;end
    def chat_scroll_thumb
      total=chat_lines.size;maximum=[total-6,0].max
      @chat_scroll=(@chat_scroll||0).clamp(0,maximum)
      height=total>6 ? [86*6/total,16].max : 86
      [48+(maximum==0 ? 0 : ((86-height)*(1-@chat_scroll.to_f/maximum)).round),height]
    end
    def handle_chat_scroll
      u=Lunetile::UIInput;point=u.mouse_position
      @chat_drag_offset=nil unless u.key_press?(:left_mouse)
      return false unless point
      p=@panels[:chat]
      if @chat_drag_offset && point
        _,height=chat_scroll_thumb;travel=86-height
        @chat_scroll=travel>0 ? ((1-(point[1]-p.y-@chat_drag_offset-48).clamp(0,travel).to_f/travel)*chat_max_scroll).round : 0
        return true
      end
      return false unless point && p.hit?(*point)
      return false if @panel_order && @panel_order.reverse.find{|key|@panels[key].hit?(*point)}!=:chat
      @chat_scroll=(@chat_scroll+u.wheel_delta*2).clamp(0,chat_max_scroll) if u.wheel_delta!=0
      return false unless u.mouse_trigger?(:left)
      x,y=u.mouse_press_position || point;x-=p.x;y-=p.y
      return false unless x.between?(p.width-18,p.width-8)&&y.between?(34,147)
      top,height=chat_scroll_thumb
      if y<46;@chat_scroll=(@chat_scroll+1).clamp(0,chat_max_scroll)
      elsif y>=136;@chat_scroll=(@chat_scroll-1).clamp(0,chat_max_scroll)
      elsif y>=top && y<top+height;@chat_drag_offset=y-top
      else;@chat_scroll=(@chat_scroll+(y<top ? 6 : -6)).clamp(0,chat_max_scroll)
      end
      true
    end
    def receive_chat(state)
      state['chat'].each do |chat|
        next if chat['seq']<=@seen_chat
        push_message("#{chat['name']}  #{chat['text']}",Theme::TEXT);@seen_chat=chat['seq']
      end
      notice=state['notice'].to_s
      if !notice.empty? && notice!=@last_notice
        push_message(notice,Theme::GOLD)
      end
      @last_notice=notice
      invite=state.dig('social','invite')
      if invite && invite!=@last_invite
        sender=state['social']['online'].find{|p|p['id']==invite['sender']}
        kind={'party_invite'=>'파티 · P','guild_invite'=>'길드 · G','trade_invite'=>'거래 · T'}[invite['kind']]
        push_message("#{sender ? sender['name'] : '상대'}님의 #{kind} 초대 · 해당 창에서 30초 안에 수락하세요.",Theme::GOLD)
      end
      @last_invite=invite
    end
    def handle_chat
      u=Lunetile::UIInput
      return false unless @chat_open
      u.text_input=true
      scrolling=handle_chat_scroll
      if !scrolling && (point=u.mouse_press_position || u.mouse_position) && u.mouse_trigger?(:left)
        panel=@panels[:chat]
        if !panel.hit?(*point);chat_focus(false);return true
        elsif point[0]>=panel.x+364 && point[1]>=panel.y+156;u.ime_open=!u.ime_open?
        end
      end
      if u.key_trigger?(:escape)
        chat_focus(false);return true
      end
      @draft=(@draft+u.text).each_char.take(100).join
      @draft=@draft[0...-1] if u.key_trigger?(:backspace) && !u.composing?
      if u.respond_to?(:text_submit?) ? u.text_submit? : (u.key_trigger?(:enter) && !u.composing?)
        @connection.send_message({'type'=>'chat','text'=>@draft}) unless @draft.strip.empty?
        @draft='';chat_focus(false)
      end
      true
    end
    def draw_chat
      comp=@chat_open ? Lunetile::UIInput.composition : ''
      @panels[:chat].redraw([@messages.size,@messages.last,@draft,comp,@chat_open,@chat_scroll,(LunetileMMO.now*2).to_i]) do |p|
        p.label(12,8,390,20,'일반 채팅  /  시스템',Theme::CYAN,13)
        lines=chat_lines
        ending=[lines.size-@chat_scroll,0].max
        lines[0...ending].last(6).each_with_index{|(line,color),i|p.label(12,34+i*19,378,20,line,color,14)}
        top,height=chat_scroll_thumb;x=p.width-18
        p.bar(x,34,10,114,1,Color.new(24,35,52))
        p.label(x-2,32,14,16,'▴',Theme::MUTED,12,1);p.label(x-2,134,14,16,'▾',Theme::MUTED,12,1)
        p.bar(x,top,10,height,1,chat_max_scroll>0 ? Theme::CYAN : Theme::MUTED)
        p.bar(8,158,404,26,1,@chat_open ? Color.new(34,64,87) : Color.new(24,35,52))
        text=@chat_open ? (@draft+comp).each_char.to_a.last(27).join : 'Enter를 눌러 대화하세요'
        text+='|' if @chat_open && (LunetileMMO.now*2).to_i.even?
        p.label(14,160,348,23,text,@chat_open ? Theme::TEXT : Theme::MUTED,14)
        p.label(370,160,36,23,Lunetile::UIInput.ime_open? ? '한' : 'EN',Theme::CYAN,13,1)
      end
      p=@panels[:chat]
      Lunetile::UIInput.caret_rect=Rect.new(p.x+18+[(@draft+comp).size,25].min*12,p.y+160,1,22) if @chat_open
    end
  end
end
