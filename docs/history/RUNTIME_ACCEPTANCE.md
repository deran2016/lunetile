# RGSSXP 첫 버전 인수 확인

> 독립 소스 저장소 안내: 아래의 이전 DLL 해시·build 경로는 분리 전 검증 기록입니다.
> 원시 자료는 포함하지 않으며, 새 저장소의 실제 빌드·검사 결과는 [VALIDATION.md](../VALIDATION.md)에 구분합니다.

2026-10-18 사용자가 **“GPU 비교 미확정을 명시하고 첫 버전 인수”**를 선택했습니다.
원본 GPU 수치 비교는 첫 버전의 필수 완료 조건에서 제외하며, 미확정 결과를 그대로 유지합니다.
GPU 비용 0 또는 GPU 성능 향상을 입증했다는 의미가 아닙니다.
아래 기능·호환성·성능·내구성 조건은 그대로 유지합니다.

대상 DLL은 `3868eeceb9fbba5ffc2509cf371e54240db726645dd64145ca4ef5b7f7fffd41`입니다.
기본 XP 스크립트를 쓰는 자체 검증 게임이 기준입니다. 다른 RPG 엔진·원본 RGSS 호출 전달,
임의 플러그인과 편집기 DLL 호환으로 목표를 바꾸지 않습니다.
아래 `build/` 경로는 로컬 증거 위치이며 원본/게임 에셋/원시 기록을 공개하라는 뜻이 아닙니다.

