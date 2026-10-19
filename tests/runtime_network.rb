class Reset < Exception; end unless defined?(Reset)
module NetworkProbe
  @checks = []
  class << self
    attr_reader :checks
    def now; Process.clock_gettime(Process::CLOCK_MONOTONIC); end
    def check(name)
      raise "Network check failed: #{name}" unless yield
      @checks << name
    end
    def raises(type)
      begin
        yield
      rescue type
        return true
      end
      false
    end
    def wait(seconds = 6)
      deadline = now + seconds
      until yield
        raise 'Network fixture deadline exceeded' if now >= deadline
        Graphics.update
        Input.update
      end
    end
    def address(path, secure = false, port = nil)
      "#{secure ? 'https' : 'http'}://localhost:#{port || NETWORK_PORTS[secure ? 'https' : 'http']}#{path}"
    end
    def request(path, method = :get, **options)
      call = Lunetile::HTTP.request(method, address(path), **options)
      wait { call.done? }
      raise "HTTP failed: #{call.error}" unless call.state == :succeeded
      call.response
    end
    def failure(url, **options)
      call = Lunetile::HTTP.request(:get, url, **options)
      wait { call.done? }
      check('HTTP failure returned without raising') { call.state == :failed && call.response.nil? && call.error.is_a?(Lunetile::NetworkError) }
      call.error.code
    end
    def connect(port, tls = false, host: nil, **options)
      connection = Lunetile::TCP.connect(host || (tls ? 'localhost' : '127.0.0.1'), NETWORK_PORTS[port], tls: tls, **options)
      wait { connection.state != :connecting }
      connection
    end
    def drain(connection, expected)
      bytes = ''.b
      wait { part = connection.read(17); bytes << part if part; bytes.bytesize >= expected }
      bytes
    end
    def idle
      wait { Lunetile.__network_counts.bytes == [0, 0] }
    end
  end
end
probe = NetworkProbe

# Exercise the runtime's actual Reset handler, including retained Ruby references.
$network_resets ||= 0
if $network_resets < 3
  $network_pending = Lunetile::HTTP.request(:get, probe.address('/slow'))
  $network_connection = probe.connect('tcp')
  raise "Reset TCP setup failed: #{$network_connection.state} #{$network_connection.error}" unless $network_connection.state == :open
  $network_resets += 1
  raise Reset
end
probe.check('F12 reset closes old jobs and preserves safe handles') do
  $network_pending.state == :cancelled && $network_connection.state == :closed && Lunetile.__network_counts.bytes == [0, 0]
end

probe.check('pinned embedded JSON') { JSON::VERSION == '2.18.0' && JSON.parse(JSON.generate({'한글' => [nil, true, 1.5]})) == {'한글' => [nil, true, 1.5]} }
%i[get post put patch delete options].each do |method|
  response = probe.request('/echo?query=ok', method, json: {'한글' => [1, false]}, headers: {'Authorization' => 'Bearer LUNETILE-TEST-SECRET'})
  data = response.json
  probe.check("REST #{method} JSON and explicit authorization") { response.status == 200 && data['method'] == method.to_s.upcase && JSON.parse(data['body']) == {'한글' => [1, false]} && data['authorization'] == 'Bearer LUNETILE-TEST-SECRET' }
end
probe.check('HEAD empty body') { probe.request('/echo', :head).body == ''.b }
probe.check('binary request body') { probe.request('/echo', :post, body: "\x00\xff\x10".b).json['body_hex'] == '00ff10' }
probe.check('timeout and URL validation before starting I/O') do
  probe.raises(ArgumentError) { Lunetile::HTTP.request(:get, 'file:///C:/secret') } &&
    probe.raises(ArgumentError) { Lunetile::HTTP.request(:get, 'https://user:password@example.com/') } &&
    probe.raises(ArgumentError) { Lunetile::HTTP.request(:get, probe.address('/echo'), timeout_ms: 0) }
