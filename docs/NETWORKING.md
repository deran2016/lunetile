# REST·TCP 통신 API

`Lunetile.dll`은 Ruby 게임 스크립트에 비동기 HTTP/HTTPS와 TCP/TLS 클라이언트를 제공합니다. API를 호출하기 전에는 접속하지 않으며 서버 주소·포트·인증 정보는 호출자가 전달합니다. 추가 Ruby·OpenSSL·통신 DLL 설치는 필요하지 않습니다. 기존 저장 형식과 실행기 ABI는 유지합니다.

## REST 요청과 결과 조회

장면 시작이나 이벤트에서 요청을 한 번 만들고, 이후 게임의 `update`에서 상태를 확인합니다. 완료를 기다리는 반복문으로 게임 갱신을 막지 마세요.

```ruby
# 시작 시 한 번
@request = Lunetile::HTTP.request(
  :post, "https://game.example.com/api/login",
  headers: {"Authorization" => "Bearer TOKEN"},
  json: {"name" => "player"}, timeout_ms: 10_000
)

# 이후 장면의 update 안에서
if @request && @request.done?
  if response = @request.response
    @http_status = response.status
    @result = response.json unless response.body.empty?
  else
    @network_error = @request.error # 취소 시에는 nil
  end
  @request = nil
end
```

`HTTP.request(method, url, headers: {}, body: ..., json: ..., timeout_ms: 10000)`은 `GET`, `POST`, `PUT`, `PATCH`, `DELETE`, `HEAD`, `OPTIONS`를 지원합니다. URL은 UTF-8 문자열이며 HTTP/HTTPS만 받습니다. URL의 사용자명·비밀번호와 fragment는 허용하지 않습니다. 프록시 없이 직접 연결합니다.

- `headers`: 문자열 이름·값으로 구성된 Hash. 이름은 대소문자를 구분하지 않으며 중복 이름·줄바꿈·NUL은 거부합니다. Host·Content-Length·Transfer-Encoding·Connection은 엔진이 관리합니다.
- `body`: 바이너리 문자열. 생략하면 빈 본문입니다. `json`과 동시에 지정할 수 없습니다.
- `json`: JSON으로 변환할 Ruby 값. `json: nil`은 JSON `null`을 전송합니다. Content-Type을 생략하면 `application/json; charset=utf-8`을 넣습니다.
- `timeout_ms`: 1~120000 정수. 기본 10000ms이며 DNS부터 응답 본문 완료까지의 전체 제한 시간입니다.

요청 객체의 `state`는 `:pending`, `:succeeded`, `:failed`, `:cancelled`입니다. `done?`는 pending이 아니면 true입니다. `cancel`은 진행 중 작업을 취소하고, 완료된 요청은 바꾸지 않습니다.

`response`는 성공한 경우 응답 객체를, 나머지는 nil을 반환합니다. 4xx·5xx는 전송 실패가 아닌 HTTP 응답입니다. 응답은 다음 값을 제공합니다.

| 멤버 | 내용 |
|---|---|
| `status` | HTTP 상태 정수 |
| `headers` | 소문자 헤더명 → 문자열 배열. 같은 이름의 헤더를 보존하며 읽기 전용 |
| `body` | 압축을 해제한 바이너리 문자열. 읽기 전용 |
| `json` | UTF-8 JSON을 Ruby 값으로 파싱. 잘못된 JSON은 `JSON::ParserError` |

`response.json`은 객체 자동 복원·NaN을 허용하지 않고 최대 중첩 깊이를 100으로 제한합니다. 파싱 오류 메시지에는 응답 본문을 넣지 않습니다. 별도로 `JSON.parse`·`JSON.generate`도 사용할 수 있습니다.

리다이렉트는 3xx 응답으로 반환합니다. 자동 쿠키·Windows 계정 인증·클라이언트 수준 재시도는 사용하지 않습니다. Authorization·Cookie가 필요하면 요청마다 명시하세요. HTTPS는 Windows의 신뢰 체인·호스트명·유효기간 검증을 사용하며 인증서 오류를 무시하는 옵션은 없습니다.

## TCP/TLS 연결

```ruby
@connection = Lunetile::TCP.connect(
  "game.example.com", 4433, tls: true, timeout_ms: 10_000
)

# 이후 update에서
case @connection.state
when :open
  bytes = @connection.read(65_536) # 현재 수신한 데이터만 즉시 반환
when :failed
  @network_error = @connection.error
end

# 사용을 마칠 때
@connection.close
```

`TCP.connect(host, port, tls: true, timeout_ms: 10000)`은 즉시 연결 객체를 반환합니다. 상태는 `:connecting`, `:open`, `:closed`, `:failed`입니다. DNS의 IPv4·IPv6 주소를 지원하며 주소 후보를 전체 연결 제한 시간 안에서 시도합니다.

