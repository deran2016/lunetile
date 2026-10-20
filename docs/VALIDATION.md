# 독립 저장소 분리 검증

## VX Ace 편집기 저장 후 런타임 복구 검증

- 설치된 VX Ace 편집기로 검증 복사본의 rvproj2를 직접 열고 Ctrl+S를 수행했습니다. Library를 System\RGSS301.dll로 바꾸면서 해당 DLL도 원본으로 덮어쓰는 것을 확인했습니다. DLL 복사만 하는 이전 로컬 패치는 폐기했고 게시하지 않습니다.
- Main 앞의 Ruby 1.9 호환 진입 코드가 원본 런타임을 감지하면 Library를 LunetileVXA.dll로 복원하고 Game.exe를 한 번 재실행한 후 종료합니다. 원본 DLL과 게임 실행기는 변경하지 않습니다.
- 실제 편집기 저장→Game.exe 실행을 두 차례 반복했습니다. 타이틀과 새 게임 맵을 확인했고, 재실행 후 게임 프로세스가 하나이며 LunetileVXA.dll만 로드한 것을 모듈 목록으로 확인했습니다. 1280×720과 stock120 설정도 편집기 저장 후 보존됩니다. 로컬 기록: build/vxa-editor-ui-validation.json.
- 기존 alpha.9 사용자는 복구 ZIP의 스크립트를 Main 바로 위에 삽입합니다. 데이터/저장 파일이나 DLL을 덮어쓰는 패치가 아닙니다. 새 전체 템플릿은 Main에 이 코드가 포함되어 있습니다.
- Python 78개 검사 통과: 진입 코드의 누락 DLL·INI 쓰기 실패·실행 실패·test/btest 인자, 복구 ZIP 내용과 원본 보존을 포함합니다.

## 2026-10-20 VX Ace 네이티브 구현 검증

- `LunetileVXA.dll` SHA-256: `677d2f1f882fb9bc1ee325e95ff170facd64631c50f0c765625682cca818c7df`.
- 제공된 Unicode `Game.exe`로 독립 DLL 로드, 544×416/60Hz, 1280×720/120Hz 및 출력 40/60/120FPS 스케줄러, 한글 경로를 검사했습니다. 원본 RGSS301 DLL이 로드되지 않았는지 모듈 목록도 확인했습니다.
- `scripts/test_runtime_vxa.py OUTPUT --stock`: 실제 SceneManager의 타이틀→새 게임→맵→메뉴→맵, 전투 공격→승리·보상→맵, 저장 헤더·16번 슬롯·손상 저장 거부·원본 저장 가져오기·새 프로세스 복원을 검사합니다. 이동 1칸은 60Hz에서 16회, 120Hz에서 32회 갱신하며 타이머 시간도 유지됩니다.
- GPU 화면 읽기로 맵·전투의 검정 화면을 거부합니다. 이 검사에서 무인자 `Color.new`의 불투명 초기값 문제를 발견해 투명 검정으로 수정했습니다. 실제 타이틀·맵·메뉴·전투 캡처도 검토했습니다.
- `scripts/test_runtime_vxa_media.py build/vxa-media-final`: PCM/MIDI 위치·재생 시작 위치·ME 일시정지/재개·루프, 유음/무음 OGV 재생 시간·화면 색상 61종, 누락·손상·잘린 영상 거부 통과.
- `scripts/test_runtime_vxa_lifecycle.py build/vxa-lifecycle-final`: 게임과 동영상 중 F12 및 종료, 오류 후 자원 재사용 통과.
- `scripts/test_runtime_vxa_window.py build/vxa-window-final`: 기본/와이드 창의 크기 변경·최대화·복원·전체 화면·논리 해상도 유지와 실제 표시 픽셀 검사 통과. 자체 시험 창에만 Win32 메시지를 보냈으며 물리 키보드 검사는 아닙니다.
- 같은 변경의 XP 실행기 회귀(`build/xp-vxa-regression-1`)와 XP 오디오 회귀(`build/vxa-media-xp-audio-regression`)도 통과했습니다.
- 최종 `build/vxa-release-verification`에서는 스킬·상태·장비 교체·상점 구매·이름 입력·메시지/선택지 Fiber와 밀리초 기준 페이드 시간도 검사했습니다. 120Hz에서 페이드 시간을 중복 보정하던 문제를 수정했습니다.
- 최종 배포물은 `build/vxa-release-final/`에 있습니다. 게임 ZIP의 30개 파일 해시를 확인하고, 압축을 푼 원본 `Game.exe`를 수정 없이 실행해 타이틀 표시·새 DLL 로드·원본 DLL 부재·정상 종료를 확인했습니다. ZIP 해시는 같은 폴더의 `SHA256SUMS.txt`에 기록했습니다.

