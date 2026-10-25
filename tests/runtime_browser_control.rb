require 'json'
$browser_runs=($browser_runs||0)+1
raise 'Browser survived F12' if $browser && !$browser.disposed?
$browser_ticks=0
$browser_actor_x=10
$browser_command=0
$browser=nil
File.delete('browser-command.json') if $browser_runs>1 && File.exist?('browser-command.json')
Graphics.frame_rate=120
background=Sprite.new
background.bitmap=Bitmap.new(Graphics.width,Graphics.height)
background.bitmap.fill_rect(background.bitmap.rect,Color.new(35,47,65))
player=Sprite.new
player.bitmap=Bitmap.new(12,12)
player.bitmap.fill_rect(player.bitmap.rect,Color.new(220,180,30))
player.y=Graphics.height-20
File.write('browser-started.json',JSON.generate({runs:$browser_runs,available:Lunetile::Browser.available?}))
loop do
  if File.exist?('browser-command.json')
    begin
      command=JSON.parse(File.binread('browser-command.json'))
    rescue Errno::EACCES,Errno::ENOENT
      command=nil
    end
    if command && command['id']>$browser_command
      case command['action']
      when 'new'
        $browser&.dispose
        $browser=Lunetile::Browser.new(Rect.new(*command.fetch('rect',[40,40,400,280])))
      when 'url';$browser.navigate(command.fetch('value'))
      when 'file';$browser.load_file(command.fetch('value'))
      when 'focus';$browser.focus
      when 'blur';$browser.blur
      when 'focus-blur';$browser.focus;$browser.blur
      when 'hide';$browser.visible=false
      when 'show';$browser.visible=true
      when 'dispose';$browser.dispose
      when 'rect';$browser.rect=Rect.new(*command.fetch('value'))
      when 'resize';Graphics.resize_screen(*command.fetch('value'))
      when 'gc';$browser=nil;GC.start;GC.compact if GC.respond_to?(:compact)
      when 'quit';break
      else;raise 'Unknown owned browser test command'
      end
      $browser_command=command['id']
    end
  end
  Graphics.update
  Input.update
  $browser_actor_x+=1 if Input.press?(Input::RIGHT)
  player.x=$browser_actor_x%Graphics.width
  $browser_ticks+=1
  if $browser_ticks%6==0
    state=$browser&.state
    error=$browser&.error
    File.write('browser-live.tmp',JSON.generate({runs:$browser_runs,ticks:$browser_ticks,command:$browser_command,state:state,error:error && [error.code,error.native_code],actor_x:$browser_actor_x,ui_right:Lunetile::UIInput.key_press?(:right),ui_pointer:!Lunetile::UIInput.mouse_position.nil?,ui_wheel:Lunetile::UIInput.wheel_delta,size:[Graphics.width,Graphics.height]}))
    begin
      File.rename('browser-live.tmp','browser-live.json')
    rescue Errno::EACCES
      # A Windows reader can briefly deny replacement; publish the next sample.
    end
  end
end
$browser&.dispose
File.write('runtime-complete.txt','browser controlled,false,false')