TLS가 기본이며 TLS 1.2 이상과 Windows 서버 인증서 검증을 사용합니다. TLS 실패 후 평문으로 전환하지 않습니다. 서버도 TLS를 지원해야 합니다. 평문 연결은 `tls: false`를 명시합니다.

- `write(bytes)`: 열린 연결의 전송 큐에 문자열 전체를 수락하고 바이트 수를 반환합니다. 큐가 부족하면 아무것도 추가하지 않고 `NetworkError(:backpressure)`를 발생시킵니다. 반환값은 서버의 수신·처리 확인이 아닙니다.
- `read(max_bytes = 65536)`: 현재 받은 바이너리 문자열을 최대 지정 크기만큼 반환합니다. 허용 크기는 1~1048576입니다. 데이터가 없으면 nil이며, EOF는 `state`로 구분합니다. 종료 전에 받은 데이터는 계속 읽을 수 있습니다.
- `close`: 진행 중 연결을 취소하거나 열린 연결을 닫습니다. 아직 보내지 않은 데이터는 폐기합니다. 자동 재접속·재전송은 하지 않습니다.

기본 제한 시간은 DNS·연결·TLS 협상 전체와 각 write의 큐 대기·전송에 적용합니다. 열린 연결의 수신 대기에는 유휴 제한 시간이 없습니다. 일반 장면 전환에서는 연결을 유지하며 F12·종료·객체 해제에서는 정리합니다.

### 길이 접두사를 사용하는 JSON 예제

TCP는 한 번 쓴 데이터가 여러 번 읽히거나 여러 write가 합쳐져 읽힐 수 있습니다. 다음은 서버와 **4바이트 네트워크 바이트 순서 길이 + UTF-8 JSON**으로 약속한 예입니다. 엔진이 이 형식을 강제하지는 않습니다.

```ruby
# 연결이 open일 때 한 번 전송
payload = JSON.generate({"type" => "hello", "name" => "player"}).b
@connection.write([payload.bytesize].pack('N') + payload)

# 이후 각 update에서 수신
@receive_buffer ||= ''.b
part = @connection.read
@receive_buffer << part if part
16.times do
  break if @receive_buffer.bytesize < 4
  size = @receive_buffer.unpack1('N')
  if size > 262_144
    @connection.close
    raise 'Server message exceeds 256 KiB'
  end
  break if @receive_buffer.bytesize < 4 + size
  message = @receive_buffer.byteslice(4, size).force_encoding(Encoding::UTF_8)
  @receive_buffer = @receive_buffer.byteslice(4 + size..-1)
  data = JSON.parse(message, create_additions: false, allow_nan: false, max_nesting: 100)
  # data에 따라 게임 상태를 갱신합니다.
end
```

## 실패 처리와 자원 제한

잘못된 입력은 즉시 ArgumentError·TypeError로 반환합니다. 비동기 실패는 객체의 `error`에서 `Lunetile::NetworkError`로 조회하며 `code`, `native_code`, `message`를 제공합니다. `code`는 `:dns`, `:connect`, `:tls`, `:timeout`, `:http`, `:io`, `:limit`, `:memory` 등이며 큐 포화는 `:backpressure`, 닫힌 연결의 write는 `:closed`입니다. 시작 요청의 동시 작업 제한 초과는 즉시 NetworkError입니다.

| 제한 | 값 |
|---|---|
| 정리 중인 작업을 포함한 동시 REST / TCP | 각각 최대 8개 |
| REST 요청 / 응답 본문 | 1MiB / 압축 해제 후 4MiB |
| REST 요청 / 응답 헤더 | 각각 64KiB |
| TCP 송신 / 수신 버퍼 | 연결별 각각 1MiB |

게임 스레드에서만 API를 호출하세요. 통신 작업은 Ruby API를 호출하지 않고 네이티브 버퍼를 사용합니다. 요청·연결 객체는 Marshal로 저장할 수 없으며 저장 대상 게임 객체에 넣지 마세요. 토큰은 자동 저장하지 않고 엔진의 통신 로그에도 기록하지 않습니다.

## 검증과 범위

PowerShell 7의 `pwsh`와 빌드된 DLL·Ruby 도구가 필요합니다.

```powershell
python -X utf8 -B scripts/test_runtime_network.py build/network-verification
```

검사는 로컬 HTTP·TCP·TLS 서버와 실제 Game.exe를 사용합니다. 개발 PC의 인증서 저장소를 변경하지 않습니다. 일회용 GitHub Actions 러너의 LocalMachine 루트 저장소에만 테스트 CA를 임시 등록해 TLS 성공과 잘못된 호스트명·만료 검사를 수행하고 종료 시 제거합니다. 테스트 키·인증서는 Release에 포함하지 않습니다.

별도 서버·로그인 UI·자동 토큰 갱신·WebSocket·UDP·C API·리소스 암호화는 포함하지 않습니다. 운영 서버 연동과 장시간 연결 안정성은 별도 검증 대상입니다. 평문 HTTP/TCP의 내용은 암호화되지 않습니다.
