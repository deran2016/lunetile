# GPU·프레임 대기 반복 측정

> 독립 소스 저장소 안내: 아래의 이전 DLL 해시·build 경로는 분리 전 검증 기록입니다.
> 원시 자료는 포함하지 않으며, 새 저장소의 실제 빌드·검사 결과는 [VALIDATION.md](VALIDATION.md)에 구분합니다.

엔진 DLL은 `3868eeceb9fbba5ffc2509cf371e54240db726645dd64145ca4ef5b7f7fffd41` 그대로입니다.
이 문서는 이후 추가한 측정 도구의 기록입니다. 기존 `RGSSXP-stock-candidate-20261018`과
`RGSSXP-stock-source-20261018.zip`은 생성 당시의 불변 스냅샷으로 보존합니다.
**별도 진단 세 쌍을 완료했습니다. 원본 GPU 실행 시간의 직접 비교는 여전히 미확정입니다.**
2026-10-18 사용자는 이 미확정 한계를 명시하고 첫 버전을 인수했습니다.
원본 GPU 수치 비교는 첫 버전의 필수 완료 조건에서 제외했으며 측정값과 원시 보고서는 바꾸지 않습니다.

## 2026-10-18 실제 실행 결과

`build/runtime-components-pairs-1`은 AB/BA/AB 순서로 각 장면 80프레임 워밍업 후
400프레임씩 측정했습니다. 여섯 실행 모두 정상 종료했고, 총 9,600프레임의 포커스,
세 쌍의 논리 상태, 원본 해시 보존 및 원본 대기 IAT 복구를 확인했습니다.
게임은 일반 권한, WPR 기록기만 사용자 UAC 승인으로 관리자 권한을 사용했습니다.
고유 WPR 인스턴스는 컨트롤러 요청으로 저장·정상 종료됐으며 실제 기록기 프로세스 종료도 확인했습니다.

분석 결과는 `build/runtime-components-review-2.json`입니다. 아래 수치는 세 실행의 중앙값입니다.
대기는 각 실행의 **평균**, GPU는 각 실행의 **p95**이며 서로 다른 통계입니다.

| 장면 | 원본 대기 평균 ms | 자체 대기 평균 ms | 자체 렌더 명령 GPU p95 ms | 자체 ETW GPU active 추정 p95 ms |
|---|---:|---:|---:|---:|
| 이벤트 0 | 22.236 | 21.872 | 0.126 | 1.092 |
| 정지 100 / 병렬 10 | 20.992 | 20.011 | 0.120 | 1.128 |
| 정지 300 / 병렬 30 | 18.199 | 16.183 | 0.134 | 4.136 |
| 이동 300 / 병렬 30 | 16.793 | 15.506 | 0.132 | 1.701 |

- 대기 시간이 줄었다는 사실만으로 성능 향상을 주장하지 않습니다. 프레임 안의 처리 시간이
  늘어나도 남은 대기는 줄어듭니다. 실제 전체 CPU 시간은 기본 비교에서 증가했습니다.
- 자체 GPU timestamp는 Present 이전 렌더 명령 구간입니다. 비동기 완료 시퀀스를 실제 렌더한
  프레임에 다시 연결했습니다. 장면별 400개 관측 중 워밍업 프레임의 지연 결과 16개를 빼고,
  실제 측정 창에 속한 **384개씩, 세 번**을 사용했습니다. 종료 시 아직 도착하지 않은 16개는
  보간하지 않았고, disjoint/유효성 오류와 포커스 대기는 0이었습니다.
- 자체 ETW는 각 측정 Graphics 구간의 QPC에 정확히 하나씩, 총 **4,800개** Present를 연결했습니다.
  `msGPUActive`는 스케줄링에서 얻은 추정치여서 timestamp 구간과 같지 않습니다. 두 값의 차이를
  정밀도 오차나 새 엔진 병목으로 단정하지 않으며 전체 표시 지연으로도 바꾸지 않습니다.
