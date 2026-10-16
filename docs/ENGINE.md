# Musicoma 엔진 — 자체 엔진(2026-10-16 교체 완료)

본인 지시(10-16): "Tracktion Engine(GPL-3.0)과 JUCE(AGPL-3.0)에 의존하지 않아도 되게".
→ `core/` 의 자체 C++ 엔진이 `musicoma-engine.exe` 를 대신한다. 같은 127.0.0.1:47800 줄 단위 JSON 규약이라 파이썬·화면·MCP 는 그대로.

## 클린룸 원칙
- Tracktion·JUCE 소스는 읽지도 옮기지도 않았다(옮기면 GPL/AGPL 파생물). REA 로 바이너리를 뜯는 것도 같은 이유로 안 함.
- 기준은 **바깥에서 본 동작만**: 옛 엔진에 명령을 보내 응답을 기록하고(`tests/golden/protocol.json`, 77개), 시험 신호를 이펙트에 통과시켜
  소리를 기록한 것(`scratch/golden/fx/`, 28경우)과 같아지게 맞췄다(널 테스트·주파수 응답·엔벨로프).
- 쓰는 외부 코드: Steinberg **VST3 SDK 3.8.1 (MIT)** — 플러그인 호스팅 규격(base · pluginterfaces · public.sdk 일부). 그 밖엔 C++ 표준 라이브러리 + Windows API.

## 구조 (`core/src/engine/`)
| 파일 | 하는 일 |
|---|---|
| `device.h` | 악기·이펙트 공통 인터페이스(prepare · process · params · setParam · state · loadFile · programs · showEditor) |
| `eng_model.h` · `eng_project.cpp` | 곡 모델(트랙·체인·클립·오토메이션), 응답 모양(edit.info 등), 편집 파일 `projects/<곡>/<곡>.edit.json`, 되돌리기(스냅숏, 같은 디바이스 인스턴스 재사용) |
| `eng_commands.cpp` | 명령 45개(옛 프로토콜 그대로) · 렌더 |
| `eng_graph.*` | 블록 처리: 클립 → MIDI 이벤트(같은 음 겹침은 앞 음을 뒤 음 시작에서 끊음) → 체인 → 볼륨·팬(L=1-p, R=1+p) → 센드/리턴 버스 → 마스터(-3 dB 기본) |
| `eng_realtime.cpp` | 실시간: 안쪽은 늘 48 kHz, 장치 레이트(원격 오디오 44.1 kHz 등)로는 마지막에 3차 보간. 루프·메트로놈·MIDI 입력 모니터·녹음(테이크 → 클립). 출력 장치가 없으면 무음 시계로 계속 돎 |
| `eng_server.cpp` | TCP 서버 · 변경 알림(`{event:"changed"}`) · 루트 찾기 |
| `eng_devices.cpp` | SFZ 샘플러(Core C1 샘플러) · 내장 이펙트 · VST3 · send/return |
| `fx_*.cpp` | 내장 이펙트 8종(아래 측정) |
| `vst3_*.cpp` | VST3 호스팅 — 자체 DLL 로더(UTF-16 경로), 플러그인 호출은 창 스레드에서, 플러그인이 죽어도 엔진은 산다(오류 문자열) |
| `io_*.cpp` | WASAPI 공유 모드 출력(MMCSS) · WinMM MIDI 입력 |
| `eng_midifile.cpp` | SMF 0/1 → MIDI 클립 |

빌드: `core\build.bat` → `core/build/musicoma-engine.exe`(+ `musicoma-core.exe` 렌더 계획 CLI, `test-fx`·`test-vst3`·`test-io` 모듈 시험).

## 측정 — 옛 엔진(Tracktion)과 같은가 (10-16)
| 항목 | 결과 |
|---|---|
| 명령 응답 모양(`tests/golden/check_protocol.py`) | 77/77 같음 |
| 믹서·팬·버스(`check_sound.py`) | 잔차 -117 ~ -129 dB (사실상 같은 비트) |
| EQ 6경우 · 로우패스 3 | -79 ~ -127 dB · -92 ~ -119 dB |
| 컴프레서 4 | -62 ~ -124 dB (검출 = |L+R|/2 → 800 Hz 평활, 문턱 기준 어택/릴리스, 선형 진폭 정특성 — 측정으로 찾음) |
| 딜레이 2 | -122 dB (150 ms 고정, 등전력 믹스) |
| 리버브 3 | -47 ~ -53 dB (Freeverb 구조, 옥타브별 RT60 오차 ≤ 7%) |
| 페이저 · 코러스 | -44 dB · -25 dB (코러스는 옛 엔진 float 위상 누적까지는 재현 안 함, 음악 구간 -48 dB) |
| 피치 시프터 | 방식이 달라 널 불가(위상 보코더) — 음높이 오차 0 센트, 음 순도 오히려 높음, 지연 1536 샘플 보고 |
| VST3 | 8개 전부 로드·처리·상태·창. Dexed -112.5 dB(같음), Dragonfly Hall 음량 +0.06 dB |
| 전체 점검 `tests/test_all.py` | 22/22 |
| 실제 곡 다시 짓기(009 「Half Past Three」) | 2분 33초(옛 엔진 3분 41초). 대역 분포 ±1 dB 안. 조용한 틈의 꼬리만 몇 dB 더 빨리 사라짐 |
| 렌더 속도 | 2분 39초 곡(플러그인 제외) 2.4초 — 실시간 약 67배 |

## 바뀐 점·주의
- **Surge XT 패치(.fxp)가 이제 진짜로 적용된다.** 옛 엔진은 `device.load_file` 이 "loaded" 라고 답하고도 파라미터를 바꾸지 않았다
  (기본 Init Saw 소리 그대로) — 그동안 Surge 를 쓴 트랙(009 오르간, 006 브라스 등)은 기본 소리였다. 새 엔진에서 다시 지으면 소리가 달라진다(맞는 쪽).
- VST3 파라미터 `id` = VST3 ParamID(옛 엔진은 플러그인 순번). 이름으로 찾는 건 그대로 된다.
- 내장 신스 `4osc`(Tracktion 것)는 없다 — 신스는 Surge XT/Dexed.
- 컴프레서 `threshold`/`ratio` 를 사람 단위(dB, N:1)로 보고한다(옛 엔진은 내부 단위).
- 편집 파일 형식이 바뀌었다: `.tracktionedit` → `.edit.json`. 옛 곡 26개는 `python -m musicoma.convert_edit` 로 옮겨 둠
  (옛 엔진이 떠 있어야 동작 — 이제는 옮길 필요가 생기면 spec.json 으로 다시 짓는다). 오토메이션은 옮기지 못함(다시 지으면 생김).
- 피치 시프터 지연 보정(PDC)은 아직 없음 — 지연 32 ms 가 그대로 남는다(곡에서 거의 안 씀).
- 실시간 MIDI 입력은 장치가 없는 PC 라 실제 건반으로는 시험하지 못함(목록·오류 경로만 확인).
