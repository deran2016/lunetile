File.open('types-reference.txt', 'w') do |file|
  [:whiten, :appear, :escape, :collapse, :blink_on].each do |method|
    sprite = RPG::Sprite.new
    sprite.send(method)
    states = []
    50.times do
      states << [sprite.opacity, sprite.color.red.to_i, sprite.color.green.to_i, sprite.color.blue.to_i, sprite.color.alpha.to_i, sprite.effect?]
      sprite.update
    end
    file.puts(method.to_s + "\t" + states.inspect)
    sprite.dispose
  end
  sprite = RPG::Sprite.new
  sprite.damage(123, true)
  file.puts('damage_fields' + "\t" + sprite.instance_variables.collect { |name| name.to_s }.sort.inspect)
  states = []
  45.times do
    child = sprite.instance_variable_get(defined?(RGSSXP) ? :@damage_sprite : :@_damage_sprite)
    states << [sprite.effect?, child ? [child.x, child.y, child.opacity] : nil]
    sprite.update
  end
  file.puts('damage_states' + "\t" + states.inspect)
  sprite.dispose
  states = []
  [:whiten, :appear, :escape, :collapse].each do |method|
    sprite = RPG::Sprite.new
    sprite.opacity, sprite.blend_type = 77, 2
    sprite.color.set(1, 2, 3, 55)
    sprite.send(method)
    states << [sprite.opacity, sprite.blend_type, sprite.color.red.to_i, sprite.color.green.to_i, sprite.color.blue.to_i, sprite.color.alpha.to_i]
    sprite.dispose
  end
  file.puts('effect_reset' + "\t" + states.inspect)
end
