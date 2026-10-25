# XP 타일 제출 배치와 XP·VXA 문자 합성

이전 로컬 검증본의 XP `70657997c26cfc1a89a82bdf4bd1df83fd73bb261efb1fe092d2809b119d7a63`, VXA `5ed9896be310661c9c88befde68a10af31707b726969eb5984c655c03371b067`를 비교 기준으로 사용합니다. 해당 작업 트리의 소스와 미추적 파일도 별도 해시/소스 ZIP으로 보존합니다. 원본 템플릿·저장·MMO 계정과 스크립트 패키지는 바꾸지 않습니다.

XP의 일반 타일은 VXA와 같은 32바이트 화면 사각형/UV 인스턴스 경로를 사용합니다. 연속된 같은 Bitmap과 클리핑의 조각만 묶고 그룹·일반 그리기·뷰포트·렌더 대상 경계를 넘지 않습니다. 플래시는 기존 색·가산 합성 quad로 제출하며 앞뒤 타일 구간을 끊습니다. 깊이 0/1000 충돌, 우선순위별 행 깊이와 Sprite 삽입 순서는 유지합니다. 일반 Sprite·Window·Plane은 기존 경로입니다.

공유 동적 인스턴스 버퍼는 출력 프레임당 한 번 WRITE_DISCARD로 갱신합니다. CPU/GPU 버퍼는 각각 최대 100,000×32바이트이고 용량을 재사용합니다. 확장 후 전체 명령 100,000개 제한도 그대로입니다. Bitmap/GPU 포인터는 프레임 사이에 저장하지 않으며 현재 프레임의 Bitmap은 Ruby 참조로 보호합니다. 생성·Map 실패와 해석 중 Bitmap 해제는 오류로 처리합니다.

공용 문자 합성은 압축하지 않을 때 원본 행과 대상 행을 순차 접근합니다. 기존 픽셀마다 수행하던 64비트 좌표 나눗셈을 줄이고, 압축 경로는 나눗셈의 몫/나머지를 누적하여 기존 floor 좌표와 같은 결과를 냅니다. 시작 좌표와 증가량만 나누고 픽셀별 나눗셈을 제거합니다. 알파 0에서 숨은 RGB를 쓰는 동작과 합성 반올림도 유지합니다.

VXA 기본 문자 경로는 문자열 변환·글꼴 읽기·전체 문자열 마스크 조회를 한 번 수행합니다. 같은 마스크로 왼쪽/오른쪽/위/아래 테두리 후 본문을 기존 순서로 합성합니다. 그림자는 테두리가 꺼졌을 때 기존처럼 처리합니다. 글꼴 색을 임시 변경하지 않으며 변경 영역은 각 패스의 영역을 합칩니다. 기존 GDI 엔진, 측정 크기, 128개/4MiB LRU와 긴 문자열·큰 마스크 우회 정책을 유지합니다.

VXA의 빠른 문자 경로는 기본 Bitmap/Font/Color/String 동작에 한정합니다. 고정 Ruby 4.0.7 빌드의 불투명 method-entry API로 기준 정의와 현재 정의를 매번 비교하며 VM 구조체 레이아웃을 복제하지 않습니다. 기준 엔트리는 복제하여 write barrier를 사용하는 하나의 TypedData GC 루트로 보호합니다. 기존 비공개 `__text`의 6필드 호출은 유지하고 내부 효과 호출만 별도 7필드 서술자를 사용합니다. 프레임 사이에 호환성 판정을 캐시하지 않습니다. 클래스/싱글턴/상속·prepend/삭제·재정의, 사용자 변환·__text 훅과 frozen Color는 기존 Ruby 경로로 처리합니다. Ruby 버전 변경 때는 이 내부 API와 GC·메서드 변경 검사를 다시 검증해야 합니다.

DLL 이름·exports·공개 RGSS API·저장·120Hz 로직은 유지합니다. `Graphics.__timings`, `__render_parts`, 기존 VXA `__tile_batches` 형식은 같습니다. XP에도 같은 내부 `__tile_batches` 카운터를 제공합니다. 문자 캐시 통계의 형식은 같고 조회 수는 실제 마스크 조회 기준입니다. VXA의 기존 효과 패스별 중복 조회는 사라집니다.

## 비교 및 완료 기준

