# 게임 내부 브라우저 (XP·VX Ace)

`Lunetile.dll`과 `LunetileVXA.dll`에 공통 WebView2 패널을 내장합니다. 게임 화면 위의 사각형 영역에서 웹페이지와 로컬 HTML을 조작합니다. 브라우저 API를 호출하지 않는 게임에는 패널·프로필·브라우저 프로세스를 만들지 않습니다.

## 사용하기

Windows 11 x64와 기존 Visual C++ x86 런타임에 더해 **Microsoft Edge WebView2 Evergreen Runtime**이 필요합니다. [Microsoft 설치 안내](https://developer.microsoft.com/microsoft-edge/webview2/)에서 설치할 수 있습니다. 엔진은 자동 다운로드/설치하지 않습니다. SDK Loader는 x86 DLL에 정적으로 포함되어 `WebView2Loader.dll`을 따로 복사하지 않습니다.

이벤트의 Script 또는 게임 스크립트에서 호출합니다. 객체가 GC로 회수되지 않도록 전역 변수나 장면의 인스턴스 변수에 보관하세요.

```ruby
if Lunetile::Browser.available?
  $browser = Lunetile::Browser.new(Rect.new(80, 60, 1120, 600))
  $browser.load_file("Web/index.html")
  # 또는 $browser.navigate("https://example.com")
end
```

기본 해상도에서는 화면 안에 맞게 Rect를 줄이세요. XP 640×480에서는 `Rect.new(40, 40, 560, 400)`, VXA 544×416에서는 `Rect.new(24, 24, 496, 368)` 등을 사용할 수 있습니다. 한 번에 패널 하나만 열 수 있습니다.

생성·탐색은 비동기입니다. `Graphics.update`를 계속 호출하여 기존 메시지 루프를 진행하세요. 준비를 기다리는 동안 스레드를 동기 대기시키지 않습니다. 기본적으로 표시하되 게임의 입력 포커스는 가져오지 않습니다. 클릭 또는 `focus`로 포커스를 이동합니다.

```ruby
case $browser.state
when :ready
  # 표시 준비 완료
when :failed
  error = $browser.error
  # error.code, error.native_code로 처리
end
```

| API | 동작 |
|---|---|
| `Browser.available?` | 사용할 Runtime이 설치됐는지 확인 |
| `Browser.new(rect)` | 패널 생성. 준비 전에는 마지막 탐색 요청 하나를 보관 |
| `navigate(url)` | HTTP/HTTPS 탐색 |
| `load_file(path)` | 프로젝트의 `Web/` 아래 HTML/HTM 열기 |
| `reload` | 준비된 페이지 새로 고침. 생성 중에는 `not_ready` 오류 |
| `rect`, `rect=` | 닫기 영역을 포함한 논리 좌표 읽기/설정. Rect를 복사하며 읽은 Rect만 수정해서는 패널이 이동하지 않음 |
| `visible`, `visible=` | 표시/숨김. 숨기면 게임으로 포커스 복귀 |
| `focus`, `blur` | 브라우저/게임으로 포커스 이동 |
| `dispose`, `disposed?` | 폐기/폐기 여부. `dispose`는 여러 번 호출 가능 |
| `state` | `:creating`, `:ready`, `:loading`, `:failed`, `:disposed` |
| `error` | 마지막 `BrowserError` 또는 `nil` |

좌표는 -4096..4096, 폭·높이는 32..4096입니다. 화면 밖은 게임 캔버스 경계에서 잘립니다. 창 크기·최대화·전체 화면·DPI·논리 해상도 변경에 맞춰 실제 창 좌표를 다시 계산합니다. API는 게임 스레드에서 호출하며 다른 스레드에서는 `ThreadError`가 발생합니다.

우측 상단 **×** 또는 브라우저 포커스 중 **Esc**를 누르면 폐기됩니다. Esc는 웹페이지와 한글 조합보다 패널 닫기를 우선합니다. 다시 열 때는 새 객체를 만드세요. F12는 기존 게임 리셋으로 전달하면서 패널을 폐기하고, Alt+Enter는 게임의 전체 화면 설정으로 전달합니다.

게임 로직·타이머는 계속 진행합니다. 브라우저가 입력을 받을 때 게임의 키보드·마우스·게임패드 입력을 차단하고 복귀할 때 눌림 상태를 정리합니다. 애플리케이션 전체가 비활성화된 경우에는 기존 런타임의 비활성 창 정책을 유지합니다.

패널 바깥의 게임 영역을 클릭하거나 `blur`를 호출하면 게임으로 돌아옵니다. 포커스가 같은 프레임에 왕복해도 기존에 누른 키는 해제 후 다시 누를 때까지 억제합니다. Browser 객체는 Sprite처럼 저장 대상에 넣지 않고 전역 변수나 장면에 보관하세요.

## 로컬 파일·프로필·오류

로컬 파일은 `Web/index.html`처럼 프로젝트 상대 경로로 지정합니다. HTML에서 같은 폴더의 CSS·JavaScript·이미지를 참조할 수 있습니다. 내부적으로 `https://lunetile-web.invalid/`에 `Web/`만 매핑합니다. 폴더 이탈, 절대 경로와 재분석 지점(심볼릭 링크/정션)은 거부합니다. 프로젝트 폴더 전체를 웹에 노출하지 않습니다.

쿠키와 웹 저장소는 `%LOCALAPPDATA%\Lunetile\WebView2\<SHA-256>/`에 저장합니다. 키는 엔진과 정규화된 프로젝트 절대 경로로 계산하므로 기본 브라우저 및 다른 프로젝트와 분리됩니다. 프로젝트를 다른 폴더로 옮기면 새 프로필을 사용합니다. 패널 닫기·F12는 프로필을 삭제하지 않습니다. 프로필을 배포 ZIP이나 진단 자료에 포함하지 마세요.

`BrowserError#code`는 `:runtime_missing`, `:runtime_version`, `:profile_path`, `:environment`, `:controller`, `:navigation`, `:navigation_blocked`, `:already_open`, `:not_ready`, `:disposed` 등입니다. `native_code`는 HRESULT 또는 WebView2 탐색 오류 값입니다. 인자/상태 오류는 즉시 예외로, 비동기 탐색/초기화 실패는 `state`와 `error`로 확인합니다. Runtime이 없어도 이 API를 사용하지 않는 게임은 계속 실행됩니다.

새 창 링크는 같은 패널에서 열고 외부 프로그램 실행·다운로드·권한 요청은 차단합니다. 개발자 도구·기본 JavaScript 대화 상자·Ruby 호스트 객체와 웹 메시지 통로는 비활성화합니다. 페이지의 일반 JavaScript는 동작하지만 JavaScript↔Ruby 연동 API는 제공하지 않습니다.

## 빌드·검사

기존 `scripts/build_runtime.ps1`가 SDK **1.0.4314.35**를 받아 SHA-256 `90778deb1b77e36292828b4b5833c9255c27533f40e0ddd55891ae718944edc4`를 확인합니다. SDK 고지는 `licenses/webview2.txt`에 있습니다. 두 엔진의 이름과 exports는 유지합니다.

```powershell
python -X utf8 -B -m unittest discover -s tests -v
python -X utf8 -B scripts/test_runtime_browser.py build/browser-new-check
python -X utf8 -B scripts/benchmark_runtime_browser.py BASELINE_DLL_DIR CANDIDATE_DLL_DIR PROJECTS NEW_OUTPUT
```

`PROJECTS`에는 동일한 변환 스크립트를 사용하는 `xp/`, `vxa/` 프로젝트를 둡니다. 벤치마크는 기본 맵 정지/왕복 이동, 기준/후보 30초×3쌍과 열린 로컬 패널, 40/60FPS를 확인합니다. CPU는 Scene 갱신에서 스케줄러 대기를 뺀 값이며 GPU와 분리합니다. 원본 실행기·RTP 및 전경 게임 창을 사용하므로 검사 중 다른 창을 조작하지 마세요.

브라우저는 네이티브 자식 창이어서 Sprite z·Viewport 색조·게임 화면 캡처/전환 효과에 포함되지 않습니다. 웹페이지 부하와 브라우저 프로세스 메모리는 별도 비용입니다. 임의 사이트·플러그인, 물리 키보드 IME 조합·혼합 DPI 모니터와 물리 스캔아웃의 보장은 포함하지 않습니다.

닫기 영역은 게임에 종속된 비활성 소유 창에서 표시하며 본문과 함께 이동·클리핑·숨김·폐기합니다. [Flip-model과 GDI를 같은 출력에 혼합할 수 없는 제약](https://learn.microsoft.com/en-us/windows/win32/direct3ddxgi/dxgi-flip-model) 때문에 닫기 버튼을 별도 표면에 두었습니다. 게임의 Flip-model 출력과 WebView2 자식 창은 유지합니다.

## 2026-10-25 최종 로컬 검증

기준 DLL은 XP `2e4093fb…`, VXA `6b57754d…`이며 같은 최적화된 기본 스크립트를 사용해 비교했습니다. 최종 DLL SHA-256:

```text
XP   a299b69c138a621b844d75e21020ec596cbf37711f4a2a88418ec5e2eccc8fc9
VXA  5bc7df0691e44480d334f66f2226fef5b9dae86f2770260928366ca6f0f23ca7
```

총 44회 전경 실행을 측정했습니다. 브라우저 미사용 기본 맵은 정지/왕복 이동 각각 기준·후보 30초×3쌍, 열린 자체 HTML은 엔진별 정지/이동 각각 30초, 40/60FPS는 닫힘/열림·정지/이동 각각 10초입니다. 미사용 전체 처리 평균 최대 변화 +0.19%, p95 -0.45%로 +5% 조건을 통과했습니다.

| 미사용 기본 맵 | 전체 평균 ms 기준→후보 | 전체 p95 ms 기준→후보 |
|---|---:|---:|
| XP 정지 | 0.6015 → 0.6026 | 0.8050 → 0.8012 |
| XP 이동 | 0.6052 → 0.6046 | 0.8157 → 0.8119 |
| VXA 정지 | 0.7851 → 0.7843 | 1.1021 → 1.0971 |
| VXA 이동 | 0.8201 → 0.8105 | 1.1665 → 1.1565 |

120FPS 후보 전체(패널 닫힘/열림)의 최소 출력 119.933FPS, 로직 119.997–120.000Hz, 최대 출력 누락 0.0556%였습니다. GPU 시간은 별도이며 CPU에 더하지 않았습니다. 출력 수는 Present 제출 횟수입니다.

원본 XP/VXA 실행기에서 로컬 HTML/CSS/JS, HTTP/HTTPS, 클릭/스크롤/한글 확정 문자열 폼 제출, 새 창 링크의 같은 패널 탐색, 다운로드/외부 URI/미디어 권한 차단을 검사했습니다. 브라우저 포커스 중 게임 입력 차단·게임 틱 진행, 포커스 복귀 시 눌림 상태 정리, 빠른 해제/재누름과 UIInput 반복 입력 차단, Esc/X/F12/Alt+Enter, 초기화 중 폐기·GC 압축·반복 생성/폐기·탐색 실패 복구를 확인했습니다. XP 640×480/VXA 544×416와 1280×720, 창 크기/최대화/전체 화면/논리 해상도 및 합성 DPI 메시지도 확인했습니다.

프로세스 및 브라우저 하위 프로세스 종료 후 재실행에서 자체 테스트 쿠키 유지, 다른 프로젝트에서 분리된 쿠키를 확인했습니다. Runtime 미설치는 테스트 프로세스의 검색 경로를 무효화해 재현했고 프로필 쓰기 오류는 새 테스트 프로필 경로에만 파일 장애물을 만들어 재현했습니다. 일반 Graphics/Input 실행은 계속됩니다. 설치된 Runtime을 제거하거나 개인 브라우저 프로필을 변경하지 않았습니다.

첫 생성 측정은 테스트 명령 왕복을 포함합니다. 다음은 자체 HTML의 짧은 하위 프로세스 스냅샷이며 외부 사이트 부하를 대표하지 않습니다.

| 엔진 | 첫 생성 ms | 프로세스 수 | private MiB | 한 코어 기준 CPU % |
|---|---:|---:|---:|---:|
| XP | 406.0 | 6 | 138.5 | 3.08 |
| VXA | 391.0 | 6 | 139.6 | 1.56 |

Python 177개, 두 엔진 x86/exports 이름·ordinal 유지, 기본 스크립트/타일·문자/저장·별도 프로세스 불러오기·속도/창 검사와 격리 MMO 네이티브/GUI 두 클라이언트 회귀를 통과했습니다. MMO 서버·프로토콜·기존 게임 스크립트는 변경하지 않았습니다. 원본·개인 파일 178개와 관련 없는 네이티브/일반 변환 소스의 해시가 유지됐습니다.

초기 빌드·테스트 fixture 실패, 포커스 복귀 입력 두 건의 실제 수정, 중단/대체된 성능 실행은 별도 실패 목록에 남겼습니다. 첫 예제 화면 검수에서 클릭 가능한 X의 픽셀이 보이지 않아 배포를 중단하고 별도 소유 표면으로 수정했습니다. 새 픽셀 검사는 작은 안티앨리어싱 글꼴의 전경/배경 대비를 확인합니다. 최종 합격 근거는 `browser-ui15`, `browser-performance6`, `browser-regression3`, `browser-failure-cases4`이며 이전 후보 결과로 대체하지 않았습니다.

결과는 `build/browser-delivery-final-20261025/`의 엔진별 오프라인 브라우저 예제 ZIP·두 DLL·공통 진단 ZIP·SHA-256 목록입니다. 새 폴더 압축 해제 실행과 ZIP CRC/동일 DLL 검사는 진단의 `extracted-execution.json`/`package-verification.json`에 기록합니다. 원본 RGSS DLL·RTP·브라우저 프로필/쿠키·개인 입력/방문 이력은 포함하지 않습니다. 원격 푸시·릴리스는 하지 않았습니다.

물리 키보드의 실제 한글 IME 조합, 혼합 DPI 모니터 이동, 물리 스캔아웃·장기 내구성·임의 사이트/플러그인은 검증하지 않았습니다. 한글 검사는 확정 Unicode 입력과 실제 DOM/폼 제출이며 합성 DPI 검사는 실제 다른 DPI 디스플레이 이동의 대체 증거가 아닙니다.
