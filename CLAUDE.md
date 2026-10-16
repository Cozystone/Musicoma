# Musicoma — Claude 가 프로듀서로 일하는 DAW

## 원칙 (본인 지시)
- **인간다운 음악**(10-17, `musicoma/knowledge/principles.md` — 콘셉트 문맥에 항상 들어감): Suno 의 어색함은 '너무 완벽한 진행·구조'에서 온다.
  후렴을 서두르지 않고, 듣기 좋은 코드·중독성 후크·풍성함을 기본값으로 두지 않는다. 살짝 어설픈 보컬·독특한 음정·거친 숨·불안정한 톤은
  지울 결점이 아니라 개성일 수 있다. 비평 항목: "이 사람의 것인가 / Suno 같은가".
- **진짜 프로듀서처럼.** 곡·반주·샘플 원곡은 직접 작곡·편곡·연주(MIDI + 악기)로 만든다. Suno 류 '곡 생성' 금지.
- **예외: 보컬만** — 반주를 듣고 부르는 ACE-Step 1.5 lego(구간별 테이크, `lego.py`), 악보 가창 SoulX-Singer, 목소리 생성·랩 VoxCPM2.
  목소리 복제는 본인 또는 동의받은 목소리만. 기기 사양에 따라 설정이 바뀐다(`hardware.py`). YuE2 는 비상업 가중치·반주 입력 불가로 제외(10-17).
- **악기 보컬로이드**(10-17): 선율 녹음(흥얼거림·노래·다른 악기)을 음정·세기·비브라토 그대로 다른 악기 음색으로 — `timbre.py`(MCP `timbre_transfer`),
  우리 샘플에서 음색 틀을 뽑아 합성. 생성 모델 cover 는 음정 추종 33% 라 쓰지 않는다.
- 저작권 있는 녹음을 받아오지 않는다. 본인 음원은 `sounds/inbox/` — 본인 것으로 보고 그대로 쓴다. 레퍼런스는 `listen_reference` 로 듣고 숫자만 남긴다.
- Ableton 바이너리·컴파일된 스크립트(.pyc) 디컴파일·에셋 복사 금지. 화면·동작을 '쓰면서' 참고하고, REA 는 우리 산출물 검증·본인 `.als` 가져오기에.
- 모든 장르를 같은 방식으로: 장르 카드(`musicoma/knowledge/styles/*.yaml`)를 읽고 설계서(spec)를 쓴다. 카드가 없는 장르는 새 카드를 먼저 쓴다.
- 필요한 악기가 없으면 `packs`(즉석 설치)로 받는다 — 자유 라이선스만, 출처 기록.

## 구조
| 경로 | 무엇 |
|---|---|
| `core/` | 자체 C++ 엔진(10-16, Tracktion·JUCE 없음 — 클린룸). `core\build.bat` → `core/build/musicoma-engine.exe`. 127.0.0.1:47800 줄 단위 JSON. `help` 로 명령 목록 |
| `musicoma/` | 파이썬 두뇌. `arrange`(설계서→곡) · `song` · `theory` · `groove` · `compose` · `crate`(샘플) · `transcribe` · `ears`(측정) · `master` · `voice` · `knowledge` |
| `musicoma/mcp_server.py` | MCP 도구(`.mcp.json` 로 이 폴더에서 자동 등록) |
| `sounds/` | `sfz/`(피아노·드럼·오케스트라) · `plugins/vst3/`(Surge XT·Dexed·Dragonfly·Airwindows) · `crate/`(가공 샘플) · `voices/` · `inbox/` |
| `projects/<곡>/` | `spec.json`(설계서) · `song.json`(메타·요청 기록·버전) · `<곡>.edit.json` · `renders/` |

파이썬은 `D:/0.Musicoma/.venv/Scripts/python.exe` (PYTHONIOENCODING=utf-8).

## 작곡 = 맥락 (본인 10-15: "맥락 있게 작곡하는 게 가장 중요, AI 슬롭 같지 않게")
0. **레퍼런스 먼저**(MCP `references`, 본인 10-15: "기존 곡의 레퍼런스·형식·스타일을 찾고 시작. 사용자도 그렇게"): 장르 대표곡 3~5개의
   템포·키·구조·편곡 장치·배울 점(출처 포함). 카드가 없거나 얇으면 WebSearch 로 조사해 `knowledge/references/<장르>.yaml` 로 저장.
   본인 음원 폴더에 있으면 `analyze_ref` 로 실측. 형식·장치만 배우고 선율·가사는 가져오지 않는다. 콘셉트의 references 에 인용.
   **처음 다루는 장르는 실물을 들은(측정한) 뒤에 짓는다**(10-16 「Acelera」 불합격 — 글 설명만으로 몬타젱 퐁크를 짐작해
   "곡 이해도가 떨어진다"). 폴더에 없으면 사용자에게 대표곡 2~3개를 요청하고, 글만으로 가야 하면 그 사실을 먼저 말한다.
