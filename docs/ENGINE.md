# Musicoma Core — 자체 엔진 계획 (2026-10-15)

## 왜 REA 로 '클론'하지 않나
- 지금 엔진 = Tracktion Engine 3.5 + JUCE 8. **둘 다 소스가 공개**돼 있다(GPLv3 / AGPLv3). 리버스 엔지니어링(REA·Ghidra)은 소스가 없는 바이너리를 읽는 도구라 여기선 쓸 일이 없다.
- 그 소스를 옮겨 오면 '우리 것'이 아니라 **GPL/AGPL 파생물**이 된다(공개 의무). 본인 목표 "남이 만든 게 없게"와 반대.
- Ableton 바이너리를 REA 로 뜯는 건 10-14 에 이미 하지 않기로 함(약관·REA 면책).
- 그래서: **같은 JSON 명령 규약을 그대로 받는 엔진을 처음부터 새로 쓴다**(클린룸). Tracktion 은 '정답지'로만 — 같은 곡을 두 엔진으로 렌더해 소리를 비교(널 테스트)한다.

## 쓰는 것 / 안 쓰는 것
| | |
|---|---|
| 쓰는 것(허용 라이선스) | Steinberg VST3 SDK(MIT, 2025-10~) — 플러그인 호스팅 규격 · Windows WASAPI/ASIO 규격 · SFZ 포맷 규격 · C++ 표준 라이브러리 |
| 안 쓰는 것 | JUCE · Tracktion 코드 · sfizz(BSD 지만 '우리 것' 원칙상 자체 샘플러로 교체) · GPL 전부 |

## 단계
| 단계 | 내용 | 끝나면 |
|---|---|---|
| C1 오프라인 렌더 | 곡 그래프(트랙·클립·센드·마스터), MIDI 스케줄링(노트·CC·벤드), **자체 SFZ 샘플러**(지금 쓰는 라이브러리가 쓰는 opcode 만: key/vel 범위·라운드로빈·엔벨로프·release·#include/#define·amp_velcurve·xf), 오디오 클립(오프셋·페이드·게인), 자체 DSP(EQ·컴프·리미터·리버브) | `render` 가 Tracktion 없이 같은 WAV. 널 테스트 기준: 샘플러만 쓴 곡에서 차이 −40dB 이하 |
| C2 VST3 호스팅 | VST3 SDK 로 Surge XT·Dexed·Dragonfly·Airwindows 로드, 파라미터·프리셋·상태 저장 | 지금 곡 전부 C1+C2 로 렌더 |
| C3 실시간 | WASAPI(공유/배타)·ASIO 출력, 트랜스포트, 미터, 루프, MIDI 입력·녹음, 메트로놈 | 화면 조작이 새 엔진으로 |
| C4 교체 | `musicoma-engine.exe` 를 Core 로 바꿈, 같은 47800 규약 · 테스트 20개 통과 | Tracktion·JUCE 제거 → 배포 라이선스 문제 해소 |

## 지금 엔진의 한계(바꾸며 고칠 것)
- 64트랙에서 RAM 7.5GB — 트랙마다 같은 샘플을 다시 읽음 → Core 는 샘플 풀 공유
- 렌더 = 실시간의 1.7배 → 오프라인은 멀티코어 병렬로

## 규모 감
C1 이 가장 크다(샘플러 + 그래프 + DSP). C1 만 끝나도 Claude 가 곡을 짓고 렌더하는 경로는 Tracktion 없이 돈다.
