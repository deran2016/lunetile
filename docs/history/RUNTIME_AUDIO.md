# 원본 오디오 대조와 현재 구현

> 독립 소스 저장소 안내: 아래의 이전 DLL 해시·build 경로는 분리 전 검증 기록입니다.
> 원시 자료는 포함하지 않으며, 새 저장소의 실제 빌드·검사 결과는 [VALIDATION.md](../VALIDATION.md)에 구분합니다.

2026-10-18. 직접 만든 단음 MIDI/WAV 및 이 WAV에서 인코딩한 Ogg/MP3/WMA만 사용했습니다.
게임 음악이나 원본 디컴파일 출력은 공개하지 않습니다. 원본 설치 파일도 변경하지 않았습니다.

## 확인한 계약

원본의 공통 볼륨 제어 함수는 1~100 입력을 다음 dB 값으로 바꿉니다.
0은 별도로 -100dB에 해당하는 최소값을 사용합니다.

| 볼륨 | 1/100 dB 단위 |
|---|---:|
| 0 | -10000 |
| 1 | -3465 |
| 25 | -2625 |
| 50 | -1750 |
| 75 | -875 |
| 100 | 0 |

MP3/WMA/MIDI는 위 18개 제어 값을 실제 API 호출에서 확인했습니다.
WAV/Ogg는 같은 원본 볼륨 함수로 연결되는 정적 경로를 확인했습니다. 이 두 형식의 개별 native
볼륨 호출은 현재 Windows API 추적으로 직접 분리하지 못했습니다.

새 엔진의 PCM 출력은 이 곡선을 XAudio2의 선형 amplitude로 변환합니다. 0은 mute로 처리합니다.
WAV/Ogg/MP3/WMA에서 각각 여섯 값을 지정하고 실제 XAudio2 voice의 GetVolume 값으로 검사합니다.
이 검사는 장치의 acoustic 파형 일치나 Windows 믹서 상태까지 증명하지 않습니다.

같은 BGM의 볼륨만 바꾸면 재생 위치가 유지되지만, 피치를 바꾸거나 fade 중 다시 재생하면
원본은 음원을 다시 엽니다. 새 PCM 경로도 이를 따르도록 수정했습니다.
fade의 논리 볼륨도 원본처럼 정수 백분율 단계를 거친 뒤 dB로 변환합니다.

## MIDI 피치

입력 50/100/150에서 원본 DirectMusic 메시지는 모두 120 BPM, MIDI note 69,
길이 1536 music tick이었습니다. 그러나 최종 MIDI 오디오 버퍼의 DirectSound SetFrequency 호출은
각각 **22050 / 44100 / 66150Hz**였습니다. 템포 메시지가 같다는 사실만으로 피치를 무시한다고
판단할 수 없습니다. 실제 출력 파형과 노트 시간의 변화는 추가 측정 대상입니다.

초기 WinMM 공유 출력은 이 버퍼를 개별적으로 재표본화할 수 없어 피치 100만 허용했습니다.
현재는 자체 SMF 파서·작업 스레드 스케줄러를 유지하고, 출력은 Windows DirectMusic의
독립 AudioPath에 연결한 synth port와 출력 버퍼를 사용합니다.
이는 설계의 WinMM 출력 경로에서 변경한 부분입니다. PCM 음원은 계속 XAudio2로 출력합니다.
원본 RGSS 함수로 전달하거나 대체 RPG 엔진 코드를 가져오지 않습니다.

피치 50/100/150의 실제 버퍼 GetFrequency 값 22050/44100/66150Hz를 검사합니다.
현재 MIDI 음량은 AudioPath에서 제어하므로 버퍼 GetVolume으로 측정했다고 표시하지 않습니다.
내부 진단의 MIDI `linear_gain`은 nil이며, 여섯 음량은 아래 프로세스별 PCM으로 비교합니다.
같은 MIDI를 BGM/BGS/SE에서 서로 다른 피치로 재생하고,
각 출력의 percussion 채널 9가 동시에 사용되는 경우도 검사합니다. ME가 BGM의 버퍼를
음소거하고 종료 후 MIDI 컨트롤러를 복원하는 회귀 검사를 포함합니다.
중단된 지속음은 원본처럼 다시 발음하지 않고 이후 음표부터 재개합니다.
이전 공유 출력의 16채널 및 단일 percussion 채널 충돌 제한은 제거했습니다.

별도 `midi_port_probe`는 직접 만든 음표가 출력 버퍼에 비영 PCM으로 기록되고 실제 재생
커서가 움직이는지 확인합니다. S_OK 반환만으로 출력 성공을 판정하지 않습니다.
Windows 시스템의 `gm.dls`를 읽으며 OS 악기 파일은 배포하지 않습니다.
해당 소프트웨어 synth/악기가 없거나 요청 bank/program이 없으면 명시적인 오류를 냅니다.