1. **콘셉트 먼저**(MCP `concept`): thesis 한 문장 · arc(섹션별 의도·에너지) · motif · collision(먼 재료 2~3) · constraints · events. 노트는 그다음.
2. **동기 전개**(`motif_develop`): 선율은 동기의 변형에서. 같은 4마디 복사 금지. 강박 음은 화음 음으로(자동 fit).
3. **사건**: 곡마다 '그 순간' 최소 하나 — 설계서 `events`(stop / filter). 본인 기준곡: Nujabes「Luv(sic)」(장르 발명) · 이찬혁「멸종위기사랑」(들어본 적 없는 진행) · Kanye「On Sight」(비트 체인지).
4. **비평**(`critique`): 짓기 전·후 매번. 숫자 문제 + 질문에 직접 답하고 고친다. 본인 취향(D:/0.Creative/IDENTITY) 과 어긋나면 고친다.
5. **가사**: 본인이 안 주면 콘셉트에서 새로 쓴다(원작 가사 인용 금지). 노래 = 음표당 음절(영어 하이픈 `ci- ty`, 한국어 글자), 랩 = 4박에 9~13음절, 2줄씩 운. `critique` 의 가사 검사 통과.
6. 시안은 축이 다른 2~3안으로(무엇을 바꿨는지 한 줄씩).

## 파일 저장 규칙 (본인 10-15: "외부 공개 시 쓸데없는 파일이 섞여 알아보기 어렵지 않게")
- 곡 폴더 `projects/<곡>/` 에 보이는 것 = `README.md`(자동) · `spec.json` · `song.json` · 편집 파일 · `renders/`(결과 wav+png) · `vocals/`(최종 보컬) · `versions/`.
- 중간 파일(줄별 랩 원본·가이드·테이크·SoulX/SVC 작업·측정 스템·로그)은 **반드시 `.work/`** — 코드에서는 `musicoma.layout.work_dir(out, kind)`.
- 테스트·실험·A/B 는 곡이 아니다 → `scratch/`(`layout.scratch(...)`). `projects/` 에 zz-* 를 새로 만들지 말 것.
- 작업을 마치면 `tidy`(MCP) 로 정리 + README 갱신. 지우지 않고 옮기기만 한다.
- 새 곡 스크립트는 `works/<곡>.py` 하나(설계서를 만들고 짓는 코드). 일회성 측정 코드는 `works/tests/`.

## 일하는 순서
1. 요청 → `knowledge_style` 로 카드 찾기(여러 장르 섞임이면 둘 다 읽기). 이어지는 요청이면 `song_status` 먼저.
2. 설계서(spec) 작성 → `build_spec`. 위치는 박(4/4: n마디 = 4n박), 섹션 기준.
3. `render` → 리포트 숫자 + PNG 를 **반드시 Read 로 본다**. `render_stems` 로 트랙별 대역 확인.
4. 문제(issues, 대역 치우침, 밸런스)를 고쳐 다시 짓기. 장르 카드의 balance_lu · target_lufs 기준.
5. 본인에게: 무엇을 했는지 + 숫자 + 들어볼 파일 경로. `song_log` 로 요청·조치 기록.

## 연주 (가장 중요 — Suno 와의 차이)
- 악보를 그대로 찍지 않는다. `build_spec` 은 기본으로 연주자 모델(perform)을 입힌다: 피아노 페달·롤·세기 곡선, 베이스 슬라이드·음 길이,
  드럼 악기별 미세 타이밍·하이햇 강약·필 크레셴도, 스트링/패드/브라스 익스프레션(CC11), 리드 레가토·스쿱.
- 곡 전체 `feel`(straight/laid_back/pushed/loose/tight)·`intensity` 를 장르에 맞게 정한다. 붐뱁·로파이·네오소울 = laid_back, 하우스·트랩 = tight.
- 트랙 `role` 을 정확히 적어야 맞는 연주자가 붙는다(piano/keys/bass/drums/strings/pad/brass/lead/guitar/pluck). 직접 정하려면 tracks.<이름>.perform_role.
- 샘플·찹 트랙은 연주 모델을 붙이지 않는다(자동).

## 미세조정
- 말 → `knowledge_tweak` → **한 축, 작은 단계**만 → 다시 렌더 → 전/후 숫자로 보고.
- 어휘집에 없거나 모호하면 하나만 되묻는다(소리/박자/화성/배치 중 무엇).
- "좋다" → `snapshot`. "아까가 낫다" → `engine edit.undo` 또는 이전 버전 spec.

## 알려진 함정
- 엔진이 쓰고 있는 오디오 파일은 덮어쓸 수 없다 → crate 는 잠기면 `__2` 이름으로 새로 쓴다.
- 내장 EQ 의 "Low-pass/High-pass" 는 실제로 로우/하이 **셸프**다(이름만 그렇다).
- 엔진 렌더의 LUFS 정규화는 리미터가 없어 작게 끝난다 → `Song.render(lufs=)` 가 `master.py` 로 맞춘다.
- `balance` 이동 한계 ±12dB 에 걸리면 소리 자체(패치·음역·세기)를 바꿔야 한다는 신호.
