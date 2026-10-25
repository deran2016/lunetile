module LunetileMMO
  class Scene
    def draw_skills(state)
      g=state['progress'];defs=state['progression']
      rows=defs['skills'].map{|r|d=state['skills'].find{|s|s['id']==r['id']};[r['id'],"#{d['name']}  #{g['skills'].fetch(r['id'],0)}/#{r['max_rank']} · #{JOB_NAMES[r['job']]}",d['icon']]}
      list_window(:skills,rows,[g,state['cooldowns'],quickslot_bindings(state)]) do |p,id|
        if id
          r=defs['skills'].find{|v|v['id']==id};d=state['skills'].find{|v|v['id']==id}
          prerequisite=r['requires']&&state['skills'].find{|v|v['id']==r['requires']}
          effect=r['passive'] ? r['bonus'].select{|_,v|v>0}.map{|k,v|"#{ {'hp'=>'HP','mp'=>'MP','attack'=>'공격','defense'=>'방어','regen'=>'MP 회복'}[k]} +#{v}/단계"}.join(' · ') : "#{r['shape']=='line' ? '직선 관통' : '전방 광역'} #{d['range']}칸 · MP #{d['mp_cost']} · #{d['cooldown_ms']/1000.0}초"
          if d['projectile'];v=d['projectile'];effect="투척 #{d['range']}칸 · 주변 #{v['radius']}칸 · #{v['delay_ms']/1000.0}초 후 폭발 · MP #{d['mp_cost']}";end
          detail(p,"SP #{g['skill_points']} · Lv.#{r['level']} · #{effect}#{prerequisite ? " · 선행 #{prerequisite['name']} 1단계" : ''}")
          button(p,:skills,14,440,130,'습득 / 강화'){window_command('progress','learn',id)}
          button(p,:skills,160,440,130,'기본 배치'){save_quickslot_layout(LunetileMMO.default_quickslots(state))}
          unless r['passive']
            QUICK_KEYS.each_with_index do |key,i|
              label=key.to_s.upcase+(quickslot_bindings(state)[i]=="skill:#{id}" ? ' ✓' : '')
              button(p,:skills,14+i*54,322,48,label){assign_quickslot(i,id)}
            end
            button(p,:skills,306,440,140,'사용하고 닫기'){popup_keys.each{|k|close_window(k)};attack(id)}
          end
        end
      end
    end
  end
end
