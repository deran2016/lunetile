# XP 타일 캐시와 VXA 명령 해석

후속 제출·문자 경로 최적화는 [SUBMIT_TEXT_PERFORMANCE.md](SUBMIT_TEXT_PERFORMANCE.md)를 참고하세요.

alpha.14 (`cba5c888`)의 DLL을 비교 기준으로 사용합니다. 기본 맵의 1280×720/120Hz 경로를 개선하며 게임 스크립트, 저장 형식, DLL 이름과 exports는 바꾸지 않습니다. 적용은 엔진에 맞는 DLL 교체입니다.

XP는 표시 범위의 숫자 셀과 타일 형상을 캐시합니다. 크기는 `ceil(viewport/32)+1`이며 픽셀 스크롤에는 좌표만 바꿉니다. 관찰 중인 맵·우선순위·플래시 Table에만 64건의 변경 기록을 할당합니다. 동일한 int16 저장값 쓰기는 기록하지 않고, 복사·크기 변경·교체·기록 초과·우선순위 변경은 표시 범위를 다시 읽습니다. 여러 Tilemap은 각자의 변경 세대를 추적합니다. Marshal 바이트는 같습니다.

기존 Ruby 생성기는 `legacy_layers`로 남고 숫자 형상 생성기를 캐시 미스에도 재사용합니다. 내부 배치는 기존 XP quad 제출 경로로 확장합니다. 행별 깊이, 같은 깊이의 Sprite, 깊이 0/1000 충돌, 7개 자동타일, 단일 행 애니메이션, 플래시의 색·가산 합성과 40Hz 점멸을 유지합니다. Table/Bitmap 읽기·형상·quad 훅이 기본 조건을 벗어나면 Ruby 경로를 사용합니다.

VXA는 전체 160바이트 Draw를 타일마다 만들지 않습니다. 기존 32바이트 CPU 인스턴스에 직접 기록하고 연속된 Bitmap 구간만 순서 목록에 넣습니다. 타일 배치 경계, 일반 그리기, 뷰포트와 렌더 대상 경계에서 구간을 끝내며 텍스처별 재정렬은 하지 않습니다. 기존 타일 버퍼와 D3D 셰이더 경로를 사용합니다.

캐시는 Bitmap/Ruby 객체/GPU 포인터를 보관하지 않습니다. 현재 프레임의 Bitmap은 해석이 끝날 때까지 별도 Ruby 참조로 보호합니다. 사용자 색/사각형/스칼라 훅이 해석 중 Bitmap을 해제하면 GPU 제출 전에 오류로 처리합니다. 캐시당 32MiB와 확장 후 100,000개 명령 제한을 적용하고 캐시 메모리는 Ruby GC에 보고합니다. 반환 명령 배열은 다음 프레임에서 덮어쓰지 않습니다.

## 재현 및 판정

먼저 alpha.14에서 빌드한 `Lunetile.dll`, `LunetileVXA.dll`을 별도 폴더에 보존합니다. 원본 템플릿 대신 새 검증 복사본을 사용합니다.

```powershell
python -X utf8 -B scripts/benchmark_runtime_client.py build/tile-xp --baseline BASELINE_DLL_DIRECTORY --profile xp-tile-cache
python -X utf8 -B scripts/benchmark_runtime_client.py build/tile-vxa --baseline BASELINE_DLL_DIRECTORY --profile vxa-tile-parse
python -X utf8 -B -m unittest discover -s tests -v
python -X utf8 -B scripts/test_runtime.py template-xp/Game.exe build/runtime-native/bin/Release/Lunetile.dll build/tile-xp-runtime
python -X utf8 -B scripts/test_runtime_vxa.py build/tile-vxa-runtime --stock
```

정지와 왕복 이동 각각 기준/후보 30초×3쌍을 번갈아 측정합니다. 후보 40/60FPS도 정지·이동 각각 10초 검사합니다. 게임 실행과 다른 부하 도구는 동시에 돌리지 않습니다. 일반 Sprite·Window·Plane 및 매번 무효화하는 타일 부하는 3쌍의 추가 검사로 평균/p95 증가 10% 이하를 판정합니다.

