# Native test-only entry driver. All credentials belong to isolated fixture accounts.
config=JSON.parse(File.read('client.json'));config.merge!('host'=>'127.0.0.1','port'=>ENTRY_PORT,'profile'=>"entry_#{ENTRY_INDEX}",'display_name'=>"Entry#{ENTRY_INDEX}")
entry=LunetileMMO::Entry.new(config);original=entry.method(:update);phase=0;last_report=0;started=LunetileMMO.now
entry.define_singleton_method(:update) do
  original.call
  if phase==0 && connection.account
    File.write('entry-login-ready.txt','ready');phase=1
  elsif phase==1 && File.exist?('entry-authenticate.txt')
    action(:toggle);instance_variable_set(:@fields,["fixture_#{ENTRY_INDEX}",'Native_test_only_1234','Native_test_only_1234']);authenticate;phase=2
  elsif phase==2 && instance_variable_get(:@mode)==:characters
    File.write('entry-select-ready.txt','ready');phase=3
  end
  if connection.account && LunetileMMO.now-last_report>0.1
    File.write('entry-live.tmp',JSON.generate({'phase'=>phase,'mode'=>instance_variable_get(:@mode),'characters'=>connection.account['characters'],
      'nickname'=>instance_variable_get(:@nickname),'appearance'=>instance_variable_get(:@appearance),'composition'=>Lunetile::UIInput.composition,'selected'=>instance_variable_get(:@selected),'status'=>instance_variable_get(:@status),'buttons'=>instance_variable_get(:@buttons),
      'password_fields_cleared'=>instance_variable_get(:@fields)[1..].all?(&:empty?)}))
    begin;File.rename('entry-live.tmp','entry-live.json');rescue Errno::EACCES;end
    last_report=LunetileMMO.now
  end
  raise 'Entry scene timeout' if LunetileMMO.now-started>600
end
connection=entry.main
if connection
 scene=LunetileMMO::Scene.new(config,connection);Graphics.transition;last_report=0;started=LunetileMMO.now
 File.write('entry-world-ready.txt','ready')
 begin
  loop do
   Graphics.update;Input.update;scene.update
   state=scene.connection.state
   data={'state'=>state,'chat_open'=>scene.instance_variable_get(:@chat_open),'draft'=>scene.instance_variable_get(:@draft),'composition'=>Lunetile::UIInput.composition,'composing'=>Lunetile::UIInput.composing?,
    'input_stats'=>Lunetile::UIInput.__stats,'profile_files'=>Dir.glob('ClientProfile/*.json').map{|p|File.basename(p)}}
   if LunetileMMO.now-last_report>0.1
    File.write('entry-world.tmp',JSON.generate(data));begin;File.rename('entry-world.tmp','entry-world.json');rescue Errno::EACCES;end
    last_report=LunetileMMO.now
   end
   break if File.exist?('entry-exit.txt')||LunetileMMO.now-started>600
  end
 ensure
  scene.dispose
 end
end