| 승인한 요구 사항 | 확인 근거 | 현재 판정 |
|---|---|---|
| 원본 32비트 Game.exe와 독립 대체 DLL | `src/runtime/abi.json`, `exports.json`, `runtime-verification-33/artifact.json`, 실제 모듈 해시 | 실행기 필수 5개 cdecl 함수 구현. 나머지 61개를 성공 반환하는 빈 함수로 내보내지 않음 |
| C++17·CMake·MSVC2022 x86·Windows 11 | `CMakeLists.txt`, `runtime-benchmark-pairs-9/environment.json`, PE 검사 | 확인 |
| Ruby 4.0.7 소스·해시·빌드 옵션·JIT 비활성화 | `src/runtime/ruby.lock.json`, `runtime-ruby-x86/patched-4.0.7/gate.json`, interpreter/PE 관문 | x86 atomic 포팅 수정 기록과 StringIO 고정 소스 검사 포함 |
| DLL 내 Ruby 실행·정상 종료·예외·리셋 | runtime/reset 관문, `runtime-stock-manual-한글-8/rgssxp.log` | 실제 F12 두 번, VM 초기화·최종화 한 번, 종료 0 |
| 원본 RGSS·기존 보조 DLL 비의존성 | 각 실행의 `modules.json`, `runtime-stock-manual-한글-8/ui-review.json` | 실제 로드된 이미지 해시에서 원본·보조 DLL 없음 |
| 명시적 프로젝트 복사본 변환·기존 출력 거부 | migration 및 migration-guards 관문, `runtime-compat-perf-package-validation.json` | 90개 검사, 8개 변경, 82개 원시 엔트리 보존. ID·이름·순서 유지 |
| 불명확한 사용자 코드·인코딩 추측 거부 | migration-guards/migration-text/legacy-pacing 관문 | 검토된 소스와 두 보조 연결만 변환. 실패 시 원본 보존 |
| RGSS 데이터형·RPG 필드·Marshal 객체 그래프 | data-and-import 관문 | 프로젝트 15개 데이터와 원본 세이브 대조. 기본 스크립트 밖의 일부 생성자는 명시적 미지원 |
| 원본 세이브 가져오기·새 저장 분리 | data-and-import, migration-text, 기본 게임 저장/로드 | Import 읽기 전용, `Saves/RGSSXP/` 버전 표식·원자적 저장. 역호환 주장 없음 |
| RTP·확장자 생략·상대/한글 경로 | `runtime-rtp-7`, migration-text, file-io 관문, 한글 경로 실제 키 검사 | 확인한 UTF-8/CP949/CP932와 설치 Standard RTP 범위. 모든 시스템 로캘 보증 아님 |
| RGSSAD v1 이름·경계·순서·인코딩 | archive/archive-names/archive-migration 관문 | 인코딩별 조회 및 잘못된 이름 거부. v2/v3는 XP 범위 밖 |
| 주 스레드 Ruby·렌더 제출, 작업 스레드 I/O/디코딩/오디오 | `src/runtime/file_io.cpp`, `bitmap.cpp`, `audio*.cpp`, file-io/audio 관문 | 작업 스레드에서 Ruby 객체에 접근하지 않음. I/O 호출자는 완료까지 대기 |
| Bitmap CPU/dirty texture·GDI 글자 | graphics 및 graphics-extended 관문 | 합성 512개 조합, 글꼴·영역·배치 대조. 손상 숫자 픽셀 해시 동일성은 아님 |
| Sprite·Plane·Viewport·Tilemap·Window·Font·합성·표시 순서 | graphics 관문의 실제 GPU 픽셀, `runtime-graphics-helpers-9`, `runtime-graphics-extended-2` | 확인한 연산·48종 오토타일 quarter·우선순위·스크롤·창 커서 범위. 모든 화면의 byte 동일성 보증 아님 |
| freeze/transition·Graphics.update·frame_count | transition-counter 관문, `runtime-scene-comparison-3` | 원본 기본 전환 8프레임, frame_reset 카운트와 전체 게임 최종 카운트 일치 |
| 640×480·40Hz QPC 누적 마감·GPU 유효성 | graphics/output-color 관문, `runtime-benchmark-pairs-9` | 기본 속도 유지. GPU timestamp 불확정 값은 성능 수치로 사용하지 않음 |
| BGM/BGS/ME/SE·볼륨·피치·페이드·루프·복귀 | audio-decoder/audio 관문, `RUNTIME_AUDIO.md`의 해시별 PCM 기록 | 현재 해시 실제 PCM의 WAV/MIDI 6개, 압축 음원 9개, WMA 역할/피치 12개, 유지/반복 채널·음량 단계 대조 통과 |
| 자동 기본 게임 전체 경로와 원본 대조 | `runtime-scene-comparison-3/summary.json` | 저장/로드·게임오버·재시작·4턴 전투·맵 전환·엔딩, 상태와 frame_count=2060/driver_tick=2101 일치 |
| 실제 조작 시작부터 엔딩까지 | `runtime-stock-manual-한글-8/ui-review.json`, `boot-result.json` | 논리 입력 주입 없이 실제 키로 완주·리셋·정상 종료. 자체 적 HP=1 시험임 |
| 접촉·결정키·병렬·자동 실행·강제 이동·점프·통행·타이머·전투 | `runtime-logic-comparison-10`, integer-order 관문, 전체 장면 대조 | 고정 시험 RNG와 논리 입력 조건을 구분해 대조 |
| CPU·GPU·프레임 간격 세 쌍, 성능 기준 | `runtime-benchmark-pairs-9/comparison.json`, `capture-validation.json` | 스트레스 p95 21.83~24.09% 감소, 일반 반복 5% 악화 없음. 전체 CPU 시간 증가. 원본 GPU 비용·전체 표시 지연 미확정 |
| 프레임 대기와 렌더 경과 구간 분리 | `runtime-components-review-2.json`, `RUNTIME_GPU_TRACE.md` | 현재 해시 세 쌍, 장면별 400프레임의 원본/자체 대기 및 자체 명령·제출 구간 수집. 자체 GPU timestamp는 완료 시퀀스를 연결한 장면별 384개씩 세 번. 원본 GPU 프레임 귀속은 미확정 |
| 30분·100왕복·메모리/충돌/진행 중단 | `runtime-endurance-30m-7/endurance-review.json`, `gpu-memory-review.json` | 1,802.005초·72,000프레임·100왕복·9,000회 이동·포커스 대기 0·정상 종료. 초기/후기 RAM·핸들 및 GPU 메모리 추세 확인 |
| Alt+Tab·전체 화면 복귀·입력 | `runtime-window-review-8/ui-review.json` | 현재 해시 Alt+Enter/Alt+Tab 복귀·원래 창 기하 복원·정상 종료. 물리 게임패드는 미검사 |
| 현재 소스·MIT·외부 라이선스·버전/해시·적용/원복 | lock 파일, [외부 구성 요소](../RUNTIME_THIRD_PARTY.md), 패키지 SHA manifest 및 독립 변환 검사 | 첫 버전 배포 묶음 제공. 원본 바이너리·에셋·세이브·디컴파일 출력·원시 추적 제외 |
| 배율 100/150/200% | 사용자 후속 지시 | 검증에서 제외. 설정 앱 접근·배율 조회/변경 안 함 |
| 60/120FPS·빠른 로직·64비트·편집기 교체 | 승인한 첫 버전 범위 | 제외 |

실행 결과의 해시가 다른 후보에 자동 적용되지 않도록 각 관문/통합/성능/내구성 보고서와
배포 manifest를 별도로 유지합니다. 첫 버전 검증 게임과 측정 조건의 결과이며, 임의 게임·모든 에셋·모든 하드웨어에 대한 호환 인증은 아닙니다.

