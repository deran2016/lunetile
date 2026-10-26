# Isolated MMO fixture: exercise the installed stock helper, not the offline save installer.
require 'json'
raise 'offline save hooks installed' if Lunetile::Comfort.installed?
raise 'stock helper missing' unless defined?(Lunetile::StockScripts) && Lunetile::StockScripts.enabled?
raise 'display helper inactive' unless Sprite_Character.instance_method(:update).source_location.first=='(Lunetile stock scripts)'
LunetileMMO.setup_game(1)
$mmo_perf_clock=0.0
LunetileMMO.define_singleton_method(:now){$mmo_perf_clock}
actor=Game_Character.new
actor.instance_variable_set(:@character_name,'001-Fighter01');actor.instance_variable_set(:@pattern,1);actor.moveto(9,7)
sprite=LunetileMMO::CombatCharacter.new(nil,actor)
rect=sprite.src_rect;original=rect.method(:set);sets=0
rect.define_singleton_method(:set){|*args|sets+=1;original.call(*args)}
100.times{sprite.update};idle_sets=sets
raise 'idle display cache did not skip redundant Rect writes' unless idle_sets==0
checks=0
[2,4,6,8].each do |direction|
 ['slash','magic'].each do |kind|
  $mmo_perf_clock=0.0;actor.instance_variable_set(:@direction,direction);sprite.update
  rest=[rect.x,rect.y,rect.width,rect.height]
  sprite.attack_motion({'direction'=>direction,'motion'=>kind,'motion_ms'=>240})
  $mmo_perf_clock=0.04;sprite.update;raise 'attack pose not visible' if [rect.x,rect.y,rect.width,rect.height]==rest
  $mmo_perf_clock=0.25;sprite.update;raise 'cached attack pose survived attack end' unless [rect.x,rect.y,rect.width,rect.height]==rest
  checks+=1
 end
end
sprite.dispose
report={'passed'=>true,'version'=>Lunetile::StockScripts::VERSION,'idle_updates'=>100,'idle_rect_sets'=>idle_sets,'pose_checks'=>checks,
 'offline_installer'=>Lunetile::Comfort.installed?,'browser_api'=>!!defined?(Lunetile::Browser),'controls_api'=>!!defined?(Lunetile::Controls),'stock_stats'=>Lunetile::StockScripts.stats}
File.write('mmo-performance.json',JSON.generate(report))
File.write('runtime-complete.txt','mmo-performance,false,false')