```powershell
python -X utf8 -B scripts/benchmark_runtime_client.py build/xp-submit --baseline BASELINE_DLL_DIRECTORY --profile xp-tile-submit
python -X utf8 -B scripts/benchmark_runtime_client.py build/vxa-regression --baseline BASELINE_DLL_DIRECTORY --profile vxa-map-regression
python -X utf8 -B scripts/benchmark_runtime_client.py build/text-composite --baseline BASELINE_DLL_DIRECTORY --profile text-composite
```

기존 cpu/render/memory/output-allocation/xp-tile-cache/vxa-tile-parse 프로필의 조건은 바꾸지 않습니다. 새 프로필은 다음을 판정합니다.

- XP 기본 맵의 타일 Draw 90%, Present 전 처리 평균 50%, 생성+해석+제출 평균 20% 이상 감소. 전체 p95 증가 5% 이하.
- 반복 문자 워밍업 후 XP 평균 25%, VXA 평균 30%, VXA 할당 50% 이상 감소. 고유/압축/효과 없는 문자 평균·p95 증가 10% 이하.
- 두 엔진의 정지/왕복 이동 각각 기준·후보 30초×3쌍 교대 측정. 후보 40/60FPS는 정지/이동 각각 10초. 출력 ≥118FPS(120 설정), 로직 119–121Hz, 누락 ≤2%.
- VXA 기본 맵 전체 평균 증가 10%, p95 증가 5%, 할당 증가 5% 이하. 일반 표시 객체/매번 무효화하는 타일 부하 평균·p95 증가 10% 이하.

기준 XP DLL에는 Draw 카운터가 없으므로 타일 수를 측정 구간 밖에서 실제 내부 배치의 확장 결과로 셉니다. 기준 렌더러의 조각당 한 번 Draw 호출과 대응시켜 기준 호출 수를 산출합니다. 후보 호출 수는 네이티브 카운터입니다. 조사와 GC가 끝난 뒤 프레임 마감 시각과 카운터를 초기화합니다.

생성·해석·Present 전·Present·GPU를 구분합니다. 기존 전체 시간은 생성+해석+Present 포함 제출의 같은 프레임 표본 합계입니다. 캐시 준비는 생성의 일부이며 중복 합산하지 않습니다. GPU는 유효한 고유 시퀀스만 기록하고 CPU 합계에 더하지 않습니다. 출력은 성공한 DXGI Present 제출이며 물리 스캔아웃이 아닙니다.

## 정확성 및 전달

```powershell
python -X utf8 -B -m unittest discover -s tests -v
python -X utf8 -B scripts/test_runtime.py template-xp/Game.exe build/runtime-native/bin/Release/Lunetile.dll build/submit-xp
python -X utf8 -B scripts/test_runtime_vxa.py build/submit-vxa --stock
python -X utf8 -B scripts/test_runtime_client_pixels.py build/submit-text-pixels --baseline BASELINE_DLL_DIRECTORY
```

기존 XP 38건/VXA 224건 타일 픽셀·형상 검사를 유지하고 XP 텍스처 교대·플래시/회전 Sprite/뷰포트 혼합과 0/1/1024/1025/4096/4097/100,000 인스턴스 경계를 추가합니다. 문자는 기존 45건과 투명 배경/본문·테두리 알파/그림자/화면 밖·압축을 조합한 256건씩 전체 RGBA와 측정 크기를 비교합니다. 글꼴 변경, GDI 핸들, LRU 예산, 작은 문자 부분 업로드, 전체 clear, GC 압축·F12, 메서드 변경과 사용자 훅도 검사합니다.

저장 왕복·별도 프로세스 불러오기, 이동·대기·타이머, 기본/와이드 창 크기·전체 화면, x86/전체 export 이름·ordinal과 격리 MMO 두 클라이언트를 검사합니다. 이동 최초 실패를 재시도 성공으로 바꾸지 않습니다.

전달 폴더는 `build/submit-text-delivery-20261025/`입니다. 엔진별 DLL, `lunetile-xp-speed-fix.zip`, `lunetile-vxa-speed-fix.zip`, `lunetile-submit-text-diagnostics.zip`과 SHA256SUMS를 생성합니다. 패키징은 검증·성능 보고서의 DLL 해시와 모든 새 프로필 조건을 확인합니다. 기존 전체 템플릿을 새 폴더에 풀고 ZIP의 DLL만 교체해 원본 RGSS DLL 없이 실행합니다.

