module LunetileMMO
  class Scene
    WINDOW_NAMES={skills:'스킬 · K',equipment:'장비 · E',quests:'퀘스트 · Q',jobs:'전직 · J',shop:'상점 · O',storage:'창고 · B',enhance:'강화 · U',party:'파티 · P',guild:'길드 · G',trade:'거래 · T'}
    JOB_NAMES={'beginner'=>'초보자','warrior'=>'전사','mage'=>'마법사','archer'=>'궁수','rogue'=>'도적','warrior2'=>'검사','mage2'=>'마도사','archer2'=>'명사수','rogue2'=>'암살자'}
    SLOT_NAMES={'weapon'=>'무기','shield'=>'방패','head'=>'투구','body'=>'갑옷','feet'=>'신발','accessory'=>'장신구'}
    def portal_entities(state)
      state.dig('services','portals').to_a.select{|p|p['from']['map_id']==state['self']['position']['map_id']}.map do |p|
        ["portal_#{p['id']}",{'id'=>p['id'],'name'=>"#{p['name']} Lv.#{p['level']}",'position'=>p['from'],'character'=>'Lunetile_Portal','direction'=>2,'portal'=>true}]
      end
    end
    def setup_windows
      WINDOW_NAMES.each_with_index do |(key,title),i|
        @panels[key]=Panel.new(460+(i%3)*24,110+(i%3)*20,460,490,title);@panels[key].visible=false
      end
      @panels[:entry]=Panel.new(390,260,500,140,'이름 입력');@panels[:entry].visible=false
      @panels[:launcher]=Panel.new(Graphics.width-232,Graphics.height-320,216,248);@panels[:launcher].visible=false
      @panel_order=@panels.keys;@window_actions={};@window_page=Hash.new(0);@window_selection={};@quantity=1;@bag_tab=:all
      @panels[:bag].visible=false
      reorder_panels
    end
    def reorder_panels
      @panel_order.each_with_index{|key,i|@panels[key].z=1500+i*4}
    end
    def raise_panel(key)
      @panel_order.delete(key);@panel_order<<key;reorder_panels
    end
    def popup_keys;[:bag,:character,:dialogue,:menu,:entry,:launcher]+WINDOW_NAMES.keys;end
    def open_window(key)
      cancel_quick_drag
      p=@panels[key];p.visible=!p.visible;@inventory_open=p.visible if key==:bag
      close_window(:launcher) unless key==:launcher
      raise_panel(key) if p.visible
    end
    def close_window(key)
      cancel_quick_drag
      @panels[key].visible=false;@inventory_open=false if key==:bag
      @form=nil if key==:entry
    end
    def update_window_focus
      return unless @panel_order
      active=combat_active?;point=Lunetile::UIInput.mouse_position
      @hover_panel=active&&point ? @panel_order.reverse.find{|key|@panels[key].hit?(*point)} : nil
      @panels.each do |key,p|
        next if [:status,:target].include?(key)
        focused=active && (@hover_panel==key||((@chat_open||@chat_drag_offset)&&key==:chat)||(@drag&&@drag[0]==key)||(@form&&key==:entry))
        p.alpha=focused ? ([:chat,:map].include?(key) ? 208 : 238) : 144
      end
    end
    def window_command(type,action,key='',amount=1,text='',revision=0)
      payload={'type'=>type,'action'=>action,'key'=>key}
      payload['amount']=amount if ['service','social'].include?(type)
      payload.merge!('text'=>text,'revision'=>revision) if type=='social'
      @avatars[@connection.id]&.flush(@connection,true)
      @connection.send_message(payload)
    end
    def button(panel,key,x,y,w,label,&action)
      panel.bar(x,y,w,26,1,Color.new(35,66,85));panel.label(x+3,y+2,w-6,22,label,Theme::TEXT,13,1)
      (@window_actions[key]||=[])<<[Rect.new(x,y,w,26),action]
    end
    def window_click(key,x,y)
      action=(@window_actions[key]||[]).find{|rect,_|x>=rect.x&&y>=rect.y&&x<rect.x+rect.width&&y<rect.y+rect.height}
      action[1].call if action
    end
    def handle_window_keys
      return false unless @panel_order
      return handle_name_entry if @form
      return false if @chat_open || !combat_active?
      u=Lunetile::UIInput
      {k: :skills,e: :equipment,q: :quests,j: :jobs,o: :shop,b: :storage,u: :enhance,p: :party,g: :guild,t: :trade}.each do |key,panel|
        if u.key_trigger?(key);open_window(panel);return true;end
      end
      false
    end
    def name_entry(&block)
      @form={value:'',callback:block};@panels[:entry].visible=true;raise_panel(:entry);Lunetile::UIInput.text_input=true
    end
    def handle_name_entry
      u=Lunetile::UIInput;u.text_input=true
      if u.key_trigger?(:escape);close_window(:entry);u.text_input=false;return true;end
      @form[:value]=(@form[:value]+u.text).each_char.take(16).join
      @form[:value]=@form[:value][0...-1] if u.key_trigger?(:backspace)&&!u.composing?
      if u.key_trigger?(:enter)&&!u.composing?
        value=@form[:value].strip;callback=@form[:callback];close_window(:entry);u.text_input=false;callback.call(value) unless value.empty?
      end
      true
    end
    def gear_definition(state,gear);state['progression']['equipment'].find{|d|d['id']==gear['definition']};end
    def gear_name(state,id,gear);d=gear_definition(state,gear);"#{d['name']} +#{gear['enhancement']}";end
    def list_window(key,rows,signature)
      p=@panels[key];return unless p.visible
      page=@window_page[key]=@window_page[key].clamp(0,[(rows.size-1)/7,0].max)
      @window_selection[key]=rows.first&.first unless rows.any?{|row|row[0]==@window_selection[key]}
      p.redraw([signature,page,@window_selection[key],@quantity]) do
        @window_actions[key]=[]
        rows.slice(page*7,7).to_a.each_with_index do |(id,label,icon),i|
          y=48+i*34;p.bar(12,y,p.width-24,30,1,@window_selection[key]==id ? Color.new(36,83,105) : Color.new(27,40,58));p.icon(18,y+3,icon) if icon
          p.label(icon ? 48 : 20,y+3,p.width-70,24,label,Theme::TEXT,14)
          @window_actions[key]<<[Rect.new(12,y,p.width-24,30),-> {@window_selection[key]=id;begin_skill_drag(id) if key==:skills}]
        end
        button(p,key,12,292,48,'‹'){@window_page[key]-=1};button(p,key,68,292,48,'›'){@window_page[key]+=1}
        p.label(130,294,310,22,"#{page+1}/#{[(rows.size+6)/7,1].max}  ·  #{key==:skills ? '스킬을 퀵슬롯에 드래그하세요' : "수량 #{@quantity}"}",Theme::MUTED,13)
        [1,10,100].each_with_index{|n,i|button(p,key,240+i*66,322,60,n.to_s){@quantity=n}} unless key==:skills
        yield p,@window_selection[key]
      end
    end
    def detail(p,text);wrap_text(text,31).first(3).each_with_index{|line,i|p.label(14,356+i*23,p.width-28,22,line,Theme::MUTED,13)};end
    def draw_windows(state)
      return unless state['progression']&&state['progress'];g=state['progress'];defs=state['progression'];social=state['social'];services=state['services']
      @panels[:menu_button].redraw(@panels[:launcher].visible){|p|p.label(4,12,108,24,@panels[:launcher].visible ? '메뉴  ▾' : '메뉴  ▴',Theme::CYAN,16,1)}
      @panels[:launcher].redraw('launcher') do |p|
        @window_actions[:launcher]=[];p.label(10,8,196,22,'모험 메뉴',Theme::CYAN,14)
        ([[:bag,'가방 · I'],[:character,'정보 · C']]+WINDOW_NAMES.to_a+[[:menu,'종료 메뉴']]).each_with_index{|(key,title),i|button(p,:launcher,8+(i%2)*102,36+(i/2)*29,98,title){open_window(key)}}
      end
      if @form
        p=@panels[:entry];comp=Lunetile::UIInput.composition
        p.redraw([@form[:value],comp]){|v|v.label(18,48,464,30,@form[:value]+comp+'|');v.label(18,96,464,22,'Enter 확인 · Esc 취소',Theme::MUTED,13)}
        Lunetile::UIInput.caret_rect=Rect.new(p.x+18+@form[:value].size*14,p.y+48,1,24)
      end
      draw_equipment(state);draw_skills(state)
      jobs=JOB_NAMES.reject{|id,_|id=='beginner'}.map{|id,name|[id,"#{name} · Lv.#{id.end_with?('2') ? 20 : 5}",nil]}
      list_window(:jobs,jobs,g) do |p,id|
        detail(p,"현재 직업: #{JOB_NAMES[g['job']]} · 마을에서 전직합니다. 2차 전직은 같은 계열로 진행합니다.")
        button(p,:jobs,14,440,180,'선택 직업으로 전직'){window_command('progress','job',id)} if id
      end
      gear_rows=g['gear'].map{|id,gear|[id,gear_name(state,id,gear),gear_definition(state,gear)['icon']]}
      list_window(:enhance,gear_rows,g) do |p,id|
        if id
          rank=g['gear'][id]['enhancement'];cost=defs['enhancement_costs'][rank];rate=defs['enhancement_chances'][rank]
          detail(p,cost ? "재화 #{g['coins']} · 비용 #{cost} + 강화석 1개 · 성공 #{rate}% · 실패해도 단계와 장비를 보존합니다." : '최대 강화 단계입니다.')
          button(p,:enhance,14,440,180,'안전 강화'){window_command('progress','enhance',id)} if cost
        end
      end
      draw_services(state) if services
      draw_social(state) if social
    end
    def draw_services(state)
      g=state['progress'];s=state['services']
      rows=s['quests'].map{|q|[q['id'],"#{q['name']} · #{g['completed'].include?(q['id']) ? '완료' : "#{g['quests'].fetch(q['id'],0)}/#{q['count']}"}",nil]}
      list_window(:quests,rows,g) do |p,id|
        if id
          q=s['quests'].find{|v|v['id']==id};detail(p,"#{q['description']} · Lv.#{q['level']} · 보상 #{q['coins']} 재화 / #{q['exp']} EXP")
          button(p,:quests,14,440,130,'수락'){window_command('service','quest_accept',id)}
          button(p,:quests,160,440,130,'보상 수령'){window_command('service','quest_claim',id)}
        end
      end
      rows=s['shop'].map{|id,price|d=state['items'].find{|i|i['id']==id};['i:'+id,"#{d['name']} · #{price} 재화",d['icon']]}
      rows+=state['progression']['equipment'].map{|d|['g:'+d['id'],"#{d['name']} · #{d['price']} 재화",d['icon']]}
      list_window(:shop,rows,[state['inventory'],g]) do |p,key|
        detail(p,"보유 재화 #{g['coins']} · 소모품은 선택 수량으로 구입합니다. 장비는 한 번에 1개입니다.")
        if key
          kind,id=key.split(':',2);button(p,:shop,14,440,130,'구입'){window_command('service',kind=='g' ? 'buy_gear' : 'buy',id,kind=='g' ? 1 : @quantity)}
          button(p,:shop,160,440,130,'소모품 판매'){window_command('service','sell',id,@quantity)} if kind=='i'
        end
      end
      rows=state['inventory'].map{|id,count|d=state['items'].find{|v|v['id']==id};['bag:'+id,"가방 · #{d['name']} ×#{count}",d['icon']]}
      rows+=g['storage'].map{|id,count|d=state['items'].find{|v|v['id']==id};['store:'+id,"창고 · #{d['name']} ×#{count}",d['icon']]}
      [['gear',g['gear']],['stored_gear',g['storage_gear']]].each{|prefix,items|items.each{|id,gear|rows<<[prefix+':'+id,"#{prefix=='gear' ? '가방' : '창고'} · #{gear_name(state,id,gear)}",gear_definition(state,gear)['icon']]}}
      list_window(:storage,rows,[g,state['inventory']]) do |p,key|
        detail(p,"보유 재화 #{g['coins']} · 창고 재화 #{g['storage_coins']}")
        if key
          prefix,id=key.split(':',2);action={'bag'=>'store_item','store'=>'withdraw_item','gear'=>'store_gear','stored_gear'=>'withdraw_gear'}[prefix]
          button(p,:storage,14,440,140,['bag','gear'].include?(prefix) ? '선택 보관' : '선택 꺼내기'){window_command('service',action,id,@quantity)}
        end
        button(p,:storage,164,440,135,'재화 보관'){window_command('service','store_coins','',@quantity)}
        button(p,:storage,309,440,135,'재화 꺼내기'){window_command('service','withdraw_coins','',@quantity)}
      end
    end
    def draw_social(state)
      data=state['social'];g=state['progress'];me=@connection.id
      rows=data['online'].reject{|p|p['id']==me}.map{|p|[p['id'],"#{p['name']} · Lv.#{p['level']} · HP #{p['hp']}/#{p['max_hp']}",nil]}
      [:party,:guild].each do |key|
        members=key==:guild ? data.dig('guild','members').to_a : []
        member_ids=key==:guild ? members.map{|m|m['id']} : data.dig('party','members').to_a
        group_rows=rows.map{|id,label,icon|[id,member_ids.include?(id) ? '[멤버] '+label : label,icon]}
        group_rows+=members.reject{|m|m['id']==me||rows.any?{|r|r[0]==m['id']}}.map{|m|[m['id'],"#{m['name']} · 오프라인",nil]}
        list_window(key,group_rows,data) do |p,target|
          group=data[key.to_s];detail(p,group ? "#{key==:party ? '파티' : group['name']} · #{group['members'].size}명" : (key==:guild ? '길드 생성: 500 재화. 상대 가까이에서 초대하세요.' : '파티는 최대 4명. 가까운 파티원과 경험치·퀘스트 처치를 공유합니다.'))
          unless group
            button(p,key,14,408,125,'만들기'){key==:guild ? name_entry{|name|window_command('social','guild_create','',0,name)} : window_command('social','party_create')}
          else
            button(p,key,14,408,125,'초대'){window_command('social',key.to_s+'_invite',target)} if target
            button(p,key,150,408,125,'탈퇴'){window_command('social',key.to_s+'_leave')}
            button(p,key,286,408,150,'추방'){window_command('social',key.to_s+'_kick',target)} if target
            button(p,key,286,440,150,'길드 해산'){window_command('social','guild_disband')} if key==:guild&&group['leader']==me
          end
          if data['invite']
            button(p,key,14,440,125,'초대 수락'){window_command('social','accept')};button(p,key,150,440,125,'초대 거절'){window_command('social','decline')}
          end
        end
      end
      trade=data['trade']
      unless trade
        list_window(:trade,rows,data) do |p,target|
          detail(p,'상대 가까이에서 거래를 요청하세요. 양쪽 확인 전에는 물품이 이동하지 않습니다.')
          button(p,:trade,14,440,130,'거래 요청'){window_command('social','trade_invite',target)} if target
          if data.dig('invite','kind')=='trade_invite'
            button(p,:trade,160,440,130,'수락'){window_command('social','accept')};button(p,:trade,306,440,140,'거절'){window_command('social','decline')}
          end
        end
        return
      end
      offer=trade['offers'][me];other=trade['members'].find{|id|id!=me};theirs=trade['offers'][other]
      rows=state['inventory'].map{|id,count|d=state['items'].find{|v|v['id']==id};['i:'+id,"#{d['name']} · 제시 #{offer['items'].fetch(id,0)} / 보유 #{count}",d['icon']]}
      rows+=g['gear'].reject{|id,_|g['equipped'].values.include?(id)}.map{|id,gear|['g:'+id,"#{offer['gear'].include?(id) ? '제시중' : '가방'} · #{gear_name(state,id,gear)}",gear_definition(state,gear)['icon']]}
      rows+=theirs['items'].map{|id,count|d=state['items'].find{|v|v['id']==id};['r:'+id,"상대 제시 · #{d['name']} ×#{count}",d['icon']]}
      rows+=theirs['gear'].map{|id|gear=trade['gear_details'][id];['r:'+id,gear ? "상대 제시 · #{gear_name(state,id,gear)}" : '상대 장비 변경됨',gear&&gear_definition(state,gear)['icon']]}
      list_window(:trade,rows,[g,trade,state['inventory']]) do |p,key|
        other_name=data['online'].find{|v|v['id']==other}&.fetch('name') || other
        offered=theirs['items'].map{|id,count|d=state['items'].find{|v|v['id']==id};"#{d['name']}×#{count}"}.join(', ')
        detail(p,"남은 #{trade['remaining_seconds']}초 · #{other_name}: #{theirs['coins']} 재화 · #{offered} · 장비 #{theirs['gear'].size}개 / 내 제시 #{offer['coins']} 재화")
        if key && !key.start_with?('r:')
          kind,id=key.split(':',2)
          button(p,:trade,14,408,100,'제시 변경'){window_command('social',kind=='g' ? 'trade_gear' : 'trade_item',id,kind=='g' ? 1 : @quantity)}
          button(p,:trade,122,408,100,'제시 취소'){window_command('social','trade_item',id,0)} if kind=='i'
        end
        button(p,:trade,230,408,100,'재화 제시'){window_command('social','trade_coins','',@quantity)}
        button(p,:trade,338,408,108,'재화 취소'){window_command('social','trade_coins','',0)}
        button(p,:trade,14,440,210,trade['confirmed'].include?(me) ? '상대 확인 대기' : '내용 확인 · 거래 동의'){window_command('social','trade_confirm','',0,'',trade['revision'])}
        button(p,:trade,236,440,210,'거래 취소'){window_command('social','trade_cancel')}
      end
    end
  end
end