SMF 이벤트는 현재 자체 wall-clock 시간표로 전송합니다. 아래 단음 시험의 피치 50/100/150은
실제 PCM을 대조했지만 모든 곡의 노트 길이·경계 지연이 일치한다고 주장하지 않습니다.
독립 port 생성·악기 다운로드 비용, MIDI tail/루프 경계·ME 복원음·SysEx·전체 bank 호환성도
추가 교정 대상입니다. 실제 API 제어 값 일치와 음향 결과의 일치는 구분합니다.

## 근거와 재현

- 볼륨 공통 함수: REA `ev_3f442938dcd2a80f1b30a022ddf364e2caa696f1025359ac25b33a6d43919b84`.
- 피치 제어 분기: REA `ev_57c37322a987e1d53e05fc4669d430249463f0a62df79a88d2cbd03435c94084`.
- 같은 파일/피치 재사용 조건: REA `ev_3e345a1a3383d80dcf423dfe8dd71051b5efe43bce9c5d9b2a2e5340325335a9`.
- 분석 대상은 앞서 확보한 로딩 후 이미지 `54e8de39535c806de4d03cb5119ca4fd0fa82ff298c52885f8261e008d7b4d8b`.
  원본 DLL은 `7b6acb5e2c245b8cfda77fced2cc0e94108384cd1b9ffc8510e7304fcb9feb6c`입니다.
- 실제 피치 API 기록: `build/runtime-midi-reference-6/`.
- 30개 형식/볼륨 입력 기록: `build/runtime-audio-volume-reference-2/`.
  `volume-comparison.json`은 실측과 정적 근거 범위를 구분합니다.
- 독립 Windows MIDI 버퍼의 재생·합성·재표본화 시험:
  `build/runtime-native/midi-port-probe-result.log`.
- 새 MIDI 출력의 실제 주파수·음량·중첩 드럼/ME 검사:
  `build/runtime-midi-backend-check-1/summary.json`.

REA의 Frida 작업은 네이티브 바인딩 누락으로 실행되지 않아, 작업 폴더의 격리 Python 환경에서
Frida 17.4.0을 사용했습니다. 이 런타임 기록은 **Python Frida 관찰이며 REA Evidence가 아닙니다**.
`capture.json`에 원본 EXE/DLL 해시, 관찰 코드 해시, 버전, 시간과 종료 상태를 기록합니다.
Frida는 분석 도구이며 엔진 DLL의 의존성이나 배포 구성 요소가 아닙니다.

```powershell
python -m venv build/runtime-analysis-venv
build/runtime-analysis-venv/Scripts/python.exe -m pip install frida==17.4.0
python scripts/launch_original_audio_probe.py "LOCAL_ORIGINAL_GAME_EXE" RGSS104E.dll build/audio-reference --source tests/rgss_audio_volume_reference.rb --prepare-only
build/runtime-analysis-venv/Scripts/python.exe scripts/capture_original_audio.py build/audio-reference --spawn --seconds 20
```

원본 파일은 직접 준비해야 합니다. 출력 폴더가 이미 있으면 새 이름을 사용합니다.
추적은 해당 복사본의 프로세스만 대상으로 하고 반환값이나 오디오 인자를 바꾸지 않습니다.
공개 빌드 스크립트는 Ruby·zlib·Ogg·Vorbis를 고정한 상태에서 다시 실행해 통과했습니다.

