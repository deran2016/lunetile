# SDR 출력과 HDR 모니터의 밝기

> 독립 소스 저장소 안내: 아래의 이전 DLL 해시·build 경로는 분리 전 검증 기록입니다.
> 원시 자료는 포함하지 않으며, 새 저장소의 실제 빌드·검사 결과는 [VALIDATION.md](../VALIDATION.md)에 구분합니다.

2026-10-18. 기본 RGSS의 내부 합성은 8비트 값으로 유지하고, 완성된 화면만 FP16 선형 scRGB로
변환해 표시합니다. 게임 해상도 640×480, 로직 40Hz, 데이터·저장 형식은 이 변경의 대상이 아닙니다.
Windows의 HDR·밝기·배율 설정은 변경하지 않았습니다.

## 관찰과 수정

원본 RGSS 프로세스에서는 `ddraw.dll`, 기존 자체 DLL에서는 D3D11 출력이 확인됐습니다.
기존 `7d310bc9...` 후보의 캡처는 더 밝고 색이 과했고, 사용자가 실제 모니터에서도 같은 차이를
확인했습니다. 내부 GPU 장면의 RGB 값이 소스와 같다는 사실만으로 표시 호환성을 통과 처리하지 않습니다.

`runtime-visual-color-fix-1/`의 무보정 FP16 후보는 캡처가 원본에 가까웠지만,
사용자는 실제 모니터에서는 더 어둡다고 확인했습니다. 이 고정 80nit 출력을 채택하지 않았습니다.
현재 출력 메타데이터는 10bit HDR, ColorSpace=12, SDR white level=5000(400nit)입니다.

`runtime-visual-color-fix-2/`의 후보 `aca5b97a...`는 Windows의 SDR white level을 읽어
선형 출력에 반영합니다. 사용자는 이 후보의 실제 밝기·색이 원본과 비슷하다고 답했습니다.
이는 해당 모니터·설정·자체 생성 장면의 사용자 관찰이며, 계측기를 통한 색 정확도나 모든 화면의 일치 판정은 아닙니다.

이 중간 후보에서는 보정값이 기존 mirror 플래그와 충돌하는 별도 결함을 GPU 검사로 찾았습니다.
최종 출력에만 쓰이는 상수로 분리해 수정했습니다. 현재 검사는 좌우 방향도 확인하며,
중간 후보에 대한 사용자 답변을 최종 DLL의 추가 물리 관찰로 바꾸어 기록하지 않습니다.

## 구현 계약

- `src/runtime/renderer.cpp`: FP16 flip swap chain과 명시적 `RGB_FULL_G10_NONE_P709` 출력.
- `src/runtime/render_shader.h`: 엔진과 GPU 검사가 공유하는 실제 shader 및 상수 배치.
  스프라이트·윈도·viewport·freeze 이미지와 transition 혼합은 기존 encoded 값으로 처리하고,
  최종 출력에서만 sRGB 역변환을 한 번 적용합니다. 마스크 값 자체에는 감마 변환을 적용하지 않습니다.
- `src/runtime/output_color.h`: 창이 놓인 모니터의 최신 DXGI 메타데이터와 활성 display path를 읽습니다.
  HDR이면 `DISPLAYCONFIG_SDR_WHITE_LEVEL / 1000`, SDR이면 1을 사용합니다.
  모니터 이동 또는 1초 경과 시 다시 읽고, 읽을 수 없는 HDR 정보를 임의의 밝기로 대체하지 않습니다.
  이 메타데이터 조회는 GPU timestamp 구간 밖에 둡니다.

선형 scRGB에서 1.0은 HDR 출력의 80nit입니다. 따라서 SDR 콘텐츠를 OS의 설정된 흰색에 맞추려면
선형 값에 `SDR white nits / 80`을 곱해야 합니다. SDR 모니터에서는 display-relative white를 사용합니다.
이 동작은 [Microsoft Advanced Color 설명](https://learn.microsoft.com/en-us/windows/win32/direct3darticles/high-dynamic-range)과
[SDR white level 정의](https://learn.microsoft.com/en-us/windows/win32/api/wingdi/ns-wingdi-displayconfig_sdr_white_level)를 기준으로 했습니다.

## 자동 검사와 범위

```powershell
cmake --build build/runtime-native --config Release --target runtime_output_color
build/runtime-native/bin/Release/runtime_output_color.exe
```

`tests/runtime_output_color.cpp`는 화면에 표시하지 않는 자체 창과 실제 FP16 swap-chain back buffer를
만듭니다. 엔진의 실제 shader를 실행하고 readback한 8,192개 채널 값을 수식 기준과 비교합니다.
0~255 단계의 RGB, 검정·흰색, 알파 유지, 좌우 방향, encoded scene 보존, 일반 출력,
서로 다른 두 이미지의 단순/마스크 transition, 보정값 1과 현재 OS 보정값을 포함합니다.
존재하지 않는 모니터는 거부합니다. 절대 0.0001 또는 상대 0.1%의 FP16 오차만 허용합니다.
전체 회귀 도구에는 이 검사의 빌드·실행 두 관문을 추가했습니다.

이 검사는 물리 패널·ICC 보정·모든 다중 모니터 배치·실제 SDR 모니터·HDR 설정 전환의 통과 근거가 아닙니다.
특히 캡처 색만으로 실제 표시를 판정하지 않습니다. Windows 배율 검사는 사용자 요청대로 제외합니다.
소스·DLL 해시가 바뀐 뒤 성능과 내구성 결과는 별도로 다시 수집합니다.