- 원본 PID 세 개는 PresentMon 종료 코드가 모두 0이었으나 프레임 CSV가 없었습니다.
  같은 ETL의 원본별 커널 추출은 손실 이벤트/버퍼, 스키마/속성 실패 모두 0이었습니다.
  원본마다 귀속된 DMA 제출~완료 구간 7쌍은 시작 시점에만 있었고 측정 장면과 겹치지 않았습니다.
  이는 **원본 GPU 비용 0의 증명이 아닙니다.** DWM 합성 전체를 게임에 귀속하지 않으며,
  원본 GPU 실행 시간과 GPU 개선율은 `null`로 남깁니다.

이번 추가 작업은 계측·분석 도구와 문서에 한정됐습니다. 엔진 DLL과 23개 native 관문의
검증 대상 소스는 그대로입니다. Python 도구 검사 **41개**, 실제 x86 타임라인 시험과
네이티브 ETW 인자 거부 4개를 통과했습니다. `review_runtime_components.py`는 잘못된 PID,
중복/누락 Present, 어긋난 시각과 유효하지 않은 GPU 결과를 거부합니다.
그 보고서의 `passed`는 진단 수집·귀속 검사 통과이며 전체 계획 완료 판정이 아닙니다.

새 반복 대기와 자체 GPU 수집은 완료했습니다. 원본 GPU의 동등한 프레임별 비교와 전체 표시
지연은 미확정으로 남기며, 기존 한 번의 진단을 세 번 실행한 결과로 바꿔 적지 않습니다.
원시 ETL, 프로세스별 원시 로그와 기존 게임 스크립트는 공개 산출물에서 제외합니다.
후속 읽기 전용 진단으로 확인한 원본의 DIB·GDI 출력 경로와 해석 한계는
[원본 GPU 경로 분석](RUNTIME_ORIGINAL_GPU.md)에 기록했습니다.

## 기존 ETW 재검토

- 렌더링을 확인했던 기존 `performance/native/phase2/etw-render` 기록은 원본 PID 40464의 역사적 자료입니다.
  현재 자체 DLL의 실행 결과로 옮기지 않습니다.
