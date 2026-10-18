# 자체 RGSS 대체 엔진 구현 상태

> 독립 소스 저장소 안내: 아래의 이전 DLL 해시·build 경로는 분리 전 검증 기록입니다.
> 원시 자료는 포함하지 않으며, 새 저장소의 실제 빌드·검사 결과는 [VALIDATION.md](VALIDATION.md)에 구분합니다.

2026-10-18. **x86 Ruby 4.0.7을 포함하는 독립 `RGSS104E.dll`을 빌드하고,
원본 Game.exe에서 기본 검증 게임의 자동/실제 키 완주를 확인했습니다. 범용 게임 호환 인증은 아닙니다.**
기존 40FPS 보조 DLL과 원본 설치 파일은 보존했습니다.
2026-10-18 사용자가 원본 GPU 비교 미확정을 명시하는 조건으로 첫 버전을 인수했습니다.
원본 GPU 비용·GPU 개선율은 계속 미확정이며, 기능·저장·완주·성능·내구성의 검증 범위는 유지합니다.
사용자 요청에 따라 Windows 배율 검증은 수행하지 않으며 완료 기준에서도 제외합니다.
배율 설정을 변경하거나 이 검사를 위해 설정 앱 접근을 다시 요청하지 않습니다.

현재 작업 DLL은 `3868eeceb9fbba5ffc2509cf371e54240db726645dd64145ca4ef5b7f7fffd41`입니다.
23개 회귀 관문, 원본과 동일한 자체 검증 게임의 상태/프레임 카운트 대조, 실제 키 입력 완주·
F12 두 번·정상 종료와 원본/자체 세 쌍 성능 비교를 통과했습니다. 같은 해시의 30분·100왕복과
Alt+Enter/Alt+Tab 창 복귀도 통과했고, 현재 해시의 실제 PCM 원본 대조도 통과했습니다.
계획의 항목별 현재 판정은 [인수 확인](RUNTIME_ACCEPTANCE.md)에 있습니다.
추가 진단 세 쌍의 대기·자체 GPU 측정과 Python 41개 도구 검사를 완료했습니다.
원본 GPU의 프레임별 비용은 여전히 미확정이며 [GPU·대기 기록](RUNTIME_GPU_TRACE.md)에 범위를 명시합니다.
아래에는 이전 후보의 실패와 수정 이력도 포함되므로 각 절의 DLL 해시를 구분해 읽습니다.

## 통과한 검사

| 범위 | 실제 결과 |
|---|---|
| Ruby | 4.0.7, MSVC 2022 x86, 4바이트 포인터, JIT 비활성화, GC·Marshal 왕복 |
| 실행기 | 원본 Game.exe의 일반 / debug / btest 모드, Ruby 예외와 정상 exit |
| 독립성 | 원본·보조 DLL이 없는 격리 폴더에서 실행; 실제 로드 DLL SHA-256 확인 |
| 종료 | GameMain 정상 반환과 예외 경로에서 Ruby cleanup 및 at_exit 실행 |
| 데이터형 | Table·Color·Tone·Rect: 원본에서 수집한 32개 동작·직렬화 항목 일치 |
| 데이터 경계 | Table 손상 헤더·길이·할당 상한 거부, 복제 독립성·3차원 resize 좌표 보존 |
| 프로젝트 데이터 | 원본 템플릿 15개 파일, 26,332개 정규화 기록: 객체 값·공유 참조·클래스·필드·native payload와 Marshal 왕복 일치 |
| 실제 세이브 | 원본 세이브 1개, 4,338개 그래프 기록 일치; 가져오기 → 새 형식 저장 → 재로드 통과 |
| 저장 보호 | 루트와 Import 보존, 새 저장 우선, 버전 표식 검사, 실패한 쓰기에서 기존 저장 보존 |
| Win32API | 자체 x86 호출: PID·문자열·출력 버퍼·void·null·음수 반환을 원본과 대조 |
| RGSSAD | 직접 만든 9개 엔트리 v1 아카이브를 양쪽에서 읽기; 키 진행·문자열 길이 1~7·대소문자·아카이브 우선 조회·한글 프로젝트 경로 일치 |
| 인코딩 | UTF-8/CP949/CP932 명시적 검증, 원본 세이브 가져오기·새 저장 재로드. 실제 한글 경로·제목·대화·메뉴 이름·그림 파일명·저장/F12/재로드 확인 |
| 변환기 | 기본 스크립트 90개 Ruby 4 구문 검사; 저장 및 ID 순서 관련 8개만 변경, 나머지 82개 엔트리 원시 바이트 보존 |
| 암호화 프로젝트 변환 | 16개 원본 데이터 파일을 RGSSAD로 묶은 복사본 변환; 아카이브 원시 바이트 유지, 별도 변환 스크립트·15개 데이터의 새 DLL 읽기 통과 |
| 변환 거부 검사 | 이벤트·조건·이동 경로의 임의 Ruby 코드 거부, 파일·객체 경로 표시, 실패 시 출력 미생성·원본 보존 |
| 그래픽 기본값 | 원본 23개 속성/텍스트 측정, 512개 Bitmap 알파 합성 조합, 스프라이트 효과·damage 공개 상태 타임라인 일치 |
| 그래픽 실행 | 실제 D3D11 GPU 픽셀·viewport clipping/빈 viewport flash, 원본 화면에서 관찰한 오토타일 48종 quarter 배치·우선순위·스크롤 검사 |
| 생성자 | Map/MapInfo/Event/Page/Condition/Graphic/CommonEvent 7종 공개 기본값을 원본과 대조 |
| 입력과 기본 게임 | 실제 키 입력으로 타이틀 → 새 게임 → 맵 → 메뉴 → 전용 폴더 저장 확인. XInput 경로는 구현했지만 물리 패드는 미검사 |
| 40Hz와 계측 | 누적 QPC 마감·개별 waitable timer, frame_count, 유효한 비동기 GPU timestamp/disjoint 결과 확인. CPU GetThreadTimes는 개별 프레임에서 양자화됨 |
| 오디오 기본 경로 | 직접 만든 WAV/Ogg/MP3/WMA/MIDI의 실제 출력 voice 진행, PCM 피치, 중첩 SE·정지·반복·페이드·ME/BGM 일시정지·재개 검사 |
| 자동 통합 시나리오 | 논리 입력 주입으로 저장 → 타이틀 → 불러오기 → 대화/선택/병렬 이벤트/날씨/그림/점프 → 전투 승리 → 맵 이동 → 엔딩 통과. 시험 적 HP=1 |
| 직접 조작 완주 | 입력 주입 없이 키 입력으로 타이틀 → 선택지 → 전투 명령/대상 선택 → 승리 → 엔딩 대화 → 타이틀 복귀 → 정상 종료. 자체 짧은 시험 게임이며 적 HP=1 |
| 리셋 | 원본 Reset 예외와 전역/Font/프레임 카운트 보존·표시 객체 폐기·40Hz 복귀 대조. 새 엔진에서 실제 F12 두 번과 VM 초기화 한 번·정상 종료 확인 |
| ID 테이블 순서 | 230개 원본 정수 Hash 순서 대조와 33개 기본 이벤트/병렬 처리/원본 세이브 가져오기 결과 일치. 새 저장에서 순서·공유 참조 보존 |

자동 통합 검사는 실제 기본 스크립트·렌더링·오디오를 실행하지만 조작 입력을 주입합니다.
아직 원본과의 전체 게임 결과·화면·음원 파형 대조나 성능 향상의 증거는 아닙니다.
이전 보조 DLL의 플레이·내구성·성능 결과도 새 엔진의 근거로 사용하지 않습니다.

## 구현한 소스

- `src/runtime/runtime.cpp`: 실행기 연결, Ruby 초기화·종료·예외 처리, zlib 스크립트 실행.
- `src/runtime/types.cpp`, `types.rb`: RGSS 값 형식과 Marshal 표현.
- `src/runtime/data.rb`, `rpg_schema.json`, `data_constructors.rb`: RPG 데이터 클래스 필드,
  프로젝트 파일 읽기와 AudioFile·EventCommand·MoveCommand·MoveRoute 생성.
  나머지 데이터 클래스는 Marshal 읽기를 지원하며, 미구현 생성자는 명시적으로 오류를 냅니다.
- `src/runtime/saves.rb`: Import 읽기와 버전 1 새 저장을 분리. 임시 파일 → flush/fsync → rename.
- `src/runtime/archive.rb`: RGSSAD v1 읽기. 파일 경계·중복 이름·상대 경로 검사. v2/v3는 지원하지 않음.
- `src/runtime/win32_api.cpp`: 32비트 Win32API I/L/P/V 인자·반환. 구형 Ruby 네이티브 확장용 ABI가 아닙니다.
- `bitmap.cpp`, `graphics.rb`, `renderer.cpp`: WIC 작업 스레드 이미지 디코딩, CPU Bitmap/dirty GPU upload,
  GDI 글자, D3D11 quad·합성·viewport·freeze/transition, Window/Plane/Font.
