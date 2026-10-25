# XP·VX Ace 공용 표시 객체·문자 경로

표시 객체는 프레임마다 WeakMap의 강한 참조 스냅샷에서 수집합니다. Tilemap 레이어를 확장하면서 뷰포트 동일성으로 분류하고, `z → Sprite y → serial` 순서를 유지합니다. 기본 정수 정렬 키는 네이티브에서 정렬하며 객체 주소 대신 스냅샷 인덱스를 보관합니다. 객체 목록·정렬 결과·반환 명령 배열은 다음 프레임에 재사용하지 않습니다.

기본 Sprite는 옵션 Hash와 좌표 배열 없이 기존 22필드 명령을 만듭니다. 사용자 quad/표시 메서드 재정의와 singleton 훅은 기존 검색 경로로 돌아갑니다. 그리기 중 VXA 뷰포트 소속 변경이 감지되면 이후 뷰포트도 기존 검색을 사용합니다. XP 타일 경로와 VXA 타일 캐시·D3D 배치 형식은 유지합니다.

문자는 기존 GDI의 문자열 전체 알파 마스크와 측정 크기를 재사용합니다. 실제 문자열·글꼴 이름·크기·굵기·기울임이 키이며 색·위치·정렬·압축 폭은 매번 적용합니다. LRU는 프로세스당 128개/4MiB이고 512 UTF-16 단위 초과 또는 1MiB 초과 마스크는 저장하지 않습니다. Bitmap/Ruby 객체/GPU 포인터와 GDI 핸들은 캐시에 보관하지 않습니다. F12·종료·프로젝트 글꼴 등록·DPI/글꼴 환경 변경 시 비웁니다.

`draw_text`는 실제로 쓴 사각형을 기존 Bitmap 변경 영역과 합칩니다. VXA 테두리·그림자는 각 패스의 영역을 합치며 전체 clear는 전체 업로드를 유지합니다. 내부 수치 진단은 문자열 내용을 기록하지 않습니다.

## 재현

변경 전 현재 HEAD를 빌드해 두 DLL을 별도 폴더에 보존한 뒤 후보를 빌드합니다. 같은 PC에서 다른 게임/부하 도구를 종료하고 실행합니다. 출력 폴더는 존재하지 않아야 합니다.

```powershell
python -X utf8 -B scripts/benchmark_runtime_client.py build/client-cpu --baseline BASELINE_DLL_DIRECTORY
python -X utf8 -B scripts/benchmark_runtime_client.py build/client-render --baseline BASELINE_DLL_DIRECTORY --profile render
python -X utf8 -B scripts/benchmark_runtime_client.py build/client-memory --baseline BASELINE_DLL_DIRECTORY --profile memory
python -X utf8 -B scripts/benchmark_runtime_client.py build/client-output-allocation --baseline BASELINE_DLL_DIRECTORY --profile output-allocation
```

CPU 프로필은 0/100/300/1,000 Sprite와 1/8/32 뷰포트 조합, 반복/고유 문자열을 두 엔진에서 3쌍 번갈아 실행합니다. 300/1,000 Sprite의 평균 25%·할당 30% 감소와 p95 증가 5% 이하, 반복 문자 평균 30% 감소, 고유 문자 평균/p95 증가 10% 이하를 각각 판정합니다.

output-allocation 프로필은 300/1,000 Sprite × 1/8/32 뷰포트에서 매번 네이티브 출력까지 강제합니다. 생성뿐 아니라 명령 해석·D3D 제출을 포함한 실제 출력 프레임당 Ruby 할당의 30% 감소를 별도로 확인합니다.

render 프로필은 변환 복사본의 1280×720 기본 맵에서 정지/왕복 이동 각 30초×3쌍과 후보 40/60FPS 각 10초를 실행합니다. 출력 118FPS 이상(120 설정), 로직 119–121Hz, 누락 2% 이하를 별도로 판정합니다. 생성/해석/제출의 합은 같은 프레임 표본으로 계산하며 GPU 시간은 더하지 않습니다. 성공한 DXGI Present 제출 수이며 물리적 스캔아웃은 측정하지 않습니다.

정확성 검사는 기존 실행 회귀에 포함됩니다.

```powershell
python -X utf8 -B -m unittest discover -s tests -v
python -X utf8 -B scripts/test_runtime.py template-xp/Game.exe build/runtime-native/bin/Release/Lunetile.dll build/client-xp
python -X utf8 -B scripts/test_runtime_vxa.py build/client-vxa --stock
python -X utf8 -B scripts/test_runtime_client_pixels.py build/client-pixels --baseline BASELINE_DLL_DIRECTORY
```

`runtime_display_commands.rb`는 명령·전체 픽셀·동일 z/y·뷰포트 동일성·훅·GC 압축·이전 명령 보존을 검사합니다. `runtime_text_cache.rb`는 픽셀·키 변경·LRU 개수/바이트·큰 문자열 우회·Bitmap 회수·GDI 핸들·실제 GPU 업로드 바이트를 검사합니다. `runtime_text_pixels.rb`는 이전 DLL과 45개 글자 픽셀/측정 크기를 비교하는 독립 시나리오입니다. XP/VXA F12 검사도 캐시 무효화를 확인합니다.

MMO GUI 회귀는 별도 격리 배포 복사본에 새 DLL만 넣은 뒤 실행합니다. 원본 계정/프로필 폴더를 복사하지 않습니다.

```powershell
python -X utf8 -B example/tools/smoke_test.py ISOLATED_BUNDLE --output build/client-mmo --native
python -X utf8 -B scripts/test_runtime_client_gui.py ISOLATED_BUNDLE build/client-mmo-gui
```

GUI 검사는 소유한 두 창에 한글 확정 문자 입력, 상대 채팅 수신, 창 드래그, 전투를 검사합니다. 물리 키보드의 IME 조합 검증과는 구분합니다. 기존 간헐적 이동 오류는 최초 실패를 보존하며 재시도 성공으로 대체하지 않습니다. 실제 수행 결과와 DLL 해시는 [VALIDATION.md](VALIDATION.md)에 기록합니다.