Windows 출력 API 참고: [DirectMusic 장치 연결](https://learn.microsoft.com/en-us/previous-versions/ms808943(v=msdn.10)),
[port 메시지 제출](https://learn.microsoft.com/en-us/previous-versions/ms809747(v=msdn.10)).
DirectSound는 이 MIDI synth 출력 버퍼의 호환성 제어에 한정합니다.
Microsoft의 [DirectSound 안내](https://learn.microsoft.com/en-us/previous-versions/windows/desktop/mt708933(v=vs.85))에
따라 일반 PCM 출력은 XAudio2를 사용합니다.

## 프로세스별 실제 PCM 대조

`process_audio_capture`는 Windows의 PID별 WASAPI loopback으로 직접 실행한 시험 게임의
프로세스 트리만 녹음합니다. 마이크나 전체 출력 장치를 녹음하지 않습니다.
44100Hz stereo PCM16을 기록하며 빈 출력·불연속·timestamp 오류를 성공적인 분석으로 처리하지 않습니다.
Microsoft의 [프로세스 loopback 매개변수](https://learn.microsoft.com/en-us/windows/win32/api/audioclientactivationparams/ns-audioclientactivationparams-audioclient_activation_params)와
[타임스탬프 기반 synth 이벤트](https://learn.microsoft.com/en-us/windows-hardware/drivers/audio/time-stamped-events)를 참고했습니다.
측정 도구는 기본 빌드와 엔진 배포에 포함하지 않습니다. Python 분석은 로컬 NumPy를 사용합니다.

```powershell
cmake --build build/runtime-native --config Release --target process_audio_capture
python scripts/capture_runtime_waveform.py System RGSS104E.dll build/runtime-native/bin/Release/RGSS104E.dll build/audio-waveform
python scripts/analyze_runtime_waveform.py build/audio-waveform
```

직접 만든 440Hz WAV와 GM organ A4 MIDI를 피치 50/100/150으로 재생합니다.
WAV는 단발 SE, MIDI는 원본에서 확인한 BGM 경로와 반복 구간을 사용합니다.
최초 `build/runtime-waveform-1/`은 원본 MIDI SE 호출 이후 완료되지 않아 비교에서 제외했습니다.
이는 SE 지원 범위를 확정한 결과가 아닙니다.

`build/runtime-waveform-2/comparison.json`은 이전 DLL `b4a6ac61...`의 첫 원본/자체 PCM 쌍입니다.
양쪽 모두 불연속·timestamp 오류 없이 획득했습니다. WAV 주파수는 약 220/440/660Hz였고,
MIDI의 주된 스펙트럼 peak도 각 피치에서 원본과 2Hz 이내였습니다. organ peak는 기본음의
배음일 수 있으므로 peak 값을 MIDI 기본음으로 간주하지 않습니다.
그러나 자체 MIDI 피치 50%의 RMS envelope와 반복 간격이 불안정하게 관찰됐습니다.
이 결과는 해당 이전 DLL의 오디오 호환성 통과가 아닙니다.
`build/runtime-waveform-3/comparison.json`에서도 피치 50% envelope 길이 차이가 반복됐습니다.
완료된 루프의 절반 진폭 길이 중앙값은 두 쌍 모두 원본 1.00초, 자체 0.75/0.77초였습니다.
이는 RMS 경계의 측정값이며 MIDI note-off 시간과 같다고 가정하지 않습니다.
피치별 반복 간격 중앙값만으로는 이 파형 차이를 발견할 수 없으므로 개별 envelope도 유지합니다.

분석은 10ms RMS의 절반 진폭 경계와 스펙트럼 peak를 비교합니다. MIDI note-off 시점 그 자체,
스피커까지의 지연, 전체 파형 동일성, 모든 악기·볼륨·ME 복원·다른 형식의 호환성을 증명하지 않습니다.

## 관리형 MIDI 출력 경로 교정

직접 연결한 버퍼 경로를 Windows의 독립 AudioPath로 바꿨습니다.
`windows_midi_path.h`는 고정된 Windows COM IID의 초기화·경로 생성·객체 조회·종료 호출만
선언하는 자체 어댑터입니다. MIDI 파일 해석·이벤트 순서·상태·루프는 기존 자체 코드를 사용하며,
SMF 해석과 segment 재생은 자체 코드로 처리합니다. 아래 후속 경로에서는 직접 만든 AudioPath
구성 바이트만 Windows의 일반 설정 로더로 읽습니다. 일반 PCM 출력은 XAudio2입니다.

- DLL SHA-256: `52e283f7b0ca018119cb24f00a91fb9c988a9090486c6a1f1b9605ebe72d79b0`.
- `build/runtime-midi-managed-check-4/summary.json`: 피치·볼륨·중첩 드럼·ME 복원 등 기존 오디오 회귀 통과.
- `build/runtime-waveform-11/comparison.json`: 같은 소스와 생성 음원의 원본/자체 12개 독립 프로세스 비교 통과.
  모든 캡처의 불연속·timestamp 오류는 0입니다. WAV와 MIDI 50/100/150의 스펙트럼 peak가
  각각 원본과 2Hz 이내였으며, 각 완료된 음표 envelope와 반복 간격은 원본 기준 50ms 이내였습니다.

| MIDI 피치 | 원본 envelope 중앙값 | 자체 envelope 중앙값 | 원본 / 자체 반복 간격 중앙값 |
|---|---:|---:|---:|
| 50 | 1.00초 | 0.97초 | 1.25 / 1.26초 |
| 100 | 1.005초 | 0.99초 | 1.25 / 1.25초 |
| 150 | 1.02초 | 0.99초 | 1.25 / 1.25초 |

이는 GM organ 단음의 첫 교정 쌍이며 전체 MIDI 호환성 인증은 아닙니다.
이 검사는 뒤의 반복 envelope를 평가했으며 첫 음표 시점 검사는 포함하지 않았습니다.
이후 연속 시험에서 첫 음표 누락이 확인돼 아래 준비 상태 교정을 추가했습니다.
각 피치에서 완료된 음표와 반복 간격을 최소 3개 요구하고 마지막 잘린 음표는 제외합니다.
음표 누락, 중앙값에 가려지는 개별 반복 지연, 짧아진 파형을 거부하는 회귀 검사를 추가했습니다.

시계 배율 조정과 포트 활성화 순서만 바꾼 후보는 파형 검사에서 실패해 채택하지 않았습니다.
`runtime-waveform-6`, `runtime-waveform-7`은 이 실패 후보의 기록입니다.
`runtime-waveform-9`의 원본 MIDI는 화면 업데이트 없이 출력되지 않아 비교에서 제외했습니다.
`runtime-waveform-10`은 창 비활성 대기와 캡처 종료가 겹쳐 비교 근거로 사용하지 않습니다.
현재 도구는 MIDI의 초기 화면 업데이트 완료 후 녹음을 시작하며 각 시험 중 게임 창을 활성 상태로 유지해야 합니다.
8초를 넘긴 시험 단계는 파형 분석에서 거부합니다. 준비 대기와 녹음은 스피커 지연 측정이 아닙니다.

## 첫 합성 버퍼 준비 확인

`52e283f7...`의 연속 시험(`runtime-waveform-13`)과 시작 시점 계측을 추가한 시험
(`runtime-waveform-15`, 별도 실패 후보)은 첫 MIDI 음표를 누락했습니다. 악기 다운로드는
진단에서 0~3ms였고, 미리 다운로드하거나 활성화 순서만 바꾸는 것으로 해결되지 않았습니다.
`runtime-midi-clock-start-trace-2`에서 초기 latency clock이 master와 거의 같다가 첫 버퍼 뒤
70~100ms 앞서는 것을 관찰했습니다. 이는 별도 Python Frida 진단이며 REA 결과나 성능 측정이 아닙니다.

현재 후보 `5bc0a17ab0a17e156399ab35f153247e9fd0d9d8c2823f6ca0dce229db3a24c2`는
이 준비 상태를 확인한 뒤 재생 시계를 시작합니다. 준비 실패는 최대 1초 뒤 오류를 냅니다.
`runtime-midi-ready-api-check-2`의 기존 오디오 회귀와
`runtime-waveform-16/comparison-boundary-fix.json`의 연속 PCM 대조를 통과했습니다.
이전 `comparison.json`의 50ms 경계 수치 오류는 그대로 보존했고 50ms 허용 기준은 유지했습니다.

| MIDI 피치 | 원본 / 자체 첫 onset (API 반환 뒤) | 자체 첫 / 이후 반복 간격 |
|---|---:|---:|
| 50 | 0.279 / 0.113초 | 1.30 / 1.25초 |
| 100 | 0.367 / 0.103초 | 1.30 / 1.24~1.26초 |
| 150 | 0.367 / 0.099초 | 1.30 / 1.25초 |

WASAPI 첫 패킷 QPC를 UTC에 대응시키고 API 반환 시점을 별도로 기록해 초기 무음을 유지합니다.
이는 프로세스 PCM의 반환 이후 시점이며 API 초기화 비용이나 물리 스피커 지연을 포함한 반응 시간 주장이 아닙니다.
첫 onset의 추가 지연은 원본보다 100ms 이하로 제한하며 더 빠른 반환 이후 반응은 허용하고 수치로 남깁니다.
각 완료된 envelope·반복 간격은 계속 50ms 이내를 요구합니다. 정확한 경계의 부동소수점 오차를
거부하지 않도록 1ns 단위로 비교하고 경계 통과/초과 회귀를 검사합니다.
배포 도구의 `--audio-report`도 첫 음표 검사가 없는 이전 보고서를 거부합니다.
이 한 음원 대조는 모든 악기·오디오 형식·ME 복원·음량 파형의 인증이 아닙니다.

## MIDI 음량·ME 후속 교정

기존 개발 패키지 `5bc0a17a...`와 현재 작업 중인 DLL은 구분합니다. 이후 채널별 PCM 시험에서
원본은 ME가 중단한 지속음을 다시 발음하지 않는데 기존 후보는 재발음하는 차이를 발견했습니다.
현재 소스는 중단 시 음표 상태를 지우고 이후 MIDI 이벤트만 재개합니다.
`runtime-audio-channels-2`의 지속음 대조는 이 동작을 확인했으나 반복음 복귀·잔향 검사는 미통과였습니다.

`runtime-original-me-trace-1`에서 원본 InitAudio의 valid=5/features=63과 AudioPath.SetVolume을
확인했습니다. 소스도 이를 사용합니다. AudioPath의 음량을 버퍼 GetVolume 값으로 표시했던 진단은
제거했습니다. 실제 MIDI 이득을 읽는 API는 없으므로 내부 `linear_gain`은 nil입니다.

- `runtime-midi-physical-volumes-1/volumes-comparison-settled.json`:
  DLL `67c65f3ffaf0961a08bd1b6e6ba414693c3045068df595a4fb3d91f15c7d0ecf`의
  0/1/25/50/75/100 볼륨을 원본의 실제 프로세스 PCM과 대조했습니다.
  1.1~1.45초 구간의 정규화 이득이 max(0.002, 원본 이득의 12%) 경계 안이었습니다.
  100 입력을 마지막에 반복해 기준음 안정성도 검사했습니다.
- 초기 `volumes-comparison.json`의 실패는 보존했습니다. 그 분석은 원본의 잔향이 남는
  0.5~1.3초 구간과 이상적인 dB→amplitude 곡선을 실제 synth 출력으로 가정했습니다.
  실제 원본도 낮은 볼륨에서 이 가정을 만족하지 않습니다. 수정 분석은 잔향 이후 구간에서
  **실측 원본**을 기준으로 비교하며 음소거·단조 증가·최종 기준음 안정성도 요구합니다.
  전체 음량은 약 -0.93dB 차이가 남아 있으므로 동일 음색·전체 파형 일치를 주장하지 않습니다.
- `runtime-midi-path-gain-api-check-1/summary.json`: 위 DLL의 voice 회귀 통과.

`runtime-original-me-length-trace-2`는 Segment.GetLength/loop/repeats를 읽기 전용으로 조회했습니다.
직접 만든 4/4 짧은 ME, 4/4 긴 ME, 3/4 ME, 90BPM ME의 세그먼트 길이는 각각
3072/6144/2304/3072 music tick이었습니다. 파일 끝은 별도의 loop end로 남았습니다.
원본의 BGM 복귀 볼륨은 약 1초 동안 단계적으로 올라갔습니다. Frida API 진단이며 성능 계측이 아닙니다.

후속 소스는 BGM 반복에 파일 끝을 유지하고 단발 MIDI는 마지막 마디 끝과 실제 출력 큐 길이를
사용합니다. MIDI BGM 복귀에는 1초 페이드를 적용합니다. `audio_decode_probe`는 원본의 위 네
길이를 별도 고정값으로 검사하고 잘못된 박자를 거부합니다. 곡 중간 박자 변경·모든 SMF,
정지 시 잔향·커스텀 AudioPath 효과의 일치는 아직 검증하지 않았습니다.

## 자체 dry/reverb 구성과 반복 볼륨 교정

`runtime-original-midi-effects-trace-2/3`의 읽기 전용 조회에서 원본의 wet 버퍼와 dry 버퍼가
분리돼 있음을 확인했습니다. dry 인덱스는 1이며 주파수 제어 플래그가 있습니다.
wet에는 Waves Reverb(입력 gain 0, mix 0, time 1000, HF ratio 약 0.001)가 있습니다.
port 요청은 voices=64/groups=8/channels=1/rate=44100/effects=0/features=3이었습니다.
이는 자체 생성 음원의 Windows API 관찰이며 원본 구성 파일이나 디컴파일 결과를 가져온 구현이 아닙니다.

표준 shared reverb 경로는 dry를 선택해도 피치 API를 거부했습니다.
`runtime-midi-reverb-api-check-1`, `runtime-midi-reverb-dry-api-check-1`은 그 실패 기록입니다.
현재 `midi_audio_config.h`는 자체 GUID와 일반 RIFF 형식으로 독립 dry/wet 버퍼를 만듭니다.
소프트웨어 synth와 효과는 Windows 라이브러리이며 MIDI 이벤트/상태/루프는 자체 코드입니다.
초기 생성기의 식별자/플래그 오류와 진단용 Save 미지원은 `runtime-midi-custom-path-api-check-1/`에 보존했습니다.
Windows 설정 객체의 Save는 E_NOTIMPL이므로 설정 왕복 통과라고 주장하지 않습니다.
실제 Load/Create와 재생 성공은 아래 voice/PCM 검사로 확인합니다.

- `1b731c1a2f01c5f8d2bf87530fcf0d0f3c6e7351215fb24769770b30afeb5bbe`:
  `runtime-midi-custom-path-api-check-3`의 기존 오디오 검사 통과.
  `runtime-audio-channels-4`의 지속 organ 단음은 원본과 band 약 -0.038dB, 전체 RMS 약 +0.027dB였습니다.
  반복음 전체 RMS 차이는 약 -0.613dB이며 완전한 오디오 일치 판정은 아닙니다.
- 같은 반복음의 볼륨 50 구간에서 실제 정규화 gain이 약 1.000으로 돌아가는 오류를 발견했습니다.
  원본은 약 0.128이었습니다. 루프의 기본 CC7 복원이 AudioPath 볼륨을 덮어쓰는 것이 원인이었습니다.
  원본 trace의 두 경로는 정상 상태에서 약 61ms 간격으로 볼륨을 다시 적용했습니다.
- 후속 소스는 기본 CC7을 루프마다 덮어쓰지 않고 60ms 주기로 경로 볼륨을 적용합니다.
  DLL `672bdfc5281befe0c1b8c69e5eb1a9ab692275b78bcc5e0c90e6398ef9d78920`의
  `runtime-midi-custom-path-api-check-4` voice 회귀는 통과했으며 PCM 재대조는 별도 진행합니다.

ME 후 복귀 위치와 정지 뒤 잔향은 계속 별도 검증합니다. 기존 패키지의 17개 관문·성능·내구성 결과를
이 해시의 통과 결과로 사용하지 않습니다.

`runtime-audio-channels-5`에서는 볼륨 50의 실제 gain이 지속음 약 0.1295, 반복음 약 0.1266으로
교정됐습니다(원본 약 0.1288/0.1326). 정지 직후 잔향은 여전히 끊겼습니다.
원본은 반복되는 BGM/ME 파일 재생 동안 두 port를 유지하는데, 이 후보는 정지 때 AudioPath를 해제했습니다.
후속 소스는 BGM/BGS/ME의 경로를 채널별로 유지하고 음표만 정지하며, 새 재생에서 경로·악기를 재사용합니다.
idle 경로는 활성 voice 진단에 포함하지 않고 종료·비동기 오류 때 작업 스레드에서 해제합니다.
`runtime-midi-persistent-api-check-1`의 기존 오디오 검사는 통과했으며 실제 tail/호환성은 별도 대조합니다.
이 변경의 SHA-256은 `fff170869a9ec585f21673559b3f1456008f46e0902ee864f04a1ddd746f4460`입니다.

출력 실험 소스를 원복한 뒤 원래 시각이 보존돼 renderer 오브젝트가 다시 컴파일되지 않은 점도 확인했습니다.
`1b731c1a...`/`672bdfc5...`는 8bit flip 출력 실험이 함께 남은 과도기 산출물입니다.
그 PCM 기록을 순수한 baseline renderer 후보의 전체 검증으로 확대하지 않습니다.
renderer를 명시적으로 다시 컴파일한 `1ac93366...`의 소스 체크포인트를 기록한 뒤 위 후속 변경을 빌드했습니다.

## 채널 검사 교정과 채택하지 않은 시퀀서 실험

`runtime-audio-channels-6`에서 경로를 유지한 후보의 정지 후 0.3~0.7초 RMS는
반복음 원본 약 0.001797 / 자체 약 0.001809로 가까워졌습니다. 이는 한 생성 음원의
한 구간 결과이며 잔향 파형 전체의 일치나 모든 악기를 보증하지 않습니다.
기존 검사는 원본의 잔향도 즉시 무음 조건에서 실패시켰습니다. 현재 시험은 정지 구간을
2.4초로 늘려 1.5~2.1초의 무음을 검사하며 초기 잔향 수치는 별도로 남깁니다.
반복음의 ME 복귀도 초기 무음 간격 하나 대신 이후 관찰 구간에서 미래 음이 나오는지 검사합니다.
중단된 지속음의 재발음, 미래 음 누락, 늦게까지 계속되는 소리를 거부하는 회귀 검사를 추가했습니다.
이 기능 검사는 복귀 위상·초기 응답·잔향 파형의 시간 일치 판정이 아닙니다.

Windows의 일반 DirectMusic 시퀀서로 자체 이벤트 스케줄러를 줄이는 실험도 수행했으나 채택하지 않았습니다.
원본의 읽기 전용 `runtime-original-midi-segment-config-1` 추적에서 전체 트랙 대상 초기화,
악기 다운로드, 재생 전 시작점 설정을 확인했습니다. 추적은 정상 종료했고 Frida 오류가 없었습니다.
이는 Frida API 관찰이며 REA Evidence나 후킹 없는 성능 측정이 아닙니다.
Windows SDK의 [표준 MIDI 및 COM 선언](https://raw.githubusercontent.com/milliet/DDReader/master/c/sdk-directx9/Include/dmusici.h)은
호출 규약 확인에만 사용했으며 헤더나 원본 엔진 코드를 재배포하지 않습니다.

- `runtime-audio-channels-8/9/10`: API 상태는 진행해도 실제 초기 MIDI가 누락되거나
  소리 비교가 실패했습니다. 원시 캡처와 채택 거부 사유를 보존했습니다.
- `runtime-midi-segment-cold-held-1`: 출력 시계 준비 검사로 초기 음과 피치를 확인했지만
  ME 뒤 중단된 지속음이 다시 울렸습니다. 원본과 달라서 이 후보도 채택하지 않았습니다.
- 실패 소스·DLL은 비공개 `build/runtime-midi-segment-rejected-1/2`에만 보존했습니다.
  현재 작업 소스는 기존 자체 이벤트 스케줄러와 baseline renderer로 바이트 단위 복구했습니다.
  재빌드 DLL SHA-256은 `7d310bc96dafec44b4084a22387f0694d75a3983186722599e56a0da2c7a0983`입니다.

`runtime-audio-channels-11/channels-comparison.json`은 이 재빌드로 원본과 지속음·반복음 두 경우 모두 통과했습니다.
지속음의 원본 대비 전체 RMS 차이는 약 +0.020dB, 반복음은 약 -0.777dB이며 후자는 유한 구간의
음 간격·초기 위상이 섞인 값입니다. 절대 레벨 일치 판정으로 쓰지 않습니다.
반복음의 정지 1.5~2.1초 RMS는 원본 약 0.0000224 / 자체 약 0.0000228입니다.

`runtime-midi-persistent-sequence-1/comparison.json`도 같은 DLL로 여섯 WAV/MIDI 피치 구간을 통과했습니다.
각 엔진을 한 프로세스에서 연속 재생했고 불연속·timestamp 오류는 없었습니다.
주파수 2Hz, MIDI 음 길이·반복 간격 50ms, 원본 대비 첫 음의 추가 지연 100ms 이내라는
기존 기준을 유지했습니다. 새 MIDI 반복 간격 중앙값은 약 1.255초, 음 길이는 약 1.00~1.01초입니다.
첫 음의 시간은 API 반환 이후 값이며 전체 초기화 시간이나 물리적 스피커 지연으로 해석하지 않습니다.
모든 악기·복귀 위상·잔향 파형 전체를 이 결과로 인증하지 않습니다.

같은 DLL의 `runtime-midi-persistent-volumes-1/volumes-comparison.json`은 MIDI 음량
0·1·25·50·75·100과 마지막 100 복귀를 원본 PCM과 대조해 통과했습니다.
지속 organ 단음의 1.1~1.45초 안정 구간이며, 기존의 실측 기준 허용 오차를 유지했습니다.
전환 순간이나 모든 악기의 음량 일치 검사는 아닙니다.

`runtime-verification-24/summary.json`의 전체 17개 관문과 Python 28개 검사는 이 재빌드로 통과했습니다.
성능·내구성은 해당 해시로 다시 확인해야 합니다.
과거 후보의 통과 기록을 새 바이너리에 이전하지 않습니다. Windows 배율 검사는 사용자 지시로 보류합니다.

## 압축 PCM 형식 확장과 WMA의 원본 피치 동작

2026-10-18. 현재 DLL은 `66aab878a7a83c6eda8083ea0163e8cec8c3da776695569499adacf84aedfd7e`입니다.

WAV/MIDI 외에 동일한 생성 tone 파일의 Ogg·MP3·WMA 피치 50/100/150을 프로세스 PCM으로
대조하도록 확장했습니다. 코덱 파일은 한 번만 생성해 두 엔진에 똑같이 공급합니다.
파일·시험 소스 해시와 각 프로세스의 실제 로드 DLL을 확인하며, 마이크·다른 앱의 소리는 수집하지 않습니다.

`build/runtime-compressed-pcm-1/`은 앞선 출력 교정 DLL의 WMA 50/150 불일치 기록입니다.
WMA에도 440×pitch/100을 기대했던 초기 분석 가정은 원본에서 성립하지 않았습니다.
원본 전용 `runtime-wma-roles-original-1/pitch-oracle.json`에서 BGM/BGS/ME/SE × 50/100/150
모두 약 440Hz임을 추가 확인했습니다. 분석 조건을 실제 원본 계약으로 바꾼 뒤에도 기존 새 엔진의
220/660Hz 출력은 계속 실패하므로, 조건을 바꾸는 것만으로 통과시키지 않았습니다.

`audio_decode.cpp`는 실제 encoded subtype으로 WMA를 식별합니다. `audio.cpp`는 이 경우에만
XAudio2 frequency ratio를 1로 유지합니다. `.wma` 확장자의 유무에 의존하지 않으며
WAV·Ogg·MP3·MIDI의 피치에는 이 조건을 적용하지 않습니다. `Audio.__voices`의 pitch는 기존처럼
요청된 값입니다. 같은 파일 재생 여부 판단도 이번 수정에서 바꾸지 않았습니다.
코덱 식별은 [Microsoft audio subtype 정의](https://learn.microsoft.com/en-us/windows/win32/medfound/audio-subtype-guids)를 사용합니다.

- `build/runtime-compressed-pcm-2/comparison.json`: 최신 DLL의 Ogg·MP3·WMA 9개 구간 모두 통과.
  주파수는 원본과 2Hz 이내이며, 압축 형식의 완료 envelope 길이는 코덱 패딩을 포함한 원본과
  50ms 이내인지 검사합니다. WAV는 기존 생성 길이 기준을 유지합니다.
- `build/runtime-wma-roles-1/wma-roles-comparison.json`: 같은 DLL의 WMA 12개 역할/피치 통과.
  API 반환 후 0.3~0.7초의 실제 주파수를 검사합니다. 최초 원본 전용 검사와 별도의 새 획득입니다.
- 두 대조의 모든 프로세스가 정상 종료했고 불연속·timestamp 오류는 0입니다.
- `build/runtime-verification-26/summary.json`: 같은 DLL의 전체 19개 관문·Python 29개 검사 통과.

재현:

```powershell
python scripts/capture_runtime_waveform.py System RGSS104E.dll build/runtime-native/bin/Release/RGSS104E.dll build/compressed-check --compressed
python scripts/analyze_runtime_waveform.py build/compressed-check
python scripts/capture_runtime_waveform.py System RGSS104E.dll build/runtime-native/bin/Release/RGSS104E.dll build/wma-roles-check --wma-roles
python scripts/analyze_runtime_wma.py build/wma-roles-check
```

WMA 시험은 WMAv2 한 생성 음원입니다. 다른 WMA 코덱·루프 경계·같은 파일 재시작 정책·모든 음량·
물리적 스피커 지연까지 통과한 것으로 확대하지 않습니다. 최신 DLL의 MIDI PCM, 성능과 30분 내구성은
각각 새 해시의 기록으로 확인합니다.

## 현재 아카이브·그래픽 교정 후보의 새 PCM 대조

대상 DLL은 `3868eeceb9fbba5ffc2509cf371e54240db726645dd64145ca4ef5b7f7fffd41`입니다.
이전 후보의 결과를 옮기지 않고 같은 생성 음원·시험 소스를 양쪽 엔진에서 새로 실행했습니다.
모든 기록은 해당 게임 PID 트리의 PCM만 수집하며 마이크나 다른 앱의 소리를 수집하지 않았습니다.

- `runtime-current-pcm-sequence-1/comparison.json`: WAV/MIDI × 피치 50/100/150의 6개 구간 통과.
  스펙트럼 차이 2Hz 이내, 완전한 음표/루프 길이 차이 50ms 이내를 확인했습니다.
  MIDI 첫 음표는 원본 API 반환 기준보다 약 0.21~0.23초 먼저 시작했습니다.
  추가 지연 100ms 기준을 통과했지만 시작 타이밍의 동일성으로 주장하지 않습니다.
- `runtime-current-pcm-compressed-1/comparison.json`: Ogg/MP3/WMA × 세 피치의 9개 구간 통과.
  WMA는 원본처럼 피치를 무시합니다. 압축 패딩은 명목상 1초가 아닌 원본 디코딩 길이를 기준으로 비교했습니다.
- `runtime-current-pcm-wma-roles-1/wma-roles-comparison.json`: WMAv2의 BGM/BGS/ME/SE × 세 피치,
  총 12개 실제 구간이 원본과 약 440Hz로 일치했습니다.
- `runtime-current-pcm-channels-1/channels-comparison.json`: 유지/반복 MIDI와 독립 WAV BGS,
  음량 변경·ME 중단·이후 음표 복귀·전체 정지 조건을 실제 PCM으로 통과했습니다.
- `runtime-current-pcm-volumes-1/volumes-comparison.json`: MIDI 음량 100→0→1→25→50→75→100의
  정착 구간을 원본과 대조했습니다. 원본 기준 허용 오차 max(0.002, 12%) 안입니다.

취득은 모두 정상 종료했고 패킷 불연속·타임스탬프 오류가 없었습니다.
생성한 한정 음원/악기의 기능·정착 구간 대조이며 전체 파형, 모든 악기/코덱 변형,
복귀 위상·과도 잔향·물리 스피커 지연의 동일성을 인증하지 않습니다.
