# Lunetile

**A modern Windows runtime for classic tile-based RPGs.**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
![Platform: Windows x86](https://img.shields.io/badge/Platform-Windows%20x86-0078D4)
![Status: Experimental](https://img.shields.io/badge/Status-Experimental-orange)

**Lunetile**(루네타일)은 고전 타일 기반 RPG를 위한 독립 런타임 프로젝트입니다. 이름은 달을 뜻하는 *lune*과 *tile*을 합쳤습니다.

[시작하기](#빌드) · [프로젝트 변환](#프로젝트-변환과-실행) · [검증 범위](#검증-기록과-한계) · [기여하기](#기여하기)

일상 검증은 `python -X utf8 -B scripts/verify_runtime.py NEW_OUTPUT`의 빠른 모드를 사용합니다. 일반 릴리스와 정밀 성능 비교, 결과 재사용 조건은 [검증 실행 안내](docs/VERIFICATION.md)를 참고하세요. 기존 네 인자 상세 검증 명령은 유지합니다.

RPG Maker XP의 기존 32비트 실행기와 RGSS 인터페이스를 대상으로 합니다. Ruby 4.0.7, C++17, Direct3D 11 기반의 `Lunetile.dll`을 빌드하며, 기존 프로젝트는 기본 해상도 640×480을 유지하며, 배포 템플릿은 **1280×720 와이드 화면**을 사용합니다. 변환된 배포판은 게임 진행 시간을 유지하는 **120Hz 로직**과 기본 **60FPS 출력**을 사용하며, 게임 내에서 40/60/120FPS를 선택할 수 있습니다. 기존 프로젝트의 기본 갱신은 40Hz를 유지합니다.

검증된 기본 XP 스크립트 게임을 대상으로 합니다. 모든 RPG Maker XP 게임이나 사용자 플러그인과의 호환성을 보장하지 않으며, 적용할 때는 제공된 변환기로 **원본과 분리된 프로젝트 복사본**을 만듭니다.

**VX Ace:** 제공된 `template-vxa/`의 126개 기본 스크립트를 위한 별도 **`LunetileVXA.dll`**도 빌드합니다. 일반 변환은 544×416·60Hz를 유지하고, 배포 템플릿은 1280×720·120Hz 로직과 40/60/120FPS 출력을 사용합니다. VX Ace의 데이터·저장·ABI는 XP와 분리합니다. 변환과 배포 명령, 검증 범위는 [VX Ace 안내](docs/VXA.md)를 참고하세요.

XP·VX Ace 공용 표시 객체 순회와 GDI 문자 마스크 캐시·부분 업로드의 구현, 비교 명령과 성능 판정 기준은 [클라이언트 성능 검증](docs/CLIENT_PERFORMANCE.md)에 있습니다.

XP 타일 표시 범위 캐시와 VXA 타일 해석 경량화의 구현·비교 절차: [타일 성능 검증](docs/TILE_CLIENT_PERFORMANCE.md).

후속 XP 타일 제출 배치와 XP·VXA 문자 합성 경량화: [구현·검증](docs/SUBMIT_TEXT_PERFORMANCE.md).

배포 템플릿에만 적용하는 캐릭터 표시·이동, 이벤트 좌표 조회, VXA 저장 미리보기 최적화: [구현·실측·검증](docs/STOCK_SCRIPT_PERFORMANCE.md). 일반 프로젝트 변환과 기존 게임/MMO 스크립트에는 적용하지 않습니다.

게임 화면 안에 웹 URL·로컬 HTML을 표시하는 XP·VXA 공통 WebView2 패널: [브라우저 API·설치·사용법](docs/BROWSER.md). 스크립트에서 요청할 때만 생성하며 WebView2 Evergreen Runtime이 필요합니다.

최신 브라우저 DLL·오프라인 예제·진단 ZIP 안내는 [v0.1.0-alpha.15 릴리스 설명](docs/releases/v0.1.0-alpha.15.md)에 있습니다. 기존 전체 템플릿·DLL 교체 ZIP은 [v0.1.0-alpha.14](docs/releases/v0.1.0-alpha.14.md)에 보존합니다.

> **개발 단계:** 검토된 기본 스크립트 범위의 실험적 런타임입니다. 원본 게임의 백업을 보관하고 별도 복사본에서 사용하세요.

Lunetile은 RPG Maker의 공식 제품이 아니며 해당 제품의 개발사·권리자와 제휴하거나 승인을 받은 프로젝트가 아닙니다. 제품명은 호환 대상을 설명하기 위해 사용합니다. 자체 엔진 파일명은 **`Lunetile.dll`**이며 변환본의 `Game.ini`에서 `Library=Lunetile.dll`로 선택합니다. RGSS 함수 이름, 기존 코드명 `RGSSXP`, `rgssxp-ruby.exe`, `Saves/RGSSXP`는 인터페이스·도구·저장 형식의 호환성을 위해 유지합니다.

## 주요 기능

- 기존 `Game.exe`가 사용하는 필수 RGSS 함수 5개와 Ruby 스크립트 실행
- RGSS 값 형식, RPG 데이터 클래스, Marshal 데이터 및 RGSSAD v1 읽기
- Bitmap, Sprite, Window, Tilemap, 글꼴, 화면 전환 및 Direct3D 11 렌더링
- 1280×720 와이드 맵·기본 UI, 창 크기 조절·최대화·Alt+Enter 전체 화면
- 120Hz 로직과 독립된 40/60/120FPS 출력, 게임 내 화면 설정과 개인 설정 저장
- 키보드·XInput 입력, WAV/Ogg/MP3/WMA/MIDI 오디오
- UTF-8·CP949·CP932 프로젝트 데이터 처리와 기존 세이브 가져오기
- 원본 보존을 전제로 한 프로젝트 변환, ABI 검사 및 회귀 검증 도구

저장소의 `template-xp/`에는 배포용으로 제공된 기본 게임 프로젝트가 있습니다. 원본 RGSS DLL과 개인 세이브는 포함하지 않습니다. 다른 게임을 변환하려면 사용 권한이 있는 원본 프로젝트를 별도로 준비해야 합니다. 기존 RGSSFramePacing 보조 DLL 구현과 실행기 시작 패치는 포함하지 않습니다.

## 준비 사항

검증 환경은 Windows 11 x64입니다. 결과물은 **Win32(x86)** DLL이며, 64비트 실행기용이 아닙니다.

| 도구 | 용도 |
|---|---|
| Visual Studio 2022 C++ 빌드 도구 | x86/x64 C++ 구성 요소와 Windows SDK 필요 |
| CMake 3.24 이상 | 네이티브 런타임 구성·빌드 |
| Python 3.12 | 빌드 보조, 프로젝트 변환 및 검사 |
| Ruby 3.1 이상 | Ruby 소스 빌드용 부트스트랩 실행기. 검증에는 MSYS2 Ruby 3.4.10 사용 |
| PowerShell, `tar.exe` | 빌드 스크립트 실행과 소스 압축 해제. 통신 검사의 테스트 인증서 생성에는 PowerShell 7 (`pwsh`) 필요 |
| Microsoft Visual C++ x86 런타임 | 생성된 DLL 실행 |

`python`, `cmake.exe`, `tar.exe`를 PATH에서 실행할 수 있어야 합니다. 최초 빌드에는 고정된 의존 소스를 다운로드할 네트워크 연결이 필요합니다. 부트스트랩 Ruby는 빌드 도구로만 사용하며 게임 실행에 별도로 필요하지 않습니다.

## 게임 프로젝트 다운로드와 자동 릴리스

| 엔진 | 원본 템플릿 | 실행용 ZIP | 진단 ZIP |
| --- | --- | --- | --- |
| XP | `template-xp/` | `lunetile-template-xp-windows-x86.zip` | `lunetile-template-xp-diagnostics.zip` |
| VX Ace | `template-vxa/` | `lunetile-template-vxa-windows-x86.zip` | `lunetile-template-vxa-diagnostics.zip` |

**VX Ace 렌더링 최적화:** [v0.1.0-alpha.13](https://github.com/deran2016/lunetile/releases/tag/v0.1.0-alpha.13)에 로컬 검증을 통과한 DLL 교체 ZIP·전체 VXA 템플릿·진단 ZIP을 제공합니다. 기존 변환본은 백업 후 `lunetile-vxa-speed-fix.zip`의 `LunetileVXA.dll`만 `Game.exe` 옆에 교체하세요. 표시 범위 캐시와 D3D 인스턴싱을 적용했으며, 기본 맵의 타일 Draw는 3,936회에서 1회로 줄었습니다. 비교 기준·실측값·한계는 [검증 기록](docs/VALIDATION.md)과 [릴리스 설명](docs/releases/v0.1.0-alpha.13.md)에 있습니다.

**게임 내부 브라우저:** [v0.1.0-alpha.15](https://github.com/deran2016/lunetile/releases/tag/v0.1.0-alpha.15)의 `lunetile-browser-xp-demo.zip` 또는 `lunetile-browser-vxa-demo.zip`을 풀고 `Game.exe`를 실행하세요. 자체 HTML을 사용하므로 인터넷과 RTP가 필요하지 않습니다. Microsoft Visual C++ x86 및 WebView2 Evergreen Runtime은 필요합니다. 기존 변환본에는 해당 엔진 DLL만 교체하고 [Ruby API](docs/BROWSER.md)를 호출합니다. 기본 게임 템플릿을 받을 때는 아래 파일이 있는 [alpha.14](https://github.com/deran2016/lunetile/releases/tag/v0.1.0-alpha.14)를 선택하세요.

[GitHub Releases](https://github.com/deran2016/lunetile/releases)에서 `lunetile-template-xp-windows-x86.zip`과 `SHA256SUMS.txt`를 받습니다. ZIP을 풀고 **`Game.exe`를 실행**하세요. 이미 변환된 `Data`, `Game.ini`, 프로젝트 파일과 새 Lunetile DLL이 들어 있으므로 Python 설치나 수동 변환이 필요하지 않습니다.

**필수 설치:** Windows 11 x64, Microsoft Visual C++ x86 런타임, **RPG Maker XP Standard RTP**. 제공된 템플릿의 Graphics·Audio 폴더는 비어 있으며 `RTP1=Standard`를 사용합니다. RTP는 ZIP에 포함하지 않습니다. 영문 Windows에서는 영문 경로에 압축을 푸세요. 기존 실행기는 시스템 ANSI 코드페이지로 표현할 수 없는 경로를 읽지 못합니다.

- 원본 `template-xp/`는 보존하고 별도 복사본만 변환합니다.
- 개인 세이브·로그·원본 RGSS DLL은 배포하지 않습니다. 새 저장은 `Saves/RGSSXP/`에 생성됩니다.
- 게임 ZIP에는 프로젝트 파일·새 DLL·짧은 실행 안내·라이선스 고지만 포함합니다. 시작 맵은 원본의 지형과 시작 위치를 유지하며 **40×23칸(1280×736픽셀)**으로 확장됩니다.
- 검증 결과·DLL 정보·변환 및 맵 확장 기록·파일별 해시·의존성 정보와 Ruby 패치는 별도 **`lunetile-template-xp-diagnostics.zip`**에 있습니다. 게임 실행에는 필요하지 않습니다. 개발 문서와 과거 기록은 이 저장소에서 제공합니다.
- `SHA256SUMS.txt`에는 XP·VX Ace 실행/진단 ZIP 및 VX Ace 편집기 복구 ZIP의 해시가 있습니다. 템플릿 파일에 엔진의 MIT 라이선스가 새로 적용되는 것은 아닙니다.
- `Get-FileHash lunetile-template-xp-windows-x86.zip -Algorithm SHA256`으로 다운로드 해시를 비교할 수 있습니다.

[Windows build and release](https://github.com/deran2016/lunetile/actions/workflows/release.yml)는 `main` 푸시 또는 수동 실행 시 빌드·검사·템플릿 변환 후 ZIP을 아티팩트로 보관합니다. **새 `v*` 태그 푸시 시 같은 결과를 GitHub 사전 릴리스로 자동 게시**합니다.

```powershell
git tag v0.1.0-alpha.9
git push origin v0.1.0-alpha.9
```

이미 게시된 태그를 덮어쓰지 않습니다. 수동 실행은 릴리스를 게시하지 않습니다. 별도 PAT 없이 게시 작업에서만 자동 `GITHUB_TOKEN`의 `contents: write` 권한을 사용합니다.

CI는 Python 검사, Ruby x86 검사, DLL ABI, 실행기 연결·640×480/1280×720 렌더링·창 동작 검사, FHD/QHD/4K 배율 계산과 템플릿 변환·맵 데이터 확장·배포 파일 분리를 확인합니다. 전체 게임 완주·렌더링·오디오 인수 검증은 포함하지 않으며 해당 빌드의 범위는 진단 ZIP의 `verification.json`에 기록됩니다.

## 빌드

저장소 루트에서 실행합니다. `BOOTSTRAP_RUBY_EXE`는 설치한 Ruby 실행 파일의 실제 경로로 바꿉니다.

```powershell
python -m pip install -r requirements-dev.txt
powershell -NoProfile -File scripts/build_runtime.ps1 -BaseRuby "BOOTSTRAP_RUBY_EXE"
```

빌드 스크립트는 Ruby·zlib·libogg·libvorbis 소스 압축 파일을 고정 URL에서 받고 SHA-256을 확인합니다. 캐시도 해시가 일치할 때만 재사용합니다. Ruby에는 검토된 MSVC x86 atomic 패치를 적용하고 JIT를 비활성화합니다.

| 출력 | 용도 |
|---|---|
| `build/runtime-native/bin/Release/Lunetile.dll` | 게임 실행용 자체 엔진 |
| `build/runtime-native/bin/Release/rgssxp-ruby.exe` | 변환 시 Ruby 구문 검사. 게임 실행에는 불필요 |
| `build/runtime-deps/` | 의존 소스와 다운로드 캐시 |
| `build/runtime-ruby-x86/` | Ruby 빌드 결과와 검사 기록 |

버전·해시는 `src/runtime/ruby.lock.json`, `src/runtime/dependencies.lock.json`에 고정되어 있습니다. 자세한 구성은 [외부 라이브러리 안내](docs/RUNTIME_THIRD_PARTY.md)를 참고하세요.

## 프로젝트 변환과 실행

### 1. 원본을 보존하고 새 복사본 만들기

`LOCAL_ORIGINAL_PROJECT`는 원본 프로젝트 폴더, `NEW_PROJECT`는 **아직 존재하지 않는 출력 폴더**로 바꿉니다. 원본에 DLL이나 스크립트를 직접 덮어쓰지 마세요.

```powershell
python -B scripts/migrate_project.py "LOCAL_ORIGINAL_PROJECT" "NEW_PROJECT"
```

엔진은 기본적으로 자동 판별하며 `--engine xp` 또는 `--engine vxa`로 명시할 수 있습니다. 프로젝트 파일·INI·검토된 실행기의 식별이 충돌하면 중단합니다. VX Ace에서는 기본 DLL 경로가 `LunetileVXA.dll`로 선택됩니다.

기본 빌드 결과를 자동으로 사용합니다. 다른 결과물을 쓰려면 `--dll`과 `--ruby`로 경로를 지정합니다.

비ASCII 프로젝트 데이터에는 실제 원본 인코딩을 `--data-encoding`으로 명시합니다. BOM 없는 `Game.ini`에도 비ASCII 문자가 있으면 `--ini-encoding`을 지정합니다. 두 옵션은 각각 `UTF-8`, `CP949`, `CP932`를 지원합니다. 다음은 데이터와 INI가 모두 CP949인 경우입니다.

```powershell
python -B scripts/migrate_project.py "LOCAL_ORIGINAL_PROJECT" "NEW_PROJECT" --data-encoding CP949 --ini-encoding CP949
```

변환기는 확인된 원본 `Game.exe` 해시와 기본 XP 스크립트만 허용합니다. 검토되지 않은 사용자 스크립트나 이벤트 Ruby 코드가 있으면 위치를 보고하고 중단합니다. 스크립트 ID·이름·순서, 변경 내용과 파일 해시는 출력의 `migration/manifest.json`에 기록합니다.

이전에 알려진 보조 DLL 연결은 `src/runtime/legacy_pacing.json`의 고정 인식 정보와 정확히 일치할 때만 제거합니다. 이 파일은 이전 연결 식별용이며 보조 DLL 구현은 포함하지 않습니다.

### 2. 변환한 프로젝트 실행하기

출력 폴더의 `Game.exe`를 실행합니다. 원본 실행기와 게임 리소스는 변환 복사본에서 사용합니다.

세이브는 다음과 같이 분리됩니다.

| 경로 | 역할 |
|---|---|
| 원본 프로젝트의 슬롯 파일 | 원본 그대로 보존 |
| 변환 복사본의 `Saves/Import/` | 원본 슬롯 파일을 가져와 읽기만 수행 |
| 변환 복사본의 `Saves/RGSSXP/` | 버전 표식이 있는 새 형식으로 저장 |

원본에 이미 `Saves/` 폴더가 있으면 형식 혼합을 막기 위해 변환을 중단합니다. 새 저장을 원본 엔진에서 읽는 역호환은 지원하지 않습니다. 원복하려면 보존한 원본 프로젝트를 실행하고, 변환 복사본의 새 저장은 별도로 보관하세요.

## 와이드 화면

Release ZIP은 1280×720 맵·메뉴·메시지·전투 배치를 적용한 template입니다. 작은 맵은 중앙에 표시하고, 타이틀·전투 배경은 비율을 유지해 채웁니다. 글자·캐릭터의 기본 픽셀 크기는 유지합니다.

다른 기본 프로젝트를 변환하려면 `migrate_project.py`에 `--widescreen`을 추가하세요. 생략하면 기존 배치를 유지합니다. `Game.ini`의 `[Lunetile] Width=1280`, `Height=720`이 내부 화면 크기를 지정합니다. 창 크기 조절과 전체 화면은 화면 비율을 유지하며, 남는 출력 공간은 검게 표시합니다.

스크립트에서는 `Graphics.width`, `Graphics.height`, `Graphics.resize_screen(width, height)`를 사용할 수 있습니다. 크기 변경 후 기존 UI는 자동 재배치되지 않으므로 장면 사이에서 변경하고 화면 객체를 다시 생성하세요. 사용자 정의 UI 플러그인은 별도 수정이 필요합니다. 설정·API·검증 범위는 [와이드 화면 안내](docs/WIDESCREEN.md)를 참고하세요.

## 60/120FPS 화면 출력

배포판에서는 메뉴 끝의 **화면 설정**에서 40/60/120FPS를 선택할 수 있습니다. 기본은 60FPS이며 게임 로직은 120Hz로 유지합니다. 이동·점프·이벤트 대기·타이머·전투 효과의 실제 진행 시간은 기존 40Hz 기준에 맞춥니다. 설정은 `Saves/Lunetile/display.ini`에 저장되어 재실행 후에도 적용됩니다.

다른 기본 프로젝트에는 변환 옵션 `--high-refresh`를 사용하세요. 와이드 화면과 함께 적용하려면 `--widescreen --high-refresh`를 지정합니다. 옵션이 없는 프로젝트는 기존 타이밍을 유지합니다. 고주기 저장은 버전 2이며 기존 버전 1·원본 가져오기 저장을 읽을 수 있지만, 새 저장을 이전 런타임에서 읽을 수는 없습니다.

`Graphics.logic_rate`는 120, `Graphics.frame_count`는 120Hz 갱신 횟수입니다. `Graphics.render_rate = 120`으로 출력만 변경할 수 있습니다. 고주기 프로필의 `Graphics.frame_rate`는 120으로 고정됩니다. [고주기 화면 안내](docs/HIGH_REFRESH.md)에 API·변환·저장·검증 범위가 정리되어 있습니다. 실제 출력 FPS는 모니터 주사율과 처리 성능에 따라 달라집니다.

## 검사

### 외부 게임 없이 실행하는 검사

Python 개발 의존성을 설치한 뒤 실행합니다.

```powershell
python -X utf8 -B -m unittest discover -s tests -v
```

빌드된 DLL의 PE 형식, x86 대상, 필수 export와 의존성을 확인합니다.

```powershell
python -B scripts/inspect_runtime.py build/runtime-native/bin/Release/Lunetile.dll
```

### 원본 파일이 필요한 검사

아래 자리표시자를 실제 파일·폴더 경로로 바꿉니다. 출력에는 기존 결과와 겹치지 않는 새 폴더를 사용하세요.

```powershell
python -B scripts/test_runtime.py "LOCAL_ORIGINAL_GAME_EXE" build/runtime-native/bin/Release/Lunetile.dll build/launcher-smoke
python -B scripts/verify_runtime.py "LOCAL_ORIGINAL_PROJECT" "LOCAL_ORIGINAL_DLL" "LOCAL_ORIGINAL_SAVE" build/verification
```

실행기·원본 비교 검사는 명시적으로 제공한 외부 파일을 읽고, 실행용 복사본과 로그를 `build/` 아래에 만듭니다. 통합 검사 통과가 임의 게임의 완주나 호환성을 인증하지는 않습니다. 세부 도구의 인자는 `--help`로 확인할 수 있습니다.

오디오 형식 비교에는 별도 `ffmpeg`가 필요합니다. Frida 진단과 ETW 추적은 선택 사항입니다. ETW 추출기는 `tools/etw/etw_build.ps1`로 빌드하며, WPR 캡처에는 별도 도구와 관리자 승인이 필요합니다. 기본 빌드·검사는 WPR 캡처나 시스템 설정 변경을 수행하지 않습니다.

### 검증 기록과 한계

[2026-10-18 독립 저장소 검증 기록](docs/VALIDATION.md)에는 새 빌드의 Python 검사 40개, PE/ABI 검사, 실제 실행기 연결 13개 경로, 프로젝트 변환과 원본 보존 검사가 기록되어 있습니다.

분리 전 DLL의 기본 검증 게임 완주, 30분 내구성, 맵 왕복 100회 및 성능 측정은 별도 이력입니다. 해당 결과를 새 빌드에서 모두 재수행한 것은 아닙니다. 각 문서의 DLL SHA-256과 검증 범위를 확인하세요.

- 원본 DLL의 전체 66개 함수, 편집기, 임의 플러그인 및 구형 Ruby 네이티브 확장의 호환성은 보장하지 않습니다.
- 64비트 실행기와 사용자 정의 스크립트·플러그인의 고주기 시간 변환은 지원 범위에 포함하지 않습니다.
- RGSSAD v2/v3는 지원하지 않습니다.
- 물리 게임패드와 실제 고배율·여러 모니터 간 DPI 변경은 검증하지 않았습니다. 현재 모니터의 창 동작과 합성 DPI 메시지는 검사합니다.
- 원본 GDI 경로의 프레임별 GPU 비용 비교는 미확정입니다. 일부 조건에서는 CPU 실행 시간이 증가했으므로 전반적인 성능 향상을 보장하지 않습니다.

## REST·TCP 통신

게임 스크립트에서 비동기 REST/JSON과 TCP/TLS 클라이언트를 사용할 수 있습니다. 서버 주소를 지정해 API를 호출하기 전에는 접속하지 않습니다. TCP는 TLS가 기본이며 별도 Ruby·OpenSSL 설치는 필요하지 않습니다.

```ruby
@request = Lunetile::HTTP.request(:post, "https://game.example.com/api/status", json: {"player" => 1})
# 이후 장면 update에서 @request.done? 확인 후 @request.response 또는 @request.error 사용
@connection = Lunetile::TCP.connect("game.example.com", 4433) # 비동기 TCP/TLS 연결
```

요청 취소, HTTP 상태·헤더·본문, TCP 바이트 송수신과 길이 접두사 JSON 예제는 [통신 API 문서](docs/NETWORKING.md)를 참고하세요. 요청·연결 객체는 저장 파일에 넣지 않습니다. 변환된 XP 프로젝트에 연결하는 **Windows Rust 서버·파일 DB·온라인 클라이언트 예제**는 [example 안내](example/README.md)와 [MMORPG 기초 설계](example/DESIGN.md)를 참고하세요. 반투명 MMORPG GUI·한글 채팅·레벨 1~30·4계열 전직·퀘스트·장비·강화·상점·창고·거래·파티·길드를 제공하며 월드와 성장 정의를 JSON으로 관리합니다. 별도 DB 설치 없이 실행합니다. 마우스·IME API는 [UIInput 문서](docs/UI_INPUT.md)에 있습니다.

## 문제 해결

| 증상 | 확인할 내용 |
|---|---|
| `BaseRuby` 관련 오류 | Ruby 3.1 이상 실행 파일의 실제 경로와 실행 가능 여부 |
| MSVC 또는 CMake 구성 실패 | VS2022 x86/x64 C++ 도구, Windows SDK, CMake 설치 여부 |
| 소스 SHA-256 불일치 | 다운로드·캐시 상태를 확인하고 lock 파일의 검증을 우회하지 않기 |
| `Output already exists` | 기존 결과를 보존하고 다른 새 출력 폴더 지정 |
| 실행기·스크립트 변환 거부 | 검증 대상 해시·기본 스크립트인지 확인. 사용자 코드는 별도 검토 필요 |
| 비ASCII 텍스트 변환 거부 | 원본 데이터와 INI의 실제 인코딩을 각각 지정 |
| 기존 `Saves/` 폴더로 변환 거부 | 저장 형식을 먼저 확인. 폴더를 무작정 삭제하지 않기 |

## 저장소 구조와 문서

```text
template-xp/      배포용 원본 게임 프로젝트 (변환 전)
template-vxa/  배포용 VX Ace 원본 프로젝트 (변환 전)
src/runtime/   C++·Ruby 엔진, ABI 정의, 의존성 lock 및 패치
scripts/       빌드·변환·검사·성능 측정 도구
tests/         Python 테스트, Ruby 검증 시나리오, 네이티브 측정 도구
tools/etw/     ETW 추출기
docs/          현재 검증 결과와 외부 라이브러리 안내
docs/history/  분리 전 구현·인수·항목별 검증 기록
licenses/      외부 라이브러리 라이선스 고지
```

| 문서 | 내용 |
|---|---|
| [독립 저장소 검증](docs/VALIDATION.md) | 새 빌드의 실제 검사 결과와 미검증 범위 |
| [구현 상태](docs/history/RUNTIME_STATUS.md) · [인수 기록](docs/history/RUNTIME_ACCEPTANCE.md) | 분리 전 기능별 구현·검증 이력 |
| [성능](docs/history/RUNTIME_PERFORMANCE.md) · [원본 GPU 조사](docs/history/RUNTIME_ORIGINAL_GPU.md) | 측정 조건, 수치와 비교 한계 |
| [오디오](docs/history/RUNTIME_AUDIO.md) · [색상](docs/history/RUNTIME_COLOR.md) | 출력 검증 기록 |
| [텍스트](docs/history/RUNTIME_TEXT.md) · [파일 입출력](docs/history/RUNTIME_FILE_IO.md) | 인코딩과 파일 처리 |
| [리셋](docs/history/RUNTIME_RESET.md) · [처리 순서](docs/history/RUNTIME_ORDER.md) | F12 및 정수 ID 테이블 호환 처리 |
| [외부 구성 요소](docs/RUNTIME_THIRD_PARTY.md) | 고정 의존성, 라이선스와 배포 범위 |
| [REST·TCP 통신](docs/NETWORKING.md) | 비동기 HTTP/JSON·TCP/TLS API와 서버 프로토콜 예제 |

## 기여하기

기여 절차와 코드 규칙은 [AGENTS.md](AGENTS.md)를 확인하세요. 버그 제보에는 실행 환경, 재현 순서, 사용한 DLL의 SHA-256과 오류 내용을 포함해 주세요. 렌더링 문제에는 권리상 공유 가능한 화면을 첨부하면 도움이 됩니다.

PR에는 변경 이유, 영향 범위와 수행한 검사를 적어 주세요. 승인된 `template-xp/` 입력 외의 게임 원본·에셋·세이브·비밀 키는 첨부하거나 커밋하지 마세요. 호환성 변경에는 해당 동작을 검증하는 회귀 검사를 포함합니다.

## 라이선스

자체 코드는 [MIT 라이선스](LICENSE)입니다. Ruby 4.0.7과 내장 JSON 2.18.0, zlib 1.3.2, libogg 1.3.6, libvorbis 1.3.7은 각각의 라이선스를 따르며, 고지 원문은 `licenses/`에 있습니다. Windows API는 Windows SDK를 통해 사용합니다.

승인된 `template-xp/` 입력을 제외한 빌드 결과, 실행 파일, 게임 데이터·에셋·세이브, 원시 추적과 덤프는 `.gitignore`로 제외합니다. 게임 실행기와 리소스의 사용·배포 권한은 별도로 확인해야 합니다.
