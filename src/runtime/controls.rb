module Lunetile::Controls
  PATH = 'Saves/Lunetile/controls.json'
  ACTIONS = {down:2, left:4, right:6, up:8, dash:11, cancel:12, confirm:13,
             x:14, y:15, z:16, previous:17, next:18}.freeze
  LABELS = %w[아래 왼쪽 오른쪽 위 달리기 취소 확인 보조X 보조Y 보조Z 이전 다음].freeze
  PADS = {down:2, left:4, right:8, up:1, start:16, back:32, ls:64, rs:128,
          lb:256, rb:512, a:4096, b:8192, x:16384, y:32768, lt:65536, rt:131072}.freeze
  DEFAULTS = [[40],[37],[39],[38],[16],[27,88,96],[32,90,13],[65],[83],[68],[81,33],[87,34]].freeze
  DEFAULT_PADS = [2,4,8,1,16384,8192,4096,32768,0,0,256,512].freeze
  def self.defaults
    {'version'=>1, 'rumble'=>true, 'bindings'=>ACTIONS.keys.each_with_index.to_h { |a,i| [a.to_s, [DEFAULTS[i].dup, DEFAULT_PADS[i]]] }}
  end
  def self.validate(value)
    raise ArgumentError, 'Invalid controls settings' unless value.is_a?(Hash) && value.keys.sort == %w[bindings rumble version] &&
      value['version'] == 1 && [true,false].include?(value['rumble']) && value['bindings'].is_a?(Hash) &&
      value['bindings'].keys.sort == ACTIONS.keys.map(&:to_s).sort
    keys, pads = [], []
    ACTIONS.each_key do |action|
      row = value['bindings'][action.to_s]
      raise ArgumentError, 'Invalid binding' unless row.is_a?(Array) && row.size == 2 && row[0].is_a?(Array) && row[0].size <= 4 &&
        row[0].all? { |k| k.is_a?(Integer) && k.between?(8,255) && ![123,229].include?(k) } &&
        row[1].is_a?(Integer) && ([0] + PADS.values).include?(row[1])
      raise ArgumentError, 'Movement, confirm and cancel require keyboard bindings' if %i[down left right up cancel confirm].include?(action) && row[0].empty?
      keys.concat(row[0]); pads << row[1] unless row[1].zero?
    end
    raise ArgumentError, 'Key or pad button is already used' unless keys.uniq == keys && pads.uniq == pads
    value
  end
  def self.apply(value)
    __configure(ACTIONS.map { |name,id| [id, *value['bindings'].fetch(name.to_s)] })
    @settings = value
    __rumble(0,0,0) unless value['rumble']
  end
  def self.save(value)
    validate(value)
    Lunetile::SaveFiles.replace(PATH, JSON.generate(value))
    apply(value)
  end
  def self.binding(action)
    keys,pad = @settings['bindings'].fetch(action.to_s)
    [keys.dup, PADS.key(pad)]
  end
  def self.bind(action, keys: nil, pad: nil)
    raise ArgumentError, 'Unknown control action' unless ACTIONS.key?(action)
    value = Marshal.load(Marshal.dump(@settings))
    row = value['bindings'].fetch(action.to_s)
    row[0] = keys if keys
    row[1] = pad == :none ? 0 : PADS.fetch(pad) if pad
    save(value)
  end
  def self.reset
    save(defaults)
  end
  def self.rumble_enabled?; @settings['rumble']; end
  def self.rumble_enabled=(enabled)
    value = Marshal.load(Marshal.dump(@settings))
    value['rumble'] = enabled
    save(value)
  end
  def self.rumble(left=0.3, right=0.5, duration_ms=150)
    return __rumble(0,0,0) unless rumble_enabled?
    __rumble(left,right,duration_ms)
  end
  def self.key_name(key)
    return key.chr if key.between?(48,90)
    {8=>'Backspace',9=>'Tab',13=>'Enter',16=>'Shift',17=>'Ctrl',18=>'Alt',27=>'Esc',32=>'Space',
     33=>'PgUp',34=>'PgDn',35=>'End',36=>'Home',37=>'←',38=>'↑',39=>'→',40=>'↓',45=>'Insert',46=>'Delete',96=>'Num0'}.fetch(key, "VK#{key}")
  end
  def self.prompt(action, source=device)
    keys,pad = binding(action)
    source == :gamepad ? (pad ? pad.to_s.upcase : '미설정') : keys.map { |k| key_name(k) }.join(' / ')
  end
  def self.load_error; @load_error; end
  apply(defaults)
  begin
    if File.file?(PATH)
      raise ArgumentError, 'Controls file exceeds 16 KiB' if File.size(PATH) > 16384
      apply(validate(JSON.parse(File.binread(PATH), create_additions:false, max_nesting:8)))
    end
  rescue StandardError => error
    @load_error = "조작 설정을 읽지 못해 기본값을 사용합니다 (#{error.class})"
  end
end
