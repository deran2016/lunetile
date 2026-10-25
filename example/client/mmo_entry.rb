module LunetileMMO
  class Entry
    DARK=Color.new(42,62,83);MUTED=Color.new(101,128,151);ORANGE=Color.new(255,149,62);WHITE=Color.new(250,253,255)
    JOB_NAMES=%w[초보자 전사 마법사 궁수 도적 검사 위자드 레인저 어쌔신].zip(%w[beginner warrior mage archer rogue warrior2 mage2 archer2 rogue2]).to_h.invert
    attr_reader :connection
    def initialize(config)
      raise '새 Lunetile.dll과 Scripts.rxdata를 함께 업데이트하세요. text_submit API가 필요합니다.' unless defined?(Lunetile::UIInput) && Lunetile::UIInput.respond_to?(:text_submit?)
      @config=config;@connection=Connection.new(config,lobby:true);@mode=:login;@fields=['','',''];@field=0;@selected=0;@appearance=0;@panels=[];@portraits=[];@buttons=[];@revision=0
      @previous_background=Graphics.background_update;Graphics.background_update=true
      @remember="ClientProfile/#{config.fetch('profile')}.account.json"
      if File.exist?(@remember)&&File.size(@remember)<1024
        data=JSON.parse(File.read(@remember));@fields[0]=data['username'] if data['username'].is_a?(String)&&data['username'].match?(/\A[a-z0-9_]{3,20}\z/)
      end
      backdrop;layout;focus(0)
    end
    def backdrop
      @background=Bitmap.new(Graphics.width,Graphics.height);b=@background
      Graphics.height.times{|y|t=y.to_f/Graphics.height;b.fill_rect(0,y,Graphics.width,1,Color.new(155+73*t,211+30*t,239+8*t))}
      [[110,120,90],[280,70,60],[1020,95,100],[1190,180,70],[70,470,85]].each do |x,y,r|
        (-r..r).each{|dy|half=Math.sqrt(r*r-dy*dy).to_i;b.fill_rect(x-half,y+dy,half*2+1,1,Color.new(244,252,255))}
      end
      b.fill_rect(0,Graphics.height-72,Graphics.width,72,Color.new(208,235,209));b.font.name='맑은 고딕';b.font.size=14;b.font.color=MUTED
      b.draw_text(32,Graphics.height-38,700,24,'LUNETILE  ·  나만의 작은 모험이 시작되는 곳')
      @background_sprite=Sprite.new;@background_sprite.bitmap=b;@background_sprite.z=1900
    end
    def panel(x,y,w,h)
      p=Panel.new(x,y,w,h,nil,background:WHITE);p.z=2000;p.alpha=248;@panels<<p;p
    end
    def layout
      @panels.each(&:dispose);@panels=[];@portraits.each(&:dispose);@portraits=[];@buttons=[]
      if @mode==:characters
        @header=panel(80,50,1120,90);@cards=3.times.map{|i|panel(110+i*360,170,340,385)};@footer=panel(110,575,1060,70)
        3.times{@portraits<<Sprite.new};@portraits.each{|s|s.z=2005;s.zoom_x=s.zoom_y=2.4}
        Lunetile::UIInput.text_input=false
      elsif @mode==:create
        @creator=panel(210,100,860,530)
        3.times{@portraits<<Sprite.new};@portraits.each{|s|s.z=2005;s.zoom_x=s.zoom_y=2.4}
        Lunetile::UIInput.text_input=false;Lunetile::UIInput.text_input=true;Lunetile::UIInput.ime_open=true
      else
        @hero=panel(80,140,640,400);@login=panel(790,110,410,490)
      end
      draw
    end
    def focus(index)
      @field=index;u=Lunetile::UIInput;u.text_input=false;u.text_input=true;u.ime_open=false
    end
    def request(message)
      return if @pending
      @pending=message['type'];@status='서버에서 확인 중입니다...';@connection.send_message(message)
    end
    def authenticate
      return if @pending
      if @mode==:register && @fields[1]!=@fields[2];@status='비밀번호 확인이 일치하지 않습니다.';return;end
      request({'type'=>@mode==:register ? 'account_register' : 'account_login','protocol'=>PROTOCOL,'username'=>@fields[0],'password'=>@fields[1]})
    end
    def button(p,x,y,w,h,text,key,primary=false)
      color=primary ? ORANGE : Color.new(222,237,245);p.bitmap.fill_rect(x,y,w,h,color);p.label(x,y,w,h,text,DARK,16,1)
      @buttons<<[p.x+x,p.y+y,w,h,key]
    end
    def draw
      @buttons=[]
      if @mode==:characters;draw_characters;elsif @mode==:create;draw_creation;else;draw_login;end
    end
    def draw_login
      @hero.redraw([:hero]) do |p|
        p.label(30,55,580,62,'LUNETILE',DARK,48,1);p.label(30,115,580,48,'STORY',ORANGE,32,1)
        p.label(30,200,580,40,'오늘은 어떤 모험을 떠나볼까요?',DARK,24,1)
        p.label(30,265,580,28,'함께 사냥하고, 성장하고, 새로운 친구를 만나세요.',MUTED,16,1)
        p.label(30,305,580,28,'로그인 후 캐릭터를 선택하면 모험이 시작됩니다.',MUTED,16,1)
      end
      @login.redraw(nil) do |p|
        p.label(28,25,354,40,@mode==:register ? '새 계정 만들기' : '다시 만나서 반가워요!',DARK,25)
        labels=['아이디','비밀번호','비밀번호 확인'];count=@mode==:register ? 3 : 2
        count.times do |i|
          y=90+i*82;p.label(28,y-24,350,24,labels[i],MUTED,14)
          p.bitmap.fill_rect(26,y,358,42,i==@field ? Color.new(102,183,215) : Color.new(203,220,232));p.bitmap.fill_rect(28,y+2,354,38,WHITE)
          text=i==0 ? @fields[i] : '•'*[@fields[i].size,24].min;text+='|' if i==@field&&(LunetileMMO.now*2).to_i.even?
          p.label(38,y+4,330,32,text,DARK,18)
        end
        p.label(28,328,354,24,'ID 3~20자 · 비밀번호 12~128자',MUTED,13)
        @status.to_s.each_char.each_slice(28).first(2).each_with_index{|line,i|p.label(28,355+i*18,354,18,line.join,Theme::RED,13)}
        button(p,28,402,354,42,@pending ? '처리 중...' : (@mode==:register ? '회원가입하고 시작하기' : '로그인'),:authenticate,true)
        button(p,28,451,354,26,@mode==:register ? '이미 계정이 있어요 · 로그인' : '처음 오셨나요? · 회원가입',:toggle)
      end
      p=@login;Lunetile::UIInput.caret_rect=Rect.new(p.x+38+[@fields[@field].size,22].min*12,p.y+96+@field*82,1,28)
    end
    def draw_characters
      slots=@connection.account.fetch('characters');username=@connection.account.fetch('username')
      @header.redraw([username]){|p|p.label(28,16,850,34,'캐릭터 선택',DARK,28);p.label(28,52,850,25,'함께할 모험가를 선택하거나 나만의 캐릭터를 만들어 보세요.',MUTED,15)}
      button(@header,960,24,130,38,'로그아웃',:logout)
      @cards.each_with_index do |p,i|
        c=slots[i];p.alpha=i==@selected ? 255 : 224
        p.redraw(nil) do |v|
          v.label(24,20,292,28,"CHARACTER  0#{i+1}",MUTED,14)
          v.bitmap.fill_rect(30,232,280,15,Color.new(166,208,178));v.bitmap.fill_rect(42,247,256,23,Color.new(220,230,212))
          if c
            v.label(12,60,316,34,c['name'],DARK,24,1);v.label(20,101,300,26,"Lv.#{c['level']}  #{JOB_NAMES.fetch(c['job'],c['job'])}",MUTED,16,1)
            v.label(18,282,304,28,c['map_name'],MUTED,14,1);button(v,25,326,290,42,'모험 시작',[:select,i],true)
          else
            v.label(20,60,300,32,'새로운 모험가',DARK,23,1);v.label(20,101,300,26,'닉네임과 캐릭터 이미지를 선택하세요.',MUTED,14,1)
            button(v,25,326,290,42,'캐릭터 생성',[:create,i],true)
          end
        end
        s=@portraits[i];bitmap=RPG::Cache.character(c ? c['character'] : @connection.account.fetch('appearances')[@appearance],0)
        s.bitmap=bitmap;w=bitmap.width/4;h=bitmap.height/4;s.src_rect=Rect.new(((LunetileMMO.now*3).to_i%4)*w,0,w,h);s.ox=w/2;s.oy=h;s.x=p.x+p.width/2;s.y=p.y+234;s.opacity=c||i==@selected ? 255 : 160
      end
      @footer.redraw(nil){|p|p.label(18,12,700,24,@status.to_s,DARK,14);p.label(18,39,700,24,'외형은 자유롭게 · 직업은 모험 중 전직으로 선택합니다.',MUTED,13)}
      legacy=@connection.legacy_credentials
      if legacy&&!slots.compact.any?{|c|c['id']==legacy['id']};button(@footer,755,16,285,38,'이전 프로필 캐릭터 연결',:claim);end
    end
    def draw_creation
      p=@creator;u=Lunetile::UIInput
      p.redraw(nil) do |v|
        v.label(28,20,804,40,'새 캐릭터 만들기',DARK,28,1)
        v.label(28,65,804,26,'함께 모험할 캐릭터 이미지를 선택하세요.',MUTED,16,1)
        3.times do |i|
          x=70+i*260;v.bitmap.fill_rect(x,204,200,8,Color.new(166,208,178))
          button(v,x,220,200,36,"#{i==@appearance ? '✓ ' : ''}캐릭터 #{i+1}",[:appearance,i],i==@appearance)
        end
        v.label(200,282,460,26,'닉네임',DARK,16)
        v.bitmap.fill_rect(198,312,464,44,Color.new(102,183,215));v.bitmap.fill_rect(200,314,460,40,WHITE)
        text=@nickname.to_s+u.composition.to_s;text+='|' if (LunetileMMO.now*2).to_i.even?
        v.label(212,318,436,32,text,DARK,20)
        v.label(200,363,600,24,'한글·영문·숫자 2~12자 · 영문 대소문자 구분 없이 중복 불가',MUTED,13)
        @status.to_s.each_char.each_slice(42).first(2).each_with_index{|line,i|v.label(150,394+i*20,620,20,line.join,Theme::RED,14,1)}
        button(v,200,463,220,42,@pending ? '확인 중...' : '캐릭터 생성',:confirm_create,true)
        button(v,440,463,220,42,'취소',:cancel_create)
      end
      @portraits.each_with_index do |s,i|
        bitmap=RPG::Cache.character(@connection.account.fetch('appearances')[i],0);w=bitmap.width/4;h=bitmap.height/4
        s.bitmap=bitmap;s.src_rect=Rect.new(((LunetileMMO.now*3).to_i%4)*w,0,w,h);s.ox=w/2;s.oy=h;s.x=p.x+170+i*260;s.y=p.y+205;s.opacity=i==@appearance ? 255 : 160
      end
      u.caret_rect=Rect.new(p.x+212+[@nickname.to_s.size,12].min*20,p.y+318,1,30)
    end
    def create_character
      return if @pending
      name=@nickname.to_s+Lunetile::UIInput.composition.to_s
      unless name.match?(/\A[가-힣A-Za-z0-9]{2,12}\z/);@status='닉네임은 한글·영문·숫자 2~12자로 입력하세요.';return;end
      @nickname=name;Lunetile::UIInput.text_input=false;Lunetile::UIInput.text_input=true
      request({'type'=>'character_create','slot'=>@selected,'appearance'=>@appearance,'name'=>@nickname})
    end
    def action(key)
      return if @pending
      case key
      when :authenticate;authenticate
      when :toggle;@mode=@mode==:login ? :register : :login;@fields[1]=@fields[2]='';@status=nil;layout;focus(0)
      when :logout;@connection.close;@connection=Connection.new(@config,lobby:true);@mode=:login;@fields[1]=@fields[2]='';@status=nil;@revision=0;layout;focus(0)
      when :claim;c=@connection.legacy_credentials;request({'type'=>'character_claim','id'=>c['id'],'token'=>c['token']})
      when :confirm_create;create_character
      when :cancel_create;@mode=:characters;@nickname='';@status=nil;layout
      when Array
        kind,index=key
        if kind==:appearance;@appearance=index
        elsif kind==:create;@selected=index;@mode=:create;@nickname='';@status=nil;layout
        else
          @selected=index
          request({'type'=>'character_select','slot'=>index})
        end
      end
    end
    def update
      @connection.update
      if @connection.account_revision!=@revision
        @revision=@connection.account_revision
        if @connection.account_response_kind==@pending
          created=@pending=='character_create' && !@connection.account_error
          @pending=nil;@status=@connection.account_error || ''
          if created;@mode=:characters;@nickname='';@status='캐릭터를 생성했습니다. 모험을 시작하세요!';layout;end
        end
        if @connection.account && @connection.account['username'] && [:login,:register].include?(@mode)
          @fields[1]=@fields[2]='';@mode=:characters;@status='캐릭터를 선택하거나 새로 생성하세요.';layout
          begin
            Dir.mkdir('ClientProfile') unless Dir.exist?('ClientProfile');File.write(@remember+'.tmp',JSON.generate({'username'=>@connection.account['username']}));File.rename(@remember+'.tmp',@remember)
          rescue SystemCallError
            @status='아이디 기억 파일을 저장하지 못했습니다. 게임 이용은 가능합니다.'
          end
        end
      end
      return if @connection.state
      u=Lunetile::UIInput
      if @mode==:create
        u.text_input=true
        chars=u.text
        unless @pending
          @nickname=(@nickname.to_s+chars)[0,12]
          @nickname=@nickname[0...-1] if u.key_trigger?(:backspace)&&!u.composing?
          create_character if u.text_submit?
          action(:cancel_create) if u.key_trigger?(:escape)
        end
      elsif @mode!=:characters
        u.text_input=true;u.ime_open=false if u.ime_open?
        count=@mode==:register ? 3 : 2
        chars=u.text.each_char.select{|ch|ch.ord.between?(32,126)}.join
        chars=chars.downcase.gsub(/[^a-z0-9_]/,'') if @field==0
        @fields[@field]=(@fields[@field]+chars)[0,@field==0 ? 20 : 128]
        @fields[@field]=@fields[@field][0...-1] if u.key_trigger?(:backspace)
        focus((@field+1)%count) if u.key_trigger?(:tab)
        authenticate if u.text_submit?
        @quit=true if u.key_trigger?(:escape)
      else
        @selected=(@selected+1)%3 if u.key_trigger?(:right);@selected=(@selected+2)%3 if u.key_trigger?(:left)
        action([:select,@selected]) if u.key_trigger?(:enter)&&@connection.account['characters'][@selected]
        action(:logout) if u.key_trigger?(:escape)
      end
      if u.mouse_trigger?(:left) && (point=u.mouse_press_position||u.mouse_position)
        if [:login,:register].include?(@mode)
          count=@mode==:register ? 3 : 2
          count.times{|i|focus(i) if point[0].between?(@login.x+28,@login.x+382)&&point[1].between?(@login.y+90+i*82,@login.y+132+i*82)}
        elsif @mode==:characters
          @cards.each_with_index{|p,i|@selected=i if p.hit?(*point)}
        end
        b=@buttons.reverse.find{|x,y,w,h,_|point[0]>=x&&point[0]<x+w&&point[1]>=y&&point[1]<y+h};action(b[4]) if b
      end
      draw
    end
    def main
      Graphics.transition
      until @quit||@connection.state;Graphics.update;Input.update;update;end
      @connection.state ? @connection : nil
    ensure
      Lunetile::UIInput.text_input=false;@connection.close unless @connection.state
      @portraits.each(&:dispose);@panels.each(&:dispose);@background_sprite.dispose;@background.dispose
      Graphics.background_update=@previous_background
    end
  end
end