end
probe.check('204 empty response') { response = probe.request('/status/204'); response.status == 204 && response.body.empty? }
[400, 401, 500].each { |status| probe.check("HTTP #{status} is a response") { probe.request("/status/#{status}").status == status } }
probe.check('binary response bytes and encoding') { response = probe.request('/binary'); response.body.encoding == Encoding::BINARY && response.body.bytes == (0..255).to_a * 3 }
probe.check('duplicate response headers preserved') { probe.request('/cookies').headers['set-cookie'] == ['a=1', 'b=2'] }
probe.check('no automatic cookies') { probe.request('/echo').json['cookie'].nil? }
probe.check('redirect returned without following') { response = probe.request('/redirect'); response.status == 302 && response.headers['location'] == ['/echo'] }
%w[/invalid-json /invalid-utf8 /deep /nan].each do |path|
  response = probe.request(path)
  probe.check("strict JSON #{path}") { probe.raises(JSON::ParserError) { response.json } || probe.raises(JSON::NestingError) { response.json } }
end
probe.check('remote JSON never restores Ruby objects') do
  response = Lunetile::HTTP::Response.new(200, '', '{"json_class":"DangerousClass","value":1}'.b)
  response.json == {'json_class' => 'DangerousClass', 'value' => 1}
end
%w[/huge /gzip-huge /headers].each { |path| probe.check("bounded response #{path}") { [:limit, :http].include?(probe.failure(probe.address(path))) } }
probe.check('overall deadline includes drip-fed response') { probe.failure(probe.address('/drip'), timeout_ms: 180) == :timeout }
probe.check('slow response timeout') { probe.failure(probe.address('/slow'), timeout_ms: 100) == :timeout }
probe.check('connection refusal or bounded connect timeout') { [:connect, :http, :timeout].include?(probe.failure(probe.address('/echo', false, NETWORK_PORTS['refused']), timeout_ms: 500)) }
probe.check('DNS failure or bounded resolver timeout') { [:dns, :timeout].include?(probe.failure('http://lunetile-no-such-host.invalid/', timeout_ms: 500)) }

probe.idle
if NETWORK_PORTS['tcp6']
  client = probe.connect('tcp6', false, host: '::1')
  client.write('IPv6')
  probe.check('IPv6 loopback roundtrip') { client.state == :open && probe.drain(client, 4) == 'IPv6' }
  client.close
end
probe.check('TCP DNS failure or bounded resolver timeout') do
  client = Lunetile::TCP.connect('lunetile-no-such-host.invalid', 1, tls: false, timeout_ms: 300)
  probe.wait { client.state != :connecting }
  client.state == :failed && [:dns, :timeout].include?(client.error.code)
end
probe.idle
calls = Array.new(8) { Lunetile::HTTP.request(:get, probe.address('/slow')) }
probe.check('HTTP concurrency limit') { probe.raises(Lunetile::NetworkError) { Lunetile::HTTP.request(:get, probe.address('/slow')) } }
calls.each { |call| call.cancel }
probe.check('cancelled request terminal state') { calls.all? { |call| call.done? && call.state == :cancelled && call.response.nil? } }
probe.idle
calls = nil
8.times { Lunetile::HTTP.request(:get, probe.address('/slow')) }
GC.start(full_mark: true, immediate_sweep: true)
probe.idle
probe.check('GC cancels unreachable requests') { Lunetile.__network_counts.bytes == [0, 0] }

connection = probe.connect('tcp')
probe.check('TCP asynchronous connection') { connection.state == :open && connection.error.nil? && connection.read.nil? }
first = [28].pack('N') + 'fragmented payload'.b
second = "\x00\xffcombined\x00".b
probe.check('TCP queues whole write') { connection.write(first) == first.bytesize && connection.write(second) == second.bytesize }
probe.check('TCP stream handles split and coalesced data') { probe.drain(connection, first.bytesize + second.bytesize) == first + second }
probe.check('TCP cannot be serialized') { probe.raises(TypeError) { Marshal.dump(connection) } }
probe.check('oversized TCP write has no partial side effect') { probe.raises(Lunetile::NetworkError) { connection.write('x' * (1024 * 1024 + 1)) } }
connection.write('probe')
probe.check('TCP still usable after rejected write') { probe.drain(connection, 5) == 'probe' }
connection.write('CLOSE')
probe.wait { connection.state == :closed }
probe.check('EOF preserves buffered data') { probe.drain(connection, 4) == 'tail' && connection.read.nil? }
probe.check('closed TCP write rejected') { probe.raises(Lunetile::NetworkError) { connection.write('x') } }
probe.idle

