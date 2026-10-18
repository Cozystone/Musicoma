"""NIGHT SHIFT · 05 「Pay Phone」 — 70년대 소울 발라드 레코드(+5) 위 Late Registration 식 스트링·팀파니·하프.
화성 장치: 샘플 루프 끝이 V7/vi 로 끝나 I 로 되돌아오는 '풀리지 않는 4마디'(칸예 시티팝 02 의 장치를 의도적으로).
전주 16마디(본인: 전주 짧고 바로 랩 금지) — 스트링이 먼저, 레코드는 8마디째, 드럼은 13마디째, 랩은 17마디부터.

    python works/musicoma_015_pay_phone.py v1
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from musicoma import arrange, concept as concept_mod, crate, theory
from musicoma.recipes import chipmunk_soul as cs

NAME = "ns-05-pay-phone"
BPM, ST = 72, 5
SRC_BPM = round(BPM / 2 ** (ST / 12), 3)            # 53.9
FORM = [("intro", 16), ("verse1", 16), ("hook1", 8), ("verse2", 16), ("hook2", 8), ("bridge", 8), ("hook3", 8), ("outro", 6)]

REC_PROG = "Imaj7 vi7 ii7 V7/vi IVmaj7 iii7 ii7 V7sus4"          # Eb: Ebmaj7 Cm7 Fm7 G7 | Abmaj7 Gm7 Fm7 Bb7sus4
REC_MEL = ("r:1 G4:1 Bb4:1 Eb5:1 | D5:2 C5:1 Bb4:1 | r:1 Ab4:1 Bb4:1 C5:1 | B4:3 r:1 | "
           "r:1 Ab4:1 C5:1 Eb5:1 | D5:2 Bb4:1 G4:1 | r:1 F4:1 G4:1 Ab4:1 | G4:3 r:1")
REC_LYR = "if you pick up I'll say no- thing at all if you pick up I'll stay on the line now"   # 20 토큰 = 20 음표

VERSE1 = [
    "Last pay phone outside the laundromat", "Six quarters and a number",
    "Dial tone like your fridge at night", "I hold the thing like a hand",
    "Dryers going round behind the glass", "Guy asleep on the folding table",
    "First quarter in, the click, the hum", "I hang it up gentle, like it's asleep",
]
VERSE2 = [
    "Second night, a dollar in quarters", "If she picks up I'll say nothing",
    "Ring one, the dryers stop", "Ring four, a machine, not her voice",
    "I listen to the nothing after the beep", "The quarters drop back, no answer",
    "Warm in my palm, like they went somewhere", "Most honest thing all week",
]
FLOW12 = [8, 8, 8, 8, 8, 8, 8, 8]
FLOW_A = FLOW12
FLOW_B = FLOW12
ADLIBS = [{"text": "uh", "beats": 16}]
def flow(lines, beats):
    return [{"text": l, "beats": b} for l, b in zip(lines, beats)]
HOOK = [("Pay phone, pay phone, six quarters and a number", 8), ("If you pick up, if you pick up, I'll say nothing", 8),
        ("Pay phone, pay phone, the price of almost", 8), ("Keep the change, keep the change, I'll keep the walk", 8)]
BRIDGE_MEL = "r:2 Eb4:1 F4:1 | G4:2 F4:2 | r:2 Eb4:1 C4:1 | Bb3:2 C4:2 | r:2 Eb4:1 F4:1 | G4:2 Ab4:2 | r:1 G4:1 F4:1 Eb4:1 | Eb4:4"
BRIDGE_LYR = "if you pick up I'll say no- thing if you pick up I'll say no- thing"       # 16 토큰 = 16 음표

RAP_CAPTION = ("old school hip hop, male rapper, laid back conversational flow, clear words, on the beat, "
               "leaves space between lines, no singing, dry close mic")
CONCEPT = {
    "thesis": "동네 마지막 공중전화 — 전화를 거는 게 아니라 거기까지 걷는 것이 목적인 사람. 받지 않는 번호에 동전을 넣고, 기계가 동전을 돌려준다",
    "arc": [{"section": "intro", "intent": "16마디: 스트링 → 8마디 레코드(필터) → 13마디 팀파니·드럼 → 17마디 랩", "energy": 0.3},
            {"section": "verse1", "intent": "첫 밤. 동전을 넣지 않는다", "energy": 0.5},
            {"section": "hook1", "intent": "찹 'if you pick up…' + 챈트, 스트링", "energy": 0.8},
            {"section": "verse2", "intent": "둘째 밤. 넷 울리고 기계가 받는다, 동전이 돌아온다", "energy": 0.6},
            {"section": "bridge", "intent": "드럼 없음. 하프·첼로 위에서 남성 가수가 느리게", "energy": 0.35},
            {"section": "hook3", "intent": "다 들어옴, 팀파니 롤", "energy": 1.0},
            {"section": "outro", "intent": "6마디 — 스트링만 남고 V7/vi 에서 끝(풀리지 않음)", "energy": 0.2}],
    "motif": {"melody": "G4:1 Bb4:1 Eb5:1 D5:2", "why": "올라가서 한 음 내려오는 '거의' — 받을 듯 안 받는"},
    "collision": ["70년대 소울 발라드(느리고 두꺼움)", "Late Registration 오케스트라(스트링·팀파니·하프)", "4마디마다 풀리지 않는 도미넌트"],
    "irregular": [{"what": "루프 끝 V7/vi 미해결", "why": "칸예 시티팝 02 의 장치 — 본인이 성공작으로 꼽은 긴장"}, {"what": "전주 16마디·아웃트로 6마디", "why": "걷는 곡"}],
    "constraints": ["72 BPM", "폭 -12~-15", "air -28~-32", "드럼 -4 · 랩 -6", "절/훅/브리지 3 dB"],
    "references": "knowledge/references/old-kanye-citypop.yaml — Heard 'Em Say·Diamonds / 칸예 시티팝 02",
    "not": ["생성기 멜로디", "추상명사", "전 구간 같은 크기"],
}


def record():
    spec = cs.record_spec(f"{NAME}-record", SRC_BPM, "Eb major", "soul", "rhodes", seed=23,
                          vocal={"voice": "gen-singer-b", "lyrics": REC_LYR, "low": 60, "high": 76})
    for p in spec["parts"]:
        for k in ("chords", "bass"):
            if k in p:
                p[k]["progression"] = REC_PROG
        if "vocal" in p:
            p["vocal"]["melody"], p["vocal"]["lyrics"] = REC_MEL, REC_LYR
        if p["track"] == "Lead":
            p["melody"]["text"] = REC_MEL
    spec["tracks"]["Keys"] = {"preset": "keys/wurlitzer", "role": "keys", "pan": -0.15, "sends": {"0": -10}}
    spec["tracks"]["Cello"] = {"preset": "strings/cello", "role": "strings", "pan": 0.2, "sends": {"0": -8}}
    spec["parts"] = [p for p in spec["parts"] if p["track"] != "Drums"] + [
        {"track": "Drums", "in": ["A", "B"], "drums": {"pattern": {"kick": "x.......x.......", "snare": "....x.......x...", "hat": "x.x.x.x.x.x.x.x."}, "swing": 0.55, "humanize_ms": 12, "humanize_vel": 14}},
        {"track": "Cello", "in": ["B"], "bass": {"progression": REC_PROG, "beats_per_chord": 4, "low": 36, "high": 55, "pattern": [[0, 3.8, 12]]}},
    ]
    spec["brief"] = "「Pay Phone」 샘플용 레코드 — 70년대 소울 발라드(부를리처·스트링·첼로), 직접 쓴 멜로디·가사, gen-singer-b"
    return spec


def sample(rec_spec, rec):
    sections, _ = arrange._sections(rec_spec)
    b = next(s for s in sections if s["name"] == "B")
    spb = 60 / SRC_BPM
    start, end = b["start_bar"] * 4 * spb, (b["start_bar"] + 4) * 4 * spb
    stems = rec["stems"]
    parts_ = [k for k in ("Keys", "Strings", "Cello", "Vox") if k in stems]
    accomp = crate.mix_files([stems[k] for k in parts_], Path(rec["mix"]).with_name(f"{NAME}_accomp.wav"), gains_db=[0, -1, -2, 2][:len(parts_)])
    aged = crate.age(accomp, "vinyl")
    loop = crate.loop_region(aged, start, end, 4, BPM, tag="sample_loop")
    vox_loop = crate.loop_region(stems["Vox"], start, end, 4, BPM, tag="vox_loop")
    chops = crate.chop(vox_loop["path"], mode="onsets", n=8, min_len=0.15, max_len=1.4)
    kit = crate.make_kit(chops, Path(chops[0]["path"]).parent / "chops.sfz")
    after = [theory.transpose_chord(c, ST) for c in theory.progression(REC_PROG, "Eb", "major")[:4]]
    return loop, kit, after


def beat(loop, kit, after):
    prog = " ".join(after)                                   # Abmaj7 Fm7 Bbm7 G7
    keys = sorted(kit["kit"].values())
    k = lambda i: keys[i % len(keys)]
    UP = [{"pitch": k(i), "start": s, "length": l, "velocity": v} for i, (s, l, v) in enumerate([(0, .9, 104), (1.5, .7, 92), (2.5, .9, 106), (4, .9, 100), (5.5, .7, 90), (6, 1.4, 108)])]
    PAD = [{"pitch": k(i), "start": i * 2, "length": 1.9, "velocity": 40} for i in range(4)]
    sw = 0.55
    D = lambda pat, fill=None: {"pattern": pat, "swing": sw, "humanize_ms": 7, "humanize_vel": 9, **({"fill": fill} if fill else {})}
    MAIN = {"kick": "x.....x...x.....", "snare": "....X.......X...", "hat": "x.x.x.x.x.x.x.x."}
    MAIN2 = {"kick": "X.....x...X..x..", "snare": "....X..o....X...", "hat": "x-x-x-x-x-x-x-x-"}
    HK = {"kick": "X..x......X..x..", "snare": "....X..o....X...", "hat": "x-x-x-x-x-x-x-x-", "open_hat": "..............x."}
    F1 = {"kick": "X.....x...X.....", "snare": "....X.......xoxo", "hat": "x.x.x.x.x.x....."}
    F2 = {"kick": "X.........X.....", "snare": "....X...XoXoXXXX", "hat": "x.x.x.x........."}
    TIMP_ROLL = [{"pitch": 44, "start": i * .25, "length": .2, "velocity": 60 + int(i * 4)} for i in range(16)]          # 4박 롤(Ab1)
    vox_fx = [{"device": "eq", "params": {"Low-pass freq": 95, "Low-pass gain": -14, "Mid freq 1": 420, "Mid gain 1": -2, "Mid Q 1": 0.9, "Mid freq 2": 3200, "Mid gain 2": 3, "Mid Q 2": 0.7, "High-pass freq": 11000, "High-pass gain": 1}},
              {"device": "compressor", "params": {"threshold": -20, "ratio": 4, "attack": 8, "release": 90}}]
    bars, b = {}, 0
    for n, kk in FORM:
        bars[n] = b; b += kk
    total = b
    spec = {
        "name": NAME, "bpm": BPM, "key": "Ab major", "style": "chipmunk-soul", "feel": "laid_back", "intensity": 0.65,
        "brief": "NIGHT SHIFT 05 「Pay Phone」 — 70년대 소울 레코드(+5) 위 Late Registration 스트링·팀파니, 전주 16마디, 루프 끝 V7/vi 미해결",
        "sections": [{"name": n, "bars": kk} for n, kk in FORM],
        "tracks": {
            "Sample": {"role": "sample loop (varispeed +5, vinyl)", "fx": [
                {"device": "eq", "params": {"Low-pass freq": 110, "Low-pass gain": -14, "Mid freq 1": 350, "Mid gain 1": -3, "Mid Q 1": 0.9, "High-pass freq": 10500, "High-pass gain": -4}},
                {"device": "lowpass", "params": {"frequency": 20000}}]},
            "Drums": {"sound": "drums_acoustic_basic", "role": "boom bap drums", "sends": {"0": -22}, "fx": [
                {"device": "eq", "params": {"Low-pass freq": 62, "Low-pass gain": 3, "Mid freq 1": 350, "Mid gain 1": -3, "Mid Q 1": 1.0, "Mid freq 2": 4500, "Mid gain 2": 2.5}},
                {"device": "compressor", "params": {"threshold": -19, "ratio": 4, "attack": 18, "release": 80, "output gain": 3}}]},
            "Bass": {"sound": "bass_sub", "role": "sub bass", "volume_db": -3, "fx": [{"device": "lowpass", "params": {"frequency": 650}}]},
            "Keys": {"preset": "keys/rhodes_dark", "role": "rhodes layer", "pan": -0.15, "sends": {"0": -8}},
            "Chops": {"sound": kit["sfz"], "role": "chipmunk vocal chops", "pan": 0.1, "sends": {"0": -10}},
            "Strings": {"preset": "strings/ensemble", "role": "strings", "pan": -0.25, "sends": {"0": -7}},
            "Cello": {"preset": "strings/cello", "role": "cello", "pan": 0.2, "sends": {"0": -9}},
            "Harp": {"preset": "pluck/harp", "role": "harp", "pan": 0.3, "sends": {"0": -8}},
            "Timpani": {"sound": "timpani", "role": "timpani", "pan": -0.1, "sends": {"0": -10}},
            "Rap": {"role": "lead rap vocal", "sends": {"0": -16}, "fx": vox_fx},
            "Chant": {"role": "hook chant", "pan": -0.08, "sends": {"0": -14}, "fx": vox_fx},
            "Adlib": {"role": "ad-libs (sung, far)", "pan": 0.25, "sends": {"0": -6}, "fx": vox_fx},
            "Singer": {"role": "bridge vocal (ns-singer-m)", "sends": {"0": -9}, "fx": [{"device": "compressor", "params": {"threshold": -18, "ratio": 3}}]},
        },
        "buses": [{"name": "Verb", "bus": 0, "device": "Dragonfly Hall Reverb", "volume_db": -6}],
        "parts": [
            {"track": "Sample", "in": ["intro"], "offset": 32, "audio": {"path": loop["path"], "every": 16, "gain_db": -3}},
            {"track": "Sample", "in": ["verse1", "verse2"], "audio": {"path": loop["path"], "every": 16, "gain_db": -3.5}},
            {"track": "Sample", "in": ["hook1", "hook2", "hook3"], "audio": {"path": loop["path"], "every": 16}},
            {"track": "Sample", "in": ["bridge"], "audio": {"path": loop["path"], "every": 16, "gain_db": -9}},
            {"track": "Strings", "in": ["intro"], "chords": {"progression": prog, "beats_per_chord": 4, "voicing": "pad", "velocity": 54, "legato": 1.0}},
            {"track": "Strings", "in": ["hook1", "hook2", "hook3", "outro"], "chords": {"progression": prog, "beats_per_chord": 4, "voicing": "pad", "velocity": 64, "legato": 1.0}},
            {"track": "Cello", "in": ["intro", "bridge", "outro"], "bass": {"progression": prog, "beats_per_chord": 4, "low": 36, "high": 55, "pattern": [[0, 3.8, 12]], "velocity": 70}},
            {"track": "Harp", "in": ["bridge"], "chords": {"progression": prog, "beats_per_chord": 4, "voicing": "spread", "rhythm": [[0, .5, .9], [.5, .5, .7], [1, .5, .8], [1.5, .5, .7], [2, .5, .85], [2.5, .5, .7], [3, .5, .8], [3.5, .5, .7]], "velocity": 62}},
            {"track": "Timpani", "in": ["intro"], "offset": 44, "notes": TIMP_ROLL},
            {"track": "Timpani", "in": ["hook3"], "offset": 28, "notes": TIMP_ROLL},
            {"track": "Timpani", "in": ["hook1", "hook2", "hook3"], "notes": [{"pitch": 44, "start": 0, "length": 1, "velocity": 96}], "cycle_beats": 16},
            {"track": "Drums", "in": ["intro"], "offset": 48, "drums": D({"kick": "x.........x.....", "snare": "....x.......x...", "hat": "................"})},
            {"track": "Drums", "in": ["verse1"], "drums": D(MAIN, F1)},
            {"track": "Drums", "in": ["verse2"], "drums": D(MAIN2, F1)},
            {"track": "Drums", "in": ["hook1", "hook2", "hook3"], "drums": D(HK, F2)},
            {"track": "Bass", "in": ["verse1", "verse2"], "bass": {"progression": prog, "beats_per_chord": 4, "pattern": [[0, 1.4, 0], [2, .9, 0], [3.25, .6, 7]], "velocity": 96, "low": 28, "high": 43}},
            {"track": "Bass", "in": ["hook1", "hook2", "hook3"], "bass": {"progression": prog, "beats_per_chord": 4, "pattern": [[0, 1.1, 0], [1.75, .5, 0], [2.5, .4, 12], [3.25, .5, 7]], "velocity": 104, "low": 28, "high": 43}},
            {"track": "Keys", "in": ["verse2", "hook1", "hook2", "hook3"], "chords": {"progression": prog, "beats_per_chord": 4, "voicing": "rhodes", "rhythm": [[1, .5, 1], [3, .5, .9]], "velocity": 62}},
            {"track": "Chops", "in": ["hook1", "hook2", "hook3"], "notes": UP, "cycle_beats": 8},
            {"track": "Chops", "in": ["bridge"], "notes": PAD, "cycle_beats": 8},
            {"track": "Rap", "in": ["verse1"], "rap": {"voice": "bomf-rapper", "lines": flow(VERSE1, FLOW_A), "style": "slow, tired, telling a story to nobody, close to the mic", "lock": 0.65, "seed": 5}},
            {"track": "Rap", "in": ["verse2"], "rap": {"voice": "bomf-rapper", "lines": flow(VERSE2, FLOW_B), "style": "slow, steadier, a little bitter, close to the mic", "lock": 0.68, "seed": 12}},
            {"track": "Chant", "in": ["hook1", "hook2", "hook3"], "rap": {"voice": "bomf-rapper", "lines": [{"text": l, "beats": b_} for l, b_ in HOOK], "style": "chanting a hook softly, almost singing", "lock": 0.88, "seed": 21}},
            {"track": "Singer", "in": ["bridge"], "vocal": {"voice": "ns-singer-m", "melody": BRIDGE_MEL, "lyrics": BRIDGE_LYR, "seed": 3}},
        ],
        "automation": [{"track": "Sample", "device": 1, "param": "frequency", "points": [
            {"bar": 8, "value": 500}, {"bar": 12, "value": 900}, {"bar": 15.9, "value": 1400}, {"bar": 16, "value": 20000},
            {"bar": bars["outro"], "value": 20000}, {"bar": total, "value": 400}]}],
        "mix": {"balance": True, "target_lufs": -11,
                "balance_lu": {"drums": 0, "rap": 1.5, "chant": 0.5, "adlib": -7, "sample": -2.5, "chops": -4, "bass": -5, "keys": -8, "strings": -6, "cello": -8, "harp": -11, "timpani": -5, "singer": 0.5}},
    }
    return spec


if __name__ == "__main__":
    label = sys.argv[1] if len(sys.argv) > 1 else "v1"
    concept_mod.save(NAME, CONCEPT)
    rspec = record()
    print("[1] 레코드 녹음", SRC_BPM, "BPM Eb major", flush=True)
    rec = arrange.bounce(rspec, stems=True, label="record")
    loop, kit, after = sample(rspec, rec)
    print("[2-3] 샘플", loop["path"], "코드(+5)", after, "찹", len(kit["kit"]), flush=True)
    spec = beat(loop, kit, after)
    from musicoma import album
    s, rep = album.rap_with_lego(spec, label, RAP_CAPTION, log=lambda m: print("[4]", m, flush=True))
    print(json.dumps({k: rep.get(k) for k in ("file", "loudness", "bands_db", "issues")}, ensure_ascii=False, default=str), flush=True)
