"""musicoma-012 「Second Shift」 — 칩멍크 소울(올드 칸예) 완성판. 10-17 본인: "칸예 시티팝·Back On My Feet 성공했던 느낌으로 하나 제대로 완성도 있게".

성공했던 두 곡에서 가져온 것
  · 002 시티팝 칩멍크: 레코드를 직접 작곡·연주하고 '생성한 여성 소울 목소리'로 부른 뒤 +4반음 배속 → 샘플·찹. 래퍼 둘(A 허스키 / C 젊은 테너) 주고받기.
  · Back On My Feet: 교회 오르간 모티프(인트로 혼자 → 2절 대답 → 아웃트로 조각), 훅 앞 1마디 'turn'(드럼 빼고 필터 구멍), 15마디 절, 3마디 아웃트로, 찹 상행↔하행.
새로 더한 것: 브리지(드럼 빠지고 콰이어·스트링·찹 패드 위에 랩이 말하듯), 마지막 훅에 혼 섹션, 훅 챈트 더블.

    python works/musicoma_012_second_shift.py v1
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from musicoma import concept as concept_mod, voice, voice_design as vd
from musicoma.recipes import chipmunk_soul as cs

NAME = "musicoma-012-second-shift"
BPM = 90                                      # 원곡 = 90 / 2^(4/12) = 71.4 BPM F장조 가스펠 → +4 = A장조
FORM = [("intro", 4), ("verse1", 15), ("turn1", 1), ("hook1", 8), ("verse2", 16), ("turn2", 1), ("hook2", 8),
        ("bridge", 8), ("hook3", 8), ("outro", 3)]

# ───────── 레코드(샘플이 될 '옛 가스펠 레코드') 가사 — 배속되면 아이 같은 목소리로 "hold on" 을 부른다 ─────────
RECORD_LYRICS = ("hold on the morning is coming hold on I am almost home "
                 "lay your head down baby the night is nearly gone")

# ───────── 랩 가사(직접 씀) — 구체적 장면, 라임은 느슨하게, 채우는 말 없음 ─────────
VERSE1 = [                                     # 15줄 = 15마디(한 마디 먼저 끊고 turn 으로)
    "Mama's shift starts at eleven, she leaves the kitchen light on",
    "Two buses and a badge, laundry room at Mercy General",
    "I'm fourteen with a cracked laptop and her old Walkman",
    "Chopping Sunday records till the needle skips at four",
    "She comes home smelling like bleach and other people's fevers",
    "Puts her feet up on the crate I keep the vinyl in",
    "Says turn it down, then hums the part I pitched up",
    "That's the first time anybody sang along to something I made",
    "Cousin says there's money in the warehouse, forklift, nights",
    "I said give me one more winter, I can feel it turning",
    "Pawned the amp in March, bought it back in May",
    "Every sample's somebody's mama singing in a church I never saw",
    "I don't pray much, but I speed the choir up until it sounds like asking",
    "Second shift, second verse, same bus, same badge",
    "She's still on the floor at Mercy, so I'm still on the floor at mine",
]
VERSE2 = [                                     # 16줄 — 2절은 조금 더 선 사람
    "Fast forward, I got a room with a window and a desk",
    "Same laptop, different crack, the fan sounds like her dryer",
    "Played the record for a man with a watch worth a year of rent",
    "He said who's the singer, I said nobody you could book",
    "She's a woman in a church in nineteen seventy-something",
    "Pitched up till her sorrow sounds like somebody's little girl",
    "He wrote a number down, I folded it into the sleeve",
    "Called Mama on the bus, she said don't you quit the forklift",
    "I never took the forklift, I just never said I didn't",
    "Now the check clears, and the lights stay on without her",
    "Bought her a chair, she still sits on the crate",
    "Says the chair's for company, the crate's for her",
    "Every hook I make, I leave a bar for her to hum in",
    "Every drum I hit is a door she came through at seven",
    "Second shift, second verse, I'm the one who's up now",
    "Kitchen light on, I'll leave it on for you",
]
HOOK = [                                       # 챈트(래퍼) — 레코드 'hold on' 위에
    ("Hold on, hold on, the morning's coming", 8),
    ("Mama on the night shift, I'm on the morning", 8),
    ("Hold on, hold on, we almost home", 8),
    ("Leave the light on, I'll be up till morning", 8),
]
BRIDGE = [                                     # 드럼 없이 콰이어 위에서 말하듯 — 8줄 8마디
    "I called the laundry room once, just to hear the machines",
    "Somebody picked up, said she's on break, said who's this",
    "I said her son, the one with the music",
    "She said oh, the one who speeds up the church",
    "Yeah, that one",
    "Tell her the song's done",
    "Tell her it's got her hum in it",
    "Tell her she can turn it down now",
]

CONCEPT = {
    "thesis": "야간 근무 나가는 엄마가 켜 둔 부엌 불 — 가스펠 레코드를 아이 목소리가 될 때까지 빨리 돌려서 '조금만 더'를 부르게 하고, "
              "그 아래 붐뱁 드럼은 엄마가 일곱 시에 들어오는 문소리처럼 무겁게",
    "arc": [{"section": "intro", "intent": "오르간이 모티프를 혼자 — 필터 닫힌 레코드 뒤에서", "energy": 0.2},
            {"section": "verse1", "intent": "드럼 들어오고 랩은 낮고 지친 채, 15마디에서 스스로 끊는다", "energy": 0.55},
            {"section": "turn1", "intent": "1마디 — 드럼·베이스 빠지고 레코드가 열쇠구멍으로", "energy": 0.3},
            {"section": "hook1", "intent": "칩멍크 찹 상행 + 챈트 + 레코드 'hold on' 전부", "energy": 0.9},
            {"section": "verse2", "intent": "같은 바닥, 랩은 조금 더 선 사람. 오르간이 빈자리에 모티프로 대답", "energy": 0.65},
            {"section": "hook2", "intent": "찹 하행 — 더는 묻지 않는다", "energy": 0.95},
            {"section": "bridge", "intent": "드럼 없음. 콰이어·스트링·찹 패드 위에서 전화 통화처럼 말한다", "energy": 0.35},
            {"section": "hook3", "intent": "혼 섹션·스트링 다 들어오고 챈트 더블 — 가장 큰 곳", "energy": 1.0},
            {"section": "outro", "intent": "3마디. 드럼 빠지고 오르간이 모티프를 조각내고 필터가 닫힌다", "energy": 0.15}],
    "motif": {"melody": "E4:1 G#4:.5 C#5:1.5", "why": "올라가는 3도 뒤 도약 — '일어나는' 소리. 오르간이 인트로에 혼자, 2절 빈자리에, 아웃트로에 조각으로"},
    "collision": ["장조 가스펠 레코드(따뜻, 느림)", "건조한 붐뱁(단단, 세속)", "배속 — 성스러운 걸 우습고 아프게 만드는 기계적 행위"],
    "irregular": [{"what": "1절 15마디", "why": "이야기가 격자보다 먼저 숨이 찬다"}, {"what": "훅 앞 1마디 turn", "why": "다 빼서 훅이 두 배로 떨어지게"},
                  {"what": "아웃트로 3마디", "why": "레코드는 깨끗한 작별을 못 한다"}],
    "constraints": ["90 BPM 정박 붐뱁", "샘플은 배속(+4)만", "샘플 105 Hz 아래 비우고 12k 위 깎기", "랩이 제일 앞, 새 악기는 뒤"],
    "references": "knowledge/styles/chipmunk-soul.yaml · 002 시티팝 칩멍크 · Back On My Feet",
    "not": ["하프타임", "타임스트레치 피치시프트", "후렴 서두르기", "추상명사 가사"],
}

VOICES = {
    "gen-singer-b": None,                       # 이미 설계됨(002) — 따뜻한 여성 소울 알토
    "bomf-rapper": None,                        # Back On My Feet 래퍼 — 본인이 들은 목소리
    "gen-rapper-c": None,                       # 젊은 테너 — 훅 더블
}


def ensure_voices():
    for name in VOICES:
        if not (vd.VOICES / name / "design.wav").exists():
            raise SystemExit(f"목소리 없음: {name} — 002/Back On My Feet 에서 만든 목소리가 sounds/voices 에 있어야 함")
    if not (voice.VOICES / "gen-singer-b" / "prompt.json").exists():
        print(voice.add_voice_aligned("gen-singer-b", vd.VOICES / "gen-singer-b" / "design.wav"))


def customize(spec, notes):
    chords = notes["sample"]["chords_after"]              # 배속 뒤 코드 4개(A장조 가스펠: IVmaj7 V/IV iii7 vi7 …)
    prog = " ".join(chords)
    prog_v = " ".join(chords + chords)                    # 8마디 주기
    spec["sections"] = [{"name": n, "bars": b} for n, b in FORM]
    spec["feel"], spec["intensity"] = "laid_back", 0.75
    spec["brief"] = "「Second Shift」 칩멍크 소울 — 가스펠 레코드(직접 연주·생성 여성 보컬) +4 배속, 붐뱁, 랩(bomf-rapper)"
    bars = {}
    b = 0
    for n, k in FORM:
        bars[n] = b
        b += k
    total = b

    t = spec["tracks"]
    t["Bass"]["volume_db"] = -3                                                   # v1~v3 sub -4~-5 dB(과다)
    t["Organ"] = {"sound": "church_organ", "role": "church organ", "pan": -0.18, "sends": {"0": -8}}
    t["Strings"] = {"preset": "strings/ensemble", "role": "strings", "pan": -0.25, "sends": {"0": -8}}
    t["Horns"] = {"preset": "brass/section", "role": "brass", "pan": 0.3, "sends": {"0": -12}}
    t["Choir"] = {"preset": "pad/choir", "role": "pad", "sends": {"0": -6}}
    vox_fx = [{"device": "eq", "params": {"Low-pass freq": 95, "Low-pass gain": -14, "Mid freq 1": 420, "Mid gain 1": -2, "Mid Q 1": 0.9,
                                           "Mid freq 2": 3200, "Mid gain 2": 3, "Mid Q 2": 0.7, "High-pass freq": 11000, "High-pass gain": 2}},
              {"device": "compressor", "params": {"threshold": -20, "ratio": 4, "attack": 8, "release": 90}}]
    t["Rap"] = {"role": "lead rap vocal", "sends": {"0": -17}, "fx": vox_fx}
    t["Chant"] = {"role": "hook chant", "pan": -0.1, "sends": {"0": -15}, "fx": vox_fx}
    t["Chant2"] = {"role": "hook chant double", "pan": 0.12, "sends": {"0": -15}, "fx": vox_fx}

    # 찹 건반(레시피가 만든 킷의 키) — 상행 / 하행 / turn 조각
    keys = sorted({n["pitch"] for p in spec["parts"] if p["track"] == "Chops" for n in p.get("notes", [])}) or [36]
    k = lambda i: keys[i % len(keys)]
    UP = [{"pitch": k(i), "start": s, "length": l, "velocity": v} for i, (s, l, v) in
          enumerate([(0, .55, 106), (1, .55, 94), (2, .6, 108), (3, .6, 98), (4, .55, 104), (5.5, .5, 90), (6, .6, 108), (7, .9, 100)])]
    DOWN = [{"pitch": k(len(keys) - 1 - i), "start": s, "length": l, "velocity": v} for i, (s, l, v) in
            enumerate([(0, .6, 108), (1, .55, 98), (2, .55, 104), (3, .6, 96), (4, .55, 106), (5.5, .5, 92), (6, .6, 108), (7, .9, 100)])]
    TURN = [{"pitch": k(0), "start": 0, "length": .35, "velocity": 96}, {"pitch": k(0), "start": .75, "length": .3, "velocity": 84},
            {"pitch": k(1), "start": 1.5, "length": .4, "velocity": 92}, {"pitch": k(2), "start": 2.5, "length": .4, "velocity": 98},
            {"pitch": k(3), "start": 3.25, "length": .7, "velocity": 104}]
    PAD = [{"pitch": k(i), "start": i * 2, "length": 1.9, "velocity": 40} for i in range(4)]     # 브리지: 찹을 길게 — 패드처럼

    sw = 0.56
    def drum(pat, fill=None):
        return {"pattern": pat, "swing": sw, "humanize_ms": 6, "humanize_vel": 8, **({"fill": fill} if fill else {})}
    D_MAIN = {"kick": "x.....x...x..x..", "snare": "....X.......X...", "hat": "x-x-x-x-x-x-x-x-"}
    D_MAIN2 = {"kick": "X.....x...X..x..", "snare": "....X..o....X..o", "hat": "x-x-x-x-x-x-x-x-", "open_hat": "..........x....."}
    D_HOOK = {"kick": "X..x......X..x..", "snare": "....X..o....X...", "hat": "x-x-x-x-x-x-x-x-"}
    D_HOOK2 = {"kick": "X..x..x...X..x..", "snare": "....X..o....X..o", "hat": "x-x-x-x-x-x-x-x-", "open_hat": "..............x."}
    D_INTRO = {"kick": "X.........x.....", "snare": "................", "hat": "................"}
    F1 = {"kick": "X.....x...X.....", "snare": "....X.......xoxo", "hat": "x.x.x.x.x.x....."}
    F2 = {"kick": "X.........X.....", "snare": "....X...XoXoXXXX", "hat": "x.x.x.x........."}

    sample = next(p for p in spec["parts"] if p["track"] == "Sample")["audio"]["path"]
    MOTIF = "E4:1 G#4:.5 C#5:1.5"
    rap_style_1 = "weary, low-key, holding something back, close to the mic"
    rap_style_2 = "steadier, a little proud, still quiet, close to the mic"
    chant_style = "chanting a hook, rhythmic, warm, not shouting"

    spec["parts"] = [
        {"track": "Sample", "in": ["intro", "verse1", "turn1", "verse2", "turn2"], "audio": {"path": sample, "every": 16, "gain_db": -4}},
        {"track": "Sample", "in": ["hook1", "hook2", "hook3"], "audio": {"path": sample, "every": 16}},
        {"track": "Sample", "in": ["bridge"], "audio": {"path": sample, "every": 16, "gain_db": -9}},
        {"track": "Sample", "in": ["outro"], "audio": {"path": sample, "every": 16, "gain_db": -3}},
        # 오르간 — 모티프 혼자 / 훅 패드 / 2절 대답 / 브리지 / 아웃트로 조각
        {"track": "Organ", "in": ["intro"], "melody": {"text": f"{MOTIF} r:1 G#4:1 E4:1 r:2 {MOTIF} r:1 B4:2 G#4:2", "velocity": 64, "repeat": False}},
        {"track": "Organ", "in": ["hook1", "hook2", "hook3"], "chords": {"progression": prog, "beats_per_chord": 4, "voicing": "pad", "velocity": 60, "low": 52, "high": 76}},
        {"track": "Organ", "in": ["verse2"], "chords": {"progression": prog_v, "beats_per_chord": 4, "voicing": "stab", "rhythm": [[2.5, .75, .9], [3.5, .5, .75]], "velocity": 50, "low": 52, "high": 74}},
        {"track": "Organ", "in": ["verse2"], "offset": 32, "melody": {"text": f"r:8 {MOTIF} r:1 r:4 r:8 C#5:1 A4:.5 E4:1.5 r:1 r:4", "velocity": 70, "repeat": False}},
        {"track": "Organ", "in": ["bridge"], "chords": {"progression": prog_v, "beats_per_chord": 4, "voicing": "pad", "velocity": 36, "low": 50, "high": 72}},
        {"track": "Organ", "in": ["outro"], "melody": {"text": f"{MOTIF} r:1 r:4 E4:2 C#5:2", "velocity": 58, "repeat": False}},
        # 드럼 — 브리지·turn 없음
        {"track": "Drums", "in": ["intro"], "drums": drum(D_INTRO)},
        {"track": "Drums", "in": ["verse1"], "drums": drum(D_MAIN, F1)},
        {"track": "Drums", "in": ["verse2"], "drums": drum(D_MAIN2, F1)},
        {"track": "Drums", "in": ["hook1"], "drums": drum(D_HOOK, F2)},
        {"track": "Drums", "in": ["hook2", "hook3"], "drums": drum(D_HOOK2, F2)},
        {"track": "Drums", "in": ["outro"], "drums": drum({"kick": "X.........x.....", "snare": "....x...........", "hat": "................"})},
        # 베이스 — 킥과 같이, 마디 끝 5도/옥타브
        {"track": "Bass", "in": ["verse1", "verse2"], "bass": {"progression": prog_v, "beats_per_chord": 4, "pattern": [[0, .9, 0], [1.5, .5, 0], [2.5, .45, 0], [3.25, .5, 7]], "velocity": 92, "low": 28, "high": 43}},
        {"track": "Bass", "in": ["hook1", "hook2"], "bass": {"progression": prog, "beats_per_chord": 4, "pattern": [[0, 1.1, 0], [1.75, .5, 0], [2.5, .4, 12], [3.25, .5, 7]], "velocity": 108, "low": 28, "high": 43}},
        {"track": "Bass", "in": ["hook3"], "bass": {"progression": prog, "beats_per_chord": 4, "pattern": [[0, .9, 0], [.75, .3, 0], [1.75, .5, 0], [2.5, .4, 12], [3.5, .4, 7]], "velocity": 110, "low": 28, "high": 43}},
        # 브리지엔 베이스 없음 — v3 스템 실측: 온음표 서브가 드럼 없는 브리지를 훅만큼 크게 만들었다
        # 로즈 — 훅에서만 얇게
        {"track": "Keys", "in": ["hook1", "hook2", "hook3"], "chords": {"progression": prog, "beats_per_chord": 4, "voicing": "rhodes", "rhythm": [[1, .5, 1], [3, .5, .9]], "velocity": 68}},
        # 찹 — 상행 / turn 조각 / 하행 / 브리지 패드 / 마지막 상행+하행
        {"track": "Chops", "in": ["hook1"], "notes": UP, "cycle_beats": 8},
        {"track": "Chops", "in": ["turn1", "turn2"], "notes": TURN},
        {"track": "Chops", "in": ["hook2"], "notes": DOWN, "cycle_beats": 8},
        {"track": "Chops", "in": ["bridge"], "notes": PAD, "cycle_beats": 8},
        {"track": "Chops", "in": ["hook3"], "notes": UP, "cycle_beats": 16},
        {"track": "Chops", "in": ["hook3"], "offset": 8, "notes": DOWN, "cycle_beats": 16},
        # 스트링·혼·콰이어 — 뒤에서
        {"track": "Strings", "in": ["hook2", "hook3"], "chords": {"progression": prog, "beats_per_chord": 4, "voicing": "pad", "velocity": 66}},
        {"track": "Horns", "in": ["hook3"], "chords": {"progression": prog, "beats_per_chord": 4, "voicing": "stab", "rhythm": [[0, .5, 1], [2.5, .75, .9]], "velocity": 90}},
        {"track": "Choir", "in": ["bridge", "outro"], "chords": {"progression": prog_v, "beats_per_chord": 4, "voicing": "pad", "velocity": 44}},
        # 랩 — 1절 15줄, 2절 16줄, 브리지 8줄(드럼 없이), 훅 챈트 + 더블
        {"track": "Rap", "in": ["verse1"], "rap": {"voice": "bomf-rapper", "lines": VERSE1, "beats_per_line": 4, "style": rap_style_1, "lock": 0.7, "seed": 5}},
        {"track": "Rap", "in": ["verse2"], "rap": {"voice": "bomf-rapper", "lines": VERSE2, "beats_per_line": 4, "style": rap_style_2, "lock": 0.72, "seed": 12}},
        {"track": "Rap", "in": ["bridge"], "rap": {"voice": "bomf-rapper", "lines": BRIDGE, "beats_per_line": 4, "style": "spoken, quiet, like a phone call, long pauses", "lock": 0.5, "seed": 19, "gain_db": -2.5}},
        {"track": "Chant", "in": ["hook1", "hook2", "hook3"], "rap": {"voice": "bomf-rapper", "lines": [{"text": l, "beats": b} for l, b in HOOK], "style": chant_style, "lock": 0.9, "seed": 21}},
        {"track": "Chant2", "in": ["hook3"], "rap": {"voice": "gen-rapper-c", "lines": [{"text": l, "beats": b} for l, b in HOOK], "style": chant_style, "lock": 0.9, "seed": 22, "gain_db": -4}},
    ]
    # 레코드 필터: 인트로 닫힘 → 열림, turn 마다 열쇠구멍, 아웃트로 닫힘
    pts = [{"bar": 0, "value": 700}, {"bar": 3.9, "value": 1100}, {"bar": 4, "value": 20000}]
    for tn in ("turn1", "turn2"):
        pts += [{"bar": bars[tn] - 0.05, "value": 20000}, {"bar": bars[tn], "value": 600}, {"bar": bars[tn] + 0.95, "value": 600}, {"bar": bars[tn] + 1, "value": 20000}]
    pts += [{"bar": bars["outro"], "value": 20000}, {"bar": total, "value": 450}]
    spec["automation"] = [{"track": "Sample", "device": 1, "param": "frequency", "points": pts}]
    spec["mix"] = {"balance": True, "target_lufs": -10.5,
                   "balance_lu": {"drums": 0, "rap": 1.5, "chant": 0.5, "chant2": -3, "sample": -2.5, "chops": -3.5, "bass": -5,
                                  "keys": -7, "organ": -8, "strings": -7, "horns": -7, "choir": -8}}
    return spec


if __name__ == "__main__":
    label = sys.argv[1] if len(sys.argv) > 1 else "v1"
    ensure_voices()
    concept_mod.save(NAME, CONCEPT)
    s, notes, rep = cs.build(NAME, bpm=BPM, semitones=4, key="F major", source_style="gospel", lead="rhodes", seed=41,
                             brief="「Second Shift」 칩멍크 소울 완성판", label=label, customize=customize,
                             vocal={"voice": "gen-singer-b", "lyrics": RECORD_LYRICS, "low": 57, "high": 72})
    print(json.dumps({k: rep.get(k) for k in ("file", "loudness", "bands_db", "issues")}, ensure_ascii=False, default=str))
