# Musicoma

**AI 가 프로듀서로 일하는 설치형 하이브리드 DAW.** Claude(또는 GPT)가 곡을 기획하고, 악기를 *연주*하고, 믹스하고,
보컬은 반주를 *듣고* 부르게 한다. 사람은 같은 화면에서 직접 고치거나 말로 고쳐 달라고 한다.

> *An installable hybrid DAW where an AI agent works as the producer. Songs are built from editable data —
> notes, patterns, instruments, mix — played by real sampled instruments, not generated as a waveform.
> Only vocals are generated, by a model that listens to the beat. Windows, work in progress.*

---

## Suno 와 무엇이 다른가

| | Suno 류 '곡 생성' | Musicoma |
|---|---|---|
| 결과물 | 파형 한 덩어리 | **편집 가능한 프로젝트** — 트랙·MIDI 노트·악기·이펙트·믹스가 그대로 남는다 |
| 악기 | 모델이 흉내 낸 소리 | 실제 샘플 악기(SFZ)·신스(VST3)를 **연주자 모델**이 연주(페달·세기 곡선·슬라이드·미세 타이밍·스윙) |
| 작곡 | 반복·맥락 없는 진행이 잦음 | **레퍼런스 → 콘셉트 → 동기 전개 → 비평** 순서. 곡마다 '사건'(비트 스톱·필터 드롭) 하나 이상 |
| 보컬 | 곡과 함께 생성 | 반주(가이드)를 **듣고** 부르는 생성 — **구간별 녹음**(벌스·훅마다 클립, NG 구간만 다시) |
| 고치기 | 다시 생성 | "2절 훅만 다시", "베이스 조금 더 앞으로" → 그 부분만 |
| 입력 | 텍스트 | 텍스트 · 화면 조작 · **목소리**(말 + 흥얼거림/비트박스를 한 녹음에 섞어도 알아들음) |

## 할 수 있는 것

- **곡 짓기** — 설계서(spec) 한 장 → 곡 전체. 장르 카드(`musicoma/knowledge/styles/`) 10종 + 레퍼런스 카드(실제 곡의 형식·장치, 출처 포함).
- **연주** — 악보를 그대로 찍지 않는다(`musicoma/perform.py`): 피아노 페달·롤, 베이스 음 길이·슬라이드, 드럼 악기별 타이밍·하이햇 강약, 스트링/패드 익스프레션(CC11), 리드 레가토.
- **맥락 있는 작곡** — 콘셉트(한 문장 주제·섹션별 의도·충돌시킬 재료·사건), 동기 하나의 변형으로 선율, 비평가(반복·대비·화성 충돌·동기 사용·정형성) 점수와 지적.
- **보컬** — ACE-Step 1.5 XL(MIT)이 가이드 반주를 듣고 구간마다 테이크를 만들고, 받아쓰기 오류율·목소리 유사도·조성 적합도로 자동 선택. 같은 사람 목소리로 이어 부름. `retake`(그 구간만 다시) · `use_take`(다른 테이크로) · `borrow`(같은 가사 구간의 좋은 테이크).
- **흥얼거림·목소리로 편집** — 🎤: "이 리듬으로 1분 20초에 네 번 넣어줘 — 투두투두…" → 지시와 음을 나눠 듣고, 박자 없이 부른 것도 곡 템포·조성으로 맞춰 MIDI 클립으로.
- **믹스·마스터** — 역할별 음량 비율 자동 밸런스(반복 측정), 4배 오버샘플 리미터로 목표 LUFS.
- **측정(귀)** — 렌더마다 LUFS·트루피크·대역·빈 공기·조성 + 스펙트로그램 PNG. Claude 는 소리를 못 들으니 숫자와 그림으로 판단하고, 최종 판단은 사람 귀.
- **화면** — 편곡/세션 뷰, 피아노롤, 믹서, 녹음·메트로놈·탭 템포, 내보내기, 오른쪽 AI 프로듀서 패널(Claude/ChatGPT 계정 연결).
- **MCP** — Claude Code 가 엔진·곡·보컬·흥얼거림을 도구 41개로 다룬다(`.mcp.json`, `musicoma/mcp_server.py`).

## 지금까지 만든 곡 (작업 기록 · 설계서는 `projects/`, 음원은 저장소에 없음)

