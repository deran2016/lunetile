# Own deterministic maps/assets; original RGSS writes the fixture's Marshal bytes.
actors=load_data('Data/Actors.rxdata')
actors.compact.each { |actor| actor.character_name='BenchActor';actor.character_hue=0 }
save_data(actors,'Data/Actors.rxdata')
tilesets=load_data('Data/Tilesets.rxdata')
tileset=tilesets[1]
tileset.tileset_name='Benchmark';tileset.autotile_names=Array.new(7,'')
tileset.panorama_name=tileset.fog_name=tileset.battleback_name=''
tileset.passages=Table.new(1024);tileset.priorities=Table.new(1024);tileset.terrain_tags=Table.new(1024)
tileset.priorities[385]=2
save_data(tilesets,'Data/Tilesets.rxdata')
[0,100,300,300].each_with_index do |count,phase|
  map=RPG::Map.new(40,30)
  40.times do |x|
    30.times do |y|
      map.data[x,y,0]=384
      map.data[x,y,1]=385 if (x+y)%7==0
    end
  end
  1.upto(count) do |id|
    event=RPG::Event.new((id-1)%38+1,((id-1)/38)%28+1);event.id=id
    page=event.pages.first;page.graphic.character_name='BenchActor';page.step_anime=true
    if id%10==0
      page.trigger=4
      page.list=[RPG::EventCommand.new(122,0,[2,2,1,0,1]),RPG::EventCommand.new(106,0,[5]),RPG::EventCommand.new]
    end
    if phase==3
      page.move_type=3;page.move_speed=3;page.move_frequency=5
      page.move_route.repeat=true;page.move_route.skippable=true
      page.move_route.list=[3,1,2,4,0].collect { |code| RPG::MoveCommand.new(code) }
    end
    map.events[id]=event
  end
  save_data(map,sprintf('Data/Map%03d.rxdata',phase*100+1))
end
File.open('types-reference.txt','w') { |file| file.puts('fixture'+"\t"+[0,100,300,300].inspect) }
