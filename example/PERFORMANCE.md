# 서버 운영과 성능 검사 (v11)

서버 EXE와 클라이언트 Scripts.rxdata를 함께 갱신합니다. 플레이어 schema 3·계정·장비·인벤토리·프로필·퀵슬롯은 유지합니다. 서버 설정과 콘텐츠는 기존 JSON으로 관리합니다.

## 저장·정상 종료·복구

변경은 `transactions/active.wal`에 기록하고 디스크 동기화가 성공한 뒤 승인합니다. 플레이어 JSON은 약 1초 간격의 체크포인트 작업으로 최신 상태를 반영합니다. 작업 소요 시간과 저장장치 상태에 따라 JSON 반영이 더 늦어질 수 있습니다. 게임에서 승인된 변경은 JSON에 아직 없어도 저널로 복구합니다.

서버 콘솔에서 Ctrl+C를 누르고 프로세스 종료를 기다리세요. 비정상 종료·강제 종료가 있었다면 다음 중 하나로 복구한 뒤 파일을 편집합니다.

```powershell
cd server
.\lunetile-mmo-server.exe --recover-only
```

배포본의 **Recover Server.cmd**도 같은 기능입니다. 복구 성공 안내를 확인하면 포트를 열지 않고 종료합니다. 같은 폴더의 서버가 실행 중이면 폴더 잠금 때문에 거부합니다. 실제 콘솔 종료 검사는 같은 처리기를 사용하는 Ctrl+Break 신호로 수행했습니다.

백업할 때는 정상 종료한 뒤 **accounts·players·transactions 전체를 같은 시점에 복사**하고, 클라이언트 ClientProfile도 보관하세요. 저널·체크포인트·기존 pending.json은 직접 수정하거나 삭제하지 않습니다. 플레이어 JSON과 저널에는 비밀 토큰이 있으므로 공개 ZIP·Git에 넣지 않습니다. `.json.bak`은 직전 JSON 체크포인트이며 최신 승인 상태는 저널에 있을 수 있습니다.

체크포인트 실패는 저널을 유지하고 다음 주기에 재시도합니다. 저널 정리 실패도 기존 저널을 보존하고 다음 반영 때 재시도합니다. 저널이 64MiB에 도달하거나 저널 저장에 실패하면 추가 변경을 승인하지 않고 복구를 요구합니다. 저장 문제를 해결하고 `--recover-only`를 실행하세요. 불완전한 마지막 기록만 제외하며, 완전한 기록의 체크섬·순번 손상은 임의로 무시하지 않습니다. 이런 경우 전체 백업을 함께 복원해야 합니다. 기존 pending.json은 새 저널보다 먼저 복구합니다.

## 처리와 통신

월드 변경은 단일 처리기로 순서를 유지합니다. 요청은 전체 1,024개·연결당 32개로 제한하고 최대 5ms/64개 묶음으로 판정합니다. 저널 작업자와 JSON 체크포인트 작업자를 분리하며 체크포인트 파일 작업은 최대 8개입니다. 거래·다중 보상은 하나의 저널 트랜잭션으로 저장합니다.

별도 공개 스냅샷에는 확정 상태만 반영합니다. 조회·프리뷰는 저장 중에도 처리하며, 응답 직렬화와 소켓 전송은 스냅샷 잠금 밖에서 실행합니다. 송신 큐 32개 포화 또는 2초 쓰기 제한은 해당 연결만 종료합니다.

정적 아이템·스킬·전직/습득 규칙·서비스·파티클 정의는 welcome.catalog로 한 번 보냅니다. 클라이언트 네트워크 스크립트가 캐시하여 기존 기능별 스크립트에 같은 state 구조를 제공합니다. 30Hz 조회는 유지합니다. 이벤트와 다른 플레이어의 이동 경로는 같은 연결에 이미 보낸 순번을 반복하지 않습니다. 본인의 위치 보정용 이력은 유지합니다. 이벤트 보관 범위를 넘긴 연결은 누락을 숨기지 않고 재접속하도록 종료합니다.

## 저장 경로와 측정 조건

32명 결과는 빠른 로컬 디스크에서 검증합니다. 이번 PC의 4KB 동기화 예비 측정은 작업 폴더에서 약 25~30ms, 시스템 임시 디스크에서 약 0.2~0.3ms였습니다. 같은 NTFS여도 디스크·가상화·동기화 경로 등에 따라 차이가 큽니다. 느린 경로의 ACK 목표 미달을 숨기기 위해 동기화를 생략하지 않습니다.

지연이 크면 서버를 정상 종료·백업한 뒤 실행 폴더 전체를 빠른 로컬 디스크에 복사해 확인하세요. 서버 EXE는 별도의 데이터 폴더도 지원합니다. 아래 경로는 예시이며 기존 데이터를 먼저 복사한 상태여야 합니다.

```powershell
.\lunetile-mmo-server.exe --root "C:\LunetileServer"
```

현재 PC의 전후 수치·30분 부하·메모리·장애 검사·화면 검사는 VALIDATION.md를 참고하세요. 로컬 TCP 부하 결과는 실제 두 PC LAN·인터넷·장기간 운영의 보장이 아닙니다. 저장장치 고장이나 실제 전원 차단은 별도 검증이 필요합니다.

## 개발자 계측과 재현

지표를 저장하려면 존재하는 쓰기 가능한 폴더의 경로를 지정합니다. 약 5초마다 누적 count·평균·최대·p95/p99와 현재/최대 큐·저널 크기를 JSONL로 기록합니다. 단계 지표의 백분위는 1ms 버킷, TCP 검사 도구의 백분위는 실제 왕복 측정값입니다. `cpu_core_percent`는 논리 CPU 하나를 100%로 보는 프로세스 사용량입니다. 요청 내용·토큰은 지표에 기록하지 않습니다.

```powershell
.\lunetile-mmo-server.exe --metrics "C:\LunetileMetrics\server.jsonl"
```

저장소 루트에서 격리 부하를 재현합니다. 출력은 새 폴더여야 합니다. `--local-disk`는 시스템 임시 폴더에서 서버 데이터를 실행하고 종료 후 결과 폴더로 보관한 뒤 임시 폴더를 지웁니다. `--previews`는 이동 전 프리뷰와 조회 사이의 프리뷰도 전송합니다. 혼합 부하는 이동·공동 사냥과 주기적인 거래/NPC 상호작용을 포함합니다.

```powershell
python -X utf8 -B example/tools/check_load.py example/output/LunetileMMO-Windows --output build/new-load --clients 32 --seconds 1800 --protocol 11 --mode mixed --metrics --local-disk --previews
python -X utf8 -B example/tools/check_load.py example/output/LunetileMMO-Windows --output build/new-stress --clients 32 --seconds 60 --protocol 11 --mode mixed --stress --metrics --local-disk --previews
python -X utf8 -B example/tools/check_persistence.py example/output/LunetileMMO-Windows --output build/new-recovery
python -X utf8 -B example/tools/check_shutdown.py example/output/LunetileMMO-Windows --output build/new-shutdown
```

테스트 출력의 server/players·transactions는 새 격리 계정이지만 비밀 토큰을 포함합니다. 성능 보고서를 공유할 때는 summary.json·metrics.jsonl만 선택하세요. 원본 프로젝트와 기존 계정을 부하 검사에 사용하지 않습니다.

32명 30분 전후 비교는 v9 측정 기록입니다. v11의 계정 처리·한글 입력과 이번 회귀 검사는 VALIDATION.md를 참고하세요. 계정 인증은 월드 처리 밖에서 수행하며 계정 파일 관리·복구는 ACCOUNTS.md에 있습니다.