| 곡 | 장르 | 메모 |
|---|---|---|
| `kanye-citypop-02-final` | 칩멍크 소울 × 시티팝 | 첫 산출물. 직접 연주한 레코드 → 샘플링 → 붐뱁, 생성 랩 + 하이톤 훅 |
| `musicoma-003-orchestral` | 오케스트라 큐 | 동기 하나에서 선율, 비평 52 → 100 |
| `musicoma-006-last-exit` | 일본 시티팝(영어) | 시대 악기 팔레트 + 구간별 조성 보컬 |
| `musicoma-008-coffee-rings` | 재즈힙합(누자베스 계열, 영어 랩) | 7구간 랩 오류율 0~0.14 |
| `musicoma-009-half-past-three` | 네오소울(남자 노래) | 새 흐름 첫 곡: 처음부터 약 13분 |
| `musicoma-010-acelera` | 브라질리언 퐁크(포르투갈어 구호) | **불합격** — 글 설명만으로 장르를 짐작(아래 '한계') |

## 구조

```
          ┌── 화면 (ui/web, http://127.0.0.1:47802) ── 사람이 직접 조작 · AI 프로듀서 패널 · 🎤
엔진 ◀────┤   WebSocket 47801 / HTTP 47802 (ui/server.py)
(C++)     └── MCP 서버 (musicoma/mcp_server.py) ── Claude Code 가 조작
 │  127.0.0.1:47800, 줄 단위 JSON (`help` 로 명령 목록)
 │
 ├─ Musicoma 엔진 (core/, 자체 C++ — Tracktion·JUCE 없음, 클린룸)
 │    곡 모델·되돌리기·편집 파일(.edit.json) · 자체 SFZ 샘플러·FLAC · 내장 이펙트 8종(EQ·컴프·리버브·딜레이·코러스·페이저·필터·피치)
 │    VST3 호스팅(Steinberg VST3 SDK, MIT) · 실시간 재생(WASAPI)·루프·메트로놈·MIDI 녹음 · 오프라인 렌더(실시간 60배 이상)
 └─ 파이썬 두뇌 (musicoma/)
      arrange(설계서→곡) · perform(연주자) · theory · groove · motif · concept · critic · lyrics
      song(밸런스·렌더) · master · ears(측정) · crate(샘플 가공) · lego(반주 조건 보컬) · hum(흥얼거림)
      knowledge/(장르·레퍼런스·소리·프리셋 카드) · bridges/ace_lego.py(ACE-Step 상주 프로세스)
```

| 경로 | 무엇 |
|---|---|
| `core/` | 자체 엔진. `core\build.bat` → `core/build/musicoma-engine.exe`. 설명 `docs/ENGINE.md` |
| `musicoma/` | 파이썬 두뇌 + MCP 서버 + 지식 카드 |
| `ui/` | 화면 서버와 웹 화면 |
| `app/` | Electron 설치판(번들 Python 런타임 · 첫 실행 음원 받기 · AI 모듈 설치). 설명 `app/README.md` |
| `works/` | 곡 스크립트(설계서를 만들고 짓는 코드). `works/tests/` 일회성 측정 |
| `projects/<곡>/` | `spec.json` 설계서 · `song.json` 요청·조치 기록 · `concept.json` · 편집 파일 · `README.md` |
| `tests/` | 전체 점검(`test_all.py` 22항목) · `golden/` 옛 엔진 기록과 비교(`check_protocol.py` · `check_sound.py`) |
| `docs/` | 설계·측정 기록 |

## 설치

### A. 설치판 (Windows 10/11 x64)
1. `Musicoma Setup 0.4.0.exe` 실행(사용자별 설치, 위치 변경 가능). Python·엔진·코드가 들어 있어 개발 환경이 없어도 된다.
2. 첫 실행 창에서 **기본 음원**(약 7 GB 다운로드, 공식 배포처에서 받음)을 받는다.
3. 보컬까지 쓰려면 **AI 모듈**(선택) — NVIDIA GPU(16 GB 권장, CUDA 12.8 드라이버)와 디스크 약 75 GB:
   ACE-Step 1.5 XL(주 보컬 엔진) · demucs · faster-whisper · VoxCPM2 · SoulX-Singer.
4. 화면 오른쪽에서 AI 계정(Claude / ChatGPT)을 연결하면 말로 곡을 만든다.

설치판 직접 만들기: `cd app && npm install && npm run dist` → `app/dist/Musicoma Setup <버전>.exe`
(번들 Python 을 다시 만들려면 `npm run dist:full`). 자세한 동작은 `app/README.md`.

