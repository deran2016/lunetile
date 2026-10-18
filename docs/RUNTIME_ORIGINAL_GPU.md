# 원본 창 모드의 GDI 출력 경로

> 독립 소스 저장소 안내: 아래의 이전 DLL 해시·build 경로는 분리 전 검증 기록입니다.
> 원시 자료는 포함하지 않으며, 새 저장소의 실제 빌드·검사 결과는 [VALIDATION.md](VALIDATION.md)에 구분합니다.

2026-10-18. 원본 DLL SHA-256은
`7b6acb5e2c245b8cfda77fced2cc0e94108384cd1b9ffc8510e7304fcb9feb6c`입니다.
이 분석은 자체 엔진의 GPU 성능 수치가 아니며 원본 GPU 비용을 0으로 확정하지 않습니다.

## 관찰한 사실

- REA/Ghidra 12.1.4로 기존 로딩 후 분석본을 열었습니다. 분석본 해시는
  `99f9ec001ee53493a84ff6c165cec195d3a01520b5cf96fa2bf4bcb64817f137`입니다.
  이 파일은 실행용 DLL이 아니며 공개 산출물에 포함하지 않습니다.
- `Graphics.update`의 기존 경로에서 `0x10004be0 → 0x100212f0 → 0x100c6c70 →
  0x100c6390`을 추가 분석했습니다. 일부 가상 호출의 대상은 Ghidra만으로 해결되지 않았습니다.
- 별도 원본 복사본의 초기화 직후 상태를 읽었습니다. 코드·픽셀·설정을 쓰지 않았고
  `Graphics.update`도 호출하지 않았습니다. 따라서 이 진단은 API 호출 횟수나 처리 시간 측정이 아닙니다.
- 실제 표시 객체의 가상 함수 표는 `0x1012e984`였습니다. 그 표의 `+0x30` 대상은
  `0x100c6960`, `+0x34`는 `0x100c68c0`, `+0x38`은 `0x100c6930`이었습니다.
  앞서 분석한 함수의 가상 호출 위치와 대응합니다.
- 객체의 DirectDraw 분기 값 `+0xc8`은 0이고 표면 포인터 `+0xfc`, `+0x100`도 0이었습니다.
  초기화된 창 모드에서 `0x100212f0`의 일반 출력 분기로 들어가는 상태와 일치합니다.
- 출력용 비트맵에서 `GetObjectType`은 bitmap, x86 `GetObjectA`는 84바이트 DIBSECTION을
  반환했습니다. 그 DIB는 **640×8, 32bpp, stride 2560**, CPU bits 포인터가 있었습니다.
  화면 해상도는 계속 640×480이며 이 8행 DIB를 전체 화면 크기라고 해석하지 않습니다.
- 간접 API 슬롯 6개의 실제 주소·소속 모듈·모듈 베이스를 읽고, 같은 Windows DLL 파일의
  export RVA와 대조했습니다. 단순 문자열이나 현재 `GetProcAddress` 반환값의 일치로 추정하지 않았습니다.

| 원본 슬롯 | 실제 모듈 export와의 대응 |
|---|---|
| `0x10126030` | GDI32 `CreateCompatibleDC` |
| `0x1012603c` | GDI32 `SelectObject` |
| `0x10126040` | GDI32 `DeleteDC` |
| `0x10126054` | GDI32 `BitBlt` |
| `0x101262dc` | USER32 `GetDC` |
| `0x101262ec` | USER32 `ReleaseDC` |

가상 대상 두 개는 Ghidra 함수 목록에 없었습니다. 같은 주소를 반복해서 디컴파일하지 않고
`read_bytes`로 확인했습니다. `0x100c6960`에는 `SRCCOPY` 값과 위 `BitBlt` 슬롯 호출이 있습니다.
`0x100c68c0`의 출력 DC 준비와 `0x100c6930`의 DC 해제도 실제 슬롯 대응과 맞습니다.

근거 REA ID:

- `ev_7a4a89d46f4b2da7498c53d7bdb8c403b752ace846fdac7731d97a3e5a592db9`: update 하위 경로
- `ev_a607c5ee2540c61d9db0dee3030460d1811bb67ccbe415ac3566258cee204bf4`: 출력 분기
- `ev_0b2f4b58b84a9c99ab76e35dbebd381fc80cd15a432bfba1b239d2aceaa44568`: dirty 영역/가상 출력 호출
- `ev_d2cc802416bc8cb69fee78c87c51d820d2cdb7b109345c6c4b0db817118f1e8c`: DC 준비
- `ev_dc5df035827fdcb7ec139e2dd0bf5984db3044023dc548d557d3d8188e516041`: 출력 대상의 코드 바이트

로컬 근거는 `build/runtime-original-render-state-6/validation.json`, `results.json`과
`build/runtime-original-render-path-2-rea.json`입니다. 전체 REA 기록에는 디컴파일 결과와
원본 바이트가 있으므로 공개하지 않습니다. 첫 진단의 시간 초과, 고정 Hash 키를 Win32API에
전달한 오류와 정상 SystemExit를 오류로 기록한 중간 결과는 성공 근거로 사용하지 않습니다.

## 해석과 남은 한계

정적 호출 경로와 실제 객체/API 주소를 결합하면, 관찰한 초기 창 모드의 출력은
CPU에서 주소를 갖는 DIB와 GDI `BitBlt`를 사용한다고 판단할 수 있습니다.
[Microsoft BitBlt 설명](https://learn.microsoft.com/en-us/windows/win32/api/wingdi/nf-wingdi-bitblt)은
원본/대상 DC 사이의 사각 영역 전송을 정의합니다.
[GetObjectA](https://learn.microsoft.com/en-us/windows/win32/api/wingdi/nf-wingdi-getobjecta)와
[DIBSECTION](https://learn.microsoft.com/en-us/windows/win32/api/wingdi/ns-wingdi-dibsection)은
비트맵 구조와 CPU bits 해석의 근거입니다.

이 결과는 원본의 D3D Present 프레임 CSV가 없는 이유를 좁힙니다. 하지만 초기 상태의 관찰이며
모든 후속 프레임·전체 화면·드라이버 경로를 직접 추적한 결과는 아닙니다.
GDI 전송 이후 드라이버와 데스크톱 합성 비용이 없어졌다는 뜻도 아닙니다.
공유 합성 비용을 원본 게임의 렌더 GPU 시간으로 귀속하거나 새 D3D11 timestamp와 나눠
GPU 개선율을 만들지 않습니다. 원본 GPU 실행 시간은 계속 미확정입니다.

이 분석에서는 원본 파일·자체 엔진 DLL을 변경하지 않았습니다. 사용자 제외 항목인 배율 검사,
Windows 설정 변경과 추가 관리자 WPR 추적도 수행하지 않았습니다.