MIDI 출력은 초기 WinMM 공유 장치에서 Windows DirectMusic의 독립 AudioPath로 바꿨습니다.
공유 출력으로는 원본의 개별 피치 동작을 재현할 수 없었기 때문이며, 자체 SMF 파서·작업 스레드
스케줄러는 유지했습니다. PCM은 계획대로 XAudio2입니다. 변경 근거와 실제 비교는 `RUNTIME_AUDIO.md`에 있습니다.

## 산출물 구분

- `build/RGSSXP-first-release-20261018/`, 같은 이름의 `.zip`: 인수한 첫 버전 DLL·변환 도구·라이선스·최신 요약 보고서.
- `build/RGSSXP-first-source-20261018.zip`: 첫 버전 인수 조건과 변환 manifest 설명을 반영한 전체 자체 소스.
- `build/RGSSXP-stock-candidate-20261018/`: 공개용 자체 DLL·변환 도구·라이선스·요약 보고서.
- `build/RGSSXP-stock-source-20261018.zip`: 원본 게임 코드/에셋을 제외한 자체 소스·시험 도구·문서.
- `build/RGSSXP-validation-playable-20261018/`: 실제 키 검사를 통과한 프로젝트와 게임 입력 파일이 같은
  로컬 전용 복사본. 원본 Game.exe와 사용자가 보유한 RTP 에셋이 있으므로 공개 패키지/소스 ZIP에 넣지 않습니다.

엔진 실행에는 원본 실행 파일·사용 권한이 있는 게임 데이터/에셋 또는 설정된 RTP가 필요합니다.
`System`은 Game.ini가 없는 설치 템플릿이므로, 변환 성공만으로 완성 게임 실행을 증명하지 않습니다.
검증 게임은 별도 복사본에 필요한 RTP 에셋과 자체 시험 이벤트를 구성해 실행했습니다.
원복은 보존한 원본 프로젝트를 실행하면 됩니다. 설치 템플릿에는 새 DLL을 반영하지 않았습니다.
이전 후보·소스·측정 보고서는 당시의 불변 기록으로 보존합니다. 이전 보고서의 미완료 판정을
소급해서 바꾸지 않으며 첫 버전의 최종 판정은 `build/runtime-first-release-validation.json`에 기록합니다.

## 내구성 검사 재현

아래 검사 명령은 소스 ZIP을 푼 저장소 루트에서 실행합니다. DLL 개발 패키지의 `scripts/`는
프로젝트 변환용 최소 파일이며, 전체 시험 도구·시험 소스는 별도 소스 ZIP에 들어 있습니다.

`MIGRATED_PROJECT`는 변환 도구로 만든 별도 프로젝트이고, `NEW_OUTPUT`은 존재하지 않는 새 경로입니다.
RTP와 원본 프로젝트는 사용 권한이 있는 로컬 파일을 준비합니다. 검사 중 게임 창을 활성 상태로 유지합니다.

```powershell
python -X utf8 scripts/test_runtime_stock_boot.py MIGRATED_PROJECT NEW_OUTPUT --scenario --endurance-seconds 1800 --roundtrips 100 --rtp LOCAL_RTP
```

다른 터미널에서 출력된 게임 PID를 지정하면 해당 PID·실행 파일 경로·생성 시각만 추적합니다.
마이크나 다른 프로그램의 내용을 수집하지 않습니다. 시스템 설정·레지스트리·배율을 변경하지 않습니다.

```powershell
powershell -NoProfile -File scripts/sample_runtime_gpu_memory.ps1 -TargetPid GAME_PID -GameExe NEW_OUTPUT/Game.exe -OutputRoot NEW_OUTPUT
```

게임과 기록 도구가 정상 종료한 뒤 분석합니다. 기존 분석 결과에는 덮어쓰지 않습니다.

```powershell
python -X utf8 scripts/review_runtime_endurance.py NEW_OUTPUT
python -X utf8 scripts/review_runtime_gpu_memory.py NEW_OUTPUT
```

GPU 분석은 50개 이상의 유효 표본, 마지막 활성 시간 1,770초 이상, 표본 사이 최대 65초,
600초 이후 30개 이상의 표본을 요구합니다. PID 변경·음수 계수·기록 공백을 거부하고,
미수집 값을 0으로 만들지 않습니다. 이 분석의 기울기·범위는 관찰 결과이며 모든 할당의 누수 부재 증명은 아닙니다.
