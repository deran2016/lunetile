# XP·VXA 검증 실행

일반 작업은 빠른 검증으로 확인하고, 성능 개선율을 발표할 때만 정밀 비교를 실행합니다. 게임 로직·공개 RGSS API·기존 정밀 합격 기준은 바꾸지 않습니다. 모든 실행은 순차적이며 원본 대신 별도 출력 폴더를 사용합니다.

## 명령

먼저 기존 빌드 명령을 실행합니다. 성공한 빌드는 `build-stamp.json`에 소스와 DLL·보조 실행기 해시를 기록합니다. 기록이 없거나 현재 소스/파일과 다르면 검증기는 재빌드를 요구합니다. 예전 DLL에 기록만 임의로 붙이지 마세요.

```powershell
# 변경된 영역만, 기본 quick
python -X utf8 -B scripts/verify_runtime.py build/check-new

# 두 엔진과 전체 검증 영역의 빠른 검사
python -X utf8 -B scripts/verify_runtime.py build/check-all --all

# 일반 릴리스: 기능·저장 재시작·F12·창·관련 브라우저·새 ZIP 실행 추가
python -X utf8 -B scripts/verify_runtime.py build/check-release --mode release

# MMO가 배포 대상이면 격리 두 클라이언트 검사도 필수로 지정
python -X utf8 -B scripts/verify_runtime.py build/check-mmo --mode release --mmo-bundle example/output/LunetileMMO-Windows

# 개선율을 주장할 때: 기존 30초 x 3쌍 기준/후보 비교
python -X utf8 -B scripts/verify_runtime.py build/check-performance --mode performance --baseline BASELINE_DLL_DIRECTORY
```

출력 폴더는 매번 새 경로를 지정합니다. 기본적으로 원본 템플릿을 허용 목록으로 복사·변환하여 시험 프로젝트를 준비합니다. 이미 준비한 `xp/`, `vxa/` 프로젝트가 있으면 `--projects DIRECTORY`를 지정할 수 있습니다. 이때도 데이터만 복사하고 검증 대상 DLL로 교체합니다. 원본 RGSS DLL·개인 저장·프로필은 복사하지 않습니다.

`--changed PATH ...`는 자동 변경 감지 대신 변경 경로를 명시합니다. 엔진 전용 파일은 해당 엔진, 공유·알 수 없는 변경은 두 엔진을 선택합니다. 문서만 바뀌면 Python 검사만 실행합니다. `release`는 두 엔진의 실제 실행을 확인합니다. MMO 번들을 지정하지 않은 결과에는 MMO 미검증이 표시되며 MMO 인증으로 사용할 수 없습니다.

기존 네 인자 상세 검증과 개별 검사 명령도 유지합니다.

```powershell
python -B scripts/verify_runtime.py ORIGINAL_PROJECT ORIGINAL_DLL ORIGINAL_SAVE NEW_OUTPUT
```

## 무엇을 줄였는가

기존 브라우저 정밀 비교는 두 엔진에서 44회, 측정 구간만 1,000초였습니다. 빠른 검사는 후보 DLL만 정지·이동 각각 5초 측정하고, 브라우저 변경이면 열린 패널도 각각 5초 측정합니다. 저프레임은 엔진별 같은 프로세스에서 40/60FPS를 각각 3초 확인합니다. 두 엔진·브라우저 포함 측정 예산은 최대 **52초**이며 워밍업·준비·기능 검사는 별도입니다.

120FPS 통과를 40/60FPS 합격으로 취급하지 않습니다. 저프레임에서는 120Hz 로직 틱 수, 출력 간격과 이동 결과를 확인합니다. 출력과 무관하게 틱을 직접 진행하는 이동·점프·대기·타이머 검사는 엔진별 한 번만 실행합니다. 기본 XP 40Hz/VXA 60Hz 동작의 상세 검사는 제거하지 않습니다.

통신의 빠른 검사는 stock120 한 번만 실행합니다. `release`와 기존 통신 상세 명령은 stock120·레거시 로직을 모두 실행합니다. 빠른 결과로 레거시 통신까지 검사했다고 표시하지 않습니다.

모듈 감시는 처음 구한 DLL 해시를 재사용합니다. 실제 런타임 로드·원본 RGSS 미사용과 실행 전후 파일 무결성은 계속 확인합니다. `monitor_hash_calls`는 이 감시 경로의 실제 파일 해시 횟수, `identity_hash_calls`는 현재 실행기의 입력/증거 해시 횟수입니다. 다른 도구 내부의 해시는 포함하지 않으므로 두 값을 전체 시스템 해시 횟수라고 부르지 않습니다.

## 결과와 재사용

`verification.json`에는 `mode`, `formal`, 선택 이유, 필수 검사 ID, 실행/재사용/생략/실패, 소요 시간, 실제 게임 프로세스 수와 해시 횟수를 기록합니다. 검사가 끝나기 전에는 `passed=false`입니다. 패키징 전용 증거는 `phase=prepackage`이며 릴리스 완료 증거와 구분합니다.

- ABI·결정적 검사만 성공 결과를 캐시합니다. DLL·테스트/보조 코드·실행기·데이터·설정·관련 실행 환경이 같고 보존된 증거 파일도 동일해야 재사용합니다. 결과가 손상/삭제되거나 앞선 실패가 있으면 재사용하지 않습니다.
- Python 검사는 실행기 호출당 한 번 실행합니다. 실제 출력, 브라우저 포커스, 릴리스의 저장 재시작·창/F12·압축 해제 검사는 새로 수행합니다. 정밀 성능도 재사용하지 않습니다.
- 빠른 검사는 120 설정 출력 ≥118FPS·로직 119–121Hz·누락 ≤2%, 저프레임은 목표의 98% 이상을 요구합니다. 짧은 CPU 평균/p95는 참고값이며 개선율이나 기존 정밀 퇴행 한도의 증거가 아닙니다.
- 첫 실패와 부분 결과를 지우지 않습니다. 포커스 준비와 시험 명령 파일 잠금만 제한적으로 기다리고, 게임 동작 실패를 자동 재시도 성공으로 바꾸지 않습니다.

