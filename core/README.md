# Musicoma Core — C1 오프라인 렌더러

`docs/ENGINE.md` 의 1단계. Tracktion·JUCE·sfizz 없이 **표준 C++ + Windows API 만으로** 곡을 WAV 로 렌더한다.
코드는 전부 새로 썼다(클린룸). SFZ 는 sfzformat.com 규격만 보고 구현했고, 동작이 애매한 곳은
**지금 엔진으로 같은 곡을 렌더해 소리를 비교(널 테스트)해서** 맞췄다 — 남의 코드를 읽어서가 아니다.

```
지금 엔진(127.0.0.1:47800) ──(읽기 명령)──> musicoma/core_export.py ──> plan.json ──> musicoma-core.exe ──> out.wav
```

## 하는 일 (C1)

| 부분 | 내용 |
|---|---|
| 렌더 계획 | `musicoma/core_export.py` — 열린 곡을 독립 JSON 으로(스키마는 파일 맨 위). 템포·길이·트랙(볼륨/팬/뮤트/솔로)·체인(악기·이펙트·센드·리턴 순서 그대로)·MIDI 클립(노트·CC·벤드)·오디오 클립(파일·오프셋·게인·페이드·리버스) |
| 곡 그래프 | 트랙 → (센드 → 버스 → 리턴 트랙) → 마스터. 체인 순서대로 처리(엔진처럼 센드는 프리페이더), 볼륨·팬은 체인 뒤, 마스터 볼륨 |
| 자체 SFZ 샘플러 | 파서 + 보이스 엔진(아래 opcode 표). 보이스 256, 서스테인 페달, 벨로시티 곡선, 피치 벤드, 16탭 카이저-sinc 보간, dB 선형 엔벨로프(DAHDSR) |
| 샘플 읽기 | WAV(8/16/24/32 정수, 32/64 float, smpl 루프) · **FLAC 자체 디코더**(libsndfile 과 비트 단위로 같음 확인) |
| 오디오 클립 | 오프셋·길이·게인·팬·페이드 인/아웃(선형)·리버스, 리샘플(같은 sinc) |
| 이펙트 | `lowpass`(2극 LPF/HPF), `compressor`(피드포워드, dB 영역 어택/릴리스) 구현. eq·reverb·delay·chorus·phaser·pitchshift 는 **통과 + 경고** |
| 믹서 | 32비트 float 내부, 24비트 WAV 출력(16/32f 선택). 팬 법칙은 엔진에서 잰 값(`L=1-p, R=1+p`: 가운데 0dB, 끝 +6dB) |
| 속도·메모리 | 트랙마다 스레드(std::thread), 트랙은 16384 샘플 조각으로 흘려 렌더(트랙당 메모리 일정), **샘플 파일은 풀에서 한 번만** 읽어 모든 트랙이 공유, 쓰는 샘플만 읽음 |

## 빌드 · 실행

```bat
core\build.bat                       :: MSVC x64 + Ninja (engine\build.bat 과 같은 도구) → core\build\musicoma-core.exe

core\build\musicoma-core.exe render plan.json out.wav [--sr 48000] [--bits 24|16|32] [--threads N] [--stats s.json] [--tune 키=값]
core\build\musicoma-core.exe sfzinfo 악기.sfz [--key 42]   :: 리전 수·빠진 샘플·무시한 opcode (+ 그 건반의 리전 목록)
core\build\musicoma-core.exe decode 샘플.flac out.wav       :: 디코더 점검(32비트 float)
```

파이썬에서:

```python
from musicoma.core_export import export_plan, save_plan
save_plan(export_plan(), "scratch/core/x/plan.json")          # 지금 엔진에 열린 곡
```

`render` 는 stdout 으로 통계 JSON(트랙별 보이스 수·렌더 시간, 무시한 opcode, 샘플 수/MB, 실시간 배수, 최대 RAM, 경고)을 낸다.
`--tune` / 계획의 `"core_tuning": {...}` 로 측정값(아래)을 바꿔 볼 수 있다.

