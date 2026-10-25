require 'json'
stock_map(32)
raise 'Cannot make owned save fixture' unless DataManager.save_game_without_rescue(0)
own=LunetileVXA.slot(0,true);good=File.binread(own)
window=Window_SaveFile.new(180,0)
records=[];raw=''.b
capture=lambda do |label|
 window.refresh
 raw<<window.contents.__pixel_bytes
 records << [label,DataManager.load_header(0)]
 if defined?(Lunetile::StockScripts)
  raise 'Preview retained header' unless window.instance_variable_get(:@lunetile_header).nil? && !window.instance_variable_get(:@lunetile_preview)
 end
end
capture.call('good')
File.binwrite(own,good[0,good.bytesize-7]);capture.call('truncated-body')
raise 'Corrupt body accepted by preview' unless DataManager.load_header(0).nil?
raise 'Corrupt body loaded' if DataManager.load_game(0)
File.binwrite(own,good)
header=DataManager.make_save_header;header[:playtime_s]='99:58:57'
changed=LunetileVXA::SAVE_MAGIC+[Graphics.frame_rate].pack('V')+Marshal.dump(header)+Marshal.dump(DataManager.make_save_contents)
File.binwrite(own,changed);capture.call('changed-between-refresh')
raise 'Preview cache stale' unless DataManager.load_header(0)[:playtime_s]=='99:58:57'
Dir.mkdir('Saves/Import') unless Dir.exist?('Saves/Import')
imported=Marshal.dump(DataManager.make_save_header)+Marshal.dump(DataManager.make_save_contents)
File.binwrite('Saves/Import/Save02.rvdata2',imported)
import_window=Window_SaveFile.new(180,1);raw<<import_window.contents.__pixel_bytes
records << ['import-header',DataManager.load_header(1)]
raise 'Import failed to load' unless DataManager.load_game(1)
raise 'Import rewritten' unless File.binread('Saves/Import/Save02.rvdata2')==imported
import_window.dispose
empty=Window_SaveFile.new(180,15);raw<<empty.contents.__pixel_bytes;empty.dispose
raise 'Missing header accepted' unless DataManager.load_header(15).nil?
window.contents.dispose
begin;window.refresh;raise 'Disposed contents accepted';rescue RGSSError;end
if defined?(Lunetile::StockScripts)
 raise 'Exception retained preview' unless window.instance_variable_get(:@lunetile_header).nil? && !window.instance_variable_get(:@lunetile_preview)
end
File.binwrite('save-preview-pixels.bin',raw)
File.write('save-preview-oracle.json',JSON.generate(records))
File.write('runtime-complete.txt','stock save correctness')