실패 구간만 명시적으로 재현할 수 있습니다. 이 결과는 `phase=diagnostic`이며 패키징/릴리스 증거로 사용할 수 없습니다.

```powershell
python -X utf8 -B scripts/verify_runtime.py build/reproduce-one --only output.quick/xp-cadence
```

태그 CI는 같은 커밋의 성공한 main 실행, 같은 저장소/워크플로, 만료되지 않은 실행/진단 아티팩트, 출처 기록·내부 파일 해시·ZIP CRC를 확인했을 때만 재사용합니다. 증거가 없거나 API 오류가 나면 기존 전체 CI를 수행합니다. main/수동 실행은 항상 새로 빌드합니다. [아티팩트 다운로드 API](https://docs.github.com/en/rest/actions/artifacts), [다른 실행에서 다운로드하는 Action 옵션](https://github.com/actions/download-artifact/tree/v4)을 사용합니다.

빌드를 제외한 빠른 모드 3분·일반 릴리스 5분은 동일 PC에서 측정할 목표입니다. 설치된 RTP/WebView2 및 시험 장면과 환경에 따라 달라지며, 실제 측정 결과를 검증 기록에 별도로 남깁니다. 빠른 합격은 장시간 안정성·물리 화면 FPS·정밀 개선율을 보증하지 않습니다.

## 2026-10-26 실제 확인

같은 PC에서 두 엔진·모든 변경 그룹을 순차 실행했습니다. quick은 빈 캐시, release는 앞선 ABI 증거 2건을 재사용했고, 실제 실행 검사는 모두 새로 수행했습니다. release에는 별도 복사한 MMO 번들을 지정했습니다. 다음은 준비·Python·기능 검사와 측정을 포함하고 빌드는 제외한 전체 시간입니다.

| 모드 | 전체 시간 | 게임 프로세스 | 감시 해시 / 입력·증거 해시 | 결과 |
|---|---:|---:|---:|---|
| quick | 148.297초 | 27 | 225 / 788 | 3분 목표 충족, MMO 미요청으로 생략 |
| release | 286.235초 | 85 | 459 / 1,000 | 5분 목표 충족, MMO·새 ZIP 실행 포함 |

최종 Python **200개**가 통과했습니다. 전체 모드의 120 설정 최소 출력은 quick 118.991FPS/release 119.589FPS, 로직은 119.979–120.021Hz, 최대 누락은 0.834%였습니다. 40/60 설정도 각 3초 별도 측정했으며 목표 출력 비율은 최소 99.98%였습니다. CPU 평균/p95는 진단으로만 보관했습니다.

기존 브라우저 정밀 비교(`build/browser-performance6/summary.json`)와 이번 빠른 검사는 같은 후보 DLL을 사용합니다. 측정 구간 합계는 1,000.017→52.003초(94.8% 감소), 출력 검사 프로세스는 44→10개입니다. 이전 전체 검증의 wall time은 기록이 없으므로 전체 시간의 감소율은 주장하지 않습니다. 정밀 기준/후보 비교와 후보 출력 검사는 서로 다른 판정입니다.

추가로 실제 보존 증거를 읽어 XP/VXA ABI·결정적 검사 4건이 게임 실행 없이 재사용되는 것을 확인했습니다. 같은 DLL의 3초 실행에서 변경 전/후 감시기를 순차 비교한 결과, 런타임 DLL 해시는 55→3회, 해당 실행 도구의 전체 파일 해시는 140→88회였습니다. 실행 시간 3.984→3.953초 차이를 성능 개선율로 취급하지 않습니다.

사용한 DLL은 다음과 같으며 이전 배포 DLL과 동일합니다.

```text
XP  a299b69c138a621b844d75e21020ec596cbf37711f4a2a88418ec5e2eccc8fc9
VXA 5bc7df0691e44480d334f66f2226fef5b9dae86f2770260928366ca6f0f23ca7
```

최종 결과는 `build/validation-roundtrip-acceptance-20261026/{quick,release}/verification.json`, 비교·보존 요약은 `build/validation-delivery-20261026/summary.json`입니다. `build/validation-efficiency-roundtrip-20261026/`에 실제 재사용/감시 비교를 보관했습니다. 런타임 소스·원본/개인 파일 178개·기존 작업 트리의 example 문서는 유지했습니다.

초기 실패도 그대로 남겼습니다. `build/validation-quick-20261026/`는 시험 맵 이동 초기화 누락, `build/validation-release-20261026/`는 패키지 시험 페이지 준비 전 포커스 시도, `build/validation-release-complete-20261026/`는 환경 tuple/list JSON 비교 문제입니다. 각 원인을 수정하고 최종 두 모드를 새 폴더에서 수행했습니다. 중간 재현은 진단 전용이며 릴리스 합격으로 합치지 않았습니다.

새 정밀 모드와 실제 GitHub workflow는 실행하지 않았습니다. 정밀 일정 유지 및 CI 재사용의 동일 SHA/저장소/출처/체크섬/만료/누락/실패 분기는 자동 검사했습니다. 원격 푸시·릴리스는 수행하지 않았습니다.
