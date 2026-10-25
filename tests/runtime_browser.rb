require 'json'
raise 'WebView2 Runtime not available' unless Lunetile::Browser.available?
Dir.mkdir('Web') unless Dir.exist?('Web')
File.write('Web/index.html','<!doctype html><meta charset="utf-8"><style>body{background:#20a060;color:white;font:24px sans-serif}input{font:24px sans-serif}</style><h1>Lunetile browser</h1><input aria-label="text" value="한글 입력"><p>Offline local page</p>')
File.write('Web/한글 파일.html',File.read('Web/index.html'))
def browser_wait(view)
  deadline=Process.clock_gettime(Process::CLOCK_MONOTONIC)+20
  loop do
    Graphics.update;Input.update
    break if [:ready,:failed,:disposed].include?(view.state)
    raise 'Browser timeout' if Process.clock_gettime(Process::CLOCK_MONOTONIC)>deadline
  end
  raise "Browser failed #{view.error}" unless view.state==:ready
end
rows=[]
begin
  Lunetile::Browser.new(Rect.new(0,0,31,100));raise 'Small browser accepted'
rescue ArgumentError
end
view=Lunetile::Browser.new(Rect.new(40,40,400,280))
begin
  Lunetile::Browser.new(Rect.new(0,0,100,100));raise 'Second browser accepted'
rescue Lunetile::BrowserError=>e
  raise e unless e.code==:already_open
end
view.navigate('http://127.0.0.1:1/')
view.load_file('Web/한글 파일.html')
browser_wait(view)
copy=view.rect;copy.x=900
raise 'Mutable rect escaped' unless view.rect.x==40
rows << ['ready',view.state,view.rect.x,view.visible]
view.focus
20.times { Graphics.update;Input.update }
raise 'UI mouse input leaked' unless Lunetile::UIInput.mouse_position.nil?
raise 'Game input leaked' unless Input.dir4==0 && !Input.press?(Input::C)
view.visible=false;Graphics.update;Input.update
raise 'Hide failed' if view.visible
view.visible=true;view.blur;Graphics.update;Input.update
rows << ['hide-show',view.visible]
thread_error=Thread.new { begin;view.rect;false;rescue ThreadError;true;end }.value
raise 'Other thread accepted' unless thread_error
['javascript:alert(1)','file:///C:/Windows/win.ini','https://example.com/a b'].each do |url|
  begin;view.navigate(url);raise 'Bad URL accepted';rescue Lunetile::BrowserError=>e;raise e unless e.code==:url;end
end
['../README.md','Web/../../Game.ini','Game.ini'].each do |path|
  begin;view.load_file(path);raise 'Bad file accepted';rescue Lunetile::BrowserError=>e;raise e unless e.code==:local_path;end
end
view.reload;Graphics.update;browser_wait(view)
rows << ['validation',true]
view.navigate('http://127.0.0.1:1/')
deadline=Process.clock_gettime(Process::CLOCK_MONOTONIC)+20
until view.state==:failed
  Graphics.update
  raise 'Missing navigation failure' if Process.clock_gettime(Process::CLOCK_MONOTONIC)>deadline
end
raise 'Missing navigation error' unless view.error.is_a?(Lunetile::BrowserError) && view.error.code==:navigation
view.load_file('Web/index.html');browser_wait(view)
rows << ['navigation-failure-recovery',true]
view.dispose;view.dispose
raise 'Dispose failed' unless view.disposed? && view.state==:disposed
20.times do
  v=Lunetile::Browser.new(Rect.new(20,20,300,200));v.load_file('Web/index.html');v.dispose
  Graphics.update
end
GC.start;GC.compact if GC.respond_to?(:compact)
view=Lunetile::Browser.new(Rect.new(-10,10,400,280));view.load_file('Web/index.html');browser_wait(view)
Graphics.resize_screen(1280,720);view.rect=Rect.new(80,60,1120,600)
20.times { Graphics.update }
rows << ['recreate-resize',view.state,view.rect.width]
view=nil;GC.start
20.times { Graphics.update }
last=Lunetile::Browser.new(Rect.new(0,0,100,100));last.dispose
File.write('browser-result.json',JSON.generate({passed:true,checks:rows}))
File.write('runtime-complete.txt','browser smoke,false,false')