보고서는 로컬 `build/`에 있으며 배포 진단 ZIP에는 해당 DLL과 일치하는 검증 요약을 포함합니다.
전체 게임 완주, 원본과의 픽셀/음향 단위 일치, 장시간 성능·물리 모니터의 120Hz 출력, 임의 사용자 플러그인은 인증하지 않습니다.

## 2026-10-20 VX Ace 변환·패키지 검사

- `python -X utf8 -B -m unittest discover -s tests -q`: 75개 통과. VX Ace 변환·패키지 10개와 기존 XP 회귀 검사를 포함합니다.
- 제공된 `template-vxa`의 126개 스크립트를 왕복 처리했으며, 변경하지 않은 항목의 바이트·문자열 메타데이터·참조 번호가 보존됩니다. 이름·순서·소스 SHA-256이 다르면 변환을 거부합니다.
- 실제 Ruby 4.0.7 x86으로 기본 데이터 15개를 검사했습니다. 잘못된 Marshal 끝부분, 아카이브 범위·중복·경로·겹침과 엔진 식별 충돌에 대한 거부 검사를 통과했습니다.
- `python -X utf8 -B scripts/migrate_project.py template-vxa build/vxa-migration-check --engine vxa --widescreen --high-refresh`: 변환 성공. Main 한 항목에만 호환 코드를 추가하고 126개 구문 검사 및 데이터 검사를 통과했습니다.
- 시작 맵 17×13×4를 40×23×4로 확장하는 검사는 기존 모든 타일·이벤트와 시작 위치 `(8,6)` 및 System 파일 바이트 보존을 확인했습니다.
- 패키지 검사는 원본 RGSS DLL·개인 저장·로그의 제외, 원본 입력 불변, 검증 보고서와 DLL 해시 불일치 거부, ZIP 내부 바이트 검증을 확인했습니다.
- 이 절의 변환·정적 검사는 플레이 완료의 증거가 아닙니다. 현재 DLL의 네이티브 실행 결과는 생성된 `verification-vxa.json`을 기준으로 확인하며 과거 XP 결과와 구분합니다. 사용법과 한계는 [VXA.md](VXA.md)에 있습니다.

## 2026-10-19 통신 API 추가 검사