```powershell
python -X utf8 -B scripts/package_tile_client.py NEW_OUTPUT --verification VERIFICATION_JSON --xp-performance XP_SUBMIT_SUMMARY --vxa-performance VXA_REGRESSION_SUMMARY --text-performance TEXT_SUMMARY
```

공용 표시 클래스 검사 축소, 일반 Sprite 배치와 MMO 패널 redraw 변경은 이번 범위에서 제외합니다. 원격 CI/푸시/릴리스는 실행하지 않습니다. 물리 IME 조합·스캔아웃·장기 내구성과 모든 플러그인/PC의 성능은 인증하지 않습니다.

## 중간 실패 기록

초기 VXA 후보의 정지 구간 전체 p95가 기준보다 약 8.6% 증가해 성능 완료로 판정하지 않았습니다. 참조 루트를 묶은 다음 후보도 같은 기준을 넘었습니다. GC write barrier와 내부 문자 호출 경로를 보완했으며, 별도로 시도한 UV 사각형 재사용은 뚜렷한 이득이 없어 제거했습니다.

보완 후보의 첫 정식 검사에서도 정지 3쌍 중 한 실행이 출력 116.67FPS/로직 117.03Hz였고, 정지 전체 p95 비율은 1.0913이었습니다. 평균은 1.0349, 이동 p95는 0.9383이었습니다. 지연 원인은 확정되지 않았습니다. 해당 결과는 `build/submit-text-vxa-verified/summary.json`에 보존하며 통과 보고서로 대체하지 않습니다. 기능 검사와 별도로, 다른 검사를 겹치지 않는 조건의 전체 성능 재측정 결과도 함께 기록합니다.

첫 문자 성능 검사에서는 반복 문자 XP 평균 33.8%, VXA 평균 47.9%와 VXA 할당 71.9% 감소를 확인했으나 XP 압축 문자 p95가 26.9% 증가했습니다. 이 실패를 `build/submit-text-text-performance/summary.json`에 보존하고 압축 좌표 계산도 경량화했습니다.

## 최종 검증 결과 — 2026-10-25

최종 DLL의 SHA-256:

- XP: `2e4093fb47a681b96399a09b5ce2d86544421a3cc89a6d4aa4b4d842af85cab1`
- VXA: `6b57754d6149eac9942963a81ec4293bd830e550b2fc0a754df3458251360bad`

같은 PC에서 다른 빌드·검사를 겹치지 않고 엔진별 정지/이동 기준·후보 각 30초×3쌍을 순차 측정했습니다. 다음은 각 3회 평균입니다. 합계는 같은 프레임의 생성+해석+제출(Present 포함)이며 GPU는 합산하지 않습니다.

| 엔진/장면 | 합계 ms 기준→후보 | Present 전 ms 기준→후보 | 합계 p95 ms 기준→후보 | 출력/로직 최소 | 누락 |
|---|---:|---:|---:|---:|---:|
| XP 정지 | 0.5462→0.3415 | 0.1820→0.0216 | 0.7115→0.4600 | 119.998/119.998 | 0% |
| XP 이동 | 0.5540→0.3401 | 0.1875→0.0220 | 0.7163→0.4506 | 119.999/119.999 | 0% |
| VXA 정지 | 0.4741→0.4724 | 0.0288→0.0290 | 0.6773→0.7098 | 119.996/119.996 | 0% |
| VXA 이동 | 0.5065→0.4585 | 0.0312→0.0286 | 0.7379→0.6565 | 119.997/119.997 | 0% |

XP 타일 Draw는 프레임당 984→1회(99.90% 감소), Present 전 평균은 정지 88.14%/이동 88.28%, 합계 평균은 37.48%/38.61% 감소했습니다. 출력당 할당은 XP 약 0.89% 증가, VXA 변화 없음입니다. VXA 정지 p95는 **4.80% 증가**하여 허용치 5% 안쪽입니다. 여유가 작으므로 다른 환경·장면의 안정성을 보장하지 않습니다. VXA 이동 수치의 변화 전체를 문자 합성 개선 효과로 해석하지 않습니다.

