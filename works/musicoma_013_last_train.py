"""NIGHT SHIFT · 01 「Last Train」 — 올드 칸예 × 시티팝 발라드 레코드. 10-17 기획(WORKS/2026-10_night-shift-album/tracks/01-last-train.md).

레코드(직접 작곡·연주·녹음, F장조 69.85 BPM): 로즈·클린 기타·스트링·브러시 드럼 + ns-singer-cp 가 B 구간을 부른다(멜로디 직접 씀).
  B 1~4마디(IVmaj7 iii7 ii7 bIIImaj7)를 비닐로 늙혀 +4반음 배속 → A장조 88 BPM 루프 + 보컬 찹 8개.
비트(College Dropout): 붐뱁, 서브 베이스는 샘플 조를 따르되 **4마디째(bIII)만 원래 I(A) 를 유지** — 샘플과 베이스의 어긋남 1마디(화성 연구 카드의 Last Train 장치).
전주 8마디: 안내방송(생성 목소리) → 레코드 필터 닫힘 → 5마디째 드럼 → 9마디째 열리며 랩.

    python works/musicoma_013_last_train.py v1
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from musicoma import arrange, concept as concept_mod, crate, theory, voice, voice_design as vd
from musicoma.recipes import chipmunk_soul as cs

NAME = "ns-01-last-train"
BPM, ST = 88, 4
SRC_BPM = round(BPM / 2 ** (ST / 12), 3)            # 69.85
ROOT = Path(__file__).resolve().parents[1]
FORM = [("intro", 8), ("verse1", 8), ("verse1b", 8), ("turn1", 1), ("hook1", 8), ("inter", 4), ("verse2", 8), ("verse2b", 8), ("turn2", 1), ("hook2", 8),
        ("bridge", 8), ("hook3", 8), ("outro", 4)]      # 절을 반으로 나눔(드럼 패턴 교체용) — 랩은 verse1/verse2 시작에 놓여 64박을 이어 간다

# ───────── 레코드 B 구간(8마디) — 가수 ns-singer-cp, 멜로디 직접 씀(한 토큰 = 한 음표) ─────────
REC_PROG = "IVmaj7 iii7 ii7 bIIImaj7 IVmaj7 iii7 ii7 V7sus4"       # F: Bbmaj7 Am7 Gm7 Abmaj7 | Bbmaj7 Am7 Gm7 C7sus4
REC_MEL = ("r:1 A4:.5 C5:.5 D5:1 C5:1 | A4:1 G4:.5 F4:.5 G4:2 | r:1 G4:.5 A4:.5 Bb4:1 A4:1 | G4:1 Eb5:1 C5:2 | "
           "r:1 A4:.5 C5:.5 D5:1 C5:1 | A4:1 G4:.5 F4:.5 G4:2 | r:.5 G4:.5 A4:.5 Bb4:.5 A4:1 G4:1 | F4:3 r:1")
REC_LYR = "stay on the last train stay with me till the lights come on with me stay on the last train stay with me hold me when the doors close"   # 29 토큰 = 29 음표

# ───────── 랩 가사(직접 씀) — 장면: 막차 플랫폼 / 사물: 끊기는 안내방송 · 손잡이의 편의점 봉지 · 거울이 된 창 ─────────
VERSE1 = [                                          # 8줄 — ACE lego 가 비트를 듣고 절 전체를 한 번에 랩(10-18 본인 "하나로 만들어 봐")
    "Badge in my pocket, bleach on my sleeve", "Last one leaves at twelve-oh-two",
    "Speaker cuts out, I know the name", "Plastic bag on the handrail",
    "Window's black, so it's a mirror", "I don't look at the guy in it",
    "Girl across from me is dressed for out", "Same door, I'm home, she's out",
]
VERSE2 = [
    "Lipstick in the window, other way", "My shift starts when the bars open",
    "His bag is dinner, mine is shoes", "Speaker cuts out, we both mouth the stop",
    "Used to hate this train", "Now it's the only hour nobody needs me",
    "He gets off at the yard, nods at nobody", "One of us is going home, not me",
]
FLOW12 = [8, 8, 8, 8, 8, 8, 8, 8]
def flow(lines, beats):
    return [{"text": l, "beats": b} for l, b in zip(lines, beats)]
ADLIBS = [{"text": "uh", "beats": 16}, {"text": "yeah", "beats": 16}, {"text": "uh huh", "beats": 16}, {"text": "mm", "beats": 16}]
           # 12줄 = 64박: 긴 줄 6박, 짧은 줄 4박, 마지막 8박(뒤를 비움)
# 하이피치 노래 훅(보컬로이드 질감 — 칸예 시티팝 02 의 '맛'): ns-singer-cp, A4~F#5, 한 토큰 = 한 음표
HI_MEL = "r:1 E5:.5 E5:.5 C#5:1 B4:1 | A4:2 r:2 | r:1 E5:.5 F#5:.5 E5:1 C#5:1 | B4:3 r:1 | r:1 E5:.5 E5:.5 C#5:1 B4:1 | A4:2 r:2 | r:1 C#5:.5 B4:.5 A4:1 G#4:1 | A4:3 r:1"
HI_LYR = "stay on the last train stay with me to- night stay on the last train one of us is home"      # 20 토큰 = 20 음표
HOOK = [("Last train, last train, one of us is going home", 8), ("Mind the gap, mind the gap, between the night and the morning", 8),
        ("Last train, last train, one of us is going home", 8), ("Leave the light on, I'll see you when the morning comes", 8)]
BRIDGE_MEL = "r:2 E4:1 D4:1 | C#4:2 B3:2 | r:2 E4:1 F#4:1 | E4:2 D4:2 | r:2 D4:1 C#4:1 | B3:2 A3:2 | r:1 C#4:1 D4:1 E4:1 | E4:4"
BRIDGE_LYR = "the win- dow is a mir- ror till the sta- tion lights come on, come on"   # 16 토큰 = 16 음표
RAP_CAPTION = ("old school hip hop, male rapper, laid back conversational flow, clear words, on the beat, "
               "leaves space between lines, no singing, dry close mic")
ANNOUNCE = ["This is the last train.", "Please mind the gap between the train and the platform.", "The next station is... the next station is..."]

CONCEPT = {
    "thesis": "막차 플랫폼 — 교대 끝낸 사람과 밤을 시작하는 사람이 같은 문으로 탄다. 거울이 된 창 앞에서 둘은 역 이름만 입 모양으로 같이 말한다",
    "arc": [{"section": "intro", "intent": "안내방송 → 필터 닫힌 레코드 → 5마디째 드럼 → 9마디째 열림. 랩 없음", "energy": 0.3},
            {"section": "verse1", "intent": "교대 끝낸 사람. 낮고 지친 랩, 사물로만 말한다", "energy": 0.55},
            {"section": "turn1", "intent": "1마디 열쇠구멍", "energy": 0.3},
            {"section": "hook1", "intent": "레코드 목소리 찹 'stay… stay…' + 챈트", "energy": 0.85},
            {"section": "inter", "intent": "4마디 간주 — 레코드와 로즈만, 숨", "energy": 0.4},
            {"section": "verse2", "intent": "시점 교대: 밤을 시작하는 사람. 같은 사물을 반대편에서", "energy": 0.6},
            {"section": "bridge", "intent": "드럼 없이 가수가 느리게 한 줄 — 창은 역 불빛이 켜질 때까지 거울", "energy": 0.35},
            {"section": "hook3", "intent": "다 들어오고 찹 하행", "energy": 1.0},
            {"section": "outro", "intent": "4마디, 안내방송 조각 + 필터 닫힘", "energy": 0.2}],
    "motif": {"melody": "A4:.5 C5:.5 D5:1 C5:1", "why": "'stay on the last' — 올라갔다 한 음 내려오는, 문이 닫히기 전의 망설임"},
    "collision": ["시티팝 발라드 레코드(따뜻·넓음)", "올드 칸예 붐뱁(좁고 어둡고 드럼이 앞)", "안내방송(기계 목소리)과 사람 목소리"],
    "irregular": [{"what": "비트 4마디째 베이스가 샘플 조(bIII=C)를 안 따르고 A 를 유지", "why": "샘플과 비트의 어긋남 1마디 — 올드 칸예의 긴장(화성 연구 카드)"},
                  {"what": "전주 8마디, 랩은 9마디부터", "why": "본인: 전주 짧고 바로 랩 들어와 꽉 채우지 말 것"},
                  {"what": "2절은 다른 사람의 1인칭", "why": "같은 사물을 반대편에서 보면 곡이 두 배가 된다"}],
    "constraints": ["88 BPM 정박 붐뱁", "폭 side/mid -12~-15(올드 칸예)", "air -28~-32", "드럼 -4 · 보컬 -6", "절/훅/브리지 3 dB 이상"],
    "references": "knowledge/references/old-kanye-citypop.yaml — Through the Wire·Heard 'Em Say / SPARKLE·真夜中のドア",
    "not": ["생성기 멜로디", "추상명사 가사", "전 구간 같은 크기"],
}


def record():
    """레코드 설계서: 레시피 기본(로즈·스트링·드럼·베이스)에 코드·멜로디·가사를 직접 쓴 것으로 바꾼다."""
    spec = cs.record_spec(f"{NAME}-record", SRC_BPM, "F major", "city-pop", "rhodes", seed=13,
                          vocal={"voice": "ns-singer-cp", "lyrics": REC_LYR, "low": 65, "high": 76})
    for p in spec["parts"]:
        for k in ("chords", "bass"):
            if k in p:
                p[k]["progression"] = REC_PROG
        if "vocal" in p:
            p["vocal"]["melody"], p["vocal"]["lyrics"] = REC_MEL, REC_LYR
        if p["track"] == "Lead":                       # A 구간 리드는 레코드 멜로디의 로즈 — 생성기 선율 대신 직접 쓴 것
            p["melody"]["text"] = REC_MEL
    spec["tracks"]["Guitar"] = {"preset": "guitar/jangle", "role": "guitar", "pan": 0.3, "sends": {"0": -9}}
    spec["parts"].append({"track": "Guitar", "in": ["A", "B"], "chords": {"progression": REC_PROG, "beats_per_chord": 4, "voicing": "guitar",
                                                                            "rhythm": [[0, 1.5, .8], [1.5, .5, .6], [2.5, 1.5, .75]], "velocity": 70}})
    spec["parts"] = [p for p in spec["parts"] if not (p["track"] == "Drums")] + [
        {"track": "Drums", "in": ["A", "B"], "drums": {"pattern": {"kick": "x.......x.......", "snare": "....x.......x...", "hat": "x.x.x.x.x.x.x.x."},
                                                       "swing": 0.52, "humanize_ms": 10, "humanize_vel": 12}}]
    spec["brief"] = "「Last Train」 샘플용 레코드 — 시티팝 발라드, 직접 쓴 멜로디·가사, ns-singer-cp"
    return spec


def sample(rec_spec, rec):
    sections, _ = arrange._sections(rec_spec)
    b = next(s for s in sections if s["name"] == "B")
    spb = 60 / SRC_BPM
    start, end = b["start_bar"] * 4 * spb, (b["start_bar"] + 4) * 4 * spb
    stems = rec["stems"]
    parts_ = [k for k in ("Keys", "Strings", "Guitar", "Vox") if k in stems]
    accomp = crate.mix_files([stems[k] for k in parts_], Path(rec["mix"]).with_name(f"{NAME}_accomp.wav"), gains_db=[0, -1, -2, 2][:len(parts_)])
    aged = crate.age(accomp, "vinyl")
    loop = crate.loop_region(aged, start, end, 4, BPM, tag="sample_loop")
    vox_loop = crate.loop_region(stems["Vox"], start, end, 4, BPM, tag="vox_loop")
    chops = crate.chop(vox_loop["path"], mode="onsets", n=8, min_len=0.15, max_len=1.2)
    kit = crate.make_kit(chops, Path(chops[0]["path"]).parent / "chops.sfz")
    src = theory.progression(REC_PROG, "F", "major")[:4]
    after = [theory.transpose_chord(c, ST) for c in src]
    return loop, kit, after


def beat(loop, kit, after):
    prog = " ".join(after)                                   # Dmaj7 Dbm7 Bm7 Cmaj7
    prog_bass = " ".join(after[:3] + ["Amaj7"])              # 4마디째 베이스는 A 유지(어긋남)
    keys = sorted(kit["kit"].values())
    k = lambda i: keys[i % len(keys)]
    UP = [{"pitch": k(i), "start": s, "length": l, "velocity": v} for i, (s, l, v) in enumerate([(0, .55, 106), (1, .55, 94), (2, .6, 108), (3, .6, 98), (4, .55, 104), (5.5, .5, 90), (6, .6, 108), (7, .9, 100)])]
    DOWN = [{"pitch": k(len(keys) - 1 - i), "start": s, "length": l, "velocity": v} for i, (s, l, v) in enumerate([(0, .6, 108), (1, .55, 98), (2, .55, 104), (3, .6, 96), (4, .55, 106), (5.5, .5, 92), (6, .6, 108), (7, .9, 100)])]
    TURN = [{"pitch": k(0), "start": 0, "length": .35, "velocity": 96}, {"pitch": k(0), "start": .75, "length": .3, "velocity": 84},
            {"pitch": k(1), "start": 1.5, "length": .4, "velocity": 92}, {"pitch": k(2), "start": 2.5, "length": .4, "velocity": 98}, {"pitch": k(3), "start": 3.25, "length": .7, "velocity": 104}]
    PAD = [{"pitch": k(i), "start": i * 2, "length": 1.9, "velocity": 40} for i in range(4)]
    sw = 0.56
    D = lambda pat, fill=None: {"pattern": pat, "swing": sw, "humanize_ms": 6, "humanize_vel": 8, **({"fill": fill} if fill else {})}
    MAIN = {"kick": "x.....x...x..x..", "snare": "....X.......X...", "hat": "x-x-x-x-x-x-x-x-"}
    MAIN2 = {"kick": "X.....x...X..x..", "snare": "....X..o....X..o", "hat": "x-x-x-x-x-x-x-x-", "open_hat": "..........x....."}
    HK = {"kick": "X..x......X..x..", "snare": "....X..o....X...", "hat": "x-x-x-x-x-x-x-x-"}
    HK2 = {"kick": "X..x..x...X..x..", "snare": "....X..o....X..o", "hat": "x-x-x-x-x-x-x-x-", "open_hat": "..............x."}
    F1 = {"kick": "X.....x...X.....", "snare": "....X.......xoxo", "hat": "x.x.x.x.x.x....."}
    F2 = {"kick": "X.........X.....", "snare": "....X...XoXoXXXX", "hat": "x.x.x.x........."}
    vox_fx = [{"device": "eq", "params": {"Low-pass freq": 95, "Low-pass gain": -14, "Mid freq 1": 420, "Mid gain 1": -2, "Mid Q 1": 0.9, "Mid freq 2": 3200, "Mid gain 2": 3, "Mid Q 2": 0.7, "High-pass freq": 11000, "High-pass gain": 1}},
              {"device": "compressor", "params": {"threshold": -20, "ratio": 4, "attack": 8, "release": 90}}]
    bars, b = {}, 0
    for n, kk in FORM:
        bars[n] = b; b += kk
    total = b
    spec = {
        "name": NAME, "bpm": BPM, "key": "A major", "style": "chipmunk-soul", "feel": "laid_back", "intensity": 0.7,
        "brief": "NIGHT SHIFT 01 「Last Train」 — 시티팝 발라드 레코드(+4) 위 올드 칸예 붐뱁, 안내방송 전주 8마디, 시점 교대 2절",
        "sections": [{"name": n, "bars": kk} for n, kk in FORM],
        "tracks": {
            "Sample": {"role": "sample loop (varispeed +4, vinyl)", "fx": [
                {"device": "eq", "params": {"Low-pass freq": 110, "Low-pass gain": -14, "Mid freq 1": 350, "Mid gain 1": -3, "Mid Q 1": 0.9, "High-pass freq": 10500, "High-pass gain": -4}},
                {"device": "lowpass", "params": {"frequency": 20000}}]},
            "Drums": {"sound": "drums_acoustic_basic", "role": "boom bap drums", "sends": {"0": -24}, "fx": [
                {"device": "eq", "params": {"Low-pass freq": 62, "Low-pass gain": 3.5, "Mid freq 1": 350, "Mid gain 1": -3, "Mid Q 1": 1.0, "Mid freq 2": 4500, "Mid gain 2": 3}},
                {"device": "compressor", "params": {"threshold": -19, "ratio": 4, "attack": 18, "release": 80, "output gain": 3}}]},
            "Bass": {"sound": "bass_sub", "role": "sub bass", "volume_db": -3, "fx": [{"device": "lowpass", "params": {"frequency": 700}}]},
            "Keys": {"sound": "rhodes", "role": "rhodes layer", "pan": -0.15, "sends": {"0": -8}},
            "Chops": {"sound": kit["sfz"], "role": "chipmunk vocal chops", "pan": 0.1, "sends": {"0": -10}},
            "Strings": {"preset": "strings/ensemble", "role": "strings", "pan": -0.25, "sends": {"0": -8}},
            "Rap": {"role": "lead rap vocal", "sends": {"0": -17}, "fx": vox_fx},
            "Chant": {"role": "hook chant", "pan": -0.08, "sends": {"0": -15}, "fx": vox_fx},
            "Announce": {"role": "train announcement (generated voice)", "pan": 0.2, "sends": {"0": -4},
                         "fx": [{"device": "eq", "params": {"Low-pass freq": 300, "Low-pass gain": -18, "Mid freq 2": 2500, "Mid gain 2": 4, "Mid Q 2": 1.2, "High-pass freq": 4000, "High-pass gain": -12}}]},
            "Adlib": {"role": "ad-libs", "pan": 0.25, "sends": {"0": -10}, "fx": vox_fx},
            "HiHook": {"role": "high vocaloid hook (ns-singer-cp)", "pan": -0.05, "sends": {"0": -8},
                       "fx": [{"device": "eq", "params": {"Low-pass freq": 200, "Low-pass gain": -10, "Mid freq 2": 4000, "Mid gain 2": 3, "High-pass freq": 10000, "High-pass gain": 3}},
                              {"device": "compressor", "params": {"threshold": -20, "ratio": 4, "attack": 6, "release": 80}}]},
            "Singer": {"role": "bridge vocal (ns-singer-cp)", "sends": {"0": -9}, "fx": [{"device": "compressor", "params": {"threshold": -18, "ratio": 3}}]},
        },
        "buses": [{"name": "Verb", "bus": 0, "device": "Dragonfly Plate Reverb", "volume_db": -5}],
        "parts": [
            {"track": "Sample", "in": ["intro", "turn1", "turn2"], "audio": {"path": loop["path"], "every": 16, "gain_db": -3}},
            {"track": "Sample", "in": ["verse1", "verse1b", "verse2", "verse2b", "inter"], "audio": {"path": loop["path"], "every": 16, "gain_db": -3.5}},
            {"track": "Sample", "in": ["hook1", "hook2", "hook3"], "audio": {"path": loop["path"], "every": 16}},
            {"track": "Sample", "in": ["bridge"], "audio": {"path": loop["path"], "every": 16, "gain_db": -9}},
            {"track": "Sample", "in": ["outro"], "audio": {"path": loop["path"], "every": 16, "gain_db": -4}},
            # 안내방송 — 전주 첫 2마디, 아웃트로 조각
            {"track": "Announce", "in": ["intro"], "rap": {"voice": "ns-singer-m", "lines": [{"text": ANNOUNCE[0], "beats": 4}, {"text": ANNOUNCE[1], "beats": 8}],
                                                           "style": "flat, calm public announcement voice, no emotion, slightly distant", "lock": 0.3, "seed": 71, "gain_db": -2}},
            {"track": "Announce", "in": ["outro"], "rap": {"voice": "ns-singer-m", "lines": [{"text": ANNOUNCE[2], "beats": 8}],
                                                           "style": "flat, calm public announcement voice, cutting out", "lock": 0.3, "seed": 72, "gain_db": -4}},
            # 드럼 — 전주 5마디째부터(offset 16박), 브리지·turn 없음
            {"track": "Drums", "in": ["intro"], "offset": 16, "drums": D({"kick": "x.........x.....", "snare": "....x.......x...", "hat": "................"})},
            {"track": "Drums", "in": ["verse1"], "drums": D(MAIN, F1)},
            {"track": "Drums", "in": ["verse1b"], "drums": D(MAIN2, F1)},                       # 절 후반 패턴 교체(4마디마다 무언가 바뀌게)
            {"track": "Drums", "in": ["verse2"], "drums": D(MAIN2, F1)},
            {"track": "Drums", "in": ["verse2b", "inter"], "drums": D(HK, F1)},
            {"track": "Drums", "in": ["hook1"], "drums": D(HK, F2)},
            {"track": "Drums", "in": ["hook2", "hook3"], "drums": D(HK2, F2)},
            {"track": "Drums", "in": ["outro"], "drums": D({"kick": "X.........x.....", "snare": "................", "hat": "................"})},
            # 베이스 — 4마디째 A 유지
            {"track": "Bass", "in": ["verse1", "verse1b", "verse2", "verse2b", "inter"], "bass": {"progression": prog_bass, "beats_per_chord": 4, "pattern": [[0, .9, 0], [1.5, .5, 0], [2.5, .45, 0], [3.25, .5, 7]], "velocity": 96, "low": 28, "high": 43}},
            {"track": "Bass", "in": ["hook1", "hook2", "hook3"], "bass": {"progression": prog_bass, "beats_per_chord": 4, "pattern": [[0, 1.1, 0], [1.75, .5, 0], [2.5, .4, 12], [3.25, .5, 7]], "velocity": 106, "low": 28, "high": 43}},
            # 로즈 — 훅·간주
            {"track": "Keys", "in": ["hook1", "hook2", "hook3", "inter"], "chords": {"progression": prog, "beats_per_chord": 4, "voicing": "rhodes", "rhythm": [[1, .5, 1], [3, .5, .9]], "velocity": 66}},
            # 찹 — 훅 상행/하행, turn 조각, 브리지 패드
            {"track": "Chops", "in": ["hook1"], "notes": UP, "cycle_beats": 8},
            {"track": "Chops", "in": ["hook2"], "notes": DOWN, "cycle_beats": 8},
            {"track": "Chops", "in": ["hook3"], "notes": UP, "cycle_beats": 16},
            {"track": "Chops", "in": ["hook3"], "offset": 8, "notes": DOWN, "cycle_beats": 16},
            {"track": "Chops", "in": ["turn1", "turn2"], "notes": TURN},
            {"track": "Chops", "in": ["bridge"], "notes": PAD, "cycle_beats": 8},
            {"track": "Strings", "in": ["hook2", "hook3"], "chords": {"progression": prog, "beats_per_chord": 4, "voicing": "pad", "velocity": 60}},
            # 랩·챈트·노래
            {"track": "Rap", "in": ["verse1"], "rap": {"voice": "bomf-rapper", "lines": flow(VERSE1, FLOW12), "style": "weary, low-key, close to the mic, talking more than rapping", "lock": 0.7, "seed": 5}},
            {"track": "Rap", "in": ["verse2"], "rap": {"voice": "gen-rapper-c", "lines": flow(VERSE2, FLOW12), "style": "young, light, a little tired but awake, conversational", "lock": 0.72, "seed": 12}},
            {"track": "HiHook", "in": ["hook1", "hook2", "hook3"], "vocal": {"voice": "ns-singer-cp", "melody": HI_MEL, "lyrics": HI_LYR, "seed": 9, "style": "vocaloid"}},
            {"track": "Chant", "in": ["hook1", "hook2", "hook3"], "rap": {"voice": "bomf-rapper", "lines": [{"text": l, "beats": b_} for l, b_ in HOOK], "style": "chanting a hook, warm, not shouting", "lock": 0.9, "seed": 21}},
            {"track": "Singer", "in": ["bridge"], "vocal": {"voice": "ns-singer-cp", "melody": BRIDGE_MEL, "lyrics": BRIDGE_LYR, "seed": 3}},
        ],
        "automation": [{"track": "Sample", "device": 1, "param": "frequency", "points": [
            {"bar": 0, "value": 600}, {"bar": 4, "value": 900}, {"bar": 7.9, "value": 1400}, {"bar": 8, "value": 20000},
            *[pt for tn in ("turn1", "turn2") for pt in ({"bar": bars[tn] - 0.05, "value": 20000}, {"bar": bars[tn], "value": 600}, {"bar": bars[tn] + 0.95, "value": 600}, {"bar": bars[tn] + 1, "value": 20000})],
            {"bar": bars["outro"], "value": 20000}, {"bar": total, "value": 400}]}],
        "events": [{"section": "verse1", "at": 30, "length": 2, "type": "stop", "why": "8마디째 끝 두 박 정적 — 숨"},
                   {"section": "verse2b", "at": 30, "length": 2, "type": "stop", "why": "훅 들어가기 전 두 박"}],
        "mix": {"balance": True, "target_lufs": -11,
                "balance_lu": {"drums": 0, "rap": 1.5, "chant": 0.5, "hihook": 1.0, "adlib": -6, "sample": -2.5, "chops": -3.5, "bass": -5, "keys": -7, "strings": -8, "announce": -4, "singer": 0.5}},
    }
    return spec


if __name__ == "__main__":
    label = sys.argv[1] if len(sys.argv) > 1 else "v1"
    concept_mod.save(NAME, CONCEPT)
    rspec = record()
    print("[1] 레코드 녹음", SRC_BPM, "BPM F major")
    rec = arrange.bounce(rspec, stems=True, label="record")
    loop, kit, after = sample(rspec, rec)
    print("[2-3] 샘플", loop["path"], "코드(+4)", after, "찹", len(kit["kit"]))
    spec = beat(loop, kit, after)
    from musicoma import album
    s, rep = album.rap_with_lego(spec, label, RAP_CAPTION, log=lambda m: print("[4]", m, flush=True))
    print(json.dumps({k: rep.get(k) for k in ("file", "loudness", "bands_db", "issues")}, ensure_ascii=False, default=str))
