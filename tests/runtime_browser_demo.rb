$demo_browser&.dispose
Graphics.frame_rate=120
canvas=Sprite.new
canvas.bitmap=Bitmap.new(Graphics.width,Graphics.height)
canvas.bitmap.fill_rect(canvas.bitmap.rect,Color.new(21,28,42))
label=Sprite.new
label.bitmap=Bitmap.new(Graphics.width-64,112)
label.x=label.y=32
label.bitmap.font.name='Malgun Gothic'
label.bitmap.font.size=20
player=Sprite.new
player.bitmap=Bitmap.new(24,24)
player.bitmap.fill_rect(player.bitmap.rect,Color.new(240,180,40))
player.x=32;player.y=Graphics.height-48
message=''
open_page=lambda do
  begin
    $demo_browser=Lunetile::Browser.new(Rect.new(80,160,Graphics.width-160,Graphics.height-240))
    $demo_browser.load_file('Web/index.html')
    message=''
  rescue Lunetile::BrowserError=>error
    message="브라우저 오류: #{error.code} (#{error.native_code})"
  end
end
open_page.call if Lunetile::Browser.available?
loop do
  Graphics.update
  Input.update
  player.x=[0,[Graphics.width-24,player.x+((Input.dir4==6 ? 2 : Input.dir4==4 ? -2 : 0))].min].max
  if Input.trigger?(Input::C) && (!$demo_browser || $demo_browser.disposed?)
    open_page.call
  end
  if Graphics.frame_count%24==0
    label.bitmap.clear
    state=$demo_browser&.state || :unavailable
    label.bitmap.draw_text(0,0,label.bitmap.width,30,'Lunetile · XP/VX Ace 브라우저 예제')
    label.bitmap.draw_text(0,32,label.bitmap.width,30,'패널 × / Esc: 닫기 · Enter/Z: 다시 열기 · 바깥 클릭: 게임 입력 · Alt+Enter: 전체 화면')
    text=message.empty? ? "진행 #{Graphics.frame_count}틱 / #{Graphics.logic_rate}Hz · 상태 #{state} · 방향키로 노란 상자 이동" : message
    label.bitmap.draw_text(0,64,label.bitmap.width,30,text)
  end
end
