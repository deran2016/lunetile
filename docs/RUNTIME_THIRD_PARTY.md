# 대체 DLL의 외부 구성 요소

> 독립 소스 저장소 안내: 아래의 이전 DLL 해시·build 경로는 분리 전 검증 기록입니다.
> 원시 자료는 포함하지 않으며, 새 저장소의 실제 빌드·검사 결과는 [VALIDATION.md](VALIDATION.md)에 구분합니다.

자체 엔진 소스와 도구는 저장소 루트의 MIT 라이선스를 적용합니다.
외부 라이브러리의 코드를 자체 코드라고 주장하지 않으며 다음 고정 소스를 사용합니다.

| 구성 요소 | 고정 버전 | 역할 / 라이선스 근거 |
|---|---|---|
| Ruby | 4.0.7 + 기록된 MSVC x86 포팅 패치 | VM·Prism·인코딩. 공식 배포 소스의 COPYING, BSDL, LEGAL |
| StringIO | 3.2.0, 위 Ruby 소스에 포함 | 작업 스레드에서 읽은 세이브의 메모리 스트림. Ruby 라이선스, 소스 해시도 ruby.lock.json에 고정 |
| JSON | 2.18.0, 위 Ruby 소스에 포함 | Ruby 파서·생성기를 DLL과 개발용 Ruby에 정적 포함. Ruby 라이선스. vendor fpconv·jeaiii·Ryu 고지와 라이선스는 배포된 Ruby-LEGAL 원문에 포함 |
| zlib | 1.3.2 | Scripts.rxdata 압축 해제. 공식 소스의 LICENSE |
| libogg | 1.3.6 | Ogg 컨테이너. 공식 소스의 COPYING (BSD 3-Clause) |
| libvorbis | 1.3.7 | Vorbis 디코딩. 공식 소스의 COPYING (BSD 3-Clause) |
| Microsoft VC Runtime / Windows | MSVC 2022 / Windows 11 | 시스템·C/C++ 런타임. 설치된 x86 VC Runtime 사용 |

소스 URL·SHA-256·패치 해시는 `src/runtime/ruby.lock.json`과
`src/runtime/dependencies.lock.json`에 있습니다. 빌드 도우미 MSYS Ruby는 DLL에 포함하지 않습니다.
일반 라이브러리 외의 RPG 엔진 코드를 재사용하거나 원본 RGSS 함수를 전달 호출하지 않습니다.

`scripts/package_runtime.py`는 개발용 DLL 묶음에 공식 소스의 라이선스 문서와
자체 포팅 변경 기록을 넣습니다. 완주·성능 검사를 통과한 공개 릴리스가 아닙니다.
Direct3D 11·GDI·WIC·XAudio2·Media Foundation·WinMM·DirectMusic core/AudioPath·DirectSound·XInput·WinHTTP·Winsock·Schannel은 Windows API를 사용합니다.
MIDI 출력은 Windows의 GM 악기 파일을 읽으며 OS DLL·악기 파일은 재배포하지 않습니다.
오디오 시험 파일 생성용 ffmpeg는 설치된 도구를 사용하며 엔진 DLL에 포함하지 않습니다.
