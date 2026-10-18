# 문자열·설정 파일·한글 경로

> 독립 소스 저장소 안내: 아래의 이전 DLL 해시·build 경로는 분리 전 검증 기록입니다.
> 원시 자료는 포함하지 않으며, 새 저장소의 실제 빌드·검사 결과는 [VALIDATION.md](../VALIDATION.md)에 구분합니다.

원본 프로젝트와 세이브는 그대로 보존합니다. 복사본의 `Game.ini`에 선택한 데이터 인코딩을
기록하고, 기본 RPG/Game 객체의 텍스트를 로드 시 UTF-8로 변환합니다.
원본 데이터 파일·RGSSAD·가져온 세이브의 바이트를 다시 쓰는 방식이 아닙니다.

```powershell
python scripts/migrate_project.py MyGame MyGame-RGSSXP --data-encoding CP949 --ini-encoding CP949
```

데이터 선택지는 UTF-8, CP949, CP932입니다. ASCII 이외 데이터는 명시적인 선택이 필요하며
자동으로 문자셋을 추측하지 않습니다. 이미 UTF-8로 표식된 문자열은 새 저장에서도 그대로 읽습니다.
잘못된 바이트·충돌하는 인코딩 표식·변환 후 중복되는 Hash 키는 오류로 중단합니다.
문자열의 공유·순환 참조·frozen Hash 키를 보존합니다. Table/Color/Tone/Rect native payload와
스크립트 컨테이너의 zlib 바이트는 텍스트로 해석하지 않습니다.
기본 프로젝트 외에 임의 바이너리를 문자열 변수로 사용하는 사용자 코드는 별도 검토가 필요합니다.

`migration/manifest.json`의 `data_text_changes`에는 위치, 전후 인코딩, 원본/UTF-8 hex와 해시를
기록합니다. 실제 변환은 같은 규칙으로 실행 중 수행되며 물리 데이터 파일의 해시는 유지됩니다.
원본 세이브 로드 시 게임 객체 텍스트와 ID 테이블 순서를 복원한 뒤 기본 게임 처리를 계속합니다.
새 저장은 `Saves/RGSSXP/`에 UTF-8 표식과 전용 저장 헤더를 사용하고 Import에는 쓰지 않습니다.

3868eece 후보부터 RGSSAD의 파일명 바이트도 선언한 `DataEncoding`으로 해석합니다.
해석 후 구분자와 ASCII 대소문자를 처리하므로 CP932 문자의 0x5C trail byte를 경로로 오인하지 않습니다.
그 문자셋에서 잘못된 이름은 EncodingError로 거부합니다. 데이터와 아카이브 파일명이 서로 다른 문자셋을 쓰는
혼합 자료를 자동 추측하지 않습니다. UTF-8/CP949/CP932의 자체 데이터·그림·음원 바이트 fixture를 검사했습니다.

## 설정 파일과 도구

원본 런처의 ANSI API와 엔진의 Unicode API가 함께 읽도록 변환본 Game.ini는
BOM이 있는 UTF-16LE로 저장합니다. 입력 INI가 BOM 없이 비ASCII 문자를 포함하면
`--ini-encoding UTF-8`, `CP949`, `CP932` 중 하나를 지정합니다. BOM이 있으면 그 표식을 사용합니다.
원본 INI 해시와 입출력 문자셋도 변환 기록에 남깁니다.

콘솔 도구 `rgssxp-ruby.exe`는 DLL과 동일한 Ruby 4.0.7 x86 및 인코딩 모듈을 사용합니다.
구문·인코딩 검사에만 사용하며 게임을 실행할 때는 필요하지 않습니다.
기본 miniruby에는 CP949/CP932 모듈이 없으므로 레거시 텍스트 검사는 이 도구로 수행합니다.
루비 버전을 낮추거나 64비트 VM으로 대체하지 않습니다.

내장 Ruby 코드에도 UTF-8 소스 표식을 넣었습니다. 표식이 없을 때는 바이너리 문자열로
계산한 절대 저장 경로의 한글이 `?`로 바뀌는 문제가 실제 UI에서 확인됐습니다.
이 문제를 고친 뒤 한글 폴더의 저장·읽기를 자동 회귀 항목에 추가했습니다.

## 확인 범위

- 동일 VM의 UTF-8/CP949/CP932 변환·참조·native payload·오류 검사.
- 실제 CP949/CP932 데이터 복사본의 인코딩 검사, 변환 기록, 원본 바이트 보존.
- 원본 RGSS가 생성한 각 인코딩 세이브를 새 DLL에서 가져오고 새 형식으로 저장·재로드.
- 한글 폴더·UTF-16 제목, CP949 원본 세이브 이어하기, 한글 대화·캐릭터 이름·그림 파일명,
  별도 저장, F12 후 새 저장 불러오기와 정상 종료를 실제 키 입력으로 확인.
  이 UI 시험의 원본 생성 fixture는 플레이어 그래픽 설정이 비어 있어 이동/캐릭터 표시 검증으로 사용하지 않습니다.

실제 UI 근거는 `build/runtime-한글-조작-1/boot-result.json`과 로컬 화면입니다.
화면에는 RTP 에셋이 있으므로 공개 묶음에 넣지 않습니다.
이 시험은 Windows ACP 949 환경입니다. 다른 시스템 로캘의 원본 ANSI 런처 제약, 한글 IME,
모든 폰트는 아직 포괄 검증하지 않았습니다. DPI 100/150/200% 배율 검증은 사용자 요청으로 범위에서 제외합니다.
설정 API 참고: [Microsoft GetPrivateProfileString](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-getprivateprofilestringw).