### B. 개발 환경
```
:: 1) 엔진 의존성: third_party/vst3sdk (github.com/steinbergmedia/vst3sdk, v3.8.1_build_84, MIT —
::    서브모듈 base · pluginterfaces · public.sdk · cmake 만)
:: 2) 빌드 도구: MSVC Build Tools(C:\BuildTools) + CMake + Ninja
core\build.bat
:: 3) 파이썬 3.13 가상환경
py -3.13 -m venv .venv
.venv\Scripts\pip install -r app\runtime\requirements-core.txt
:: 4) 음원·플러그인 받기 (+ 선택: AI 모듈)
.venv\Scripts\python -m musicoma.setup_assets --sounds core [--ai]
:: 5) 실행
.venv\Scripts\python ui\server.py          → http://127.0.0.1:47802
```
Claude Code 에서 이 폴더를 열면 `.mcp.json` 으로 MCP 도구가 등록된다(경로는 각자 환경에 맞게).

## 쓰는 법

- **말로**: 화면 오른쪽 패널 또는 Claude Code 에 — "누자베스 느낌 재즈힙합, 영어 랩으로", "훅만 다시 불러 줘", "베이스 2dB 앞으로".
- **🎤**: 누르고 말하거나 부르고(섞어도 된다) 다시 누름.
- **곡 스크립트**: `python works/musicoma_009_half_past_three.py dry | all v1 | final v2`
  — `dry` 비평만 · `all` 가이드 → [보컬 구간별 녹음 ∥ 반주 빌드·밸런스] → 보컬만 재고 렌더 · `final` 보컬은 그대로 두고 다시 짓기.
- **보컬 구간 고치기**: `lego.retake("projects/<곡>/vocals/vox.json", "chorus2")` 또는 MCP `vocal_retake` / `vocal_use_take`.
- **점검**: `.venv\Scripts\python tests\test_all.py` (엔진·파이썬·프리셋·MCP·화면 22항목) ·
  옛 엔진과 같은지: `tests\golden\check_protocol.py`(명령 77개 응답 모양) · `check_sound.py`(이펙트·믹서 28경우 널 테스트)

작곡 절차(레퍼런스 → 콘셉트 → 동기 → 사건 → 비평 → 가사)와 파일 저장 규칙은 `CLAUDE.md` 에 있다 — 에이전트가 따르는 작업 규약.

## 측정 (2026-10, RTX 5080 16 GB)
- 곡 하나(2분 30초 안팎, 보컬 포함): 처음부터 **약 11~14분**(10-15 초기 약 40분). 반주 빌드는 보컬 생성 시간 안에 숨는다.
- 보컬 테이크: 3개 묶음으로 테이크당 약 8초. 통과 테이크가 모이면 그 구간은 멈춘다.
- 랩 보컬 박자: ±20 ms 안에 떨어지는 비율 25%(사람 래퍼 실측 19%) — 정박에 붙지 않는 사람 느낌.
- 자세한 수치와 실패 기록: `docs/VOCAL.md`, 엔진: `docs/ENGINE.md`, 목소리 입력: `docs/VOICE_UI.md`, 기획: `docs/PLAN.md`.

## 한계 (솔직하게)
- **처음 다루는 장르는 실제 곡을 듣고(측정하고) 시작해야 한다.** 글 설명만으로 만든 브라질리언 퐁크는 "곡 이해도가 떨어진다"로 불합격.
  지금 규칙: 대표곡을 사용자 폴더에서 측정하고, 없으면 먼저 요청한다.
- 한국어 노래 보컬은 아직 부자연스럽다(영어·포르투갈어 랩/노래는 통과).
- 보컬 모델이 가끔 한 구간을 통째로 안 부른다(후렴 1·2 가 24테이크 모두 실패한 적 있음) — 같은 가사 구간의 테이크를 빌려 해결, 원인은 미확인.
- Windows 전용. 보컬은 NVIDIA GPU 필요.
- 실존 가수 목소리 복제는 하지 않는다(스타일 — 말투·강세·태도 — 만). 저작권 있는 녹음은 받지 않는다(사용자 본인 파일만).

## 라이선스
**아직 정하지 않았다** — 정해질 때까지 이 저장소의 Musicoma 코드는 저작권자에게 모든 권리가 있다.
제3자 구성요소는 각자의 라이선스를 따른다: `app/THIRD_PARTY_NOTICES.md`.
2026-10-16 부터 엔진은 자체 코드(클린룸)이고 런타임에서도 GPL 패키지(pedalboard)를 뺐다 — **설치 파일 안에 GPL/AGPL 구성요소가 없다.**
엔진이 쓰는 외부 코드는 Steinberg VST3 SDK(MIT)뿐. 첫 실행 때 받는 플러그인(Surge XT·Dexed·Dragonfly, GPL-3.0)은 따로 배포되는 별개 프로그램이다.
