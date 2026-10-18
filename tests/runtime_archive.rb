records = []
File.open('archive-started.txt', 'w') { |file| file.write('started') }
['Data/probe.rxdata', 'data/PROBE.rxdata'].each do |name|
  begin
    records << load_data(name)
  rescue Exception => error
    records << ['error', error.class.name]
  end
end
(1..7).each { |length| records << load_data("Data/bytes#{length}.rxdata") }
File.open('types-reference.txt', 'w') { |file| file.puts('archive' + "\t" + records.inspect) }
File.open('runtime-complete.txt', 'w') { |file| file.write('archive,false,false') }
sleep 0.5
