# Lunetile

**A modern Windows runtime for classic tile-based RPGs.**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
![Platform: Windows x86](https://img.shields.io/badge/Platform-Windows%20x86-0078D4)
![Status: Experimental](https://img.shields.io/badge/Status-Experimental-orange)

**Lunetile**(루네타일)은 고전 타일 기반 RPG를 위한 독립 런타임 프로젝트입니다. 이름은 달을 뜻하는 *lune*과 *tile*을 합쳤습니다.

[시작하기](#빌드) · [프로젝트 변환](#프로젝트-변환과-실행) · [검증 범위](#검증-기록과-한계) · [기여하기](#기여하기)

RPG Maker XP의 기존 32비트 실행기와 RGSS 인터페이스를 대상으로 합니다. Ruby 4.0.7, C++17, Direct3D 11 기반의 `RGSS104E.dll`을 빌드하며, 기본 해상도 640×480과 논리 갱신 40Hz를 유지합니다.

검증된 기본 XP 스크립트 게임을 대상으로 합니다. 모든 RPG Maker XP 게임이나 사용자 플러그인과의 호환성을 보장하지 않으며, 적용할 때는 제공된 변환기로 **원본과 분리된 프로젝트 복사본**을 만듭니다.

> **개발 단계:** 검토된 기본 스크립트 범위의 실험적 런타임입니다. 원본 게임의 백업을 보관하고 별도 복사본에서 사용하세요.

Lunetile은 RPG Maker의 공식 제품이 아니며 해당 제품의 개발사·권리자와 제휴하거나 승인을 받은 프로젝트가 아닙니다. 제품명은 호환 대상을 설명하기 위해 사용합니다. 기존 코드명 `RGSSXP`, `rgssxp-ruby.exe`, `Saves/RGSSXP`와 실행기가 요구하는 `RGSS104E.dll` 이름은 인터페이스·도구·저장 형식의 호환성을 위해 유지합니다.

## 주요 기능

- 기존 `Game.exe`가 사용하는 필수 RGSS 함수 5개와 Ruby 스크립트 실행
- RGSS 값 형식, RPG 데이터 클래스, Marshal 데이터 및 RGSSAD v1 읽기
- Bitmap, Sprite, Window, Tilemap, 글꼴, 화면 전환 및 Direct3D 11 렌더링
- 키보드·XInput 입력, WAV/Ogg/MP3/WMA/MIDI 오디오
- UTF-8·CP949·CP932 프로젝트 데이터 처리와 기존 세이브 가져오기
- 원본 보존을 전제로 한 프로젝트 변환, ABI 검사 및 회귀 검증 도구

저장소의 `template/`에는 배포용으로 제공된 기본 게임 프로젝트가 있습니다. 원본 RGSS DLL과 개인 세이브는 포함하지 않습니다. 다른 게임을 변환하려면 사용 권한이 있는 원본 프로젝트를 별도로 준비해야 합니다. 기존 RGSSFramePacing 보조 DLL 구현, 실행기 시작 패치, 이벤트 인덱스 최적화도 포함하지 않습니다.

## 준비 사항

검증 환경은 Windows 11 x64입니다. 결과물은 **Win32(x86)** DLL이며, 64비트 실행기용이 아닙니다.

| 도구 | 용도 |
|---|---|
| Visual Studio 2022 C++ 빌드 도구 | x86/x64 C++ 구성 요소와 Windows SDK 필요 |
| CMake 3.24 이상 | 네이티브 런타임 구성·빌드 |
| Python 3.12 | 빌드 보조, 프로젝트 변환 및 검사 |
| Ruby 3.1 이상 | Ruby 소스 빌드용 부트스트랩 실행기. 검증에는 MSYS2 Ruby 3.4.10 사용 |
| PowerShell, `tar.exe` | 빌드 스크립트 실행과 소스 압축 해제 |
| Microsoft Visual C++ x86 런타임 | 생성된 DLL 실행 |

`python`, `cmake.exe`, `tar.exe`를 PATH에서 실행할 수 있어야 합니다. 최초 빌드에는 고정된 의존 소스를 다운로드할 네트워크 연결이 필요합니다. 부트스트랩 Ruby는 빌드 도구로만 사용하며 게임 실행에 별도로 필요하지 않습니다.

## 게임 프로젝트 다운로드와 자동 릴리스

[GitHub Releases](https://github.com/deran2016/lunetile/releases)에서 `lunetile-template-windows-x86.zip`과 `SHA256SUMS.txt`를 받습니다. ZIP을 풀고 **`Game.exe`를 실행**하세요. 이미 변환된 `Data`, `Game.ini`, 프로젝트 파일과 새 Lunetile DLL이 들어 있으므로 Python 설치나 수동 변환이 필요하지 않습니다.

**필수 설치:** Windows 11 x64, Microsoft Visual C++ x86 런타임, **RPG Maker XP Standard RTP**. 제공된 템플릿의 Graphics·Audio 폴더는 비어 있으며 `RTP1=Standard`를 사용합니다. RTP는 ZIP에 포함하지 않습니다.

- 원본 `template/`는 보존하고 별도 복사본만 변환합니다.
- 개인 세이브·로그·원본 RGSS DLL은 배포하지 않습니다. 새 저장은 `Saves/RGSSXP/`에 생성됩니다.
- 라이선스·검사 결과·변환 내역·파일별 해시를 포함합니다. 템플릿 파일에 엔진의 MIT 라이선스가 새로 적용되는 것은 아닙니다.
- `Get-FileHash lunetile-template-windows-x86.zip -Algorithm SHA256`으로 다운로드 해시를 비교할 수 있습니다.

[Windows build and release](https://github.com/deran2016/lunetile/actions/workflows/release.yml)는 `main` 푸시 또는 수동 실행 시 빌드·검사·템플릿 변환 후 ZIP을 아티팩트로 보관합니다. **새 `v*` 태그 푸시 시 같은 결과를 GitHub 사전 릴리스로 자동 게시**합니다.

```powershell
git tag v0.1.0-alpha.3
git push origin v0.1.0-alpha.3
```

이미 게시된 태그를 덮어쓰지 않습니다. 수동 실행은 릴리스를 게시하지 않습니다. 별도 PAT 없이 게시 작업에서만 자동 `GITHUB_TOKEN`의 `contents: write` 권한을 사용합니다.

CI는 Python 검사, Ruby x86 검사, DLL ABI, 제공된 실행기의 연결 검사와 템플릿 변환을 확인합니다. 전체 게임 완주·렌더링·오디오 인수 검증은 포함하지 않으며 해당 빌드의 범위는 `verification.json`에 기록됩니다.

## 빌드

저장소 루트에서 실행합니다. `BOOTSTRAP_RUBY_EXE`는 설치한 Ruby 실행 파일의 실제 경로로 바꿉니다.

```powershell
python -m pip install -r requirements-dev.txt
powershell -NoProfile -File scripts/build_runtime.ps1 -BaseRuby "BOOTSTRAP_RUBY_EXE"
```

빌드 스크립트는 Ruby·zlib·libogg·libvorbis 소스 압축 파일을 고정 URL에서 받고 SHA-256을 확인합니다. 캐시도 해시가 일치할 때만 재사용합니다. Ruby에는 검토된 MSVC x86 atomic 패치를 적용하고 JIT를 비활성화합니다.

| 출력 | 용도 |
|---|---|
| `build/runtime-native/bin/Release/RGSS104E.dll` | 게임 실행용 자체 엔진 |
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

## 검사

### 외부 게임 없이 실행하는 검사

Python 개발 의존성을 설치한 뒤 실행합니다.

```powershell
python -X utf8 -B -m unittest discover -s tests -v
```

빌드된 DLL의 PE 형식, x86 대상, 필수 export와 의존성을 확인합니다.

```powershell
python -B scripts/inspect_runtime.py build/runtime-native/bin/Release/RGSS104E.dll
```

### 원본 파일이 필요한 검사

아래 자리표시자를 실제 파일·폴더 경로로 바꿉니다. 출력에는 기존 결과와 겹치지 않는 새 폴더를 사용하세요.

```powershell
python -B scripts/test_runtime.py "LOCAL_ORIGINAL_GAME_EXE" build/runtime-native/bin/Release/RGSS104E.dll build/launcher-smoke
python -B scripts/verify_runtime.py "LOCAL_ORIGINAL_PROJECT" "LOCAL_ORIGINAL_DLL" "LOCAL_ORIGINAL_SAVE" build/verification
```

실행기·원본 비교 검사는 명시적으로 제공한 외부 파일을 읽고, 실행용 복사본과 로그를 `build/` 아래에 만듭니다. 통합 검사 통과가 임의 게임의 완주나 호환성을 인증하지는 않습니다. 세부 도구의 인자는 `--help`로 확인할 수 있습니다.

오디오 형식 비교에는 별도 `ffmpeg`가 필요합니다. Frida 진단과 ETW 추적은 선택 사항입니다. ETW 추출기는 `tools/etw/etw_build.ps1`로 빌드하며, WPR 캡처에는 별도 도구와 관리자 승인이 필요합니다. 기본 빌드·검사는 WPR 캡처나 시스템 설정 변경을 수행하지 않습니다.

### 검증 기록과 한계

[2026-10-18 독립 저장소 검증 기록](docs/VALIDATION.md)에는 새 빌드의 Python 검사 40개, PE/ABI 검사, 실제 실행기 연결 13개 경로, 프로젝트 변환과 원본 보존 검사가 기록되어 있습니다.

분리 전 DLL의 기본 검증 게임 완주, 30분 내구성, 맵 왕복 100회 및 성능 측정은 별도 이력입니다. 해당 결과를 새 빌드에서 모두 재수행한 것은 아닙니다. 각 문서의 DLL SHA-256과 검증 범위를 확인하세요.

- 원본 DLL의 전체 66개 함수, 편집기, 임의 플러그인 및 구형 Ruby 네이티브 확장의 호환성은 보장하지 않습니다.
- 64비트 실행기, 60/120FPS 및 고주기 로직은 지원 범위에 포함하지 않습니다.
- RGSSAD v2/v3는 지원하지 않습니다.
- 물리 게임패드와 Windows 배율은 검증하지 않았습니다.
- 원본 GDI 경로의 프레임별 GPU 비용 비교는 미확정입니다. 일부 조건에서는 CPU 실행 시간이 증가했으므로 전반적인 성능 향상을 보장하지 않습니다.

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
template/      배포용 원본 게임 프로젝트 (변환 전)
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

## 기여하기

기여 절차와 코드 규칙은 [AGENTS.md](AGENTS.md)를 확인하세요. 버그 제보에는 실행 환경, 재현 순서, 사용한 DLL의 SHA-256과 오류 내용을 포함해 주세요. 렌더링 문제에는 권리상 공유 가능한 화면을 첨부하면 도움이 됩니다.

PR에는 변경 이유, 영향 범위와 수행한 검사를 적어 주세요. 승인된 `template/` 입력 외의 게임 원본·에셋·세이브·비밀 키는 첨부하거나 커밋하지 마세요. 호환성 변경에는 해당 동작을 검증하는 회귀 검사를 포함합니다.

## 라이선스

자체 코드는 [MIT 라이선스](LICENSE)입니다. Ruby 4.0.7, zlib 1.3.2, libogg 1.3.6, libvorbis 1.3.7은 각각의 라이선스를 따르며, 고지 원문은 `licenses/`에 있습니다. Windows API는 Windows SDK를 통해 사용합니다.

승인된 `template/` 입력을 제외한 빌드 결과, 실행 파일, 게임 데이터·에셋·세이브, 원시 추적과 덤프는 `.gitignore`로 제외합니다. 게임 실행기와 리소스의 사용·배포 권한은 별도로 확인해야 합니다.
