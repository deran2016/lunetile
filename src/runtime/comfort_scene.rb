module Lunetile
  module Comfort
    class Scene
      def main
        @origin = self.class.instance_variable_get(:@origin) || :title
        @mode = :home
        @index = @scroll = 0
        @message = Controls.load_error || Comfort.error || ''
        width,height = [720,Graphics.width-32].min,[600,Graphics.height-32].min
        @window = Window_Base.new((Graphics.width-width)/2,(Graphics.height-height)/2,width,height)
        @window.contents = Bitmap.new(@window.width-32,@window.height-32) unless @window.contents
        @window.windowskin = nil
        @window.contents.font.size = 22
        @window.contents.font.color = Color.new(238,242,255)
        @visible = [(@window.contents.height-130)/32,1].max
        @running = true
        Graphics.transition
        while @running
          Graphics.update
          Input.update
          @window.update
          update
          draw
        end
        Graphics.freeze
      ensure
        @window&.dispose
      end
      def rows
        case @mode
        when :home
          ['키보드 버튼 설정','게임패드 버튼 설정',"진동: #{Controls.rumble_enabled? ? '켜짐' : '꺼짐'}",'진동 테스트',
           "자동 저장: #{Comfort.enabled? ? '켜짐' : '꺼짐'}",'자동 저장 / 백업 불러오기','조작 설정 기본값 복원','돌아가기']
        when :keyboard, :gamepad
          Controls::ACTIONS.keys.each_with_index.map { |a,i| "#{Controls::LABELS[i]}: #{Controls.prompt(a,@mode)}" } + ['돌아가기']
        when :recovery
          @entries.map { |path,label| label + '  ' + File.mtime(path).strftime('%m/%d %H:%M') } + ['돌아가기']
        when :confirm then ['이 저장으로 불러오기 (현재 진행은 저장되지 않음)','취소']
        end
      end
      def back
        if @mode == :home
          Comfort.vxa? ? SceneManager.return : $scene = (@origin == :menu ? Scene_Menu.new : Scene_Title.new)
          @running = false
        else
          @mode = :home
          @index = @scroll = 0
        end
      end
      def update
        key,pad = Controls.capture
        if @capturing
          if key == 27 || Process.clock_gettime(Process::CLOCK_MONOTONIC) >= @capture_until
            @capturing = false
            @message = '버튼 설정을 취소했습니다.'
          elsif (@mode == :keyboard && key) || (@mode == :gamepad && pad)
            action = Controls::ACTIONS.keys[@index]
            @mode == :keyboard ? Controls.bind(action, keys:[key]) : Controls.bind(action, pad:Controls::PADS.key(pad))
            @capturing = false
            @message = '설정을 저장했습니다.'
          end
          return
        end
        if key == 27 || Input.trigger?(Input::B)
          back
        elsif Input.repeat?(Input::DOWN)
          @index = (@index+1) % rows.size
        elsif Input.repeat?(Input::UP)
          @index = (@index-1) % rows.size
        elsif key == 13 || Input.trigger?(Input::C)
          select
        end
      rescue StandardError => failure
        @capturing = false
        @message = "처리하지 못했습니다 (#{failure.class}): #{failure.message}"[0,130]
      end
      def select
        if @index == rows.size-1 && @mode != :confirm
          return back
        end
        case @mode
        when :home
          case @index
          when 0,1 then @mode = @index.zero? ? :keyboard : :gamepad
          when 2 then Controls.rumble_enabled = !Controls.rumble_enabled?
          when 3 then @message = Controls.rumble(0.35,0.6,300) ? '진동 테스트 요청 완료' : '활성 XInput 게임패드가 없습니다.'
          when 4 then Comfort.enabled = !Comfort.enabled?
          when 5 then @entries = Comfort.candidates; @mode = :recovery; @message = @entries.empty? ? '자동 저장이나 백업이 없습니다.' : '불러올 저장을 선택하세요.'
          when 6 then Controls.reset; @message = '조작 설정을 기본값으로 복원했습니다.'
          end
          @index = @scroll = 0 unless @mode == :home
        when :keyboard, :gamepad
          @capturing = true
          @capture_until = Process.clock_gettime(Process::CLOCK_MONOTONIC) + 10
          @message = '새 버튼을 누르세요. Esc: 취소 (10초). 중복 버튼은 사용할 수 없습니다.'
        when :recovery
          @load_path = @entries[@index][0]
          @mode = :confirm
          @index = @scroll = 0
        when :confirm
          if @index.zero?
            Comfort.load(@load_path)
            @running = false
          else
            @mode = :recovery
            @index = @scroll = 0
          end
        end
      end
      def draw
        signature = [@mode,@index,@capturing,@message,Controls.device,Controls.rumble_enabled?,Comfort.enabled?]
        return if @drawn == signature
        @drawn = signature
        canvas = @window.contents
        canvas.fill_rect(canvas.rect,Color.new(23,31,45))
        canvas.draw_text(12,4,canvas.width-24,28,'Lunetile · 조작 / 저장 설정')
        @scroll = @index if @index < @scroll
        @scroll = @index-@visible+1 if @index >= @scroll+@visible
        canvas.fill_rect(6,40+(@index-@scroll)*32,canvas.width-12,32,Color.new(46,79,112))
        rows.slice(@scroll,@visible).each_with_index { |text,i| canvas.draw_text(14,40+i*32,canvas.width-28,32,text) }
        @window.cursor_rect.empty
        bottom = canvas.height-80
        canvas.font.size = 16
        confirm = Controls.prompt(:confirm).split(' / ').first
        cancel = Controls.prompt(:cancel).split(' / ').first
        canvas.draw_text(8,bottom,canvas.width-16,24,"#{confirm}: 확인 · #{cancel}: 뒤로 (Enter/Esc 가능)")
        lines = ['']
        @message.each_char do |char|
          lines << '' if canvas.text_size(lines.last+char).width > canvas.width-16
          lines[-1] += char
        end
        lines.first(2).each_with_index { |text,i| canvas.draw_text(8,bottom+24+i*22,canvas.width-16,22,text) }
        canvas.font.size = 22
      end
    end
  end
end