XP 기준은 생성+해석 평균 60%, 생성+해석+제출 평균 50%, 출력당 Ruby 할당 70% 감소입니다. VXA는 해석 평균 30%, 전체 평균 10%, 타일 중간 저장 공간 사용량/예약량 각각 70% 감소입니다. 두 엔진 모두 전체 p95 증가 5% 이하, 120 설정에서 출력 118FPS 이상, 로직 119–121Hz, 누락 2% 이하를 요구합니다. VXA 할당 증가는 5% 이하입니다. 기존 cpu/render/memory/output-allocation 프로필의 조건은 유지합니다.

`Graphics.__timings`, `__render_parts`, VXA `__tile_batches` 형식은 그대로입니다. 새 내부 `__tile_parse_stats`는 `[전체 사용량, 전체 예약량, 타일 중간 사용량, 타일 중간 예약량, 확장 명령 수, Present 전 ms, Present ms]`입니다. 바이트는 해당 프레임의 네이티브 해석용 Ruby String 저장 공간이며 기존 32바이트 CPU/GPU 인스턴스는 별도입니다. alpha.14의 중간 저장 공간은 소스의 x86 Draw 크기(타일당 160바이트)와 실제 타일 수로 산출합니다.

생성/캐시 준비/해석/Present 전/Present/GPU 시간을 구분해 기록합니다. 캐시 준비는 생성 시간의 일부이며 합계에 다시 더하지 않습니다. GPU는 유효한 고유 시퀀스만 집계하며 CPU 합계에 더하지 않습니다. 출력 수는 성공한 DXGI Present 제출 수입니다. 모니터의 물리적 스캔아웃 측정은 포함하지 않습니다.

문자 패스 통합, 일반 Sprite D3D 배치, MMO 패널의 전체 clear/redraw 축소는 범위 밖입니다. 모든 PC와 사용자 플러그인의 성능을 보장하지 않습니다.

## 2026-10-25 로컬 성능 결과

기준/후보를 번갈아 정지·왕복 이동 각각 30초×3쌍 측정했습니다. 두 프로필의 모든 성능·퇴행 조건을 통과했습니다. 제출 구간에는 Present 대기가 포함됩니다.

| 엔진/장면 | 생성+해석 이전→후보 | 전체 이전→후보 | 할당/출력 이전→후보 |
|---|---:|---:|---:|
| XP/정지 | 4.195→0.307ms | 4.419→0.546ms | 6329→561 |
| XP/이동 | 4.224→0.306ms | 4.451→0.543ms | 6335→567 |
| VXA/정지 | 0.575→0.394ms | 0.687→0.478ms | 678→688 |
| VXA/이동 | 0.575→0.414ms | 0.690→0.496ms | 737→747 |

VXA 해석 평균은 정지 0.282→0.139ms, 이동 0.289→0.156ms였습니다. 타일 중간 저장 공간은 이전 629,760바이트에서 사용 36바이트/예약 141,696바이트로 줄었습니다(예약 77.5% 감소). 이 기본 맵의 CPU/GPU 인스턴스 측정 최대는 각각 131,072바이트로 동일합니다. 전체 한도는 각각 100,000×32바이트입니다. 타일 외 명령까지 포함한 후보 해석 공간은 사용 3,808바이트/예약 145,468바이트였습니다.

기본 맵 캐시는 XP 229,324바이트, VXA 1,162,560바이트였습니다. 측정 종료 시 두 엔진의 맵 셀 읽기 누계는 각각 최초 표시 범위 984셀로 유지됐습니다. 이 기본 맵의 왕복 이동은 캐릭터 이동이며 카메라 경계 이동의 새 행/열 갱신은 별도의 합성 시나리오로 확인합니다.

후보 120 설정의 최소 출력은 XP 119.998FPS, VXA 119.997FPS였고 로직은 119–121Hz, 누락은 0%였습니다. 40/60 설정도 두 엔진의 정지·이동 각각 10초에서 출력 목표와 약 120Hz 로직을 유지했습니다. 전체 p95 비율(후보/기준)은 XP 정지/이동 0.134/0.134, VXA 0.656/0.682였습니다.

