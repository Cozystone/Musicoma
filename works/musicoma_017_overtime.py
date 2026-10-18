"""NIGHT SHIFT · 08 「Overtime」 — 시티팝 디스코 레코드(+3) 위 Just Blaze 식 찹·혼. 가장 빠르고 화려. 훅 = 찹이 부른다(챈트는 한 줄).
화성 장치: IV 에서 시작해 I 를 sus4 로만 스치기(Street Lights) — 3음은 찹(샘플)이 정한다. 훅 앞 1마디 turn 반복.
전주 4마디(이 곡만 짧게 — 야근은 바로 시작한다).

    python works/musicoma_017_overtime.py v1
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from musicoma import arrange, concept as concept_mod, crate, theory
from musicoma.recipes import chipmunk_soul as cs

NAME = "ns-08-overtime"
BPM, ST = 94, 3
SRC_BPM = round(BPM / 2 ** (ST / 12), 3)            # 79.0
FORM = [("intro", 4), ("verse1", 16), ("turn1", 1), ("hook1", 8), ("verse2", 16), ("turn2", 1), ("hook2", 8), ("bridge", 8), ("turn3", 1), ("hook3", 8), ("outro", 4)]

REC_PROG = "IVmaj7 Isus4 ii7 Isus4 IVmaj7 Isus4 ii7 V7sus4"       # D: Gmaj7 Dsus4 Em7 Dsus4 | …
REC_MEL = ("r:.5 D5:.5 B4:.5 A4:.5 B4:1 D5:1 | r:.5 A4:.5 B4:.5 A4:.5 G4:2 | r:.5 E4:.5 G4:.5 A4:.5 B4:1 D5:1 | A4:3 r:1 | "
           "r:.5 D5:.5 B4:.5 A4:.5 B4:1 D5:1 | r:.5 A4:.5 B4:.5 A4:.5 G4:2 | r:.5 E4:.5 G4:.5 A4:.5 B4:1 D5:1 | G4:3 r:1")
REC_LYR = ("o- ver- time o- ver- time I'll be home when I'm home o- ver- time "
           "o- ver- time o- ver- time I'll be home when I'm home o- ver- time")   # 30 토큰 = 30 음표(마디별 5·4·5·1)

VERSE1 = [
    "Ninth floor, lights on a timer", "I wave so it stays lit",
    "Printer's doing two hundred pages", "For a meeting nobody reads",
    "Cart in the hall, radio low", "That's the only music",
    "Boss said hustle at six", "Hustle's a word for staying",
]
VERSE2 = [
    "Twelve-forty, the stairwell light", "Follows me floor by floor",
    "I take one warm page", "That's the bonus tonight",
    "Guard's asleep, TV on", "Pen on a chain, I sign out",
    "Street's wet, no rain", "I'm the walking one",
]
FLOW12 = [8, 8, 8, 8, 8, 8, 8, 8]
FLOW_A = FLOW12
FLOW_B = FLOW12
def flow(lines, beats):
    return [{"text": l, "beats": b} for l, b in zip(lines, beats)]
FLOW12 = [8, 8, 8, 8, 8, 8, 8, 8]
FLOW_A = FLOW12
FLOW_B = FLOW12
ADLIBS = [{"text": "uh", "beats": 16}, {"text": "wave", "beats": 16}, {"text": "yeah", "beats": 16}, {"text": "ha", "beats": 16}]
def flow(lines, beats):
    return [{"text": l, "beats": b} for l, b in zip(lines, beats)]
HOOK_CHANT = [("Overtime, overtime, I'll be home when I'm home", 8), ("Overtime, overtime, wave at the lights", 8)]
BRIDGE = ["Slide forty-one", "same sentence three ways", "I pick the worst one", "that's the one that sounds like work"]

RAP_CAPTION = ("old school hip hop, male rapper, laid back conversational flow, clear words, on the beat, "
               "leaves space between lines, no singing, dry close mic")
CONCEPT = {
    "thesis": "9층 야근 — 20분마다 일어나 센서등에 손을 흔드는 사람. 프린터·청소 카트·마지막 엘리베이터. 훅은 사람이 아니라 찹(빨라진 레코드)이 부른다",
    "arc": [{"section": "intro", "intent": "4마디, 바로 시작 — 찹 한 번 + 드럼", "energy": 0.6},
            {"section": "verse1", "intent": "빠른 말, 사물 나열, 혼 스탭이 줄 끝마다", "energy": 0.7},
            {"section": "turn1", "intent": "1마디 전부 뺌(Just Blaze)", "energy": 0.3},
            {"section": "hook1", "intent": "찹이 훅 — 'o-ver-time' 8조각 + 혼, 챈트 한 줄만", "energy": 0.95},
            {"section": "bridge", "intent": "드럼 없이 찹 패드 + 말", "energy": 0.35},
            {"section": "hook3", "intent": "찹 둘 겹침 + 혼 + 스트링", "energy": 1.0},
            {"section": "outro", "intent": "4마디, IV 에서 끝(안 끝난 느낌)", "energy": 0.4}],
    "motif": {"melody": "D5:.5 B4:.5 A4:.5 B4:1 D5:1", "why": "'o-ver-time' — 내려갔다 되돌아오는 야근"},
    "collision": ["시티팝 디스코(밝고 빠름)", "Just Blaze 찹·혼(거칠고 큼)", "I 를 끝내 3음 없이"],
    "irregular": [{"what": "I 는 sus4 로만", "why": "3음은 찹이 정한다 — 장·단이 흐려짐"}, {"what": "전주 4마디", "why": "야근은 바로 시작"}, {"what": "turn 3번", "why": "같은 장치를 세 번 — 기대하게"}],
    "constraints": ["94 BPM", "폭 -12~-15", "air -28~-32", "드럼 -3 · 랩 -6", "절/훅/브리지 3 dB"],
    "references": "knowledge/references/old-kanye-citypop.yaml — Touch the Sky·Street Lights / SPARKLE",
    "not": ["생성기 멜로디", "추상명사", "긴 전주(이 곡만)"],
}


def record():
    spec = cs.record_spec(f"{NAME}-record", SRC_BPM, "D major", "city-pop", "rhodes", seed=31,
                          vocal={"voice": "gen-singer-b", "lyrics": REC_LYR, "low": 62, "high": 76})
    for p in spec["parts"]:
        for k in ("chords", "bass"):
            if k in p:
                p[k]["progression"] = REC_PROG
        if "vocal" in p:
            p["vocal"]["melody"], p["vocal"]["lyrics"] = REC_MEL, REC_LYR
        if p["track"] == "Lead":
            p["melody"]["text"] = REC_MEL
    spec["tracks"]["Bass"] = {"preset": "bass/slap", "role": "bass"}
    spec["tracks"]["Brass"] = {"preset": "brass/section", "role": "brass", "pan": 0.25, "sends": {"0": -8}}
    spec["tracks"]["Guitar"] = {"preset": "guitar/clean", "role": "guitar", "pan": -0.3, "sends": {"0": -9}}
    spec["parts"] = [p for p in spec["parts"] if p["track"] not in ("Drums", "Bass")] + [
        {"track": "Drums", "in": ["A", "B"], "drums": {"pattern": {"kick": "x...x...x...x...", "snare": "....x.......x...", "hat": "x.x.x.x.x.x.x.x.", "open_hat": "..x...x...x...x."}, "swing": 0.5, "humanize_ms": 6, "humanize_vel": 10}},
        {"track": "Bass", "in": ["A", "B"], "bass": {"progression": REC_PROG, "beats_per_chord": 4, "pattern": [[0, .4, 0], [.5, .4, 12], [1, .4, 0], [1.5, .4, 12], [2, .4, 0], [2.5, .4, 12], [3, .4, 0], [3.5, .4, 7]], "velocity": 104}},
        {"track": "Brass", "in": ["B"], "chords": {"progression": REC_PROG, "beats_per_chord": 4, "voicing": "stab", "rhythm": [[0, .4, 1], [1.5, .4, .85], [3, .6, .9]], "velocity": 96}},
        {"track": "Guitar", "in": ["A", "B"], "chords": {"progression": REC_PROG, "beats_per_chord": 4, "voicing": "guitar", "rhythm": [[.5, .25, .8], [1.5, .25, .7], [2.5, .25, .8], [3.5, .25, .7]], "velocity": 72}},
    ]
    spec["brief"] = "「Overtime」 샘플용 레코드 — 시티팝 디스코(슬랩·브라스·클린 기타), IV→Isus4, gen-singer-b"
    return spec


def sample(rec_spec, rec):
    sections, _ = arrange._sections(rec_spec)
    b = next(s for s in sections if s["name"] == "B")
    spb = 60 / SRC_BPM
    start, end = b["start_bar"] * 4 * spb, (b["start_bar"] + 4) * 4 * spb
    stems = rec["stems"]
    parts_ = [k for k in ("Keys", "Strings", "Brass", "Guitar", "Vox") if k in stems]
    accomp = crate.mix_files([stems[k] for k in parts_], Path(rec["mix"]).with_name(f"{NAME}_accomp.wav"), gains_db=[0, -2, -1, -3, 2][:len(parts_)])
    aged = crate.age(accomp, "vinyl")
    loop = crate.loop_region(aged, start, end, 4, BPM, tag="sample_loop")
    vox_loop = crate.loop_region(stems["Vox"], start, end, 4, BPM, tag="vox_loop")
    chops = crate.chop(vox_loop["path"], mode="onsets", n=8, min_len=0.1, max_len=0.9)
    kit = crate.make_kit(chops, Path(chops[0]["path"]).parent / "chops.sfz")
    after = [theory.transpose_chord(c, ST) for c in theory.progression(REC_PROG, "D", "major")[:4]]
    return loop, kit, after


def beat(loop, kit, after):
    prog = " ".join(after)                                   # Bbmaj7 Fsus4 Gm7 Fsus4
    keys = sorted(kit["kit"].values())
    k = lambda i: keys[i % len(keys)]
    # 훅 = 찹이 부른다: 'o-ver-time' 조각(처음 3개)을 리듬으로
    HOOK_CH = [{"pitch": k(p), "start": s, "length": .3, "velocity": v} for p, s, v in
               [(0, 0, 110), (1, .5, 100), (2, 1, 112), (0, 2, 108), (1, 2.5, 98), (2, 3, 110), (3, 3.5, 104),
                (0, 4, 110), (1, 4.5, 100), (2, 5, 112), (4, 6, 106), (5, 6.5, 100), (6, 7, 108), (7, 7.5, 112)]]
    HOOK_CH2 = [{**n, "start": n["start"] + .25, "velocity": n["velocity"] - 14} for n in HOOK_CH]
    INTRO_CH = [{"pitch": k(0), "start": 0, "length": .4, "velocity": 110}, {"pitch": k(1), "start": .5, "length": .4, "velocity": 100}, {"pitch": k(2), "start": 1, "length": .8, "velocity": 112}]
    TURN = [{"pitch": k(7), "start": 0, "length": .5, "velocity": 100}, {"pitch": k(7), "start": 1, "length": .5, "velocity": 92}, {"pitch": k(7), "start": 2, "length": .5, "velocity": 96}, {"pitch": k(0), "start": 3, "length": .9, "velocity": 112}]
    PAD = [{"pitch": k(i), "start": i * 2, "length": 1.9, "velocity": 44} for i in range(4)]
    sw = 0.57
    D = lambda pat, fill=None: {"pattern": pat, "swing": sw, "humanize_ms": 5, "humanize_vel": 8, **({"fill": fill} if fill else {})}
    MAIN = {"kick": "X..x..x...X..x..", "snare": "....X..o....X...", "hat": "x-x-x-x-x-x-x-x-"}
    HK = {"kick": "X..x..x...X.x.x.", "snare": "....X..o....X..o", "hat": "x-x-x-x-x-x-x-x-", "open_hat": "..............x."}
    F2 = {"kick": "X.........X.....", "snare": "....X...XoXoXXXX", "hat": "x.x.x.x........."}
    vox_fx = [{"device": "eq", "params": {"Low-pass freq": 95, "Low-pass gain": -14, "Mid freq 1": 420, "Mid gain 1": -2, "Mid Q 1": 0.9, "Mid freq 2": 3200, "Mid gain 2": 3, "Mid Q 2": 0.7, "High-pass freq": 11000, "High-pass gain": 1}},
              {"device": "compressor", "params": {"threshold": -20, "ratio": 4, "attack": 8, "release": 90}}]
    bars, b = {}, 0
    for n, kk in FORM:
        bars[n] = b; b += kk
    total = b
    spec = {
        "name": NAME, "bpm": BPM, "key": "F major", "style": "chipmunk-soul", "feel": "laid_back", "intensity": 0.9,
        "brief": "NIGHT SHIFT 08 「Overtime」 — 시티팝 디스코 레코드(+3) 위 Just Blaze 찹·혼, 훅은 찹, IV→Isus4",
        "sections": [{"name": n, "bars": kk} for n, kk in FORM],
        "tracks": {
            "Sample": {"role": "sample loop (varispeed +3, vinyl)", "fx": [
                {"device": "eq", "params": {"Low-pass freq": 110, "Low-pass gain": -14, "Mid freq 1": 350, "Mid gain 1": -3, "Mid Q 1": 0.9, "High-pass freq": 10500, "High-pass gain": -4}},
                {"device": "lowpass", "params": {"frequency": 20000}}]},
            "Drums": {"sound": "drums_acoustic_basic", "role": "boom bap drums (hard)", "sends": {"0": -24}, "fx": [
                {"device": "eq", "params": {"Low-pass freq": 62, "Low-pass gain": 4, "Mid freq 1": 350, "Mid gain 1": -3, "Mid Q 1": 1.0, "Mid freq 2": 4500, "Mid gain 2": 3.5}},
                {"device": "compressor", "params": {"threshold": -18, "ratio": 4.5, "attack": 15, "release": 70, "output gain": 3.5}}]},
            "Bass": {"sound": "bass_sub", "role": "sub bass", "volume_db": -3, "fx": [{"device": "lowpass", "params": {"frequency": 700}}]},
            "Horns": {"preset": "brass/section", "role": "horn stabs", "pan": 0.25, "sends": {"0": -10}},
            "Keys": {"preset": "keys/rhodes_classic", "role": "rhodes", "pan": -0.15, "sends": {"0": -8}},
            "Chops": {"sound": kit["sfz"], "role": "chipmunk vocal chops (the hook)", "pan": 0.05, "sends": {"0": -9}},
            "Chops2": {"sound": kit["sfz"], "role": "chops double", "pan": 0.3, "sends": {"0": -9}},
            "Strings": {"preset": "strings/ensemble", "role": "strings", "pan": -0.25, "sends": {"0": -8}},
            "Rap": {"role": "lead rap vocal", "sends": {"0": -17}, "fx": vox_fx},
            "Chant": {"role": "hook chant (one line)", "pan": -0.08, "sends": {"0": -15}, "fx": vox_fx},
            "Adlib": {"role": "ad-libs (C)", "pan": 0.25, "sends": {"0": -10}, "fx": vox_fx},
        },
        "buses": [{"name": "Verb", "bus": 0, "device": "Dragonfly Plate Reverb", "volume_db": -5}],
        "parts": [
            {"track": "Sample", "in": ["intro", "turn1", "turn2", "turn3"], "audio": {"path": loop["path"], "every": 16, "gain_db": -2}},
            {"track": "Sample", "in": ["verse1", "verse2"], "audio": {"path": loop["path"], "every": 16, "gain_db": -3.5}},
            {"track": "Sample", "in": ["hook1", "hook2", "hook3", "outro"], "audio": {"path": loop["path"], "every": 16}},
            {"track": "Sample", "in": ["bridge"], "audio": {"path": loop["path"], "every": 16, "gain_db": -9}},
            {"track": "Chops", "in": ["intro"], "notes": INTRO_CH, "cycle_beats": 8},
            {"track": "Chops", "in": ["hook1", "hook2", "hook3", "outro"], "notes": HOOK_CH, "cycle_beats": 8},
            {"track": "Chops2", "in": ["hook3"], "notes": HOOK_CH2, "cycle_beats": 8},
            {"track": "Chops", "in": ["turn1", "turn2", "turn3"], "notes": TURN},
            {"track": "Chops", "in": ["bridge"], "notes": PAD, "cycle_beats": 8},
            {"track": "Drums", "in": ["intro", "verse1", "verse2"], "drums": D(MAIN, F2)},
            {"track": "Drums", "in": ["hook1", "hook2", "hook3", "outro"], "drums": D(HK, F2)},
            {"track": "Bass", "in": ["intro", "verse1", "verse2", "hook1", "hook2", "hook3", "outro"], "bass": {"progression": prog, "beats_per_chord": 4, "pattern": [[0, .9, 0], [.75, .3, 0], [1.75, .5, 0], [2.5, .4, 12], [3.5, .4, 7]], "velocity": 108, "low": 28, "high": 43}},
            {"track": "Horns", "in": ["verse1", "verse2"], "chords": {"progression": prog, "beats_per_chord": 4, "voicing": "stab", "rhythm": [[3, .5, .9], [3.5, .5, .8]], "velocity": 86}},
            {"track": "Horns", "in": ["hook1", "hook2", "hook3"], "chords": {"progression": prog, "beats_per_chord": 4, "voicing": "stab", "rhythm": [[0, .5, 1], [1.5, .4, .85], [2.5, .75, .95]], "velocity": 100}},
            {"track": "Keys", "in": ["hook1", "hook2", "hook3"], "chords": {"progression": prog, "beats_per_chord": 4, "voicing": "rhodes", "rhythm": [[1, .5, 1], [3, .5, .9]], "velocity": 66}},
            {"track": "Strings", "in": ["hook3", "outro"], "chords": {"progression": prog, "beats_per_chord": 4, "voicing": "pad", "velocity": 62}},
            {"track": "Rap", "in": ["verse1"], "rap": {"voice": "bomf-rapper", "lines": flow(VERSE1, FLOW_A), "style": "fast, dry, counting things, a little manic, close to the mic", "lock": 0.8, "seed": 5}},
            {"track": "Rap", "in": ["verse2"], "rap": {"voice": "bomf-rapper", "lines": flow(VERSE2, FLOW_B), "style": "fast, tired-funny, close to the mic", "lock": 0.8, "seed": 12}},
            {"track": "Rap", "in": ["bridge"], "rap": {"voice": "bomf-rapper", "lines": BRIDGE, "beats_per_line": 8, "style": "spoken, flat, reading a slide out loud", "lock": 0.5, "seed": 19, "gain_db": -2}},
            {"track": "Chant", "in": ["hook1", "hook2", "hook3"], "offset": 16, "rap": {"voice": "bomf-rapper", "lines": [{"text": l, "beats": b_} for l, b_ in HOOK_CHANT], "style": "chanting a hook, loud, rough", "lock": 0.9, "seed": 21}},
        ],
        "automation": [{"track": "Sample", "device": 1, "param": "frequency", "points": [
            {"bar": 0, "value": 20000},
            *[pt for tn in ("turn1", "turn2", "turn3") for pt in ({"bar": bars[tn] - 0.05, "value": 20000}, {"bar": bars[tn], "value": 600}, {"bar": bars[tn] + 0.95, "value": 600}, {"bar": bars[tn] + 1, "value": 20000})],
            {"bar": total - 1, "value": 20000}, {"bar": total, "value": 500}]}],
        "mix": {"balance": True, "target_lufs": -11,
                "balance_lu": {"drums": 0, "rap": 1.5, "chant": 0.5, "adlib": -6, "sample": -2.5, "chops": -2, "chops2": -5, "bass": -5, "horns": -6, "keys": -8, "strings": -8}},
    }
    return spec


if __name__ == "__main__":
    label = sys.argv[1] if len(sys.argv) > 1 else "v1"
    concept_mod.save(NAME, CONCEPT)
    rspec = record()
    print("[1] 레코드 녹음", SRC_BPM, "BPM D major", flush=True)
    rec = arrange.bounce(rspec, stems=True, label="record")
    loop, kit, after = sample(rspec, rec)
    print("[2-3] 샘플", loop["path"], "코드(+3)", after, "찹", len(kit["kit"]), flush=True)
    spec = beat(loop, kit, after)
    from musicoma import album
    s, rep = album.rap_with_lego(spec, label, RAP_CAPTION, log=lambda m: print("[4]", m, flush=True))
    print(json.dumps({k: rep.get(k) for k in ("file", "loudness", "bands_db", "issues")}, ensure_ascii=False, default=str), flush=True)
