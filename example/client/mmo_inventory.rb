module LunetileMMO
  class Scene
    def inventory_entries(state)
      tab=@bag_tab||:all
      entries=state['inventory'].filter_map do |id,count|
        item=state['items'].find{|v|v['id']==id};usable=item['heal'].to_i>0||item['mp_heal'].to_i>0
        next if tab==:gear || tab==:use&&!usable || tab==:other&&usable
        [id,item,count,nil]
      end
      if [:all,:gear].include?(tab) && state['progression']
        state['progress']['gear'].each do |id,gear|
          definition=gear_definition(state,gear);entries<<[id,definition,1,gear]
        end
      end
      entries
    end
    def activate_inventory(state)
      entry=inventory_entries(state)[@inventory_index];return unless entry
      id,_,_,gear=entry
      gear ? window_command('progress','equip',id) : use_item(id)
    end
    def inventory_click(state,x,y)
      if y.between?(40,64)&&x.between?(12,363)
        @bag_tab=[:all,:use,:gear,:other][(x-12)/88];@inventory_index=0;return
      end
      entries=inventory_entries(state);col=(x-16)/58;row=(y-74)/54;index=(@inventory_index/18)*18+row*6+col
      if x>=16&&y>=74&&(0..5).include?(col)&&(0..2).include?(row)&&index<entries.size
        @inventory_index=index
      elsif y.between?(320,350)&&x.between?(240,364)
        activate_inventory(state)
      elsif y.between?(320,350)&&x<100
        page=@inventory_index/18+(x<52 ? -1 : 1);@inventory_index=[[page*18,0].max,[entries.size-1,0].max].min
      elsif y.between?(320,350)&&x.between?(120,228)
        entry=entries[@inventory_index]
        window_command('service','sell_gear',entry[0]) if entry&&entry[3]
      end
    end
    def draw_inventory(state)
      entries=inventory_entries(state);@inventory_index=0 if @inventory_index>=entries.size
      @panels[:bag].redraw([state['inventory'],state['progress'],@inventory_index,@bag_tab]) do |p|
        ['전체','소모품','장비','기타'].each_with_index do |text,i|
          p.bar(12+i*88,40,82,24,1,(@bag_tab||:all)==[:all,:use,:gear,:other][i] ? Color.new(39,95,118) : Color.new(27,40,58));p.label(12+i*88,41,82,22,text,Theme::TEXT,13,1)
        end
        18.times do |i|
          x=16+(i%6)*58;y=74+(i/6)*54
          p.bar(x,y,50,46,1,i==@inventory_index%18 ? Color.new(39,95,118) : Color.new(27,40,58))
          entry=entries[(@inventory_index/18)*18+i];next unless entry
          id,item,count,gear=entry;p.icon(x+13,y+4,item['icon'])
          value=gear ? "+#{gear['enhancement']}" : count.to_s
          value='E '+value if gear&&state['progress']['equipped'].values.include?(id)
          p.label(x+3,y+29,44,16,value,Theme::TEXT,12,2)
        end
        p.label(16,322,100,26,"‹   › #{@inventory_index/18+1}/#{[(entries.size+17)/18,1].max}",Theme::MUTED,13)
        if entry=entries[@inventory_index]
          id,item,_,gear=entry;p.label(16,244,350,24,item['name'],Theme::CYAN,16)
          text=item['description']
          if gear
            old_id=state['progress']['equipped'][item['slot']];old=old_id&&state['progress']['gear'][old_id]
            old_def=old&&gear_definition(state,old)
            keys=(item['bonus'].keys+item['enhancement'].keys+(old_def ? old_def['bonus'].keys+old_def['enhancement'].keys : [])).uniq
            deltas=keys.map do |key|
              value=item['bonus'].fetch(key,0)+item['enhancement'].fetch(key,0)*gear['enhancement']
              previous=old_def ? old_def['bonus'].fetch(key,0)+old_def['enhancement'].fetch(key,0)*old['enhancement'] : 0
              "#{ {'hp'=>'HP','mp'=>'MP','attack'=>'공격','defense'=>'방어','regen'=>'회복'}[key]} #{value-previous>=0 ? '+' : ''}#{value-previous}"
            end
            text="Lv.#{item['level']} #{JOB_NAMES[item['job']]} · "+deltas.join(' / ')
            p.bar(120,320,108,30,1,Color.new(55,58,70));p.label(120,322,108,26,'장비 판매',Theme::TEXT,13,1)
          end
          wrap_text(text,27).first(2).each_with_index{|line,i|p.label(16,270+i*21,350,22,line,Theme::MUTED,13)}
          p.bar(240,320,124,30,1,Color.new(41,82,105));p.label(240,322,124,26,gear ? '착용' : '사용',Theme::TEXT,14,1)
        else;p.label(16,264,350,30,'가방이 비어 있습니다.',Theme::MUTED,17)
        end
      end
    end
  end
end
