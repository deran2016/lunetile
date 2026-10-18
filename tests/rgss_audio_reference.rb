File.open('types-reference.txt','w') do |file|
  file.sync = true
  record = proc do |label, method, args|
    begin
      answer = Audio.send(method, *args)
    rescue Exception => error
      answer = error.class.name
    end
    file.puts(label + "\t" + answer.inspect)
  end
  ['bgm','bgs','me','se'].each do |kind|
    play = kind + '_play'
    record.call(play,play,[''])
    record.call(kind+'_stop',kind+'_stop',[])
    record.call(kind+'_fade',kind+'_fade',[0]) unless kind == 'se'
    [nil,123].each do |value|
      begin
        Audio.send(play,value)
        answer = 'accepted'
      rescue Exception => error
        answer = error.class.name
      end
      file.puts(play + value.inspect + "\t" + answer.inspect)
    end
  end
end