후보 40/60FPS 정지·이동 각 10초도 목표 출력과 로직 119–121Hz를 통과했습니다. 두 엔진의 일반 Sprite/Window/Plane과 매번 캐시를 무효화하는 부하는 평균·p95 증가 10% 이하였습니다. GPU 고유 시퀀스 평균은 XP 정지/이동 0.5302/0.5327→0.4556/0.4591ms, VXA 0.4472/0.4470→0.4474/0.4426ms였으며 별도 참고 수치입니다.

| 문자 부하 | XP 평균 변화 | XP p95 변화 | VXA 평균 변화 | VXA p95 변화 |
|---|---:|---:|---:|---:|
| 반복 | -34.20% | -40.54% | -47.08% | -46.84% |
| 고유 | -2.87% | +4.88% | -24.88% | -22.30% |
| 압축 | -26.36% | -25.32% | -43.07% | -43.79% |
| 효과 없음 | -34.50% | -34.60% | -27.94% | -23.85% |

문자는 각 부하당 100회 워밍업 후 1,500회×3쌍을 교대 측정했습니다. VXA 반복/고유/압축 할당은 약 71.9% 감소했습니다. 효과 없는 VXA 호출은 약 15.4% 할당 증가가 있으나 해당 부하의 시간은 개선됐고 기본 맵 할당 증가 기준도 통과했습니다. 마스크 LRU 제한과 부분 업로드는 기존 회귀 검사로 확인했습니다.

Python 167개, 네이티브 보조 검사 3개, XP/VXA 원본 실행기·저장/새 프로세스 불러오기·오류·120Hz 속도 검사, 기본/와이드 창 크기·최대화·전체 화면, F12를 통과했습니다. XP 기존 38건과 추가 혼합 배치 6건, VXA 기존 224건 타일 전체 화면 픽셀 비교와 버퍼 경계·100,000개 제한을 확인했습니다. 문자는 엔진별 기존 45건+추가 256건의 전체 RGBA·측정 크기가 기준 DLL과 같습니다. 추가 검사에는 압축 폭 1/3/27/69와 정렬도 포함합니다.

격리 MMO 네이티브 두 클라이언트의 이동·전투·재접속과 GUI 두 클라이언트의 한글 확정 입력/채팅·창 드래그·전투를 통과했습니다. 이 최종 실행의 최초 실패는 없었습니다. 물리 IME 조합 검사는 아닙니다. 전체 DLL export 이름/ordinal과 x86을 확인했고 원본/개인 파일 178개의 해시가 유지됐습니다.

정식 결과는 `build/submit-text-xp-accepted/summary.json`, `build/submit-text-vxa-accepted/summary.json`, `build/submit-text-text-accepted/summary.json`, `build/submit-text-accepted/verification.json`입니다. 하드웨어 성능 측정은 로컬 실행 결과이며 원격 CI 실행 결과가 아닙니다. 앞선 후보의 실패와 보완 이력은 위 중간 기록과 진단 ZIP에 함께 보존합니다. 최종 런타임 코드는 이 측정 이후 변경하지 않았습니다.


새 폴더에 alpha.14 전체 템플릿 ZIP을 압축 해제하고 이번 교체 ZIP의 DLL만 적용했습니다. 두 엔진에서 원본 RGSS DLL 없이 타이틀→맵→메뉴→F12 타이틀 복귀→정상 종료를 확인했습니다. 엔진별 프로젝트 입력 29개의 해시는 DLL 교체 전후 같았습니다. 타이틀/맵/메뉴/리셋 캡처 8장을 직접 검토했습니다. 캡처의 색상 표현은 이전 검증본과 같았으며 원본 RGSS와의 색상 일치 인증은 아닙니다. 원본/개인 파일 178개 해시를 전달 직전에도 다시 확인했습니다.

교체 ZIP 두 개의 DLL은 성능/회귀 검사에 사용한 해시와 정확히 같습니다. 모든 ZIP CRC와 소스 해시 목록을 검증했습니다. 진단 ZIP에는 전후 해시, 세 성능 보고서, 픽셀/배치/사용자 훅 결과, LRU/업로드 검사 결과, 압축 해제 실행 결과와 중간 실패 보고서 5개를 포함합니다. 원본 RGSS DLL·프로젝트 데이터·개인 저장·로그·프로필은 포함하지 않습니다. 최종 런타임/게임 및 MMO 스크립트·서버·프로토콜은 측정 이후 변경하지 않았고 원격 게시도 하지 않았습니다.
