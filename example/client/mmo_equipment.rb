module LunetileMMO
  class Scene
    def draw_equipment(state)
      g=state['progress']
      rows=SLOT_NAMES.map{|slot,name|id=g['equipped'][slot];gear=id&&g['gear'][id];[slot,"#{name}: #{gear ? gear_name(state,id,gear) : '비어 있음'}",gear&&gear_definition(state,gear)['icon']]}
      list_window(:equipment,rows,[g,state['self'].values_at('attack','defense')]) do |p,slot|
        detail(p,"공격 #{state['self']['attack']} · 방어 #{state['self']['defense']} · 재화 #{g['coins']}")
        button(p,:equipment,14,440,140,'선택 장비 해제'){window_command('progress','unequip',slot)} if slot&&g['equipped'][slot]
        button(p,:equipment,170,440,130,'가방 열기'){open_window(:bag)}
      end
    end
  end
end