- 로컬 DLL SHA-256: `d4d4182ff8856a3df8447bed63da40aa139d231037aa2ec78e54d1d6f3be55c4`. 공개 CI 빌드의 해시는 각 Release 진단 ZIP의 `verification.json`을 기준으로 확인합니다.
- `python -X utf8 -B scripts/verify_ci.py build/network-final-verification`: Python 65개, Ruby 인터프리터, PE/ABI·실제 실행기·창·해상도·타이밍·저장 회귀, 통신 검사 통과.
- 로컬 fixture와 실제 Game.exe에서 1280×720/120Hz의 통신 확인 70개, 640×480/40Hz의 68개 통과. 고주기 프로필에서 40/60/120FPS 출력 중 지연 응답을 기다려도 게임 갱신을 지속했습니다.
- REST 메서드·헤더·JSON·바이너리, 4xx/5xx, 취소·제한 시간·크기 제한·gzip 확장 제한·자동 리다이렉트 미사용, TCP IPv4/IPv6·순서·분할 수신·큐 포화·서버 종료·DNS 실패, TLS 인증서 거부와 협상 실패를 검사했습니다.
- 각 실행에서 F12 처리 경로를 3회 반복하고, GC와 종료 후 남은 통신 작업이 `[0, 0]`임을 확인했습니다. 테스트 토큰은 런타임 로그에 포함되지 않았습니다.
- 로컬 인증서 저장소를 변경하지 않고 Ruby 공식 사이트에 읽기 요청을 보내 HTTPS `200`, TCP/TLS를 통한 `HTTP/1.1 200 OK`를 확인했습니다. CI에서는 일회용 테스트 CA로 TLS 성공·만료·호스트명 불일치를 추가 검증하도록 구성했습니다.
- 게임 묶음은 기존과 같은 29개 파일로 생성했습니다. 실제 실행기에서 타이틀·맵·메뉴·화면 설정·저장/불러오기·전투 시나리오를 주입된 논리 입력으로 통과했습니다. 개인 저장·테스트 인증서·키·서버 파일은 게임 ZIP에 넣지 않습니다.
- 실제 운영 서버와 장시간 연결·장시간 플레이는 검사하지 않았습니다. 아래의 분리 당시 결과와 구분하세요.

검사일: 2026-10-18. 이 문서는 새 저장소에서 실제 수행한 검사만 기록합니다.
엔진 동작·실행기 ABI·640×480·40Hz·저장 형식의 변경은 없습니다.

## 새 빌드

- DLL SHA-256: 3e44070efb5c963c000f967d5e1f1016574fbb1129a40818e7ba5e7e1932be2c
- Ruby: 4.0.7, i686-mswin32, 실제 인터프리터 출력 i386-mswin32_140, 포인터 4바이트.
- 환경: Windows 11 10.0.26300, MSVC 2022 19.44.35226 / 도구 14.44.35207, Python 3.12.10.
- Ruby 소스 및 zlib/libogg/libvorbis 압축 파일은 lock 파일의 SHA-256과 일치하는 캐시만 재사용했습니다.
- Ruby 정적 라이브러리, x86 구성 헤더, CMake 프로젝트, DLL을 새 저장소의 build 아래에서 새로 만들었습니다. 이전 폴더의 라이브러리·gate·생성 설정은 복사하지 않았습니다.
- gate의 소스·설정·정적 라이브러리 경로가 모두 새 저장소 내부임을 확인했습니다. 생성된 CMake/MSBuild 텍스트 설정에서 이전 작업 폴더 참조는 0개입니다.
- Ruby MSVC x86 atomic 경계 검사, GC·Marshal·인코딩 인터프리터 검사를 통과했습니다. JIT는 비활성화합니다.
- 빌드는 성공했으나 upstream CMake 지원 버전과 C/C++ 형 변환·미사용 인자 등의 경고는 남아 있습니다.

| 검사 | 실제 결과 |
|---|---|
| Python | 40개 통과. 기존 시작 패치 전용 검사 1개 제외 |
| PE/ABI | PE32, x86. 필수 5개 함수의 이름·ordinal 일치, forwarded export 없음 |
| DLL 의존성 | 원본 RGSS·보조 DLL·외부 Ruby DLL import 없음. Windows·VC 런타임 사용 |
| 실제 실행기 연결 | 명시적 외부 원본 Game.exe로 새 DLL 실행, 13개 경로 통과 |
| 연결 검사 내용 | normal/debug/btest, 데이터형·저장·한글 경로, 입력 오류, UTF-8/CP949/CP932, Win32API, Ruby 예외 및 exit, at_exit/finalize |
| 독립 실행 | 실행 복사본에 원본 RGSS·보조 DLL 없음. 실행 중 모듈 해시로 새 DLL 확인, 이름을 바꾼 원본 모듈도 없음 |
| 변환 | 90개 스크립트 재파싱·Ruby 4 구문 검사, 8개 변경 |
| 보존 | ID·이름·순서 일치. 비대상 82개 엔트리의 압축 바이트와 엔트리 원시 바이트 완전 일치 |
| 덮어쓰기 차단 | 동일 출력으로 다시 변환 시 실패하고 완성된 복사본의 전체 파일 해시 유지 |
| 이전 연결 해제 | 보조 구현 파일 없이 고정 메타데이터 SHA-256과 변형/거부 검사로 검증 |
| 원본 보존 | 복사한 원본 소스 입력 208개의 해시 유지, 변환에 사용한 프로젝트 입력 해시 유지 |
| 엔진 변경 없음 | runtime 소스/설정 및 CMake 40개 파일의 해시가 분리 전과 동일 |
| ETW 도구 | 새 경로의 VS2022로 독립 빌드. 인자 오류·잘못된 PID·없는 추적 파일 4개 거부 경로 확인. 새 캡처는 하지 않음 |
| 라이선스 | MIT와 외부 고지 7개 포함. 외부 고지 원문이 고정 아카이브의 파일과 동일 |

