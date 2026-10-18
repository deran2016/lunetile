# RGSSXP

기존 32비트 RPG Maker XP 실행기에서 동작하는 자체 RGSS104E 대체 DLL입니다. Ruby 4.0.7, C++17, Direct3D 11을 사용하며 기본 해상도 640×480, 논리 갱신 40Hz와 기존 실행기 인터페이스를 유지합니다.

이 저장소에는 자체 엔진 소스와 빌드·변환·검증 도구만 있습니다. 기존 RGSSFramePacing 보조 DLL 구현, Game.exe 시작 패치, 이벤트 인덱스 최적화는 포함하지 않습니다. 원본 실행기·RGSS DLL·게임 데이터·에셋·세이브·역분석 출력도 배포하지 않습니다. 각자 사용 권한이 있는 원본 프로젝트를 외부 입력으로 제공해야 합니다.

## 빌드

검증 환경은 Windows 11 x64, Visual Studio 2022 C++ 도구(x86/x64 및 Windows SDK), CMake 3.24 이상, Python 3.12입니다. Ruby 소스 빌드에 Ruby 3.1 이상의 부트스트랩 실행기가 필요합니다. 이번 검증에서는 MSYS2 Ruby 3.4.10을 사용했습니다. 생성된 DLL 실행에는 Microsoft Visual C++ x86 런타임이 필요합니다.

저장소 루트에서 실행합니다.

    python -m pip install -r requirements-dev.txt
    powershell -NoProfile -File scripts/build_runtime.ps1 -BaseRuby "BOOTSTRAP_RUBY_EXE"

의존 소스는 고정 URL·SHA-256으로 확인한 뒤 무시되는 build/runtime-deps에 다운로드합니다. 기존에 받은 압축 파일도 해시가 일치할 때만 캐시로 재사용합니다. Ruby 라이브러리·설정·DLL은 이 저장소 안에서 새로 생성하며 다른 작업 폴더의 빌드 결과를 참조하지 않습니다. Ruby의 검토된 MSVC x86 atomic 패치를 적용하고 JIT는 비활성화합니다. 핀과 패치는 src/runtime의 lock/patch 파일 및 [외부 라이브러리 안내](docs/RUNTIME_THIRD_PARTY.md)에 있습니다.

출력:

- build/runtime-native/bin/Release/RGSS104E.dll — 자체 엔진
- build/runtime-native/bin/Release/rgssxp-ruby.exe — 프로젝트 변환 시 구문 검사 도구. 게임 실행에는 필요하지 않습니다.

## 프로젝트 변환과 적용

원본을 보존하고 존재하지 않는 새 출력 폴더를 지정합니다.

    python -B scripts/migrate_project.py "LOCAL_ORIGINAL_PROJECT" "NEW_PROJECT"

기본 빌드 출력을 자동으로 사용합니다. 다른 빌드는 --dll 및 --ruby로 명시할 수 있습니다. 변환기는 확인된 원본 Game.exe 해시와 기본 XP 스크립트만 허용하고, 불명확한 사용자 스크립트·이벤트 Ruby 코드는 위치를 보고하고 중단합니다. 비ASCII 프로젝트 데이터에는 --data-encoding UTF-8, CP949 또는 CP932를 명시하며, BOM 없는 비ASCII INI에는 --ini-encoding도 지정합니다. 소스·변환 결과 해시와 스크립트 ID·이름·순서·변경 내역은 출력의 migration/manifest.json에 기록합니다.

이전에 알려진 보조 DLL 연결은 src/runtime/legacy_pacing.json의 고정된 인식 메타데이터와 정확히 일치할 때만 제거합니다. 이 메타데이터는 이전 연결을 식별하기 위한 것이며 보조 DLL 구현이나 새 엔진에서의 로드를 포함하지 않습니다.

변환된 복사본의 Game.exe로 실행합니다. 원본 실행기와 게임 리소스는 사용자가 직접 제공해야 합니다. 프로젝트 루트의 기존 슬롯 파일은 복사본의 Saves/Import로 옮겨 읽기만 하고, 새 저장은 Saves/RGSSXP에 버전 표식과 함께 기록합니다. 기존 Saves 폴더가 있는 프로젝트는 형식 혼합을 피하기 위해 검토를 요구합니다. 새 저장을 원본 엔진에서 읽는 역호환은 지원하지 않습니다.