## 지원하는 SFZ

헤더: `<control> <global> <master> <group> <region> <curve>` (`<effect>` 는 건너뜀). `#include`(어느 줄 중간이든, 루트 SFZ 기준 상대경로), `#define $이름`(줄 순서대로 다시 정의 가능), `/* */` · `//` 주석, 공백이 든 sample 경로, `\` 경로.

| 묶음 | opcode |
|---|---|
| control | `default_path` `set_ccN` `set_hdccN` `note_offset` `octave_offset` (`label_*` 는 무시) |
| 매핑 | `sample` (`*silence` 포함) `key` `lokey` `hikey` `pitch_keycenter` (음 이름 c4=60) `lovel` `hivel` `lorand` `hirand` `seq_length` `seq_position` `trigger=attack/release/first/legato/release_key` `loccN` `hiccN` (`lohdccN`) `on_loccN` `on_hiccN` (CC 로 울리는 리전) `sw_last` `sw_lokey` `sw_hikey` `sw_default` `sw_down` `sw_up` |
| 음량 | `volume` `amplitude` `pan` `amp_velcurve_N` `amp_veltrack` `amp_keytrack` `amp_keycenter` `xfin/xfout_lovel/hivel` `xfin/xfout_lokey/hikey` `xfin/xfout_loccN/hiccN` `xf_velcurve` `xf_keycurve` `xf_cccurve` `rt_decay` `group_volume` `master_volume` `global_volume` |
| 음높이 | `tune` `transpose` `pitch_keytrack` `bend_up` `bend_down` |
| 재생 | `offset` `end` `delay` `loop_mode=no_loop/one_shot/loop_continuous/loop_sustain` `loop_start` `loop_end` (없으면 WAV smpl 루프) |
| 엔벨로프 | `ampeg_delay/attack/hold/decay/sustain/release` |
| 끄기 | `group` `off_by` `off_mode=fast/normal/time` `off_time` `polyphony` `note_polyphony` |
| 필터·EQ | `fil_type`/`fil2_type` (lpf/hpf 1p·2p·4p·6p, bpf_2p, brf_2p) `cutoff` `cutoff2` `resonance` `fil_keytrack` `fil_keycenter` `fil_veltrack` · `eq1~3_freq/bw/gain` |
| CC 모듈레이션 | `X_onccN` / `X_ccN` / `XccN`(v1) + `X_curveccN` — X = amplitude, volume, pan, tune/pitch, offset, delay, ampeg_*, amp_veltrack, cutoff(2), resonance(2), eqN_gain/freq. 음량·팬·크로스페이드는 64샘플마다 CC 를 다시 읽고(곡 중 CC7/CC10/CC11 변화 반영), 나머지는 노트온 때 한 번 |
| 곡선 | 기본 0~6 (선형·양극·반전·반전양극·x²·√x·√(1-x)) + `<curve> curve_index vNNN` |

무시하는 것(세어서 `sfzinfo`/통계에 보고): LFO(`lfoN_*`), flex EG(`egN_*`), `fileg_*`/`pitcheg_*`, ARIA `varN_*`, `width`/`width_onccN`, `*_smoothccN`/`*_stepccN`, `*_shape`, `ampeg_dynamic`, `offset_random`/`amp_random`, `*noise`/`*sine` 같은 내장 파형, `<effect>`.
지금 라이브러리 160개 프로그램 전부 읽힘(빠진 샘플 0). 무시한 것 대부분은 기본 CC 값에서 꺼져 있는 연주용 손잡이(비브라토 깊이 등)라 기본 소리엔 영향이 없다. 예외: meatbass·weresax 의 상시 `lfoN_volume`(트레몰로), meatbass 의 flex EG 피치.

## 엔진과 맞춘 동작 (널 테스트로 측정)

`tests/core_null_projects.py` 가 샘플러만 쓴 곡을 지금 엔진으로 만들고(→ `scratch/core/<곡>/`, 임시 `projects/zz-core-*` 는 지움) 렌더,
`tests/core_null_run.py` 가 같은 계획을 Core 로 렌더해 비교한다(`tests/core_compare.py`: 통합 음량, 옥타브 대역, 시간·이득 맞춘 뒤 잔차).

| 측정으로 확인한 것 | 값 |
|---|---|
| 트랙 팬 법칙 | `L = 1-p, R = 1+p` (가운데 0dB, 끝 +6dB) |
| 마스터 볼륨 기본 | -3 dB (계획에 들어 있음) |
| SFZ 가 CC7 을 안 쓰면 | `amplitude_oncc7=100` (x² 곡선) 을 기본으로 → CC7 기본 100 에서 -4.15 dB. CC10 도 같은 식(양극) |
| amplitude_onccN | 곱 (여러 개면 서로 곱함) |
| 벨로시티 | 곡선 c (기본 (v/127)², `amp_velcurve_N` 은 점 사이 선형, 끝점 (0,0)(127,1)) → `g = 1 - t + t·c` (t = amp_veltrack/100, CC 모듈 포함) |
| 라운드로빈 | 리전마다 카운터, **건반 범위만 맞으면 센다**(벨로시티 층이 달라도) |
| `offset_curveccN` | 무시(선형) |
| SFZ 필터 Q | `Q = 10^(resonance/20)` (0 dB → Q 1) |
| 릴리스·디케이 | 시간 T 동안 e^-9 (≈ -78 dB) 까지 dB 선형 |
| 서스테인 페달 | CC64 ≥ 64. 페달이 눌린 동안 `trigger=release` 는 페달을 뗄 때 울림, rt_decay 는 노트온부터 잰 시간 |
| MIDI 지연 | 1 샘플 |

### 널 테스트 결과 (48 kHz, 마스터 이펙트·리버브 없음)

| 곡 | 내용 | 통합 음량 차 | 잔차 (맞춘 뒤) | 대역 차 (63 Hz ~ 1 kHz) |
|---|---|---|---|---|
| cal-piano | Salamander C4 벨로시티 7단 + 저/고음 | +0.02 LU | **-50.6 dB** | ±0.02 dB |
| cal-pan | 팬 0/-1/+0.5, 볼륨 -6 | +0.02 LU | **-50.2 dB** | ±0.02 dB |
| piano | 화성 진행 8마디 + 서스테인 페달 | +0.02 LU | **-35.3 dB** | ±0.02 dB |
| cal-bass | babyblue 8음 (필터·릴리스) | +0.04 LU | **-32.9 dB** | ±0.04 dB |
| bass | 베이스 라인 4마디 + 피치 벤드 | -0.01 LU | **-32.5 dB** | ±0.03 dB |
| cal-drums | Big Rusty 킥·스네어·햇·탐·심벌, RR | 0.00 LU | **-21.2 dB** | ±0.02 dB |
| drums | 그루브 4마디 + 필인 | 0.00 LU | **-23.1 dB** | ±0.03 dB |
| mix | 위 셋 + 볼륨/팬 | +0.05 LU | **-29.8 dB** | ±0.02 dB |

목표 -40 dB 에 닿은 것은 피아노 단음·팬. 남은 차이의 원인(측정으로 확인):
- **피아노 곡**: 페달 소리 샘플을 `lorand/hirand` 로 무작위 선택 → 엔진과 다른 샘플이 나오는 마디만 차이(마디 가운데는 -50 dB). 무작위라 맞출 수 없음.
- **하이햇·베이스 첫 몇 ms**: 엔진은 `ampeg_release_onccN` 이 있는 리전에서 보이스가 시작된 **첫 오디오 블록(512샘플) 동안 이득이 낮다**(햇 ≈ 0.7배, 블록 경계에서 1.0 으로 점프 / 베이스 ≈ 0.4→1.0, 8 ms). 킥·스네어·탐은 이게 없어 상관 1.000. 참조 엔진의 블록 처리 특성이라 따라 하지 않았다.
- **베이스 릴리스**: 기울기는 같고 엔진이 약 3 ms 늦게 시작(-0.9 dB). 지속 구간은 -44 dB.
- 8 kHz 이상 대역의 큰 숫자(+8~18 dB)는 둘 다 신호보다 100 dB 이상 작은 바닥 잡음이라 무의미.

### 속도·메모리

| 곡 | 길이 | 지금 엔진 렌더 | Core 렌더 | Core 최대 RAM |
|---|---|---|---|---|
| piano | 24.9 s | 3.27 s (7.6×) | 0.58 s (43×) | 184 MB |
| drums | 15.0 s | 3.37 s (4.5×) | 0.18 s (85×) | 57 MB |
| bass | 12.0 s | 0.85 s (14×) | 0.08 s (142×) | 29 MB |
| mix (3트랙) | 12.4 s | 3.23 s (3.9×) | 0.44 s (28×) | 228 MB |
| 벤치 48트랙 × 3분 (피아노·드럼·베이스 16벌) | 179 s | — | **4.0~4.5 s (40~45×)**, 1스레드 50.6 s (3.5×) | **475 MB** (샘플 355 MB) |

(Core 시간에는 샘플 읽기·FLAC 디코딩 포함. 짧은 곡은 처음 읽는 샘플 디코딩이 대부분.)
ENGINE.md 의 지금 엔진 수치: 64트랙 7.5 GB, 실시간의 1.7배.

## 테스트

```
.venv\Scripts\python tests\test_core.py           :: 엔진 없이: 빌드 → 작은 계획(SFZ+오디오 클립+센드/리턴+LPF/컴프) 렌더·검증, 스레드 결정성, 라이브러리 파싱 + 널 수치(참고)
.venv\Scripts\python tests\core_null_projects.py  :: (엔진 사용) 널 테스트 곡 만들기·엔진 렌더·계획 내보내기
.venv\Scripts\python tests\core_null_run.py       :: (엔진 안 씀) Core 렌더 + 비교, --tune 키=값 으로 실험
```

## 아직 안 된 것 (C1 범위 밖 또는 다음)

- 이펙트: EQ(4밴드)·리버브·딜레이·코러스·페이저·피치시프트 — 지금은 통과. 컴프레서는 '간단한 것'이라 Tracktion 컴프와 소리가 같지 않다(널 테스트 대상 아님).
- 템포 변화·박자 변화(첫 템포만), 자동화 곡선(`automation.set`), 클립 루프/MIDI 클립 오프셋, 트랙 폴더/서브믹스.
- SFZ: LFO·flex EG·필터 EG·ARIA var·width/position, 무작위(offset/amp_random), 내장 파형(*sine/*noise 등).
- VST3 악기·이펙트(Surge XT·Dexed·Dragonfly 등) → 무음/통과 + 경고.
- 마스터 LUFS 정규화(`render {lufs}`) — Python `musicoma.master` 쪽에서 처리.

## 다음 단계

| 단계 | 내용 |
|---|---|
| C2 | Steinberg VST3 SDK(MIT)로 Surge XT·Dexed·Dragonfly·Airwindows 호스팅, 파라미터·프리셋·상태 저장 → 지금 곡 전부 C1+C2 로 렌더. 그리고 자체 EQ·리버브 |
| C3 | 실시간: WASAPI(공유/배타)·ASIO 출력, 트랜스포트·미터·루프, MIDI 입력·녹음, 메트로놈 (조각 렌더 구조가 그대로 블록 처리로 이어짐) |
| C4 | `musicoma-engine.exe` 를 Core 로 교체(같은 47800 JSON 규약, 테스트 20개 통과) → Tracktion·JUCE 제거 |
