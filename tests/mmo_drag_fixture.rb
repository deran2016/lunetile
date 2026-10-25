Rect=Struct.new(:x,:y,:width,:height)
module Input
  def self.dir4;0;end
end
class Bitmap
  attr_reader :disposed
  def initialize(*);end
  def fill_rect(*);end
  def dispose;@disposed=true;end
end
class Sprite
  attr_accessor :bitmap,:x,:y,:ox,:oy,:opacity,:z,:visible
  attr_reader :disposed
  def initialize;@visible=true;end
  def dispose;@disposed=true;end
end
module RPG
  module Cache
    def self.icon(name);(@icons||={})[name]||=Bitmap.new;end
    def self.icons;@icons.values;end
  end
end
DragPanel=Struct.new(:x,:y,:width,:height,:visible) do
  attr_accessor :z
  def hit?(px,py);visible && px>=x && py>=y && px<x+width && py<y+height;end
  def redraw(*);yield self;end
  def bar(*);end
  def label(*);end
  def icon(*);end
end
state={'self'=>{'hp'=>100,'mp'=>50,'direction'=>6},'skills'=>%w[basic burst grenade].map{|id|{'id'=>id,'icon'=>id,'mp_cost'=>0,'cooldown_ms'=>600}},
 'items'=>%w[potion mana_potion].map{|id|{'id'=>id,'icon'=>id}},'inventory'=>{'potion'=>3,'mana_potion'=>3},'cooldowns'=>{},
 'progress'=>{'skills'=>{'burst'=>1,'grenade'=>1,'passive'=>1}},'progression'=>{'skills'=>[{'id'=>'burst','passive'=>false},{'id'=>'grenade','passive'=>false},{'id'=>'passive','passive'=>true}]}}
layout=LunetileMMO.default_quickslots(state);writes=[];fail_save=false
connection.define_singleton_method(:state){state}
connection.define_singleton_method(:quickslots){layout}
connection.define_singleton_method(:save_quickslots){|slots|raise IOError,'blocked' if fail_save;layout=slots;writes<<slots.dup}
panels={quicks:DragPanel.new(1048,16,216,100,true),skills:DragPanel.new(460,110,460,490,true),chat:DragPanel.new(0,0,1,1,false),bag:DragPanel.new(0,0,1,1,false)}
scene.instance_variable_set(:@panels,panels);scene.instance_variable_set(:@panel_order,panels.keys)
scene.instance_variable_set(:@window_page,Hash.new(0));scene.instance_variable_set(:@window_selection,{})
scene.instance_variable_set(:@window_actions,{});scene.instance_variable_set(:@quantity,1)
scene.define_singleton_method(:handle_movement){|*|};scene.define_singleton_method(:suspend_movement){}
u=Lunetile::UIInput;point_for=->(i){r=scene.quickslot_rect(i);[1048+r.x+20,16+r.y+20]}
press=->(i){u.pointer=u.press_pointer=point_for.call(i);u.held=[:left_mouse];u.clicked=true;scene.handle_mouse(state);u.clicked=false}
move=->(point){u.pointer=point;scene.handle_mouse(state)}
release=->(point){u.pointer=point;u.held=[];scene.handle_mouse(state)}