원복은 보존한 원본 프로젝트로 실행하면 됩니다. 원본에 DLL이나 변환 스크립트를 덮어쓰지 마세요. 변환 복사본의 새 저장은 별도로 보관하세요.

## 검사

    python -X utf8 -B -m unittest discover -s tests -v
    python -B scripts/inspect_runtime.py build/runtime-native/bin/Release/RGSS104E.dll
    python -B scripts/test_runtime.py "LOCAL_ORIGINAL_GAME_EXE" build/runtime-native/bin/Release/RGSS104E.dll build/launcher-smoke
    python -B scripts/verify_runtime.py "LOCAL_ORIGINAL_PROJECT" "LOCAL_ORIGINAL_DLL" "LOCAL_ORIGINAL_SAVE" build/verification

40개 Python 검사에서 시작 패치 전용 검사는 제외했습니다. 실행기·원본 비교 검사는 명시적 외부 파일만 읽으며 실행용 복사본·로그는 build 아래에 생성합니다. 검사 도구에 따라 추가 인자가 필요하므로 --help도 확인하세요. 오디오 형식 비교에는 별도 ffmpeg가 필요하고 Frida 기반 진단은 선택 사항입니다.

선택적 ETW 추출기는 tools/etw/etw_build.ps1로 빌드합니다. WPR 캡처는 별도 도구와 관리자 승인이 필요하지만 게임 자체는 일반 권한으로 실행합니다. 기본 빌드·검사는 WPR 기록이나 시스템 설정 변경을 수행하지 않습니다.

[이번 분리본의 실제 검증](docs/VALIDATION.md)을 먼저 확인하세요. 나머지 RUNTIME 문서의 기존 장시간·실제 조작·성능 결과는 당시 DLL SHA-256에 대한 기록이며 새 빌드의 재검증과 구분합니다.

## 지원 범위와 제한

첫 버전은 검증된 기본 XP 스크립트 게임 범위입니다. 실행기에서 사용하는 필수 export 5개를 구현하며, 원본 DLL 전체 66개 함수·편집기·임의 플러그인·구형 Ruby 네이티브 확장의 호환성을 주장하지 않습니다. 64비트 실행기, 60/120FPS, 고주기 로직은 포함하지 않습니다. 이번 분리 작업에서 배율 검사는 수행하지 않았습니다.

분리 전 인수 DLL(3868eeceb9fbba5ffc2509cf371e54240db726645dd64145ca4ef5b7f7fffd41)은 기본 게임 완주·저장·30분 내구성·맵 왕복 100회 및 반복 CPU/대기 측정을 통과했습니다. 원본 GDI 경로의 프레임별 GPU 비용 비교는 미확정입니다. 일부 조건에서는 CPU 실행 시간이 증가했으므로 전체적인 CPU/GPU 성능 향상을 보장하지 않습니다. 자세한 조건과 수치는 [성능 기록](docs/RUNTIME_PERFORMANCE.md)과 [원본 GPU 조사](docs/RUNTIME_ORIGINAL_GPU.md)에 있습니다.

## 라이선스와 공개 범위

자체 코드는 [MIT](LICENSE)입니다. Ruby 4.0.7, zlib 1.3.2, libogg 1.3.6, libvorbis 1.3.7은 각 라이선스를 따르며 licenses에 고지 원문을 보존합니다. Windows 시스템 API는 Windows SDK를 통해 사용합니다. 고정 소스 URL·해시·빌드 옵션은 저장소의 lock 파일과 빌드 스크립트에 기록됩니다.

build, 실행 파일, 게임 데이터, 에셋, 세이브, 원시 추적, 덤프, 압축 파일은 .gitignore로 제외합니다. GitHub 공개 전에도 추가 파일의 권리와 내용을 확인하세요. 이 분리 작업은 로컬 Git 최초 커밋까지만 수행하며 GitHub 저장소 생성·업로드·push는 하지 않습니다.
