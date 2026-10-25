# Online state belongs to the server; stock XP saves and map event interpreters are unused.
module LunetileMMO
  PROTOCOL=11
  def self.now; Process.clock_gettime(Process::CLOCK_MONOTONIC); end

  class Connection
    attr_reader :state, :notice, :id, :account, :account_error, :account_revision, :account_response_kind
    def initialize(config,lobby:false)
      @config = config
      profile = config.fetch('profile')
      raise 'profile은 영문 소문자/숫자/_ 1~32자로 지정하세요.' unless profile.match?(/\A[a-z0-9_]{1,32}\z/)
      @profile_path = "ClientProfile/#{profile}.json"
      @credentials = File.exist?(@profile_path) ? JSON.parse(File.read(@profile_path)) : nil
      @legacy_profile_path=@profile_path;@lobby=lobby;@account_requests=[];@account_revision=0
      @socket = Lunetile::TCP.connect(config.fetch('host'), config.fetch('port'), tls: false, timeout_ms: 5000)
      @buffer = ''.b
      @outgoing = ''.b
      @states = []
      @notice = '서버에 접속 중입니다...'
      @last_poll = LunetileMMO.now
      @last_response = @last_poll
    end

    def send_message(message)
      @account_requests << message['type'] if @lobby && (message['type'].start_with?('account_')||message['type'].start_with?('character_'))
      message=message.merge('seq'=>(@move_seq||0)+1) if message['type']=='move'
      payload = JSON.generate(message).b
      raise '요청이 너무 큽니다.' if payload.bytesize > 16_384
      raise '서버 송신 버퍼가 너무 큽니다.' if @outgoing.bytesize + payload.bytesize + 4 > 65_536
      @outgoing << [payload.bytesize].pack('N') << payload
      @move_seq=message['seq'] if message['type']=='move'
      message['seq']
    end

    def drain_states
      states,@states = @states,[]
      states
    end

    def update
      case @socket.state
      when :failed then raise "서버 접속 실패: #{@socket.error}"
      when :closed then raise '서버 연결이 종료되었습니다. 서버 실행과 client.json 주소를 확인하세요.'
      when :open
        unless @sent_login
          if @lobby
            send_message({'type'=>'account_poll'})
          elsif @credentials
            send_message({'type'=>'login', 'protocol'=>PROTOCOL, 'id'=>@credentials.fetch('id'), 'token'=>@credentials.fetch('token')})
          else
            name = @config.fetch('display_name')
            name = "모험가#{rand(100_000)}" if name.empty?
            send_message({'type'=>'register', 'protocol'=>PROTOCOL, 'name'=>name})
          end
          @sent_login = true
        end
        part = @socket.read(262_144)
        @buffer << part if part
        raise '서버 수신 버퍼가 너무 큽니다.' if @buffer.bytesize > 524_288
        16.times do
          break if @buffer.bytesize < 4
          size = @buffer.unpack1('N')
          raise '서버 메시지 크기 오류' unless size.between?(1,262_144)
          break if @buffer.bytesize < size+4
          bytes = @buffer.byteslice(4,size).force_encoding(Encoding::UTF_8)
          raise '서버 UTF-8 오류' unless bytes.valid_encoding?
          message = JSON.parse(bytes, create_additions: false, allow_nan: false, max_nesting: 32)
          @buffer = @buffer.byteslice(size+4..-1)
          receive(message)
          @last_response = LunetileMMO.now
        end
        raise '서버 응답 제한 시간 초과' if LunetileMMO.now - @last_response > 8
        if @state && LunetileMMO.now - @last_poll >= 1.0/30
          send_message({'type'=>'poll'})
          @last_poll = LunetileMMO.now
        end
        if @lobby && @account_requests.empty? && LunetileMMO.now-@last_poll>=1
          send_message({'type'=>'account_poll'});@last_poll=LunetileMMO.now
        end
        # One write per tick prevents poll and move frames delaying each other.
        unless @outgoing.empty?
          @socket.write(@outgoing)
          @outgoing = ''.b
        end
      end
    end

    def receive(message)
      case message.fetch('type')
      when 'account','account_error'
        raise '서버와 클라이언트를 함께 업데이트하세요. Protocol 11이 필요합니다.' if message['type']=='account' && message['protocol']!=PROTOCOL
        if message['type']=='account'
          valid=message['username'].nil? || (message['username'].is_a?(String) && message['username'].match?(/\A[a-z0-9_]{3,20}\z/))
          valid &&= message['characters'].is_a?(Array) && message['characters'].size==3 && message['characters'].all?{|c|c.nil? ||
            (c.is_a?(Hash) && c['id'].is_a?(String) && c['id'].match?(/\A[a-z0-9_]{1,48}\z/) && c['name'].is_a?(String) && c['name'].size.between?(1,16) &&
              c['character'].is_a?(String) && c['character'].match?(/\A[A-Za-z0-9 _-]{1,64}\z/) && c['level'].is_a?(Integer) && c['level'].between?(1,1000) &&
              c['job'].is_a?(String) && c['job'].match?(/\A[a-z0-9_]{1,24}\z/) && c['map_name'].is_a?(String) && c['map_name'].size.between?(1,64))}
          valid &&= message['appearances'].is_a?(Array) && message['appearances'].size==3 && message['appearances'].all?{|v|v.is_a?(String)&&v.match?(/\A[A-Za-z0-9 _-]{1,64}\z/)}
          raise '캐릭터 선택 응답 형식 오류' unless valid
        end
        @account_response_kind=@account_requests.shift;@account_revision+=1
        if message['type']=='account';@account=message;@account_error=nil
        else;@account_error=message.fetch('message');raise '인증 오류 메시지 형식 오류' unless @account_error.is_a?(String) && @account_error.size<=1024
        end
        return
      when 'error' then raise message.fetch('message')
      when 'welcome'
        raise '서버와 클라이언트를 함께 업데이트하세요. Protocol 11이 필요합니다.' unless message['protocol'] == PROTOCOL
        @catalog=message.fetch('catalog')
        raise '서버 정의 캐시 형식 오류' unless @catalog.is_a?(Hash) && @catalog.keys.sort==%w[items particle_presets progression services skills] &&
          %w[items skills particle_presets].all?{|k|@catalog[k].is_a?(Array)} && %w[progression services].all?{|k|@catalog[k].nil? || @catalog[k].is_a?(Hash)}
        @id = message.fetch('id')
        if @lobby
          raise '캐릭터 ID 형식 오류' unless @id.is_a?(String) && @id.match?(/\A[a-z0-9_]{1,48}\z/)
          @profile_path="ClientProfile/c_#{@id}.json"
          old=@legacy_profile_path.sub(/\.json\z/,'.quicks.json');target=@profile_path.sub(/\.json\z/,'.quicks.json')
          if @credentials && @credentials['id']==@id && File.exist?(old) && !File.exist?(target)
            bytes=File.binread(old);data=JSON.parse(bytes) if bytes.bytesize<=4096
            if data && data['id']==@id && valid_quickslots?(data['slots'])
              File.open(target+'.tmp','wb'){|f|f.write(bytes);f.flush;f.fsync};File.rename(target+'.tmp',target)
            end
          end
          @lobby=false
        end
        Dir.mkdir('ClientProfile') unless Dir.exist?('ClientProfile')
        credentials = JSON.generate({'id'=>@id,'token'=>message.fetch('token')})
        File.open(@profile_path+'.tmp','wb') { |file| file.write(credentials); file.flush; file.fsync }
        File.rename(@profile_path+'.tmp',@profile_path)
        @state = @catalog.merge(message.fetch('state'))
      when 'state'
        raise '서버 정의를 받기 전에 상태가 도착했습니다.' unless @catalog
        @state = @catalog.merge(message)
      else raise '알 수 없는 서버 메시지'
      end
      ack=@state.fetch('move_ack');seq=ack.fetch('seq')
      raise '서버 이동 순번 오류' unless seq.is_a?(Integer) && seq.between?(@acked_move||0,@move_seq||0) && [true,false].include?(ack['accepted'])
      @acked_move=seq
      @states << @state
      @notice = @state['notice'] unless @state['notice'].to_s.empty?
    end

    def quickslots
      unless @quicks_loaded
        path=@profile_path.sub(/\.json\z/,'.quicks.json')
        if File.exist?(path)
          raise '퀵슬롯 설정 파일이 너무 큽니다.' if File.size(path)>4096
          data=JSON.parse(File.read(path,encoding:'UTF-8'))
          raise '퀵슬롯 설정 형식을 확인하세요.' unless data.is_a?(Hash) && data.keys.sort==['id','slots'] && data['id'].is_a?(String) && valid_quickslots?(data['slots'])
          @quicks=data['slots'] if data['id']==@id
        end
        @quicks_loaded=true
      end
      @quicks || LunetileMMO.default_quickslots(@state)
    end
    def legacy_credentials;@credentials;end
    def valid_quickslots?(slots)
      slots.is_a?(Array) && slots.size==8 && slots.all?{|s|s.nil? || (s.is_a?(String) && s.match?(/\A(?:skill|item):[a-z0-9_]{1,64}\z/))}
    end
    def save_quickslots(slots)
      raise '퀵슬롯 설정 형식 오류' unless valid_quickslots?(slots)
      path=@profile_path.sub(/\.json\z/,'.quicks.json')
      File.open(path+'.tmp','wb'){|file|file.write(JSON.generate({'id'=>@id,'slots'=>slots}));file.flush;file.fsync}
      File.rename(path+'.tmp',path)
      @quicks=slots.dup;@quicks_loaded=true
    end
    def close; @socket&.close; end
  end

end
