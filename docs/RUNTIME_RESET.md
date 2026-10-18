# RGSS1 리셋 계약

> 독립 소스 저장소 안내: 아래의 이전 DLL 해시·build 경로는 분리 전 검증 기록입니다.
> 원시 자료는 포함하지 않으며, 새 저장소의 실제 빌드·검사 결과는 [VALIDATION.md](VALIDATION.md)에 구분합니다.

원본 32비트 실행기와 RGSS104E.dll을 별도 폴더에서 조사했습니다. 원본은 변경하지 않았습니다.

REA로 기존 로딩 후 분석 이미지의 Graphics.update 호출 경로를 확인했습니다.
F12 상태를 확인하는 함수는 `Reset` 상수를 찾거나 예외 클래스를 만들고 예외를 발생시킵니다.
정적 분석은 키 입력이 실제 실행됐다는 증거가 아닙니다.

- Graphics.update 증거: `ev_8bc00d4da1ace6bdf60206a84f67dc317f4368a991d535032703834f237ea2c2`
- F12/Reset 경로 증거: `ev_63df2f765cd9c4ddb7405a37514e854d824f6a309e34eb0ae397d541e8734b88`
- 분석 이미지 SHA-256: `54e8de39535c806de4d03cb5119ca4fd0fa82ff298c52885f8261e008d7b4d8b`
- 원본 DLL SHA-256: `7b6acb5e2c245b8cfda77fced2cc0e94108384cd1b9ffc8510e7304fcb9feb6c`

`tests/rgss_reset_reference.rb`는 명시적으로 `Reset`을 발생시킵니다. 원본에서 다음을 관찰했습니다.

| 항목 | 재실행 때 관찰 |
|---|---|
| 전역 카운터 | 1 → 2: Ruby VM을 새로 시작하지 않음 |
| Bitmap / Sprite / Plane / Window | 이전 객체가 disposed 상태 |
| Font.default_size | 변경한 30 유지 |
| Graphics.frame_count | 5 유지 |
| Graphics.frame_rate | 변경한 60에서 40으로 복귀 |
| Viewport.disposed? | 원본 XP에는 해당 조회 메서드가 없음 |

새 엔진은 같은 VM에서 스크립트를 다시 실행합니다. 표시 객체·Bitmap을 폐기하고 오디오를 정리하며,
기본 Font와 Ruby 전역 상태·프레임 카운트는 유지합니다. 새 엔진의 Viewport.disposed?는 내부 표시 레지스트리용
추가 조회이므로 원본 대조에서는 제외합니다. 오디오의 리셋 시점 파형은 별도 교정 대상입니다.

F12는 창 메시지에서 눌림을 보관하고 Ruby로 돌아온 Graphics.update 경계에서 Reset을 발생시킵니다.
짧은 키 입력도 처리하고 한 번의 누름에서 한 번 리셋합니다. 원본의 짧은 F12 입력 두 번은 프로브에서
리셋되지 않았으므로, 물리 입력 유지 시간까지 원본과 같다고 주장하지 않습니다.

`tests/rgss_reset_review.rb`를 새 엔진에서 직접 F12 키로 두 번 리셋해 화면 카운터 1 → 2 → 3,
이전 Bitmap 폐기, 40Hz 복귀, VM 초기화 한 번과 정상 종료를 확인했습니다.
서드파티 플러그인의 반복 alias나 구형 네이티브 확장을 호환한다는 뜻은 아닙니다.

로컬 원본 동작 기록은 `build/runtime-reset-reference-5/`, 전체 대조는
`build/runtime-verification-9/reset/`, 실제 F12 입력 기록은 `build/runtime-reset-key-new-1/`에 있습니다.
디컴파일 출력과 원본 DLL은 공개하지 않습니다.