일반 Sprite·Window·Plane의 생성+해석 평균/p95 증가는 XP 2.5%/5.6%, VXA 2.7%/2.6%였습니다. 매번 무효화하는 부하는 XP 평균/p95 약 66% 감소, VXA 평균 1.1% 증가/p95 0.7% 감소였습니다. VXA 기본 맵의 할당 증가는 정지 1.47%/이동 1.36%입니다.

30초 표본당 GC 누계 평균(정지/이동)은 XP 526/354→10/36ms, VXA 47/42→68/73ms였습니다. GPU 평균은 XP 약 0.53ms, VXA 약 0.45ms로 별도 기록했습니다. GC 주기와 드라이버가 포함된 단일 PC 결과이며 장기 메모리 안정성 또는 모든 환경의 개선율을 보장하지 않습니다.

| DLL | alpha.14 SHA-256 | 후보 SHA-256 |
|---|---|---|
| XP | `72ccc1cf5c775fc1a3558122f6629be580ffdb6c01d0f79d8a5574874d52d65d` | `70657997c26cfc1a89a82bdf4bd1df83fd73bb261efb1fe092d2809b119d7a63` |
| VXA | `6ad4492f9c11b99045c88280c6a984121a550bfa355c6e5b60432b2e9ffe3382` | `5ed9896be310661c9c88befde68a10af31707b726969eb5984c655c03371b067` |

## 실행 회귀와 전달

Python 164개, XP 원본 실행기 28개 시나리오 및 보강 XP 픽셀 38건, VXA 기존 픽셀 224건과 기하 비교를 통과했습니다. 저장/프로세스 재시작, 두 엔진의 기본/와이드 HWND 크기 변경과 전체 화면, F12, GC 압축과 사용자 훅, 격리 MMO 네이티브 두 클라이언트 및 한글 확정 입력/채팅/드래그/전투를 확인했습니다. 원본·개인 파일 178개의 전후 해시가 같았습니다. 세부 범위는 [VALIDATION.md](VALIDATION.md)에 있습니다.

로컬 결과물은 `build/tile-client-delivery-20261025/`의 두 DLL, `lunetile-xp-speed-fix.zip`, `lunetile-vxa-speed-fix.zip`, `lunetile-tile-performance-diagnostics.zip`, `SHA256SUMS.txt`입니다. 이미 Lunetile로 변환된 프로젝트에서 게임을 종료한 뒤 해당 엔진의 DLL만 교체합니다. 설치된 RTP 요구 사항은 유지하며 RTP와 원본 RGSS DLL은 포함하지 않습니다.

```powershell
python -X utf8 -B scripts/package_tile_client.py NEW_OUTPUT --verification VERIFICATION_JSON --xp-performance XP_SUMMARY_JSON --vxa-performance VXA_SUMMARY_JSON
```

패키징 도구는 측정/검증 DLL 해시, 두 성능 프로필과 일반/반복 무효화 판정을 확인합니다. 실패·불완전 보고서나 다른 DLL은 거부합니다. 이전 cpu/render 프로필의 완료 조건을 덮어쓰지 않습니다. 원격 게시는 이번 작업에 포함하지 않습니다.


새 폴더에 alpha.14의 전체 템플릿 ZIP을 풀고 교체 ZIP에서 DLL만 적용한 뒤 원본 실행기로 타이틀→맵→메뉴→F12 타이틀 복귀→정상 종료를 두 엔진 모두 확인했습니다. XP 29개/VXA 29개 프로젝트 입력 파일의 해시가 DLL 교체 전후 같고 원본 RGSS DLL은 없었습니다. 창 캡처를 직접 검토했습니다. 초기 GetDC(window)의 색상 집합 비교로 메뉴 전환을 확인하지 못한 로그는 남겼고, 최종 검사는 전경 포커스/순서 있는 실제 화면 픽셀/창 캡처로 확인했습니다. 런타임 코드는 이 검사 중 변경하지 않았습니다.
