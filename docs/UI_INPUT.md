# Lunetile::UIInput (Windows)

기존 RGSS `Input`의 키 매핑·계약을 유지하면서 GUI용 실제 키·마우스·텍스트 입력을 제공합니다. `Input.update` 직후 읽으세요. 게임 스레드에서 사용합니다.

온라인 장면에서는 `Graphics.background_update=true`로 비활성 창에서도 로직·통신을 계속 갱신합니다. 기본값은 false로 기존 XP 일시정지를 유지합니다. 키·마우스와 IME 입력은 전경 창에만 적용합니다. 예제는 장면 종료 시 이전 값을 복원합니다.

```ruby
Input.update
ui=Lunetile::UIInput
ui.text_input=true               # 채팅 시작 시, 종료 시 false
ui.caret_rect=Rect.new(30,600,1,22)
draft+=ui.text                   # UTF-8 확정 문자열; 읽으면 비움
composition=ui.composition       # 화면에만 표시하고 draft에 합치지 않음
if ui.text_submit?
  # 마지막 조합이 확정된 뒤 같은 Enter 한 번으로 전송
end
```

| API | 결과 / 용도 |
|---|---|
| key_trigger?(key) | 해당 로직 갱신의 최초 누름 |
| key_press?(key) | 누르고 있는 상태 |
| direction4 | 현재 누른 방향 중 가장 최근 키: 2/4/6/8, 없으면 0 |
| direction_trigger | 이번 Input.update 사이의 마지막 새 방향 누름: 2/4/6/8, 없으면 0 |
| mouse_position | 게임 좌표 [x,y], 창 밖·비활성 시 nil |
| mouse_press_position | 이번 누름이 시작한 게임 좌표(빠른 드래그에 사용) |
| mouse_trigger?(:left / :right) | 버튼 최초 누름 |
| wheel_delta | 이번 갱신의 휠 단위 수 |
| text | 확정 UTF-8 문자열, 읽을 때 비움 |
| composition / composing? | 조합 문자열 / 조합 여부 |
| text_submit? | 텍스트 입력 중 Enter 전송 의도. 조합 확정 후 한 번만 발생 |
| text_input= | 텍스트 수집·IME 활성화, 전환 시 대기 입력 초기화 |
| caret_rect= | 조합·후보 창의 게임 좌표 입력 위치 |
| ime_open? / ime_open= | 한국어/native 모드 조회·전환 |

key는 A~Z·0~9 문자/심벌, enter/escape/space/tab/backspace/delete/left/right/up/down/home/end/shift/left_mouse/right_mouse 심벌 또는 Windows VK 정수 0~255입니다. 휠·트리거는 다음 Input.update에서 갱신됩니다. 포커스를 잃으면 눌림·조합·미확정 입력을 초기화합니다. 창 픽셀을 실제 렌더링의 letterbox 배율과 여백으로 역변환하므로 DPI·크기 변화에도 논리 좌표를 사용합니다.

방향 API는 실제 Windows 방향키 메시지 순서를 따릅니다. 여러 키가 겹치거나 같은 갱신 전에 눌렀다 떼어도 마지막 새 누름을 보존하며 OS 자동 반복은 우선순위를 바꾸지 않습니다. direction_trigger는 읽어도 소비되지 않고 다음 Input.update에서 갱신됩니다. 텍스트 입력 전환은 대기 트리거를, 포커스 상실/리셋은 방향 상태 전체를 비웁니다. 기존 Input.dir4의 우선순위·키 매핑과 게임패드 계약은 바꾸지 않습니다.

텍스트 활성화 중 WM_CHAR와 Windows IMM 조합·확정 문자열을 처리합니다. 소비한 IME 결과를 기본 윈도 처리에 다시 넘기지 않아 중복을 방지합니다. 한국어 IME가 조합 확정 뒤 전달하는 Enter/Backspace/Delete는 직후 75ms 동안 GUI trigger에서 제외합니다. 기존 key_trigger 계약은 유지합니다. 채팅은 text_submit?를 사용해 이 대기 없이 한 번에 보냅니다. TranslateMessage 전에 ImmGetVirtualKey로 IME가 처리한 원래 Enter를 읽고, GCS_RESULTSTR을 수신한 뒤 전송 트리거를 한 번 발생시킵니다. `text_input=false`로 닫을 때 조합을 취소하고 IME를 일시 닫으며 다음 입력 때 언어 모드를 복원합니다. 이 API를 사용하지 않는 기존 게임의 IME 상태에는 개입하지 않습니다.

채팅 Esc는 먼저 검사하여 같은 메시지 묶음에서 IME가 확정 결과를 보낸 경우에도 취소한 글자를 draft에 넣지 마세요. Ctrl+V는 활성 입력에서 Unicode 클립보드를 읽습니다. 붙인 문자열도 클라이언트/서버의 길이·제어문자 검사를 적용해야 합니다.

Microsoft의 [TextInputCtrl.cpp](https://github.com/microsoft/Windows-classic-samples/blob/main/Samples/Win7Samples/winui/input/tsf/tsfapps/tsfpad-step1/TextInputCtrl.cpp)의 Windows 메시지 입력 처리와 비교하고, 이 구현의 IMM 조합·확정은 실제 Windows 한국어 IME에서 별도로 검사했습니다. 문자열 주입 검사와 실제 조합 검사는 example/VALIDATION.md에 구분합니다. 실제 다른 DPI·전체화면 환경의 수동 클릭 검사는 수행하지 않았으며 역좌표 계산은 네이티브 단위 검사로 확인했습니다.