- `rpg_graphics.rb`, `tilemap.rb`: 캐시 공유 수명, RPG::Sprite 효과/애니메이션, 타일·오토타일·날씨.
- `input.cpp`: 키 latch/반복/방향과 XInput. `renderer.cpp`에 포커스 대기와 Alt+Enter 창 전환.
- `audio.cpp`, `audio_decode.cpp`, `audio.rb`: Ruby 객체를 접근하지 않는 전용 작업 스레드,
  XAudio2 PCM 출력, 직접 WAV, libvorbis, Media Foundation MP3/WMA, 독립 Windows MIDI synth 출력과 BGM 복원.
- `scripts/migrate_project.py`: 검토된 기본 소스 해시만 허용하는 복사본 변환.
  이 저장소에서 만든 두 가지 보조 DLL 연결 코드만 정확히 식별해 해제합니다.
  제거 후 Main이 검토된 기본 소스와 일치해야 하며, 사용자 Main·플러그인을 추측해서 삭제하지 않습니다.
  RGSSAD 프로젝트는 원본 아카이브를 유지하고 별도 경로에 변환 스크립트를 만듭니다.

실행기가 조회하는 5개 함수의 이름·ordinal·cdecl 계약은 `src/runtime/abi.json`,
원본 66개 내보내기의 지원 여부는 `src/runtime/exports.json`에 있습니다.
다른 61개 원본 함수와 편집기 호환을 지원한다고 주장하지 않습니다.
정적 Ruby 라이브러리가 노출하는 내부 심볼 5개는 공개 RGSS API가 아닙니다.

## Ruby x86 포팅 수정

공식 소스 SHA-256:
`911ace20f90d068ca0e4dda6d0e4f0f81e52e52f2dd4f4004c721e253412e82d`.

최초 검사에서는 `include/ruby/atomic.h`의 Windows size_t fetch-add가
32비트 값에 64비트 연산을 수행해 이웃 값을 `12345678 → 12345679`로 바꿨습니다.
초기 실패 기록은 로컬 build 폴더에 보존했습니다. 이후 별도 소스 복사본에
MSVC x86 분기만 수정하는 포팅 패치를 추가했습니다. 버전이나 대상 비트 수를 내리지 않았습니다.

`scripts/patch_runtime_ruby.py`가 원본·수정 헤더 해시를 확인하며,
`ruby.lock.json`에 패치와 해시가 기록됩니다. 수정 후 결과입니다.

```text
size_t=4 previous=ffffffff value=00000000 neighbor=12345678 expected=12345678
32-bit fetch/add/sub/inc/dec/exchange/CAS boundaries: PASS
```

