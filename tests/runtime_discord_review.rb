require 'json'
$discord_review_runs=($discord_review_runs||0)+1
File.delete('review-command.json') if File.exist?('review-command.json')
$game_player.moveto($data_system.start_x,$data_system.start_y) if REVIEW_ENGINE=='xp'
Graphics.render_rate=120 if REVIEW_WIDE
hud=Sprite.new
hud.z=100000
hud.bitmap=Bitmap.new([Graphics.width,600].min,106)
hud.bitmap.font.size=18
hud.bitmap.font.name='Arial'
foreground=Win32API.new('user32','GetForegroundWindow','','L')
active=Win32API.new('user32','GetActiveWindow','','L').call
ticks=command_id=direction_ticks=cancel_triggers=0
browser=nil
sample=nil
loop do
 if File.exist?('review-command.json')
  begin
   command=JSON.parse(File.binread('review-command.json'))
  rescue Errno::EACCES,Errno::ENOENT,JSON::ParserError
   command=nil
  end
  if command && command.fetch('id')>command_id
   case command.fetch('action')
   when 'quit';break
   when 'browser'
    if browser && !browser.disposed?
     browser.dispose;browser=nil
    else
     Dir.mkdir('Web') unless Dir.exist?('Web')
     File.write('Web/review.html','<!doctype html><meta charset="utf-8"><style>body{background:#234;color:white;font:20px sans-serif}</style><p>Lunetile local input test</p><input aria-label="Local test input">')
     browser=Lunetile::Browser.new(Rect.new(40,120,[Graphics.width-80,600].min,[Graphics.height-160,300].min))
     browser.load_file('Web/review.html')
    end
   when 'sample'
    raise 'Sample already running' if sample
    sample={start:Process.clock_gettime(Process::CLOCK_MONOTONIC),frame:Graphics.frame_count,stats:Graphics.__refresh_stats,foreground:true}
   else;raise 'Unknown review command'
   end
   command_id=command['id']
  end
 end
 Input.update if REVIEW_ENGINE=='xp'
 scene.update
 ticks+=1
 direction_ticks+=1 if Input.dir4!=0
 cancel_triggers+=1 if Input.trigger?(Input::B)
 focused=foreground.call==active
 if sample
  sample[:foreground] &&= focused && Graphics.__timings[10]==0
  elapsed=Process.clock_gettime(Process::CLOCK_MONOTONIC)-sample[:start]
  if elapsed>=5
   delta=Graphics.__refresh_stats.zip(sample[:stats]).map { |a,b| a-b }
   row={seconds:elapsed,logic_fps:(Graphics.frame_count-sample[:frame])/elapsed,present_fps:delta[1]/elapsed,
    missing_fraction:delta[0]>0 ? [delta[0]-delta[1],0].max.to_f/delta[0] : 1.0,render_rate:Graphics.render_rate,
    foreground_entire_sample:sample[:foreground],discord_overlay_verified:false}
   File.write("review-sample-#{command_id}.json",JSON.generate(row))
   sample=nil
  end
 end
 if ticks%6==0
  data={runs:$discord_review_runs,ticks:ticks,direction_ticks:direction_ticks,cancel_triggers:cancel_triggers,
   position:[$game_player.x,$game_player.y],foreground:focused,background_update:Graphics.background_update,
   size:[Graphics.width,Graphics.height],logic_rate:Graphics.frame_rate,render_rate:Graphics.render_rate,
   browser_state:browser && browser.state,command:command_id}
  File.write('review-live.tmp',JSON.generate(data))
  begin;File.rename('review-live.tmp','review-live.json');rescue Errno::EACCES;end
 end
 if ticks%30==0
  bitmap=hud.bitmap;bitmap.clear;bitmap.fill_rect(bitmap.rect,Color.new(12,24,40,230))
  lines=["Discord review #{REVIEW_ENGINE} #{Graphics.width}x#{Graphics.height}  F12:reset Alt+Enter:borderless",
   "ticks:#{ticks} directions:#{direction_ticks} cancel:#{cancel_triggers} foreground:#{focused}",
   "Discord shortcut: use YOUR Discord setting. Type only; do not send messages."]
  lines.each_with_index { |line,i| bitmap.draw_text(6,i*30,bitmap.width-12,30,line) }
 end
end
browser.dispose if browser && !browser.disposed?
hud.bitmap.dispose;hud.dispose
File.write('runtime-complete.txt','Discord review,false,false')