- 공식 [PresentMon 2.6.0](https://github.com/GameTechDev/PresentMon/releases/tag/v2.6.0)의 콘솔 실행 파일을
  공개된 SHA-256 `b2a706bc6ad475749e3b7e3409263aa1e6906d45bdcf993f6dbc0f660188f1af`와 대조했습니다.
  설치 프로그램·서비스는 사용하지 않았습니다. 도구와 고정 정보는 `build/analysis-tools/`에만 있습니다.
- 기존 ETL을 오프라인으로 분석한 PresentMon은 종료 코드 0이었지만 대상 프레임 CSV를 만들지 않았습니다.
  따라서 0ms 또는 GPU 작업이 없었다는 결론으로 사용하지 않습니다.
- 설치된 WPR의 기본 GPU 프로필을 조회했을 때 D3D9·Win32k·DWM 이벤트가 포함되지 않았습니다.
  [PresentMon의 화면 경로 설명](https://github.com/GameTechDev/PresentMon/blob/v2.6.0/PresentData/PresentMonTraceConsumer.hpp)은
  레거시 복사 경로의 표시 추적에도 합성 이벤트가 필요함을 보여 줍니다.
  제공자 부족은 확인했지만 새 추적이 해결할지는 실제 검증 전입니다.
- 기존 ETW 추출기는 프로세스 내부 `hHwQueue`를 전역 식별자로 사용했습니다.
  동일 값이 다른 두 커널 컨텍스트에서 재사용돼, 대상이 아닌 생성 이벤트 2개가 포함됐습니다.
  전역 커널 큐 식별자 `ParentDxgHwQueue`만 사용하도록 수정했습니다.
  새 추출의 43개 행과 기존 45개 행을 대조해 두 행만 제거됐고, 대상 DMA 7쌍은 그대로임을 확인했습니다.
  근거는 `build/etw-lifecycle-check-1/regression.json`입니다.
  그 7쌍은 제출~완료 구간이며 정확한 GPU 실행 시간으로 채택하지 않습니다.

## 사용한 도구와 준비 검증

- `tests/runtime_gpu_trace.wprp`: D3D9·DXGI·DxgKrnl 스케줄링·DWM·Win32k 표시 이벤트와 프로세스 메타데이터.
  Win32k는 이벤트 201/301만 허용하며 입력·스택 이벤트는 사용하지 않습니다.
  설치된 WPR의 `-profiles`/`-profiledetails`에서 프로필과 필터를 확인했습니다.
  필터 문법은 [Microsoft EventFilters](https://learn.microsoft.com/en-us/windows-hardware/test/wpt/eventfilters)를 따릅니다.
- `scripts/record_runtime_trace.ps1`: 저장소 `build/` 안의 새 경로만 사용하고 WPR 전용 관리자 권한을 요구합니다.
  고유 `-instancename`으로 시작·종료하므로 다른 WPR 기록을 종료하지 않습니다.
  최대 480초 또는 정상 권한 컨트롤러의 종료 요청까지 기록합니다.
  일반 권한·허용 경로 밖 입력이 실제로 거부되고 출력이 생성되지 않았음을 확인했습니다.
- `tests/runtime_bench_metrics.c`의 `BenchWriteTimeline`: 기존 프레임 스냅샷의 절대 QPC만 추가로 내보냅니다.
  측정 프레임 안에 호출을 추가하지 않습니다. 기존 CSV 형식은 유지합니다.
  실제 x86 DLL을 동적으로 로드한 `runtime_bench_timeline.c` 시험에서 시각 순서, 주파수,
  잘못된 상태 거부와 기존 구간 시간의 일치를 확인했습니다.
- `scripts/benchmark_runtime_components.py`: 정상 권한 게임만 실행하고 AB/BA/AB 세 쌍으로
  원본 대기 관측·복구, 자체 명령/제출/대기, GPU timestamp와 절대 QPC를 수집합니다.
  기록기의 실제 PID/생성 시각도 확인합니다. 완료한 본 성능 비교에 진단 표본을 섞지 않습니다.
  ETW 귀속 결과는 위 실제 실행 결과와 구분합니다.
- `build/runtime-component-preflight-1`: Python 38개 검사, 네이티브 QPC 시험,
  WPR 프로필 문법 및 기록기 거부 시험의 준비 결과입니다. 실측 통과 보고서는 아닙니다.

## 실행 순서

게임 창을 유지할 수 있는 시점과 실제 UAC 승인이 필요합니다. 게임 컨트롤러는 일반 권한으로 유지합니다.
각 출력 경로는 새 이름을 쓰며 기존 결과에 덮어쓰지 않습니다. 아래는 소스 저장소 루트에서 실행합니다.

WPR 기록기만 관리자 권한으로:

```powershell
powershell -NoProfile -File scripts/record_runtime_trace.ps1 -OutputRoot build/gpu-wait-trace-NEW
```

기록기의 `recording.json`과 실제 프로세스가 확인된 뒤 일반 권한으로:

```powershell
python -X utf8 scripts/benchmark_runtime_components.py System build/runtime-benchmark-pairs-9/fixture RGSS104E.dll build/runtime-native/bin/Release/RGSS104E.dll build/gpu-wait-trace-NEW build/gpu-wait-pairs-NEW --frames 400
```

컨트롤러가 종료 요청을 남기면 해당 WPR 인스턴스만 저장·종료합니다.
두 프로세스의 실제 종료와 `session-result.json`을 확인한 후, 기록된 대상 PID별로 PresentMon을 오프라인 실행합니다.
QPC 행과 논리 결과·원본 보존·포커스 상태가 일치해야 비교에 사용합니다.
미귀속 프레임이나 불확정 GPU 결과를 0으로 만들거나 제출~완료 지연으로 대체하지 않습니다.
[공식 도구도 하드웨어 스케줄링의 GPU 시간 오차를 설명합니다](https://github.com/GameTechDev/PresentMon/blob/v2.6.0/README.md#tracking-gpu-work-with-hardware-accelerated-gpu-scheduling-enabled).
원시 ETL에는 다른 프로세스의 시스템 메타데이터도 포함될 수 있으므로 공개 패키지에 넣지 않습니다.
배율·전역 타이머·우선순위·GPU 설정은 바꾸지 않습니다.