실행기는 필수 RGSS 함수 5개 이외에 정적 Ruby의 내부 심볼 5개도 노출합니다.
이 내부 심볼은 RGSS 호환 API로 지원하지 않습니다.

재현 명령은 루트 README에 있습니다. 기본 40개 검사는 외부 게임 없이 실행됩니다.
실행기·프로젝트 변환 검사는 원본 파일을 명시적 외부 인자로만 읽고 build에 실행용 복사본을 생성했습니다.
공개 소스에는 원본·변환 데이터·로그·빌드 결과를 넣지 않습니다.

로컬 상세 기록은 build/independent-unit-tests.log, build/independent-pe.json,
build/independent-separation-check.json, build/independent-smoke/summary.json,
build/independent-project/migration/manifest.json, build/independent-etw-check.json에 있습니다.
이 경로들은 Git에서 제외되므로 GitHub에는 존재하지 않습니다.

## 분리 전 검증과의 구분

`history/`의 RUNTIME_ACCEPTANCE.md, RUNTIME_STATUS.md, 성능·오디오·색상 등의 문서는 분리 전의 검증 이력을 보존합니다.
당시 인수된 DLL SHA-256은 3868eeceb9fbba5ffc2509cf371e54240db726645dd64145ca4ef5b7f7fffd41입니다.
그 해시의 23개 회귀 관문, 기본 검증 게임 자동/실제 키 완주, 30분·100왕복,
세 쌍 CPU/대기 측정은 이번 새 빌드에서 다시 수행한 결과가 아닙니다.
과거 문서의 41개 Python 검사는 분리 전 구성에 대한 수치이고 이 저장소는 시작 패치 검사를 제외한 40개입니다.

원본 GDI 경로의 프레임별 GPU 비용 비교는 미확정이며, 일부 시나리오에서 CPU 실행 시간은 증가했습니다.
GPU 개선율이나 모든 게임의 성능 향상을 주장하지 않습니다.
기존 원시 추적·화면 캡처·세이브·디컴파일 결과는 포함하지 않습니다.

이번 분리는 소스와 배포 준비 작업입니다. 새 빌드에서 장시간 내구성·실제 키 완주·성능 반복 비교를 다시 하지 않았습니다.
사용자 지시에 따라 Windows 배율 검사도 수행하지 않았습니다. 임의 플러그인·게임의 호환성 인증 범위를 확대하지 않습니다.

## 공개 준비

기존 RPGXP 작업 폴더와 Git 이력은 보존하며 새 폴더에는 독립 최초 이력만 만듭니다.
기존 보조 DLL 구현·시작 패치·이벤트 인덱스 구현은 제외했습니다.
자체 엔진·빌드/변환/검증 도구·테스트·문서·라이선스만 공개 대상으로 점검합니다.
build와 비공개 형식은 .gitignore로 제외합니다. GitHub 저장소 생성·remote 등록·업로드·push는 수행하지 않습니다.
