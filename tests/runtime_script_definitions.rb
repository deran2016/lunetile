entries = load_data('Data/StockScripts.rxdata')
loaded = 0
entries.each_with_index do |entry, index|
  next if entry[1] == 'Main'
  source = RGSSXP.inflate(entry[2]).force_encoding('UTF-8')
  eval(source, TOPLEVEL_BINDING, "#{index}:#{entry[1]}")
  loaded += 1
end
raise 'script definition count changed' unless loaded == 89
raise 'title class missing' unless Scene_Title.instance_methods.include?(:command_new_game)
raise 'battle class missing' unless Scene_Battle.instance_methods.include?(:update_phase4)
File.write('runtime-complete.txt', 'definitions,false,false')
sleep 0.5