Ruby의 builtin 초기화와 인코딩/변환기를 정적으로 포함했습니다.
실행 PC에 별도 Ruby나 enc/*.so 설치가 필요하지 않습니다.
빌드용 MSYS Ruby 3.4.10 x64는 엔진 런타임이 아닙니다.
컴파일러는 MSVC 2022 14.44.35207 / 19.44.35226입니다.

## 재현

MSVC 2022 x86 C++, Windows SDK, CMake, Python 3.12 이상, 빌드용 Ruby 3.1 이상이 필요합니다.
프로세스 모듈 검사는 Python psutil을 사용합니다. BOOTSTRAP_RUBY_EXE에는 설치된 부트스트랩 Ruby 실행기 경로를 지정합니다.
오디오 시험 음원 생성에는 설치된 ffmpeg, 통합 시나리오의 자체 그림 생성에는 Python Pillow가 필요합니다.
두 도구 모두 엔진 런타임에는 포함하지 않습니다.

```powershell
powershell -NoProfile -File scripts/build_runtime.ps1 -BaseRuby "BOOTSTRAP_RUBY_EXE"
python -m unittest discover -s tests -v
python scripts/inspect_runtime.py build/runtime-native/bin/Release/RGSS104E.dll
python scripts/test_runtime.py "LOCAL_ORIGINAL_GAME_EXE" build/runtime-native/bin/Release/RGSS104E.dll build/check-runtime
python scripts/migrate_project.py "LOCAL_ORIGINAL_PROJECT" build/project-ruby4
# 비ASCII 데이터와 BOM 없는 레거시 INI는 실제 원본 문자셋을 지정합니다.
# python scripts/migrate_project.py MyGame MyGame-RGSSXP --data-encoding CP949 --ini-encoding CP949
# 원본에서 만든 세이브 복사본을 별도로 준비한 뒤 실행
python scripts/verify_runtime.py "LOCAL_ORIGINAL_PROJECT" "LOCAL_ORIGINAL_DLL" "LOCAL_ORIGINAL_SAVE" build/check-evidence
# 에셋이 없는 템플릿은 보유한 RTP를 검사 복사본에만 보충합니다. 프로젝트 파일이 우선입니다.
python scripts/test_runtime_stock_boot.py build/project-ruby4 build/stock-scenario --scenario --rtp "LOCAL_RTP"
python scripts/package_runtime.py build/check-evidence build/RGSSXP-dev
# RTP 에셋은 자신이 사용할 권한을 가진 복사본에만 배치합니다.
python scripts/test_runtime_stock_boot.py build/project-ruby4 build/scenario --scenario
python scripts/test_runtime_stock_boot.py build/project-ruby4 build/manual-scenario --scenario --manual
```

출력 폴더는 매번 새 이름을 사용합니다. 기존 출력은 덮어쓰지 않습니다.
DLL은 `build/runtime-native/bin/Release/RGSS104E.dll`에 생성됩니다.
원본 파일을 포함하지 않는 개발용 묶음에는 DLL·해시·검사 요약·외부 라이선스를 넣습니다.
빌드 관문·로그는 `build/runtime-ruby-x86/patched-4.0.7/`, 실행 기록은
`build/runtime-smoke-*`, 데이터 대조는 `build/runtime-data-*`, 실제 세이브 대조는
`build/runtime-import-*/comparison.json`에 있습니다. 모두 Git에서 제외합니다.

변환 프로젝트의 원본 파일 해시, 스크립트 ID·이름·순서·변경 전후 소스 해시,
변경 문자열과 위치, 변환 소스, 구문 검사 결과는 `migration/`에 생깁니다.
데이터 객체 검사 결과도 기록합니다. 비ASCII 데이터 텍스트는 `--data-encoding UTF-8`,
`CP949`, `CP932` 중 실제 문자셋을 명시합니다. 변환 위치·전후 hex와 해시를 기록하고
데이터/아카이브 바이트를 보존한 채 로드 시 UTF-8로 해석합니다. 문자셋을 추측하지 않습니다.
Game.ini는 UTF-16LE BOM으로 저장합니다. 자세한 동작과 한글 경로 수정은 [문자열 검증](RUNTIME_TEXT.md)에 있습니다.
`rgssxp-ruby.exe`는 같은 Ruby 4.0.7 x86의 구문·인코딩 검사 도구이며 게임 실행에는 필요하지 않습니다.
기존 Save1~4는 Import 복사본으로 이동하며 새 저장은 `Saves/RGSSXP/`만 사용합니다.
원복은 원본 프로젝트를 실행하면 됩니다. 설치 템플릿에는 반영하지 않았습니다.

## 첫 버전 지원 한계와 후속 검증

기본 XP 스크립트의 자체 검증 게임을 기준으로 구현합니다. 첫 버전 밖의 범위는 다음과 같습니다.

- 기본 스크립트가 호출하지 않는 일부 RPG 생성자, 임의 사용자 플러그인·원본 내부 주소 호출과 구형 Ruby 네이티브 확장.
- 모든 게임 에셋의 픽셀 동일성. 손상 숫자 글꼴/범위는 대조했지만 픽셀 해시는 다르고,
  hue는 레거시 정수 양자화와 RGB 최대 3단계 차이가 있습니다. 720도 같은 범위 밖 데이터는 동일하지 않습니다.
- 모든 MIDI 악기·코덱 변형·물리 스피커 지연·잔향/복귀 위상 파형의 동일성. 현재 해시의 유한 PCM 검사는 아래 별도로 기록합니다.
- 물리 게임패드, 추가 시스템 로캘/IME, 다른 GPU·모니터 조합, 임의 게임의 장시간 안정성.
- 60/120FPS 표시·고주기 로직·64비트 실행기·편집기 DLL 교체. Windows 배율 검사는 사용자 지시로 제외합니다.

기본 게임의 자동/실제 키 완주, 원본 상태 대조, 3쌍 성능과 30분/100왕복은 현재 해시에서 확인했습니다.
이것이 모든 조건을 검증한 범용 호환 엔진을 뜻하지는 않습니다. 미지원 호출은 성공하는 빈 구현으로 숨기지 않습니다.
원본 바이너리·에셋·세이브·디컴파일 출력은 공개 소스에 포함하지 않습니다.

## 그래픽·오디오 검증 묶음

- `build/runtime-verification-8/summary.json`: 확장된 전체 회귀 11개 관문 통과, 원본 해시 보존.
- `build/runtime-stock-scenario-4/boot-result.json`: 자동 통합 시나리오.
- `build/runtime-stock-manual-1/boot-result.json`, `modules.json`: 실제 UI 조작 완주와 원본/보조 DLL 부재.
  `dialogue.png`, `victory.png`, `ending.png`는 로컬 화면 증거이며 게임 에셋이 보여 공개하지 않습니다.
- 위 세 검사가 사용한 DLL SHA-256:
  `e198142cdd409470b540de5b0dc8000b8ab99b567dbfeb7235716ce04892e3da`.
- `build/RGSSXP-graphics-audio-dev-20261018/`: 해당 해시의 개발용 DLL·검사 요약·고정 소스 정보·라이선스.
  첫 공개 후보의 성능/내구성/호환성 완료 기준을 통과한 릴리스가 아닙니다.

## 추가 리셋 검증

- `build/runtime-verification-9/summary.json`: Reset 원본 대조를 포함한 12개 관문 통과.
- `build/runtime-stock-scenario-5/boot-result.json`: 리셋 추가 후 자동 저장/로드/전투/엔딩 회귀.
- `build/runtime-reset-key-new-1/`: 실제 F12 두 번, 카운터 1 → 2 → 3과 정상 종료.
- 이 검증의 DLL SHA-256:
  `9f3faad7097eff002683626744c97f1097addefc3cf13a9d88df5a47cebba90f`.
- `build/RGSSXP-graphics-audio-reset-dev-20261018/`: 리셋이 추가된 개발용 묶음.
  리셋 계약·제약은 [리셋 동작 기록](RUNTIME_RESET.md)에 있습니다.

## 오디오 호환성 교정 검증

- 원본에서 공통 dB 음량 곡선·피치 변경 시 재시작 조건을 확인해 PCM 출력에 반영했습니다.
- MIDI 출력은 자체 SMF 파서/스케줄러와 Windows 독립 synth port/PCM 버퍼로 연결했습니다.
  피치 50/100/150의 실제 주파수, MIDI/PCM 음량, 독립 드럼 중첩과 ME 복원 검사가 통과했습니다.
- `build/runtime-verification-11/summary.json`: 전체 12개 관문 및 원본 해시 보존 통과.
- `build/runtime-stock-scenario-6/boot-result.json`: 같은 DLL의 자동 저장/로드/전투/엔딩 회귀 통과.
- `build/runtime-stock-manual-2/boot-result.json`: 같은 DLL에서 입력 주입 없이 실제 키로 선택지,
  전투 명령/대상 선택, 승리, 엔딩, 타이틀 복귀와 정상 종료를 확인했습니다. 시험 적 HP=1입니다.
  `modules.json`의 실행 중 103개 이미지 해시에 원본 RGSS와 보조 DLL은 없습니다.
  `victory.png`, `ending.png`는 게임 에셋이 포함된 로컬 증거로만 보관합니다.
- 위 검증의 DLL SHA-256:
  `06fdae51ef73eba3906d93647ea20384f530ec8b038c77c3d14c4e14f0ec9023`.
- `build/RGSSXP-audio-compat-dev-20261018/`: 이 DLL과 검사 요약·고정 버전·라이선스 묶음.
- `build/RGSSXP-midi-dev-20261018/`: 자동 검사와 최신 실제 키 조작 완주 기록을 함께 포함한 묶음.
  MIDI 출력 파형/노트 길이 대조와 성능·내구성은 아직 공개 완료 기준에 도달하지 않았습니다.

## ID 순서·문자열·한글 경로 추가 검증

- `build/runtime-integer-order-check-3/`: 230개 정수 Hash 순서 및 33개 기본 이벤트/가져오기 결과 대조.
- `build/runtime-verification-16/summary.json`: 한글 경로 저장, CP949/CP932 원본 저장 가져오기,
  인코딩·INI·새 저장 재로드를 포함한 전체 14개 관문 통과. 스크립트 8개 변경·82개 원시 바이트 보존.
- `build/runtime-stock-scenario-8/boot-result.json`: 같은 DLL의 자동 저장/로드/전투/엔딩 통과.
- `build/runtime-한글-조작-1/boot-result.json`: 같은 DLL의 실제 한글 경로/제목/대화/메뉴/그림,
  원본 저장 가져오기, 별도 저장, F12 후 새 저장 재로드와 정상 종료. 로컬 화면은 공개하지 않습니다.
- DLL SHA-256: `bd75859992990f0c6036b656922e3ce26e4aa850a878c55859a4fcae4b428f90`.
- `build/RGSSXP-text-order-dev-20261018/`: 해당 개발 DLL·변환 도구·동일 x86 Ruby 검사 도구와 라이선스.

별도 이전 빌드 `03a8302f16491ad16dd8a903de97d3596e8863a7a6cc1711be1f3ed6d3511e84`는
`build/runtime-endurance-30m-1/boot-result.json`에서 활성 1825.13초·72,000프레임·100왕복,
플레이어 이동 9,000회를 완료했습니다. 비활성 522.74초는 플레이 시간에서 제외했습니다.
10분 워밍업 이후 private 메모리 중앙값 증가는 약 0.32MiB, 기울기는 약 0.029MiB/분,
핸들 중앙값 변화는 -2로 관찰 임계 범위 안이었습니다. 모든 할당의 누수 부재를 증명하지 않습니다.
이는 최신 한글 경로 수정 DLL의 30분 검사로 대체할 수 없으며 서로 다른 해시의 근거로 구분합니다.

## 반복 할당 감소와 성능 비교

- `IntegerMap.values`의 호환 순서 재구성을 캐시하고 반환 배열은 복사합니다.
  대입·치환·삭제·clear·복사·로드, frozen 읽기와 저장 객체의 공유/순환 참조를 검사했습니다.
- 표시 객체 속성 접근 시 필드명 문자열을 매번 만들지 않도록 수정했습니다.
  속성별 독립성·해제된 객체의 오류와 전체 그래픽 회귀 검사를 통과했습니다.
- `build/runtime-verification-17/summary.json`: 최신 DLL 전체 14개 관문 통과.
- `build/runtime-stock-scenario-10/boot-result.json`: 같은 DLL의 자동 저장/로드/전투/엔딩 통과.
- `build/runtime-benchmark-pairs-2/`: 원본과 3쌍, 장면별 각 1,200프레임의 논리 결과·포커스·원본 보존 검사 통과.
  이동 이벤트 300개의 p95는 각 쌍 12.49~15.29% 감소, 37.5ms 초과 프레임 합계는 원본 11개 / 자체 0개입니다.
  일반 장면의 반복 p95 악화는 없지만 자체 CPU 사용은 원본보다 높습니다.
- DLL SHA-256: `f9287c0594b5a101e35809cb73085733ee95732a6d9f0aa7953184d5dc2c51d6`.

이 결과는 해당 장면의 프레임 간격 검증이며 전체 게임·오디오·DPI·장시간 안정성의 완료 근거가 아닙니다.

`build/RGSSXP-performance-dev-20261018/`는 같은 DLL·변환 도구·라이선스·3쌍 집계를 포함한
개발용 묶음입니다. 37개 파일의 manifest 해시와 묶음 안의 변환 도구만 사용하는
독립 프로젝트 변환(90개 검사, 8개 변경)을 확인했습니다. 원본 게임/에셋은 포함하지 않습니다.

이 DLL의 `build/runtime-endurance-30m-3/` 검사는 아래 전체 화면 수정으로 후보가 바뀌어
의도적으로 중단했습니다. 활성 644.01초·24,800프레임·100왕복을 기록했으며 30분 통과 결과가 아닙니다.
화면 전환 안의 여러 tick에서 발생한 포커스 대기를 모두 누적하도록 검사 스크립트를 보완했고,
분리 자기 검사와 실제 게임의 짧은 2왕복 검사를 통과했습니다. `runtime-endurance-30m-2`는
이 계측 보완을 위해 의도적으로 종료한 예비 실행이며 안정성 실패/통과의 근거로 사용하지 않습니다.

## 전체 화면 복귀 수정과 보조 코드 이전

- DXGI의 자동 창 처리와 자체 Alt+Enter 처리가 충돌해 전체 화면 크기가 적용되지 않는 문제를 수정했습니다.
  자체 창 처리만 사용하도록 `MakeWindowAssociation(DXGI_MWA_NO_WINDOW_CHANGES)`을 지정했습니다.
- `build/runtime-window-review-2/ui-review.json`: 실제 키로 전체 화면 1024×768,
  Alt+Tab 후 복귀, 창 모드 640×480 및 원래 위치·스타일 복원을 확인했습니다.
  관찰 환경은 1024×768 60Hz, HWND DPI 96입니다. 배율 150%·200% 검증을 대신하지 않습니다.
- `build/runtime-verification-18/summary.json`: 보조 코드 이전을 포함한 전체 15개 관문 통과.
  인라인 연결·별도 연결·미사용 연결의 ID/순서·원본 보존과 알 수 없는 Main/연결 코드 거부를 검사했습니다.
  별도 연결 엔트리는 ID/순서를 유지하는 주석으로 바꾸고 보조 DLL을 출력에 복사하지 않습니다.
- `build/runtime-stock-scenario-11/boot-result.json`: 같은 DLL의 저장/로드/전투/엔딩 자동 회귀 통과.
  `build/runtime-legacy-inline-boot-1/`, `build/runtime-legacy-separate-boot-1/`도 같은 시나리오를
  통과했습니다. 논리 입력 주입과 HP=1 시험 전투이며 원본 전체 게임 결과 대조는 아닙니다.
- 해당 DLL SHA-256: `b4a6ac61bf66d66e0bae5fd6950ff2e306e000e26221736e51e8543b51cd2fc0`.
  위 성능 비교와 개발 묶음은 이전 `f9287c...` 해시의 기록입니다.
  그 후보의 3쌍 성능·30분 내구성 검사는 완료하지 않았습니다.
  100%·150%·200% 배율 검증은 사용자 요청으로 범위에서 제외했습니다.
- 설정 앱 실행 재시도에서 조작 가능한 창이 나타나지 않았으며, 배율은 변경하지 않았습니다.
- `build/RGSSXP-window-migration-dev-20261018/`: 이 DLL과 15개 회귀 관문·세 자동 통합 기록을
  포함한 개발용 묶음입니다. 37개 manifest 해시와 묶음 안의 도구만 사용하는 기본 프로젝트 변환을
  확인했습니다. 이전 해시의 성능 수치를 현재 DLL의 결과로 포함하지 않습니다.
- 추가한 프로세스별 PCM 대조 두 쌍에서 MIDI 50% 피치의 envelope 차이를 확인했습니다.
  원본과 스펙트럼 peak가 가깝더라도 음표 길이·루프 호환성을 통과한 것으로 취급하지 않습니다.
  [오디오 대조 기록](RUNTIME_AUDIO.md)에 측정 방법과 제약을 기록했습니다.

## MIDI 출력 경로와 첫 음표 교정

- 직접 연결한 synth 버퍼를 Windows의 독립 AudioPath로 바꿔 낮은 피치의 반복 envelope 문제를 교정했습니다.
  중간 DLL `52e283f7...`는 `build/runtime-verification-21/summary.json`의 15개 관문을 통과했습니다.
  다만 뒤이은 연속 PCM 검사에서 첫 음표 누락을 발견했으므로 오디오 완료 후보로 채택하지 않습니다.
- 초기 지연 시계가 master 시간과 같은 동안은 음표를 제출하지 않고 첫 출력 버퍼 준비를 확인합니다.
  최대 1초의 제한과 명시적 오류를 두고, Ruby에 접근하지 않는 C++ 작업 스레드 대기를 사용합니다.
- 기존 개발 패키지의 검증 후보 SHA-256: `5bc0a17ab0a17e156399ab35f153247e9fd0d9d8c2823f6ca0dce229db3a24c2`.
  `build/runtime-midi-ready-api-check-2/summary.json`의 오디오 voice 회귀를 통과했습니다.
- `build/runtime-waveform-16/comparison-boundary-fix.json`: 동일 소스/생성 음원의 연속 WAV·MIDI
  50/100/150 피치, 첫 음표, 반복 envelope 대조를 통과했습니다. 첫 반복 간격 차이는 50ms 경계입니다.
  기존 `comparison.json`은 정확한 50ms 경계를 부동소수점 오차로 거부한 기록이며 보존했습니다.
  시간 값의 수치 오차만 1ns 단위로 정리했고 50ms 허용 기준을 늘리지 않았습니다.
- `build/runtime-verification-22/summary.json`: 같은 DLL의 전체 15개 관문과 원본 해시 보존 통과.
  22개 Python 검사와 기본 스크립트 90개 변환 검사(8개 변경·82개 원시 바이트 보존)를 포함합니다.
- `build/runtime-stock-scenario-12/boot-result.json`: 같은 DLL의 저장/로드/이벤트/HP=1 전투/엔딩 통과.
- `build/runtime-stock-full-combat-2/boot-result.json`: 게임오버 → 타이틀 → 새 게임 → 4턴 전투 →
  승리 → 맵 이동 → 엔딩 통과. 적 행동 3회·아군 피해 171·적 피해 10,000을 확인했습니다.
  적 HP=10,000, 장비 방어/회피=0, 고정 37% RNG와 논리 입력 주입을 쓰는 시험 콘텐츠입니다.
  원본과의 전투 결과 대조나 무작위 실제 게임의 난이도 검증은 아닙니다.
- `build/runtime-endurance-30m-4/endurance-review.json`: 같은 DLL의 활성 1,810.67초·72,000프레임·
  100왕복·9,000회 이동과 정상 종료를 확인했습니다. 비활성 대기는 0초입니다.
  초기 60~600초의 private 메모리 중앙값 증가는 약 1.33MiB, 기울기는 약 0.204MiB/분,
  핸들 변화는 -2입니다. 600초 이후 중앙값 변화는 약 -0.11MiB, 기울기는 약 -0.0011MiB/분,
  핸들 변화는 +4로 설정한 경계 안이었습니다. 모든 할당의 누수 부재를 증명하지는 않습니다.
  실행 중 101개 이미지 해시에서 원본 RGSS와 보조 DLL이 없음을 확인했습니다.
  GPU 메모리는 종료 전 두 시점만 읽었으므로 전체 VRAM 증가 추세 검증으로 취급하지 않습니다.
- `build/runtime-logic-comparison-3/summary.json`: 원본과 고정 입력 로직 54개 기록 일치.
  접촉/결정/병렬/자동 이벤트, 통행/through/강제 이동/점프, 타이머, 화면 상태, 맵 설정,
  6회 전투 행동/선택/피해/순서, 속도가 같은 12개 행동 순서, 스킬·아이템·지속 피해를 대조했습니다.
  숫자 타입·정수·문자열은 정확히 비교하며 float 출력 표현의 1e-12 이내 오차만 허용합니다.
  이 직접 로직 호출 대조는 전체 장면·모든 난수·화면이나 오디오의 검증이 아닙니다.
- 최신 3쌍 성능 비교와 추가 실제 조작·오디오 대조는 미완료입니다. 배율 검증은 계속 제외합니다.
  이전 해시의 성능이나 내구성 결과를 이 후보의 결과로 사용하지 않습니다.

## 후속 MIDI 교정 작업

- 기존 개발 패키지는 그대로 보존합니다. 작업 DLL `540aeb1dda13703f6e73caf35216f15034261d2a81c005721691f9e8da8e6dd3`는
  ME 뒤 지속음 재발음 제거, 원본에서 확인한 InitAudio/AudioPath 볼륨 제어,
  단발 MIDI의 마디 단위 종료 및 1초 복귀 페이드를 포함합니다.
- `build/runtime-midi-me-length-api-check-1/summary.json`: 작업 DLL의 오디오 voice 회귀 통과.
  `audio_decode_probe`는 원본에서 확인한 4가지 세그먼트 길이와 잘못된 박자 거부를 통과했습니다.
- Python 검사 26개 통과. 전체 회귀 도구에는 decoder 빌드/실행 관문을 추가했습니다.
- 앞 단계 DLL `67c65f3f...`의 여섯 음량은 실제 원본 PCM 대조를 통과했습니다.
  약 -0.93dB의 절대 음량 차이와 정지 후 잔향·ME 복귀 파형 차이는 별도로 남아 있습니다.
  자세한 근거와 실패 기록은 `RUNTIME_AUDIO.md`에 기록했습니다.
- `build/runtime-verification-23/summary.json`: 작업 DLL의 전체 17개 관문 통과.
  decoder 빌드/실행, Python 26개 검사, 원본 해시 보존, 스크립트 8개 변경/82개 원시 바이트 보존을 포함합니다.
- `build/runtime-logic-comparison-4/summary.json`: 같은 작업 DLL과 원본의 고정 입력 54개 기록 일치.
- `build/runtime-stock-full-combat-3/boot-result.json`: 같은 DLL에서 저장/로드 → 게임오버 →
  재시작 → 4턴 전투 → 맵 이동 → 엔딩 → 정상 종료를 통과했습니다.
  시험 적 HP=10,000, 고정 37% RNG, 논리 입력 주입 조건에서 적 행동 3회·아군 피해 171·적 피해 10,000입니다.
  실제 키 조작 완주나 원본 게임과의 전체 장면 대조를 대신하지 않습니다.
- `build/runtime-audio-channels-3/channels-comparison.json`: 지속음 중단/비재발음 대조는 양쪽 통과.
  반복음 시험은 원본도 만족하지 못하는 초기 복귀/즉시 무음 가정과 일부 음량 차이로 미통과입니다.
  원시 획득은 4개 프로세스 모두 정상 종료·불연속 0·timestamp 오류 0입니다. 전체 오디오 통과가 아닙니다.
- `build/runtime-visual-original-4/`, `runtime-visual-replacement-4/`의 생성 화면은 직접 관찰했습니다.
  새 DLL의 Return 입력은 40프레임 전환 후 phase=2를 남겼고 원본에서는 같은 자동화 키의 전환을
  확인하지 못했습니다. 초기 화면에 밝기 차이가 관찰됐으므로 시각 일치 판정을 보류합니다.
  `runtime-visual-replacement-5/render-review-pixels.txt`의 실제 GPU 장면 픽셀은 소스와 일치합니다
  (배경 24/34/45, 불투명 빨강 230/50/40). 내부 합성과 표시/캡처 차이는 구분합니다.
  읽기 전용 `display_color_probe`는 현재 출력 10bit, DXGI ColorSpace=12를 보고했습니다.
  HDR/출력/캡처의 어느 단계가 원인인지는 미확정이며 설정이나 배율을 변경하지 않았습니다.
- `build/runtime-benchmark-pairs-3/comparison.json`: 같은 작업 DLL의 세 쌍 측정 통과.
  300개 이동 이벤트의 p95는 16.14~19.28% 감소했고 37.5ms 초과는 원본 3개/자체 0개였습니다.
  일반 장면의 반복적 5% 악화는 없었습니다. 프로세스 CPU 시간은 증가했으므로 CPU 효율 개선 주장은 하지 않습니다.
  `runtime-render-profile-3/parts-summary.json`의 명령 생성/제출/대기와 `runtime-original-wait-profile-3/`
  관측은 기본 세 쌍과 분리했습니다. 최신 환경은 RTX 3090·2560×1440·280Hz·10bit 출력이며 게임은 40Hz입니다.
- 작업 DLL의 30분 내구성과 남은 음향·최종 시각 호환성은 별도 검증 대상입니다.
  기존 `5bc0a17a...`의 통과 기록을 새 해시에 적용하지 않습니다. 배율 검증은 보류합니다.
- `build/RGSSXP-midi-me-dev-20261018/`: 같은 작업 DLL·Ruby 변환 도구·라이선스·검증 범위를 담은
  38개 파일의 개발 패키지입니다. `runtime-midi-me-package-validation.json`에서 정확한 manifest,
  패키지 자체 도구의 90개 스크립트 변환(8개 변경), 원본 4개 해시 보존을 재검사했습니다.
  원본 실행 파일·RGSS·게임 에셋·세이브는 패키지에 포함하지 않았습니다. 전체 호환성 공개 후보가 아닙니다.

## 후속 경로 실험과 검증 범위

- HDR 캡처 차이를 분리하려고 출력 경로를 시험했습니다. FP16+G22는 현재 GPU에서 지원되지 않았고,
  FP16+G10과 최종 선형 변환은 캡처 색이 가까워졌습니다. 하지만 현재 SDR white level=5000(400nit)이며
  무보정 FP16은 80nit이므로 그것만으로 물리적 밝기 일치를 판정하지 않았습니다.
  명시적 G22의 8bit flip도 캡처 차이를 해결하지 않았습니다. 두 직접 비교 창은 5분 제한으로 종료됐고
  사용자 관찰 답변은 아직 없습니다. 배율·시스템 설정은 바꾸지 않았으며 renderer 소스는 검증된
  `540aeb1d...`와 정확히 같은 상태로 복구했습니다. 원시 실험은 `runtime-visual-fp16-*`,
  `runtime-visual-unorm-g22-flip-1/`, `runtime-visual-original-6/7/`에 보존했습니다.
- 현재 작업 소스는 원본에서 확인한 독립 dry/Waves Reverb AudioPath를 자체 RIFF 구성으로 만듭니다.
  원본 구성 바이트나 다른 RPG 엔진 코드를 사용하지 않습니다. `RUNTIME_AUDIO.md`에 근거·실패 기록을 구분했습니다.
- 중간 DLL `1b731c1a...`는 기존 voice 검사를 통과했고 생성 지속음의 원본 대비 전체 RMS 차이가
  약 +0.027dB로 줄었습니다. 반복 시 볼륨이 덮어써지는 별도 오류도 실제 PCM에서 발견해 수정했습니다.
- 당시 중간 DLL `672bdfc5281befe0c1b8c69e5eb1a9ab692275b78bcc5e0c90e6398ef9d78920`는
  기본 CC7 복원을 줄이고 원본처럼 약 60ms마다 경로 볼륨을 적용합니다.
  `runtime-midi-custom-path-api-check-4/summary.json`의 voice 회귀 통과만 확인된 상태입니다.
  전체 17개 관문·3쌍 성능·30분 내구성·최종 음향/시각 검증을 이 해시에 적용했다고 주장하지 않습니다.

## 자체 MIDI 스케줄러 복구 후 확인

현재 작업 DLL은 `7d310bc96dafec44b4084a22387f0694d75a3983186722599e56a0da2c7a0983`입니다.
Windows MIDI 시퀀서 실험은 초기 음 누락 또는 ME 뒤 지속음 재발음 때문에 채택하지 않았습니다.
기존 이벤트 스케줄러와 baseline renderer의 바이트 단위 복구 및 원본 4개 해시 보존을 확인했습니다.
`build/runtime-midi-persistent-checkpoint-1.json`에 전체 런타임 소스와 산출물의 대응을 기록했습니다.

- `build/runtime-audio-channels-11/channels-comparison.json`: 새 DLL과 원본의 지속음·반복음 두 경우 모두 통과.
  중단된 지속음의 비재발음, 반복음 복귀, BGS 유지, 음량 50, 생성 음원 피치, 늦은 정지 무음을 검사했습니다.
  정지 1.5~2.1초 RMS는 반복음 원본 약 0.0000224 / 자체 약 0.0000228입니다.
  초기 잔향과 전체 RMS 차이도 보존했으며 복귀 위상·잔향 파형 전체의 일치를 인증하지 않습니다.
- 검사 조건을 교정한 Python 회귀 28개가 통과했습니다. 원본도 실패하던 즉시 무음·초기 음 간격 가정을
  제거했고, 지속음 재발음·미래 반복음 누락·계속 울리는 소리는 계속 거부합니다.
- `build/runtime-midi-persistent-sequence-1/comparison.json`: 같은 DLL의 여섯 WAV/MIDI 피치 구간 통과.
  각 엔진의 한 프로세스 내 피치 전환·MIDI 반복을 검사했으며 불연속·timestamp 오류는 없었습니다.
  주파수 2Hz, 음 길이·반복 간격 50ms 등의 기존 기준을 유지했습니다. 전체 파형·스피커 지연 검증은 아닙니다.
- `build/runtime-midi-persistent-volumes-1/volumes-comparison.json`: 같은 DLL의 MIDI 음량
  0·1·25·50·75·100을 실제 원본 PCM과 대조해 통과했습니다. 지속 organ 단음의 안정 구간 검사이며
  전환 순간이나 모든 악기의 음량 일치를 보증하지 않습니다.
- `build/runtime-verification-24/summary.json`: 같은 DLL의 17개 관문 모두 통과.
  Python 28개 검사, 원본 4개 해시 보존, 스크립트 8개 변경/82개 원시 엔트리 보존을 포함합니다.
- `build/runtime-logic-comparison-5/summary.json`: 같은 DLL과 원본의 고정 입력 54개 기록 일치.
- `build/runtime-stock-full-combat-4/boot-result.json`: 같은 DLL에서 저장·로드, 게임오버·재시작,
  4턴 전투, 맵 이동·엔딩·정상 종료를 통과했습니다. 고정 시험 RNG와 논리 입력 주입 조건이며,
  적 행동 3회·아군 피해 171·적 피해 10,000입니다. 직접 키 조작 완주나 원본 전체 장면 대조는 아닙니다.
- 이 해시의 후속 성능·실제 조작 결과는 아래에 기록합니다. 30분 내구성은 아직 별도 확인 대상입니다.
  과거 후보의 결과를 이전하지 않습니다. 이전 개발 패키지는 보존하며 배율 검사는 계속 보류합니다.
- `build/RGSSXP-midi-path-dev-20261018/`: 같은 DLL, 패키지 자체 Ruby 변환 도구,
  17개 관문·전투·여섯 피치 보고서와 라이선스를 담은 39개 파일의 개발 패키지입니다.
  `build/runtime-midi-path-package-validation.json`에서 정확한 파일 목록·전체 해시,
  패키지 자체 도구의 90개 스크립트 변환(8개 변경/82개 보존), 원본 4개 해시 보존을 확인했습니다.
  원본 실행 파일·RGSS·에셋·세이브·원시 추적은 포함하지 않았습니다. 전체 호환성 공개 후보는 아닙니다.

## 현재 후보의 성능과 실제 조작 재검증

아래 결과는 모두 DLL `7d310bc96dafec44b4084a22387f0694d75a3983186722599e56a0da2c7a0983`에 한정합니다.
기존 개발 패키지는 생성 당시의 기록과 함께 보존하며, 아래 후속 결과를 넣기 위해 덮어쓰지 않습니다.

- `build/runtime-benchmark-pairs-4/summary.json`, `comparison.json`: 원본과 세 쌍, 장면별 각 엔진
  1,200프레임의 활성 창·논리 상태 일치·원본 보존 검사 통과. 이동 이벤트 300개/병렬 30개의
  p95는 각 쌍 15.72~16.57% 감소했고, 37.5ms 초과는 원본 4개/자체 0개였습니다.
  일반 장면의 반복적 p95 5% 악화는 없습니다. 프로세스 CPU 시간은 증가했으므로 CPU 효율 개선이 아닙니다.
  별도 GPU 진단은 장면별 유효한 고유 시퀀스 400개, p95 0.125/0.133/0.167/0.167ms입니다.
  원본 GPU 실행 시간이나 전체 표시 지연과의 비교로 취급하지 않습니다.
- `build/runtime-render-profile-4/parts-summary.json`과 `runtime-original-wait-profile-4/summary.json`은
  렌더 명령 생성·제출·대기의 별도 경과 시간 관측입니다. CPU 실행 시간과 다르며 기본 세 쌍에 섞지 않았습니다.
  환경과 전체 p50/p95/p99·CPU 수치는 [성능 기록](RUNTIME_PERFORMANCE.md)에 있습니다.
- `build/runtime-stock-manual-한글-5/boot-result.json`, `ui-review.json`: 논리 입력 주입 없이 실제 OS 키로
  타이틀 → 새 게임 → 대화/선택지 → 그림/강제 점프 → 전투 명령/대상 선택 → 승리 → 맵 이동 →
  엔딩 → 타이틀 → 종료를 확인했습니다. 원래 스크립트를 사용하는 자체 짧은 시험 콘텐츠이며 적은 한 번에
  쓰러지는 조건입니다. 저장·로드·게임오버와 다중 턴 전투는 별도의 자동 통합/로직 검사가 담당합니다.
  실제 모니터 밝기나 원본의 전체 장면·오디오 일치를 확인했다는 뜻은 아닙니다.
- `build/runtime-window-review-5/`에서는 실제 Alt+Enter로 창 모드 640×480에서 전체 화면
  2560×1440(4:3 화면 1920×1440과 좌우 여백) 진입을 관찰했습니다. 이후 Explorer 활성화가
  `Computer Use app approval timed out`으로 끝났고, 검사 실행기는 600초 제한 후 프로세스를 종료했습니다.
  `process-result.json`의 exit 1은 이 제한 종료 기록입니다. 엔진 충돌 또는 창 복귀/Alt+Tab 통과로
  판정하지 않습니다. 창 모드 복원·포커스 복귀·실제 F12는 같은 해시에서 다시 확인해야 합니다.
- `build/runtime-visual-original-8/`, `runtime-visual-current-8/`에 원본과 현재 후보의 같은 자체 생성
  화면을 다시 열었습니다. `review-session.json`에 프로세스·DLL·시험 소스 해시를 기록했으며,
  사용자 모니터 관찰 답변을 기다립니다. 캡처의 밝기 차이만으로 최종 출력을 교정하거나 통과 처리하지 않습니다.
  배율·시스템 설정은 변경하지 않았습니다.

현재 해시의 30분/100왕복 내구성, 최종 실제 표시와 남은 음향 교정은 완료하지 않았습니다.
이전 `5bc0a17a...`의 내구성 통과를 현재 후보로 옮기지 않습니다.

## HDR 출력 교정 후보

`7d310bc9...`의 실제 모니터 밝기·색 차이에 대한 사용자 확인 후, 최종 출력만 FP16 선형 scRGB로
변환하고 OS의 SDR white level을 반영하는 후보를 만들었습니다. 무보정 FP16은 실제로 더 어두웠고,
OS 보정 후보 `aca5b97a...`는 실제 밝기·색이 원본과 비슷하다는 사용자 답변을 받았습니다.
이어 GPU 검사로 mirror 플래그 충돌을 찾아 별도 수정했습니다.

해당 표시 교정 DLL은 `88565e7ed82556287512fea568fd932b063932f8ce4f54d0f725eac99d955b6d`입니다.
`build/runtime-verification-25/summary.json`의 전체 19개 관문, Python 28개 검사, 원본 4개 해시 보존,
기본 소스 8개 변경/82개 원시 엔트리 보존을 통과했습니다.
`output-color.log`는 실제 GPU의 8,192개 채널 값과 OS white scale=5를 확인했습니다.

- `build/runtime-window-review-6/ui-review.json`: 실제 Alt+Enter로 640×480 창 → 2560×1440 전체 화면,
  두 자체 게임 창 사이의 Alt+Tab 이탈·복귀, 원래 창 크기·위치·스타일 복원, Alt+F4 정상 종료 확인.
- `build/runtime-reset-key-new-4/ui-review.json`: 실제 F12 두 번으로 카운터 1→2→3, 이전 Bitmap 폐기,
  Font 기본값·프레임 카운트 보존, 40Hz 유지, VM 초기화·종료 각각 한 번 확인.
- `build/runtime-logic-comparison-6/summary.json`: 같은 DLL과 원본의 고정 입력 로직 54개 기록 일치.
- `build/runtime-stock-full-combat-5/boot-result.json`: 저장·로드 → 게임오버·새 게임 → 4턴 전투 →
  맵 이동·엔딩·정상 종료 통과. 적 행동 3회·아군 피해 171·적 피해 10,000이며 고정 시험 RNG와
  논리 입력 주입 조건입니다. 원본 전체 게임 플레이 대조는 아닙니다.
- `build/runtime-color-checkpoint-1.json`: 현재 소스/DLL 해시와 원본 보존 확인.
  이전 런타임 소스는 renderer 외에 변경하지 않았으며 output/shader 헤더 두 개를 추가했습니다.

이전 후보의 성능·30분 내구성·오디오 검사를 새 해시의 통과 기록으로 옮기지 않습니다.
구현·실패 기록·사용자 관찰 범위·실제 GPU 출력 검사는 [색 출력 기록](RUNTIME_COLOR.md)에 있습니다.

`build/runtime-benchmark-pairs-5/comparison.json`은 이 표시 교정 해시의 세 쌍 비교입니다.
이동 스트레스 p95는 15.89~17.35% 감소했고 37.5ms 초과는 원본 6개/자체 0개였습니다.
일반 장면의 반복적 p95 5% 악화는 없었습니다. CPU 시간은 증가했으며 CPU 효율 개선으로 주장하지 않습니다.
`build/runtime-stock-manual-한글-6/`는 같은 DLL에서 실제 키로 선택지·전투·맵 이동·엔딩·정상 종료를
확인한 기록입니다. 한 번에 쓰러지는 시험 적을 사용하며 원본 전체 게임 대조는 아닙니다.

## 압축 음원 PCM 대조와 WMA 피치 교정

현재 작업 DLL은 `66aab878a7a83c6eda8083ea0163e8cec8c3da776695569499adacf84aedfd7e`입니다.
`build/runtime-verification-26/summary.json`의 전체 19개 회귀 관문과 Python 29개 검사를 통과했습니다.
원본 4개 해시와 스크립트 8개 변경/82개 원시 엔트리 보존도 확인했습니다.

- `build/runtime-compressed-pcm-1/comparison.json`: 앞선 후보의 Ogg·MP3는 통과했지만 WMA 50/150은
  원본과 실제 음높이·길이가 달랐습니다. 최초 분석의 모든 PCM에 피치를 적용한다는 가정도 WMA 원본에
  맞지 않았습니다. 실패 결과를 보존하고 원본 전용 추가 검사로 실제 계약을 확인했습니다.
- `build/runtime-wma-roles-original-1/pitch-oracle.json`: 변경하지 않은 원본에서 생성 WMAv2 음원의
  BGM/BGS/ME/SE × 피치 50/100/150 모두 약 440Hz. WMA의 피치 지정 무시를 확인했습니다.
- 실제 encoded codec을 Media Foundation에서 읽어 WMA일 때만 출력 주파수 비율을 1로 유지합니다.
  확장자 생략에도 적용되며 WAV·Ogg·MP3·MIDI에는 이 조건을 적용하지 않습니다.
  기존 requested-pitch 저장과 같은 파일 재생 정책은 이번 변경에서 유지합니다.
- `build/runtime-compressed-pcm-2/comparison.json`: 같은 원본/수정 음원 파일로 Ogg·MP3·WMA의
  50/100/150 피치 9개 구간의 실제 주파수·완료 envelope 길이 대조 통과.
- `build/runtime-wma-roles-1/wma-roles-comparison.json`: 같은 후보의 WMA 12개 역할/피치 대조 통과.
  두 엔진 모두 정상 종료·PCM 불연속 0·timestamp 오류 0이며, 시험 소스와 음원 해시를 대조했습니다.
  다른 WMA 코덱, 루프 경계·같은 파일 재시작 정책 전체의 인증은 아닙니다.

이전 해시의 성능·30분 내구성·직접 조작 결과를 이 DLL의 새로운 실행 기록으로 옮기지 않습니다.

현재 `66aab878...`의 후속 재검증입니다.

- `build/runtime-midi-persistent-sequence-2/comparison.json`: 같은 DLL의 WAV/MIDI 여섯 구간 통과.
  첫 음·반복 길이 기준을 유지했으며, API 반환 후 첫 MIDI 음은 원본보다 약 0.18~0.22초 빨랐습니다.
  전체 초기화나 물리 스피커 지연의 동일성을 의미하지 않습니다.
- `build/runtime-benchmark-pairs-6/comparison.json`: 같은 DLL의 세 쌍 통과. 이동 스트레스 p95는
  17.22~18.53% 감소했고, 37.5ms 초과는 원본 7개/자체 0개입니다. 일반 장면의 반복적 p95 5% 악화는 없습니다.
  CPU 시간은 증가했습니다. 별도 GPU p95는 0.154/0.166/0.208/0.217ms이며 원본 GPU 비용은 미확정입니다.
- `build/runtime-render-profile-6/parts-summary.json`, `runtime-original-wait-profile-5/summary.json`:
  기본 세 쌍과 분리한 경과 시간 구간·원본 대기 관측입니다. 원래 import 복원과 다른 DLL 거부도 통과했습니다.
- `build/runtime-logic-comparison-7/summary.json`: 원본과 고정 로직 54개 기록 일치.
- `build/runtime-stock-full-combat-6/boot-result.json`: 저장·로드, 게임오버·재시작, 4턴 전투,
  맵 이동·엔딩·정상 종료 통과. 적 행동 3회·아군 피해 171·적 피해 10,000의 고정 시험 조건입니다.
- `build/runtime-package-report-guards-1/`: 누락된 음원 경우, 다른 DLL, 실패한 WMA 경우의
  보고서를 출력 생성 전에 거부했습니다. 4개 실제 CLI 호출의 명시적 오류도 대조했습니다.

`build/runtime-stock-manual-한글-7/ui-review.json`은 같은 DLL을 한글 경로에서 실제 키로 완주한 기록입니다.
선택지·그림/점프·네 배우의 명령/대상 선택·승리·맵 이동·엔딩·타이틀 복귀 후 F12 두 번과 정상 종료를
확인했습니다. 타이틀 BGM이 설정된 상태의 리셋 두 번에서 VM 초기화/종료는 각각 한 번입니다.
한 번에 쓰러지는 시험 적을 사용하며 실제 원본 게임 전체와의 결과 대조는 아닙니다.
`build/runtime-window-review-7/ui-review.json`도 같은 DLL의 실제 Alt+Enter 왕복·Alt+Tab 이탈/복귀·
초기 창 크기/위치/스타일 복원·Alt+F4 정상 종료를 확인했습니다. 배율은 시험하거나 변경하지 않았습니다.

같은 해시의 30분/100왕복 내구성은 `build/runtime-endurance-30m-5/`에서 정상 종료했습니다.
`endurance-review.json`은 활성 1,801.637초·72,000프레임·100왕복·9,000회 이동·비활성 대기 0을 확인했습니다.
초기 맵 이동 구간의 private 중앙값 증가는 256KiB, 600초 이후 구간은 72KiB,
후자의 기울기는 0.00284MiB/분, 핸들 중앙값 증가는 4개로 검사 기준 안입니다.
`gpu-memory-review.json`의 59개 PID/생성시각 고정 표본에서 GPU 전용 메모리는 약 27.52MiB,
commit은 약 30.64MiB로 안정적이었습니다. GPU 메모리 관측은 GPU 처리 시간이나 모든 할당의 누수 부재 증명이 아닙니다.

`build/RGSSXP-sdr-wma-dev-20261018/`은 생성 시 완료된 19개 관문·통합·세 쌍·6/9/12 PCM 기록을
포함한 43개 파일의 개발용 묶음입니다. `runtime-sdr-wma-package-validation.json`에서 정확한 manifest와
패키지 자체 변환 도구의 90개 검사(8개 변경/82개 보존), 원본 4개 해시 보존을 확인했습니다.
실행 중인 내구성 결과를 미리 포함하거나 기존 묶음을 덮어쓰지 않았습니다. 원본 바이너리·게임 에셋·세이브·
원시 추적은 포함하지 않았습니다. 전체 호환성 공개 후보는 아닙니다.

## RTP 조회와 애니메이션 추가 교정

현재 후보는 `d57f1a60090ec48e9dd23824bad7327e6ba21d5129444c3d2aef970f522c30be`입니다.
`rpg_graphics.rb`만 바꿨으며 기존 DLL/소스는 `build/runtime-before-animation-fix-1/`에 보존했습니다.
머리·발 애니메이션 위치를 원본의 높이 1/4 기준으로 수정하고, 반복 애니메이션의 첫 프레임을 즉시 설정했습니다.
일반·반복 애니메이션 모두 전역 Graphics.frame_count의 짝수 프레임에서 진행합니다.

- `build/runtime-graphics-helpers-3/`: 교정 전 위치·초기화·반복 타이밍 차이를 관찰했습니다.
- `build/runtime-graphics-helpers-5/`: 시작 프레임이 홀수일 때의 추가 차이를 확인했습니다.
- `build/runtime-graphics-helpers-6/summary.json`: 교정 후 40개 기록 중 캐시 및 일반/반복 애니메이션
  네 위치·두 시작 위상·9회 갱신의 공개 상태가 정확히 일치했습니다. 이 검사는 frame_count를 명시적으로
  설정하는 상태 비교이며, 모든 애니메이션 이미지·효과음·flash 픽셀의 동일성 검사는 아닙니다.
  색상 회전은 여섯 RGBA 색에 대해 알파가 일치하고 RGB 차이가 최대 3단계입니다.
  레거시 정수 양자화와 byte 단위 동일하지 않으며, 범위 밖 720도 결과는 원본과 다릅니다.
- `build/runtime-rtp-4/summary.json`: 설치된 32비트 Standard RTP 등록을 읽고 에셋 복사 없이
  확장자를 생략한 타이틀·윈도 스킨·MIDI를 조회했습니다. 프로젝트 파일 우선, 음원 진행,
  원본/등록 보존과 실제 로드 모듈을 확인했습니다. PNG와 상태 세 항목은 정확히 일치하며,
  JPEG 세 픽셀 표본은 디코더 반올림 차이 최대 1단계(허용 2단계)입니다. 전체 JPEG 픽셀 일치 판정은 아닙니다.

재현 명령은 `scripts/test_runtime_graphics_helpers.py`와 `scripts/test_runtime_rtp.py`의 `--help`에서 확인합니다.
이 후보는 `build/runtime-verification-27/`의 전체 19개 관문·Python 29개 검사, 8개 소스 변경/82개 엔트리 보존을 통과했습니다.
`build/runtime-stock-full-combat-7/boot-result.json`도 저장·로드 → 게임오버·재시작 → 4턴 전투 → 맵 이동·엔딩을
정상 종료했습니다. 적 행동 3회, 아군 피해 171, 적 피해 10,000의 고정 시험 조건이며 실제 키 조작 검사는 아닙니다.
`66aab878...`의 성능·PCM·30분 결과를
이 해시의 새 실행 기록으로 옮기지 않습니다. 해당 d57 후보의 일반 파일/아카이브 읽기는 Ruby 주 스레드에서 수행했습니다.

## 파일 읽기 작업 분리 후보

현재 후보는 `d51cbd7e2bc9bab619a1f9ea4c5222e1c8bac0cd388a9a3d83ca9f46e56853a7`입니다.
`file_io.cpp`로 스크립트·데이터·이미지·오디오·원본/새 세이브의 내용 읽기를 네이티브 작업으로 옮겼습니다.
RGSSAD 인덱싱에는 64KiB 버퍼를 두고, 기존 파서와 손상/중복/경계 검사는 유지했습니다.
Ruby 객체는 작업 스레드에서 접근하지 않습니다. StringIO 3.2.0은 고정한 Ruby 배포 소스에서 정적으로 포함하며,
소스 해시와 증분 빌드에서의 불일치 거부도 확인했습니다.
기본 저장 화면이 쓰는 mtime은 100ns 정밀도·표시 시간대·초 미만 순서를 보존합니다.
세이브 버전 표식·원본 Import 읽기 전용·원자적 쓰기와 루트 저장 보호는 바꾸지 않았습니다.

현재 전체 회귀 기록은 `build/runtime-verification-32/`입니다. 새 `file-io` 관문을 포함해 20개이며,
기존 해시의 통과 기록을 현재 해시의 실행 결과로 옮기지 않습니다. 구현·재현 명령과 실제 제한은
[파일 읽기 기록](RUNTIME_FILE_IO.md)에 있습니다. 호출자는 읽기가 끝날 때까지 기다리며,
경로 검색의 파일 정보 조회와 저장 쓰기는 주 스레드에 남습니다. 비동기 맵 로딩이나 로딩 시간 개선을 주장하지 않습니다.

현재 해시의 20개 관문·Python 29개 검사와 원본 보존, 8개 스크립트 변경/82개 원시 엔트리 보존을 통과했습니다.
`runtime-graphics-helpers-8`의 애니메이션/캐시 상태, `runtime-rtp-6`의 설치 RTP 조회,
`runtime-logic-comparison-9`의 원본과 고정 로직 54개 기록도 통과했습니다.
`runtime-stock-full-combat-9`는 저장 화면·불러오기 → 게임오버/재시작 → 4턴 전투 → 맵 이동/엔딩을
정상 종료했습니다. 논리 입력과 고정 시험 RNG이며 적 행동 3회·아군 피해 171·적 피해 10,000입니다.

`runtime-benchmark-pairs-7`은 세 쌍에서 이동 스트레스 p95가 13.05~15.42% 감소했고,
37.5ms 초과는 원본 6개/자체 0개였습니다. 일반 장면의 반복적 p95 5% 악화는 없었습니다.
CPU 시간은 증가했습니다. 별도 GPU p95는 0.225/0.237/0.272/0.273ms이며 원본 GPU 비용은 여전히 미확정입니다.
별도 렌더/대기 경과 구간과 환경도 기록했습니다. [성능 기록](RUNTIME_PERFORMANCE.md)에 범위를 구분했습니다.
같은 해시의 `build/runtime-endurance-30m-6/endurance-review.json`은 활성 1,801.651초·72,000프레임·
100왕복·9,000회 이동·비활성 대기 0·정상 종료를 확인했습니다.
600초 이후 private 중앙값 변화는 -8KiB, 기울기 -0.00150MiB/분, 핸들 변화 -2개였습니다.
초기 맵 로딩 구간도 private 증가 422KiB·0.0489MiB/분으로 검사 기준 안입니다.
GPU 메모리는 59개 표본에서 전용 약 27.52MiB·commit 약 31.13MiB로 안정적이었습니다.
모든 할당의 누수 부재 증명은 아닙니다. 이전 해시의 실제 키 조작·PCM 녹음도 현재 해시의 새 실행으로 옮기지 않습니다.

## 아카이브 이름·기본 그래픽 의미 교정

후속 후보는 `3868eeceb9fbba5ffc2509cf371e54240db726645dd64145ca4ef5b7f7fffd41`입니다.
변경한 런타임 소스는 archive.rb·graphics.rb·rpg_graphics.rb 세 개이며,
기존 원본 해시와 이전 DLL/소스를 보존했습니다.

- 선언된 UTF-8/CP949/CP932로 아카이브 이름을 먼저 해석하고 구분자를 처리합니다.
  CP932 `ソ`의 0x5C trail byte를 슬래시로 바꾸던 결함과 CP949 키 불일치를 교정했습니다.
  `runtime-archive-name-normalize-1`은 수정 전 실패, `runtime-archive-name-normalize-3`은 소스 수준 통과입니다.
  `runtime-archive-names-before-1`은 이전 DLL의 잘못된 이름 수용을 실제 재현했습니다.
  `runtime-archive-names-after-1`은 현재 DLL의 인코딩별 데이터·확장자 없는 PNG·음원 바이트 조회와
  잘못된 인코딩 이름 거부, 아카이브 바이트 보존을 통과했습니다. 음향 시험은 아닙니다.
- `runtime-graphics-extended-1`에서 원본과 다른 손상 숫자 글꼴·배치 및 viewport 화면 애니메이션
  위치를 확인했습니다. Arial Black/비굵게, 숫자 y=12·CRITICAL y=0과 외곽선,
  화면 애니메이션의 viewport 폭/2·높이-160 기준으로 교정했습니다.
  `runtime-graphics-extended-2`는 세 손상 표시의 글꼴·색·범위와 세 viewport의 일반/반복 좌표가
  정확히 일치했습니다. 픽셀 해시는 다르므로 글자 래스터화 동일성은 주장하지 않습니다.
- `runtime-scene-comparison-1/2`는 원본/새 엔진에서 같은 자체 콘텐츠·고정 RNG로 저장/로드·게임오버·
  재시작·4턴 전투·엔딩까지 실행했습니다. 게임 상태·피해·보상은 일치했지만 프레임 카운트가 달랐습니다.
  호출 추적에서 원본의 인자 없는 transition이 8프레임임을 확인해 10에서 8로 고쳤습니다.
  `runtime-transition-counter-3`은 기본/명시적 전환과 frame_reset의 카운트를 대조해 통과했습니다.
  `runtime-scene-comparison-3`은 실제 키 입력을 배제한 같은 논리 입력·고정 RNG로 양쪽 전체 장면을
  정상 종료했습니다. 스위치·변수·파티 상태·아이템·플레이어 위치·타이머·40Hz,
  frame_count=2060·driver_tick=2101과 전투 4개 수치가 정확히 일치했습니다.
  이는 자체 검증 게임의 숫자/상태 대조이며 모든 화면·음향 또는 물리 키 조작 대조는 아닙니다.

`runtime-archive-graphics-checkpoint-1.json`은 현재 소스와 DLL·원본 해시의 대응입니다.
이전 d51 후보의 성능·30분 기록은 이 새 해시의 실행 결과가 아닙니다.
`build/runtime-verification-33/summary.json`의 전체 23개 관문과 Python 29개 검사,
원본 보존·8개 스크립트 변경/82개 원시 엔트리 보존을 통과했습니다.

같은 해시의 `runtime-benchmark-pairs-9`에서 원본/자체 엔진 세 쌍과 별도 GPU 진단을 완료했습니다.
이동 스트레스 p95는 각 쌍에서 24.09%·21.83%·22.69% 감소했고,
37.5ms 초과는 원본 17개/자체 0개였습니다. 일반 장면의 반복적 5% 악화는 없었습니다.
전체 프로세스 CPU 시간은 증가했습니다. GPU p95는 0.119~0.131ms이며 원본 GPU 비용은 미확정입니다.
앞선 pairs-8은 포커스 이탈로 무효 처리하고 이번 결과와 섞지 않았습니다.
상세 표와 해석 범위는 [성능 기록](RUNTIME_PERFORMANCE.md)에 있습니다.
현재 해시의 30분 내구성·실제 키 완주는 아직 별도 검사 대상입니다.

`runtime-stock-manual-한글-8/ui-review.json`은 같은 현재 DLL의 실제 OS 키 검사를 기록합니다.
ScenarioDriver와 논리 입력 덮어쓰기를 끈 복사본에서 대화·Continue 선택·네 캐릭터 공격/대상 선택·
2개 시험 적 승리(4 EXP / 32 G)·맵 전환·엔딩 대화·타이틀 복귀를 확인했습니다.
실제 F12 두 번 뒤 Shutdown으로 정상 종료했고, VM 초기화/최종화 각 한 번과 Reset 두 번을 확인했습니다.
로드된 106개 이미지에서 현재 DLL을 확인했으며 원본·보조 DLL은 없습니다. 원본 파일도 보존했습니다.
이번 검사는 타이틀 BGM을 별도로 지정하지 않았고 화면 픽셀·물리 음향 대조는 아닙니다.
현재 해시의 30분 내구성은 별도 검사 중이며 완료 보고 전에는 통과로 간주하지 않습니다.

## 현재 후보의 내구성·창 복귀 재검사

같은 `3868eece...`의 `runtime-endurance-30m-7/endurance-review.json`은
활성 1,802.005초·72,000프레임·100왕복·9,000회 이동·포커스 대기 0초·정상 종료 0을 기록했습니다.
600초 이후 private 중앙값 변화 +12KiB, 기울기 -0.000281MiB/분, 핸들 변화 0개로 기준 안입니다.
초기 맵 로딩 구간도 private 증가 416KiB·0.0575MiB/분, 핸들 변화 -2개로 기준 안입니다.
`gpu-memory-review.json`의 60개 유효 표본(미수집 0개)은 전용 메모리 약 27.5MiB,
commit 약 31.1MiB이며 600초 이후 두 기울기 모두 음수였습니다.
원본·보조 DLL이 없는 실제 모듈 해시와 중간/종료 전 플레이어 표시도 확인했습니다.
모든 할당의 누수 부재 또는 모든 프레임의 픽셀 동일성 증명은 아닙니다.

`runtime-window-review-8/ui-review.json`은 실제 Alt+Enter 2560×1440 전체 화면,
두 자체 검사 창 사이 Alt+Tab 왕복과 프레임 재개, 640×480 창의 원래 스타일·위치·외곽 크기 복원을
확인했습니다. 두 창은 Alt+F4로 정상 종료했습니다. 배율을 조회·변경·시험하지 않았습니다.
현재 해시의 `runtime-logic-comparison-10`은 고정 RNG 로직 54개 기록,
`runtime-graphics-helpers-9`는 애니메이션/캐시와 제한된 hue 검사,
`runtime-rtp-7`은 설치 Standard RTP 조회와 등록/원본 보존을 재검사해 통과했습니다.
기존 원본 및 이전 개발 패키지는 보존합니다.

현재 해시의 생성 음원 실제 PCM도 별도로 대조했습니다. `runtime-current-pcm-sequence-1`의
WAV/MIDI 6개, `runtime-current-pcm-compressed-1`의 9개, `runtime-current-pcm-wma-roles-1`의
12개 구간과 `runtime-current-pcm-channels-1`의 유지/반복 채널 중단·복귀,
`runtime-current-pcm-volumes-1`의 7개 음량 정착 구간을 통과했습니다.
MIDI 첫 음표는 원본보다 약 0.21~0.23초 빨랐으며 동일 타이밍이라고 주장하지 않습니다.
전체 파형·모든 악기/코덱·물리 스피커 지연의 인증도 아닙니다. [오디오 기록](RUNTIME_AUDIO.md)에 범위를 구분했습니다.
