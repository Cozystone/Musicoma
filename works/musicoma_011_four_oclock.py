"""musicoma-011 「Four O'Clock」 — 외주(한국 얼터너티브 팝 록 밴드 사운드, 140 BPM, 영어 남자 보컬). 10-17 재작업.

앱 AI 의 1차(네 시의 운동장)가 불합격(포크송 같다 · 단조롭다 · 한국어 보컬 깨짐 · 악기 라인업 틀림)이라
이번엔 사람이 직접: 악기 = 드라이브 기타 3대(파워·크런치·리드) + 록 드럼(크래시·라이드) + 피크 베이스 + 피아노 악센트,
멜로디·가사 = 음표 단위로 직접 씀(생성기 안 씀), 보컬 = ACE-Step lego 영어(구간별 녹음).

    python works/musicoma_011_four_oclock.py dry        비평만
    python works/musicoma_011_four_oclock.py band v1    반주만(빠른 확인)
    python works/musicoma_011_four_oclock.py all v2     보컬까지
    python works/musicoma_011_four_oclock.py final v3   보컬 그대로 두고 다시 짓기
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from musicoma import arrange, concept as concept_mod, critic, lego, theory

NAME = "musicoma-011-four-oclock"
BPM, KEY = 140, "A major"     # 10-17 본인: "템포도 더 빨라도 되겠어, 밴드 특유의 짜릿함" (125 → 140; LUCY 아니근데진짜 ~143)
SPB = 60 / BPM

# ───────── 가사(영어) — 구체적 장면, 사람 말투, 완벽한 라임 피함 ─────────
LYR = {
    "verse1": "Two bikes leaning on the fence, your lock was busted anyway\n"
              "Four o'clock cut the goalpost in half, we didn't say a thing\n"
              "You kept flicking that lighter, you never even smoked\n"
              "I counted streetlights coming on like that could make it stay",
    "pre1": "Nobody told us the hours were counting down\n"
            "We just figured summer was a place you could walk back into",
    "chorus": "So if I'm standing on that road again\n"
              "Would you still be laughing with your head thrown back\n"
              "We got the words wrong, sang it loud anyway\n"
              "Four o'clock, the light goes long, and we don't go home",
    "verse2": "Chalk lines fading on the court, the net's been gone for years\n"
              "You're in another city with a name I had to learn\n"
              "I still take the long way past the school, I don't know why",
    "pre2": "Nobody told us the hours were counting down\n"
            "And now we know, so we just talk a little quieter",
    "bridge": "I know there's no way back there\n"
              "I still keep the busted lock in a drawer",
}

# ───────── 멜로디(직접 씀) — 줄마다 16박(4마디), 뒤 절반은 쉬어서 밴드가 대답할 자리 ─────────
MEL = {
    "verse1": ["A3:.5 A3:.5 B3:.5 C#4:1 A3:.5 r:.5 E3:.5 F#3:.5 A3:.5 A3:1 B3:.5 A3:.5 F#3:1.5 r:5.5",
               "C#4:.5 C#4:.5 B3:.5 A3:1 F#3:.5 r:.5 A3:.5 A3:.5 B3:.5 C#4:1 E4:.5 C#4:.5 B3:1 r:6",
               "A3:.5 A3:.5 B3:.5 C#4:.5 E4:1 C#4:.5 r:.5 B3:.5 A3:.5 F#3:1 r:7.5",
               "E4:.5 E4:.5 D4:.5 C#4:1 B3:.5 r:.5 A3:.5 B3:.5 C#4:1.5 B3:.5 A3:1.5 r:6"],
    "pre1": ["F#4:.5 F#4:.5 E4:.5 D4:1 C#4:.5 B3:.5 C#4:1 D4:1 r:.5 B3:.5 C#4:1.5 r:5.5",
             "E4:.5 E4:.5 E4:.5 F#4:1 E4:.5 D4:.5 C#4:1 B3:1 C#4:.5 D4:.5 E4:1.5 r:5"],
    "chorus": ["E4:.5 F#4:.5 A4:1.5 A4:.5 G#4:.5 E4:1 r:1 C#4:.5 E4:.5 F#4:2 r:6",
               "F#4:.5 A4:.5 A4:.5 G#4:1 F#4:.5 E4:.5 C#4:.5 E4:1.5 r:.5 B3:.5 C#4:.5 D4:1.5 r:6",
               "E4:.5 E4:.5 F#4:1 r:.5 E4:.5 E4:.5 A4:1.5 r:1 r:7",
               "F#4:.5 F#4:.5 E4:.5 D4:.5 C#4:1 B3:.5 C#4:.5 r:.5 A3:.5 B3:.5 C#4:1.5 B3:.5 A3:2 r:5.5"],
    "verse2": ["A3:.5 A3:.5 B3:.5 C#4:1 A3:.5 r:.5 E3:.5 F#3:.5 A3:.5 B3:1 A3:.5 F#3:1.5 r:6",
               "C#4:.5 C#4:.5 B3:.5 A3:1 F#3:.5 r:.5 A3:.5 B3:.5 C#4:1 E4:.5 C#4:.5 B3:1.5 r:6",
               "E4:.5 E4:.5 D4:.5 C#4:1 B3:.5 r:.5 A3:.5 B3:.5 C#4:1.5 B3:.5 A3:2 r:5.5"],
    "pre2": ["F#4:.5 F#4:.5 E4:.5 D4:1 C#4:.5 B3:.5 C#4:1 D4:1 r:.5 B3:.5 C#4:1.5 r:5.5",
             "E4:.5 E4:.5 E4:.5 F#4:1 E4:.5 D4:.5 C#4:1 B3:1 r:.5 A3:.5 B3:2 r:5"],
    "bridge": ["C#4:1 C#4:.5 B3:.5 A3:1.5 r:.5 F#3:.5 A3:.5 B3:2 r:7.5",
               "C#4:.5 C#4:.5 D4:.5 E4:1 D4:.5 C#4:.5 B3:1 A3:1 r:.5 B3:.5 C#4:2.5 r:5"],
}

CONCEPT = {
    "thesis": "운동장 끝에 자전거를 세워 두던 네 시 — 돌아갈 수 없는 건 그 여름이 아니라 그때의 우리. 밝은 밴드 사운드 위에 씁쓸한 말",
    "arc": [{"section": "intro", "intent": "리드 기타 리프 혼자 → 4마디 뒤 밴드 전부", "energy": 0.6},
            {"section": "verse1", "intent": "속삭이듯 — 크런치 기타 뮤트, 피아노가 줄 끝마다 대답", "energy": 0.35},
            {"section": "pre1", "intent": "쌓기 — 4분 킥, 스네어 빌드, 베이스 8분", "energy": 0.6},
            {"section": "chorus", "intent": "폭발 — 파워코드 벽, 크래시, 보컬 한 옥타브 위, 하모니", "energy": 1.0},
            {"section": "post", "intent": "리프로 숨 돌리기", "energy": 0.7},
            {"section": "verse2", "intent": "조금 더 차오른 절(12마디)", "energy": 0.5},
            {"section": "bridge", "intent": "피아노와 목소리만 — 가장 조용한 곳", "energy": 0.25},
            {"section": "build", "intent": "스네어 16분 롤 + 기타 트레몰로 → 한 박 정적", "energy": 0.7},
            {"section": "stabs", "intent": "밴드 전체 유니즌 '딴딴딴딴딴' 두 마디 — 끊었다가 때리는 클라이맥스", "energy": 1.0},
            {"section": "chorus_last", "intent": "다 쌓음 + 리드 기타 대선율", "energy": 1.0},
            {"section": "outro", "intent": "리프 네 번, 마지막 한 방", "energy": 0.8}],
    "motif": {"melody": "E5:.5 C#5:.5 A4:1 r:.5 B4:.5 C#5:1", "why": "리프 = 내려왔다 되돌아 올라가는 자전거 바퀴"},
    "collision": ["DAY6·LUCY 식 밝은 장조 밴드 팝", "운동장·네 시 빛의 구체적 장면", "라이브 밴드의 거친 가장자리(드라이브·크래시)"],
    "constraints": ["후렴은 I–V–vi–IV 를 쓰되 후반에 bVII 로 한 번 비튼다", "절은 반 비워 두고 기타·피아노가 대답한다",
                    "보컬 멜로디·가사는 직접 쓴다(생성기 금지)", "의뢰 조건(캐치한 후렴·하모니·풍성함) 우선"],
    "events": [{"section": "pre1", "at": 30, "length": 2, "type": "stop", "why": "후렴 들어가기 전 두 박 딱 끊기"},
               {"section": "pre2", "at": 30, "length": 2, "type": "stop", "why": "같은 자리 — 두 번째는 기대하게"},
               {"section": "chorus", "at": 30, "length": 2, "type": "stop", "why": "후렴 한가운데 밴드가 빠지고 목소리만 두 박"},
               {"section": "build", "at": 15, "length": 1, "type": "stop", "why": "스탭 앞 한 박 정적"}],
    "irregular": [{"what": "2절 12마디", "why": "할 말이 짧다"}, {"what": "브리지 피아노+목소리만", "why": "가장 조용한 고백"}],
    "references": "knowledge/references/korean-band-pop.yaml — DAY6 Happy · LUCY 아니 근데 진짜·조깅 등 · 유다빈밴드 항해",
    "not": ["클린 아치톱만", "순차 진행 선율", "4마디 복사", "추상명사 가사"],
}

SECTIONS = [{"name": "intro", "bars": 8}, {"name": "verse1", "bars": 16}, {"name": "pre1", "bars": 8}, {"name": "chorus", "bars": 16},
            {"name": "post", "bars": 4}, {"name": "verse2", "bars": 12}, {"name": "pre2", "bars": 8}, {"name": "chorus", "bars": 16},
            {"name": "bridge", "bars": 8}, {"name": "build", "bars": 4}, {"name": "stabs", "bars": 2}, {"name": "chorus_last", "bars": 16}, {"name": "outro", "bars": 8}]

PROG = {"verse": "Imaj7 V vi7 IVmaj7 Imaj7 V ii7 V7sus4", "pre": "ii7 iii7 IVmaj7 V7sus4 ii7 IVmaj7 V bVII",
        "chorus": "I V vi IV I V ii7 V I V vi IV ii7 IV bVII V", "bridge": "vi IV I V vi IV ii7 V7sus4", "outro": "I V vi IV"}

RIFF_A = "E5:.5 C#5:.5 A4:1 r:.5 B4:.5 C#5:1 | F#5:.5 A5:.5 F#5:1 C#5:.5 B4:.5 A4:1"
RIFF_B = "E5:.5 C#5:.5 A4:1 r:.5 B4:.5 C#5:1 | D5:.5 E5:.5 F#5:1.5 E5:.5 C#5:1"
RIFF_HI = "A5:.5 G#5:.5 E5:1 r:.5 F#5:.5 G#5:1 | A5:.5 B5:.5 A5:1 F#5:.5 E5:.5 C#5:1"      # 마지막 후렴 대선율(한 옥타브 위 변형)
COUNTER = "r:2 E5:.5 F#5:.5 A5:1 | r:1 G#5:.5 F#5:.5 E5:1 C#5:1"                           # 후렴 리드(보컬 쉬는 자리에)
# 바이올린 선율(직접 씀) — 절: 노래가 쉬는 뒤 절반에 대답(8마디 주기), 프리: 긴 활로 오르기, 후렴: 훅을 한 옥타브 위 + 쉬는 자리 채움
VLN_VERSE = "r:8 | r:2 C#5:1 B4:1 | A4:2 F#4:2 | r:4 | r:8 | r:1 E5:1 D5:1 C#5:1 | B4:2 A4:1 B4:1 | C#5:4"
VLN_PRE = "D5:4 | E5:4 | F#5:2 E5:2 | D5:4 | B4:4 | D5:4 | E5:2 F#5:2 | G5:4"
VLN_CHORUS = "E5:.5 F#5:.5 A5:1.5 A5:.5 G#5:.5 E5:1 | r:1 C#5:.5 E5:.5 F#5:2 | r:1 E5:.5 F#5:.5 A5:1 G#5:1 | F#5:2 E5:2 | r:4 | r:4 | A4:2 B4:2 | C#5:2 D5:2"
VLN_BRIDGE = "E5:4 | D5:2 C#5:2 | B4:4 | A4:2 B4:2 | C#5:4 | D5:2 E5:2 | F#5:4 | E5:2 D5:2"

DR = {
    "verse": {"kick": "x.......x.x.....", "snare": "....x.......x...", "hat": "x.x.x.x.x.x.x.x."},
    "verse_light": {"kick": "x...............", "snare": "................", "hat": "x.x.x.x.x.x.x.x."},   # 1절 앞 8마디: 킥 한 번·햇만(속삭임)
    "pre": {"kick": "x...x...x...x...", "snare": "....x.......x...", "hat": "x.x.x.x.x.x.x.x."},
    "chorus": {"kick": "x.....x.x.....x.", "snare": "....x.......x...", "hat": "x.x.x.x.x.x.x.x."},
    "last": {"kick": "x..xx..x.x..x.x.", "snare": "....x..o....x.o.", "hat": "x.x.x.x.x.x.x.o."},
    "build": {"kick": "x...x...x...x...", "snare": "xxxxxxxxxxxxxxxx", "hat": "................"},
    "fill": {"kick": "x.......", "snare": "....x.xxoxoxXXXX"},
}


def drums(p, fill=True, hv=10):
    return {"pattern": DR[p], "swing": 0.5, "humanize_ms": 6, "humanize_vel": hv, **({"fill": DR["fill"]} if fill else {})}


CRASH = [{"pitch": 49, "start": 0, "length": 1, "velocity": 112}]                                   # 4마디마다 첫 박 크래시(cycle 16)
RIDE = [{"pitch": 51, "start": i * 0.5, "length": 0.4, "velocity": 84 if i % 2 == 0 else 66} for i in range(8)]   # 8분 라이드(cycle 4)
STRUM8 = [[0, .5, .9], [.5, .5, .7], [1, .5, .85], [1.5, .5, .7], [2, .5, .9], [2.5, .5, .7], [3, .5, .85], [3.5, .5, .75]]
MUTE8 = [[0, .4, .8], [.5, .4, .55], [1, .4, .75], [1.5, .4, .55], [2, .4, .8], [2.5, .4, .55], [3, .4, .75], [3.5, .4, .6]]
PUSH = [[0, 1.5, .9], [1.5, .5, .7], [2.5, 1.5, .85]]                                              # 시티팝·밴드식 밀어치기(1 · 2& · 3&)
STAB = [[0, .35, 1], [.5, .35, 1], [1, .35, 1], [1.5, .35, 1], [2, .6, 1],                        # 1마디: 딴딴딴딴딴— (2박 반 뒤 쉼)
        [4, .35, 1], [4.5, .35, 1], [5, .35, 1], [5.5, .35, 1], [6, .35, 1], [6.5, .35, 1], [7, .35, 1], [7.5, .5, 1]]   # 2마디: 8분 연타로 후렴에 꽂기
STAB_DR = [{"pitch": pch, "start": s, "length": .3, "velocity": 124} for s, _, _ in STAB for pch in (36, 49)]   # 킥+크래시 유니즌

spec = {
    "name": NAME, "bpm": BPM, "key": KEY, "style": "korean-band-pop", "feel": "straight", "intensity": 0.85,
    "brief": "「Four O'Clock」 외주 — 한국 얼터너티브 팝 록 밴드 사운드, 140 BPM, 영어 남자 보컬, 청춘·기억의 씁쓸함",
    "sections": SECTIONS,
    "tracks": {
        "Drums": {"preset": "drums/rock", "role": "drums", "sends": {"0": -16}},
        "Bass": {"preset": "bass/picked_rock", "role": "bass"},
        "GtrPower": {"preset": "guitar/power", "role": "guitar", "pan": -0.6, "sends": {"0": -18}},
        "GtrCrunch": {"preset": "guitar/crunch", "role": "guitar", "pan": 0.6, "sends": {"0": -16}},
        "GtrLead": {"preset": "guitar/lead_bright", "role": "lead", "pan": 0.15, "sends": {"0": -10}},
        "Piano": {"preset": "piano/grand_bright", "role": "piano", "pan": -0.3, "sends": {"0": -12}},
        "Violin": {"preset": "strings/solo_violin", "role": "lead", "pan": 0.35, "sends": {"0": -8}},   # LUCY 의 상징 악기 — 기타보다 바이올린이 선율을 맡는다
        # 팬: v3 폭 side/mid -9.6 dB 가 LUCY(-5~-8)보다 좁아 기타 ±0.6 으로 벌림
    },
    "buses": [{"name": "Room", "bus": 0, "device": "Dragonfly Room Reverb", "volume_db": -5}],
    "parts": [
        # 드럼
        {"track": "Drums", "in": ["intro"], "offset": 16, "drums": drums("chorus")},
        {"track": "Drums", "in": ["verse1"], "drums": drums("verse_light", fill=False, hv=6)},
        {"track": "Drums", "in": ["verse1"], "offset": 32, "drums": drums("verse")},
        {"track": "Drums", "in": ["verse2"], "drums": drums("verse")},
        {"track": "Drums", "in": ["pre1", "pre2"], "notes": CRASH, "cycle_beats": 32},
        {"track": "Drums", "in": ["pre1", "pre2"], "drums": drums("pre")},
        {"track": "Drums", "in": ["chorus", "post", "outro"], "drums": drums("chorus")},
        {"track": "Drums", "in": ["chorus_last"], "drums": drums("last")},
        {"track": "Drums", "in": ["build"], "drums": drums("build", fill=False, hv=4)},
        {"track": "Drums", "in": ["stabs"], "notes": STAB_DR, "cycle_beats": 8},
        {"track": "Drums", "in": ["chorus", "outro"], "notes": CRASH, "cycle_beats": 16},
        {"track": "Drums", "in": ["chorus_last"], "notes": CRASH, "cycle_beats": 8},
        {"track": "Drums", "in": ["chorus_last"], "notes": RIDE, "cycle_beats": 4},
        # 베이스
        {"track": "Bass", "in": ["verse1", "verse2"], "bass": {"progression": PROG["verse"], "beats_per_chord": 4, "low": 28, "high": 50,
                                                              "pattern": [[0, 2.5, 0], [2.5, 1, 0], [3.5, .5, 7]]}},
        {"track": "Bass", "in": ["pre1", "pre2"], "bass": {"progression": PROG["pre"], "beats_per_chord": 4, "low": 28, "high": 52,
                                                          "pattern": [[0, .5, 0], [.5, .5, 0], [1, .5, 0], [1.5, .5, 0], [2, .5, 0], [2.5, .5, 0], [3, .5, 0], [3.5, .5, 12]]}},
        {"track": "Bass", "in": ["chorus", "chorus_last", "outro", "post"], "bass": {"progression": PROG["chorus"], "beats_per_chord": 4, "low": 28, "high": 52,
                                                                                   "pattern": [[0, .5, 0], [.5, .5, 0], [1, .5, 0], [1.5, .5, 0], [2, .5, 0], [2.5, .5, 7], [3, .5, 0], [3.5, .5, 12]]}},
        # 브리지엔 베이스 없음 — 피아노와 목소리만(10-17 본인: 너무 채워 넣지 말 것. 빈자리는 일부러 둔 것)
        {"track": "Bass", "in": ["stabs"], "bass": {"progression": "IV V", "beats_per_chord": 4, "low": 28, "high": 50, "pattern": [[s, l, 0] for s, l, _ in STAB]}},
        {"track": "Bass", "in": ["build"], "bass": {"progression": "V", "beats_per_chord": 16, "low": 28, "high": 50,
                                                   "pattern": [[i * .5, .5, 0] for i in range(8)]}},
        # 파워코드 기타(왼) — 절은 뮤트 8분, 후렴은 풀 스트럼
        {"track": "GtrPower", "in": ["verse1", "verse2"], "chords": {"progression": PROG["verse"], "beats_per_chord": 4, "voicing": "power", "rhythm": MUTE8, "velocity": 64}},
        {"track": "GtrPower", "in": ["pre1", "pre2"], "chords": {"progression": PROG["pre"], "beats_per_chord": 4, "voicing": "power", "rhythm": STRUM8, "velocity": 82}},
        {"track": "GtrPower", "in": ["chorus", "outro", "post"], "chords": {"progression": PROG["chorus"], "beats_per_chord": 4, "voicing": "power", "rhythm": STRUM8, "velocity": 112}},
        {"track": "GtrPower", "in": ["chorus_last"], "chords": {"progression": PROG["chorus"], "beats_per_chord": 4, "voicing": "power", "rhythm": STRUM8, "velocity": 124}},
        {"track": "GtrPower", "in": ["stabs"], "chords": {"progression": "IV V", "beats_per_chord": 4, "voicing": "power", "rhythm": STAB, "velocity": 127}},
        {"track": "GtrCrunch", "in": ["stabs"], "chords": {"progression": "IV V", "beats_per_chord": 4, "voicing": "guitar", "rhythm": STAB, "velocity": 120}},
        {"track": "Piano", "in": ["stabs"], "chords": {"progression": "IV V", "beats_per_chord": 4, "voicing": "rhodes", "rhythm": STAB, "velocity": 110}},
        {"track": "GtrPower", "in": ["build"], "chords": {"progression": "V", "beats_per_chord": 16, "voicing": "power",
                                                          "rhythm": [[i * .25, .25, .6 + .4 * i / 16] for i in range(16)], "velocity": 96}},
        # 크런치 기타(오른) — 밀어치기 보이싱, 후렴은 상성부 8분
        {"track": "GtrCrunch", "in": ["intro"], "offset": 16, "chords": {"progression": PROG["chorus"], "beats_per_chord": 4, "voicing": "guitar", "rhythm": STRUM8, "velocity": 84}},
        {"track": "GtrCrunch", "in": ["verse1", "verse2"], "chords": {"progression": PROG["verse"], "beats_per_chord": 4, "voicing": "guitar", "rhythm": PUSH, "velocity": 66}},
        {"track": "GtrCrunch", "in": ["pre1", "pre2"], "chords": {"progression": PROG["pre"], "beats_per_chord": 4, "voicing": "guitar", "rhythm": PUSH, "velocity": 80}},
        {"track": "GtrCrunch", "in": ["chorus", "chorus_last", "outro", "post"], "chords": {"progression": PROG["chorus"], "beats_per_chord": 4, "voicing": "guitar", "rhythm": STRUM8, "velocity": 104}},
        # 리드 기타 — 리프
        {"track": "GtrLead", "in": ["intro"], "melody": {"text": f"{RIFF_A} | {RIFF_B} | {RIFF_A} | {RIFF_B}", "velocity": 100, "repeat": False}},
        {"track": "GtrLead", "in": ["post"], "melody": {"text": f"{RIFF_A} | {RIFF_B}", "velocity": 104}},
        {"track": "GtrLead", "in": ["outro"], "melody": {"text": f"{RIFF_A} | {RIFF_B} | {RIFF_HI} | {RIFF_B}", "velocity": 106, "repeat": False}},
        {"track": "GtrLead", "in": ["chorus"], "offset": 8, "melody": {"text": COUNTER, "velocity": 92, "repeat": False}},
        {"track": "GtrLead", "in": ["chorus"], "offset": 40, "melody": {"text": COUNTER, "velocity": 92, "repeat": False}},
        {"track": "GtrLead", "in": ["chorus_last"], "melody": {"text": f"{RIFF_HI} | {COUNTER}", "velocity": 100}},
        # 바이올린 — 절은 줄 끝 대답(피아노와 번갈아), 프리는 긴 활, 후렴은 훅 한 옥타브 위, 브리지 대선율, 아웃트로는 리프 함께
        {"track": "Violin", "in": ["intro"], "offset": 16, "melody": {"text": "r:2 A4:2 | B4:2 C#5:2 | D5:1 C#5:1 B4:2 | A4:4", "velocity": 78, "repeat": False, "legato": 1.0}},
        {"track": "Violin", "in": ["verse2"], "melody": {"text": VLN_VERSE, "velocity": 70, "legato": 1.0}},   # 1절은 비워 둔다
        {"track": "Violin", "in": ["pre1", "pre2"], "melody": {"text": VLN_PRE, "velocity": 84, "legato": 1.0}},
        {"track": "Violin", "in": ["chorus", "chorus_last"], "melody": {"text": VLN_CHORUS, "velocity": 92, "legato": 0.95}},
        {"track": "Violin", "in": ["bridge"], "melody": {"text": VLN_BRIDGE, "velocity": 74, "legato": 1.0, "repeat": False}},
        {"track": "Violin", "in": ["build"], "melody": {"text": "E5:16", "velocity": 60, "repeat": False, "legato": 1.0}},
        {"track": "Violin", "in": ["outro"], "melody": {"text": f"{RIFF_A} | {RIFF_B} | {RIFF_HI} | {RIFF_B}", "velocity": 90, "repeat": False}},
        # 피아노 — 절 끝 대답, 브리지 주역, 후렴 뒤 옥타브
        {"track": "Piano", "in": ["verse1", "verse2"], "chords": {"progression": PROG["verse"], "beats_per_chord": 4, "voicing": "rhodes",
                                                                 "rhythm": [[2.5, .5, .7], [3, 1, .8]], "velocity": 62}},
        {"track": "Piano", "in": ["pre1", "pre2"], "chords": {"progression": PROG["pre"], "beats_per_chord": 4, "voicing": "pad", "rhythm": [[0, 4, .9]], "velocity": 70, "legato": 1.0}},
        {"track": "Piano", "in": ["chorus_last"], "chords": {"progression": PROG["chorus"], "beats_per_chord": 4, "voicing": "rhodes",
                                                                      "rhythm": [[0, .5, .9], [1, .5, .7], [2, .5, .9], [3, .5, .7]], "velocity": 78}},
        {"track": "Piano", "in": ["bridge"], "chords": {"progression": PROG["bridge"], "beats_per_chord": 4, "voicing": "rhodes",
                                                       "rhythm": [[0, 1.5, .9], [1.5, .5, .6], [2, 1, .8], [3, 1, .7]], "velocity": 72}},
        {"track": "Piano", "in": ["build"], "chords": {"progression": "V", "beats_per_chord": 16, "voicing": "pad", "rhythm": [[0, 16, 1.0]], "velocity": 84, "legato": 1.0}},
    ],
    "master": [{"device": "eq", "params": {"Mid freq 2": 3500, "Mid gain 2": 1.5, "High-pass freq": 9000, "High-pass gain": 3}}],   # 레퍼런스 대비 어두움(presence·air) 보정
    "events": CONCEPT["events"],
    "mix": {"balance": True, "target_lufs": -11,
            "balance_lu": {"drums": 0, "bass": -1, "gtrpower": -2.5, "gtrcrunch": -3, "gtrlead": -4, "piano": -8, "vox": 2.5}},
}

VOX = Path(arrange.ROOT) / "projects" / NAME / "vocals" / "vox.wav"
CAPTION = ("male pop rock band lead vocal, english, bright youthful chest voice with a little rasp, confident, "
           "sings on top of a live band, big stacked vocal harmonies on the chorus, no rap")
spec["tracks"]["Vox"] = {"role": "lead vocal (generated over the arrangement)", "sends": {"0": -10},
                         "fx": [{"device": "eq", "params": {"Low-pass freq": 110, "Low-pass gain": -8, "Mid freq 2": 3000, "Mid gain 2": 2}},
                                {"device": "compressor", "params": {"threshold": -18, "ratio": 3.5, "attack": 6, "release": 100}}]}
VOX_PART = {"track": "Vox", "vocal_sections": str(VOX.with_suffix(".json"))}


def _notes(text, start_beat):
    return [{**n, "start": round(n["start"] + start_beat, 4)} for n in arrange.melody(text)[0]]   # melody() 는 (노트, 길이) 튜플


def vocal_sections():
    out, bar, count = [], 0, {}
    tags = {"chorus": "Chorus", "chorus_last": "Chorus", "bridge": "Bridge", "pre1": "Pre-Chorus", "pre2": "Pre-Chorus"}
    for s_ in SECTIONS:
        name, n = s_["name"], s_["bars"]
        lyr_key = {"chorus_last": "chorus"}.get(name, name)
        if lyr_key in LYR:
            count[name] = count.get(name, 0) + 1
            lines = MEL[lyr_key]
            per = n * 4 / len(lines)
            notes, phrases = [], []
            lyr_lines = LYR[lyr_key].split("\n")
            for i, m in enumerate(lines):
                notes += _notes(m, bar * 4 + i * per)
                first = arrange.melody(m)[0]
                phrases.append({"start": round((bar * 4 + i * per + (first[0]["start"] if first else 0)) * SPB, 3),
                                "text": lyr_lines[i] if i < len(lyr_lines) else ""})     # 줄 시작 = 그 줄 첫 음(보컬 정렬 기준)
            out.append({"name": f"{name}{count[name]}", "start": round(bar * 4 * SPB, 3), "end": round((bar + n) * 4 * SPB, 3),
                        "tag": tags.get(name, "Verse"), "lyrics": LYR[lyr_key], "key": KEY, "melody_notes": notes, "phrases": phrases})
        bar += n
    return out


def make_vocals(log=print):
    guide = lego.render_guide(spec)
    _, rep = lego.vocal_track(guide, vocal_sections(), BPM, KEY, CAPTION, VOX, takes=12, guide_wav=guide,
                              pass_wer=0.25, min_key_fit=0.75, lang="en", log=log)
    for x in rep:
        log(f"{x['section']}: seed {x['chosen']} · 오류율 {x['wer']} · 유사도 {x['voice_sim']} · 조성 {x['key_fit']}")
    return VOX_PART


if __name__ == "__main__":
    step = sys.argv[1] if len(sys.argv) > 1 else "band"
    label = sys.argv[2] if len(sys.argv) > 2 else "v1"
    concept_mod.save(NAME, CONCEPT)
    r = critic.critique({**spec, "tracks": {k: v for k, v in spec["tracks"].items() if k != "Vox"}}, CONCEPT)
    print(critic.format_report(r).split("Claude 가")[0])
    if step == "dry":
        sys.exit(0)
    t0 = time.time()
    stamp = lambda m: print(f"{time.time() - t0:6.0f}s {m}", flush=True)
    if step == "band":
        s, rep = arrange.build({**spec, "tracks": {k: v for k, v in spec["tracks"].items() if k != "Vox"}}, label=label, log=stamp)
    elif step == "all":
        from concurrent.futures import ThreadPoolExecutor
        lego.render_guide(spec)
        stamp("가이드")
        fut = ThreadPoolExecutor(1).submit(make_vocals, stamp)
        s, rep = arrange.build(spec, label=label, later={"Vox": fut.result}, log=stamp)
    elif step in ("final", "align"):
        if step == "align":   # 생성 보컬을 쓴 멜로디 줄 시작에 맞춰 당긴 뒤 다시 짓기(10-17 본인 "보컬 싱크가 안 맞아")
            from musicoma import vocal_align
            vocal_align.align_state(VOX.with_suffix(".json"), lang="en", log=stamp)
        spec["parts"].append(VOX_PART)
        s, rep = arrange.build(spec, label=label, log=stamp)
    else:
        raise SystemExit(f"unknown step {step}")
    stamp("끝")
    print(json.dumps({k: rep[k] for k in ("file", "loudness", "bands_db", "issues")}, ensure_ascii=False, default=str))