connections = Array.new(8) { probe.connect('tcp') }
probe.check('TCP concurrency limit') { probe.raises(Lunetile::NetworkError) { probe.connect('tcp') } }
connections.each(&:close)
probe.idle
probe.check('refused TCP connection') { client = probe.connect('refused'); client.state == :failed && client.error.code == :connect }
probe.check('TCP TLS handshake has deadline') { client = probe.connect('stall', true, host: '127.0.0.1', timeout_ms: 150); client.state == :failed && client.error.code == :timeout }
probe.check('TCP TLS handshake rejects plaintext') { client = probe.connect('junk', true, host: '127.0.0.1'); client.state == :failed && [:tls, :io].include?(client.error.code) }

probe.idle
client = probe.connect('stall', false, timeout_ms: 300)
backpressure = false
32.times do
  begin
    client.write('x' * (1024 * 1024))
  rescue Lunetile::NetworkError => error
    backpressure = error.code == :backpressure
    break
  end
end
probe.check('TCP bounded send queue') { backpressure }
probe.wait { client.state == :failed }
probe.check('TCP stalled write deadline') { client.error.code == :timeout }
client.close
probe.idle

if NETWORK_TRUSTED_TLS
  request = Lunetile::HTTP.request(:get, probe.address('/echo', true))
  probe.wait { request.done? }
  probe.check('HTTPS trusted certificate succeeds') { request.state == :succeeded && request.response.status == 200 }
  client = probe.connect('tls', true)
  probe.check('TCP trusted TLS connection') { client.state == :open }
  client.write('encrypted roundtrip')
  probe.check('TCP TLS encrypted roundtrip') { probe.drain(client, 19) == 'encrypted roundtrip' }
  client.close
else
  probe.check('HTTPS rejects untrusted certificate') { probe.failure(probe.address('/echo', true)) == :tls }
  probe.check('TCP rejects untrusted certificate') { client = probe.connect('tls', true); client.state == :failed && client.error.code == :tls }
end
%w[expired wrong].each do |name|
  probe.check("HTTPS rejects #{name} certificate") { probe.failure(probe.address('/echo', true, NETWORK_PORTS[name + '_https'])) == :tls }
  probe.check("TCP rejects #{name} certificate") { client = probe.connect(name + '_tls', true); client.state == :failed && client.error.code == :tls }
end
probe.idle

rates = Graphics.logic_rate == 120 ? [40, 60, 120] : [40]
rates.each do |rate|
  Graphics.render_rate = rate if Graphics.logic_rate == 120
  started = probe.now
  call = Lunetile::HTTP.request(:get, probe.address('/slow'))
  elapsed = probe.now - started
  frames = Graphics.frame_count
  probe.wait { call.done? }
  probe.check("#{rate}FPS keeps game logic updating during network wait") { elapsed < 0.2 && Graphics.frame_count - frames >= 20 && call.state == :succeeded }
end
probe.idle
request = Lunetile::HTTP.request(:get, probe.address('/slow'))
probe.check('request cannot be serialized') { probe.raises(TypeError) { Marshal.dump(request) } }
client = probe.connect('tcp')
at_exit do
  raise 'Shutdown left a live request' unless request.state == :cancelled && client.state == :closed
  raise 'Shutdown accepted a new request' unless probe.raises(Lunetile::NetworkError) { Lunetile::HTTP.request(:get, probe.address('/echo')) }
  File.write('network-finalized.json', JSON.generate(Lunetile.__network_counts.bytes))
end
File.write('network-results.json', JSON.generate({'checks' => probe.checks, 'reset_count' => $network_resets, 'trusted_tls' => NETWORK_TRUSTED_TLS, 'logic_rate' => Graphics.logic_rate, 'rates' => rates}))
File.write('runtime-complete.txt', 'network,false,false')
