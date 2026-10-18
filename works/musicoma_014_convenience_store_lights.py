"""NIGHT SHIFT · 04 「Convenience Store Lights」 — 시티팝 펑크 레코드(+3) 위 Graduation 식 바운스·신스 브라스.
브리프: WORKS/2026-10_night-shift-album/tracks/04-convenience-store-lights.md · 화성 장치: 레코드 B 의 I7 → IV(가스펠 2차 도미넌트)를 신스 브라스 스탭이 때림.

    python works/musicoma_014_convenience_store_lights.py v1
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from musicoma import arrange, concept as concept_mod, crate, theory
from musicoma.recipes import chipmunk_soul as cs

NAME = "ns-04-convenience-store-lights"
BPM, ST = 96, 3
SRC_BPM = round(BPM / 2 ** (ST / 12), 3)            # 80.7
FORM = [("intro", 8), ("verse1", 16), ("hook1", 8), ("verse2", 16), ("hook2", 8), ("bridge", 8), ("hook3", 8), ("outro", 4)]

REC_PROG = "Imaj7 I7 IVmaj7 iv7 Imaj7 I7 IVmaj7 V7sus4"          # G: Gmaj7 G7 Cmaj7 Cm7 | … V7sus4
REC_MEL = ("r:.5 D4:.5 B4:.5 B4:.5 A4:1 G4:1 | r:1 F4:.5 G4:.5 A4:1 G4:1 | r:.5 E4:.5 G4:.5 A4:.5 B4:1 A4:1 | G4:.5 Eb4:.5 D4:2 r:1 | "
           "r:.5 D4:.5 B4:.5 B4:.5 A4:1 G4:1 | r:1 F4:.5 G4:.5 A4:1 G4:1 | r:.5 E4:.5 G4:.5 A4:.5 B4:1 A4:1 | D5:1 B4:1 G4:2")
REC_LYR = ("o- pen all night ba- by come in- side come in from the cold we're o- pen "
           "o- pen all night ba- by come in- side the lights are on for you to- night")   # 34 토큰 = 34 음표(마디별 5·4·5·3)

VERSE1 = [                                          # 8줄 — ACE lego 가 절 전체를 한 번에
    "Three a.m., the only sun is the sign", "Fluorescent on the gum, on me",
    "Expiry stickers, little days I lost", "Ding-dong, first face in an hour",
    "He wants the spicy one, no bag", "Outside is black glass, inside is noon",
    "One umbrella nobody's claimed", "When the sky goes grey I put the bread out",
]
VERSE2 = [                                          # 손님과 알바를 한 사람이 번갈아 말함
    "Kid's got a lanyard on, security", "He's off, I'm on, same shift",
    "Walked eleven blocks, train stopped at one", "Every shop dark but this box of light",
    "Ding-dong, nobody, just the wind", "Welcome to the wind, come in",
    "Took the umbrella, it's not raining", "Little roof over my head",
]
FLOW12 = [8, 8, 8, 8, 8, 8, 8, 8]
FLOW12 = [8, 8, 8, 8, 8, 8, 8, 8]
def flow(lines, beats):
    return [{"text": l, "beats": b} for l, b in zip(lines, beats)]

HOOK = [("Convenience store lights, the only sun tonight", 8), ("Come in from the cold, we're open all night", 8),
        ("Convenience store lights, the only sun tonight", 8), ("Hot or mild, hot or mild, we're open all night", 8)]
BRIDGE = ["The microwave says done", "like it's talking to me", "nobody else has all night", "I say thank you to a machine",
          "and the machine says done", "and the door says ding", "and the freezer holds the note", "and I hold mine"]

RAP_CAPTION = ("old school hip hop, male rapper, laid back conversational flow, clear words, on the beat, "
               "leaves space between lines, no singing, dry close mic")
CONCEPT = {
    "thesis": "새벽 3시, 밖은 다 꺼지고 편의점만 낮 — 야간 알바와 밤일 끝난 손님이 '맵게요 순하게요' 한 마디로 사람이 되는 곳",
    "arc": [{"section": "intro", "intent": "문 차임 두 번 → 필터 닫힌 펑크 레코드 → 5마디 드럼 → 9마디 랩", "energy": 0.35},
            {"section": "verse1", "intent": "알바의 1인칭 — 형광등·스티커·우산꽂이", "energy": 0.6},
            {"section": "hook1", "intent": "신스 브라스가 I7→IV 를 때리고 찹 + 챈트", "energy": 0.9},
            {"section": "verse2", "intent": "알바(A)와 손님(C)이 4마디씩 — 대화", "energy": 0.7},
            {"section": "bridge", "intent": "드럼 없음. 전자레인지 벨·찹 패드 위에서 C 가 말하듯", "energy": 0.3},
            {"section": "hook3", "intent": "C 더블 + 스트링, 가장 큼", "energy": 1.0},
            {"section": "outro", "intent": "문 차임 한 번, 필터 닫힘", "energy": 0.2}],
    "motif": {"melody": "E5:.5 C#5:.5", "why": "편의점 문 차임 — 딩동. 곡의 처음과 끝, 그리고 브리지"},
    "collision": ["시티팝 펑크 레코드(밝음·슬랩)", "Graduation 신스 스탭(차갑고 네온)", "효과음을 악기로 연주"],
    "irregular": [{"what": "I7 → IV", "why": "장조에 b7 한 음 — 교회 냄새 한 번(화성 연구 카드)"}, {"what": "2절은 두 사람 대화", "why": "손님·알바가 같은 교대"}],
    "constraints": ["96 BPM 바운스", "폭 -12~-15", "air -28~-32", "드럼 -4 · 랩 -6", "절/훅/브리지 3 dB"],
    "references": "knowledge/references/old-kanye-citypop.yaml — Touch the Sky(I7→IV·혼)·Flashing Lights / SPARKLE",
    "not": ["생성기 멜로디", "추상명사", "전 구간 같은 크기"],
}


def record():
    spec = cs.record_spec(f"{NAME}-record", SRC_BPM, "G major", "city-pop", "rhodes", seed=17,
                          vocal={"voice": "gen-singer-b", "lyrics": REC_LYR, "low": 60, "high": 74})
    for p in spec["parts"]:
        for k in ("chords", "bass"):
            if k in p:
                p[k]["progression"] = REC_PROG
        if "vocal" in p:
            p["vocal"]["melody"], p["vocal"]["lyrics"] = REC_MEL, REC_LYR
        if p["track"] == "Lead":
            p["melody"]["text"] = REC_MEL
    spec["tracks"]["Bass"] = {"preset": "bass/slap", "role": "bass"}
    spec["tracks"]["Keys"] = {"preset": "keys/dx_ep", "role": "keys", "pan": -0.15, "sends": {"0": -10}}
    spec["tracks"]["Brass"] = {"preset": "brass/section", "role": "brass", "pan": 0.25, "sends": {"0": -8}}
    spec["parts"] = [p for p in spec["parts"] if p["track"] not in ("Drums", "Bass")] + [
        {"track": "Drums", "in": ["A", "B"], "drums": {"pattern": {"kick": "x..x..x...x..x..", "snare": "....x.......x...", "hat": "xxxxxxxxxxxxxxxx"},
                                                       "swing": 0.5, "humanize_ms": 7, "humanize_vel": 12}},
        {"track": "Bass", "in": ["A", "B"], "bass": {"progression": REC_PROG, "beats_per_chord": 4, "pattern": [[0, .4, 0], [.75, .25, 12], [1, .4, 0], [1.75, .25, 7], [2, .4, 0], [2.5, .4, 12], [3, .4, 0], [3.5, .4, 10]], "velocity": 104}},
        {"track": "Brass", "in": ["B"], "chords": {"progression": REC_PROG, "beats_per_chord": 4, "voicing": "stab", "rhythm": [[0, .4, 1], [2.5, .4, .9], [3, .6, .85]], "velocity": 94}},
    ]
    spec["brief"] = "「Convenience Store Lights」 샘플용 레코드 — 시티팝 펑크(슬랩·DX EP·브라스), 직접 쓴 멜로디·가사, gen-singer-b"
    return spec


def sample(rec_spec, rec):
    sections, _ = arrange._sections(rec_spec)
    b = next(s for s in sections if s["name"] == "B")
    spb = 60 / SRC_BPM
    start, end = b["start_bar"] * 4 * spb, (b["start_bar"] + 4) * 4 * spb
    stems = rec["stems"]
    parts_ = [k for k in ("Keys", "Strings", "Brass", "Vox") if k in stems]
    accomp = crate.mix_files([stems[k] for k in parts_], Path(rec["mix"]).with_name(f"{NAME}_accomp.wav"), gains_db=[0, -2, -1, 2][:len(parts_)])
    aged = crate.age(accomp, "vinyl")
    loop = crate.loop_region(aged, start, end, 4, BPM, tag="sample_loop")
    vox_loop = crate.loop_region(stems["Vox"], start, end, 4, BPM, tag="vox_loop")
    chops = crate.chop(vox_loop["path"], mode="onsets", n=8, min_len=0.12, max_len=1.0)
    kit = crate.make_kit(chops, Path(chops[0]["path"]).parent / "chops.sfz")
    after = [theory.transpose_chord(c, ST) for c in theory.progression(REC_PROG, "G", "major")[:4]]
    return loop, kit, after


def beat(loop, kit, after):
    prog = " ".join(after)                                   # Bbmaj7 Bb7 Ebmaj7 Ebm7
    keys = sorted(kit["kit"].values())
    k = lambda i: keys[i % len(keys)]
    UP = [{"pitch": k(i), "start": s, "length": l, "velocity": v} for i, (s, l, v) in enumerate([(0, .4, 106), (.75, .4, 94), (1.5, .4, 108), (2, .4, 98), (3, .4, 104), (3.5, .4, 90), (4, .5, 108), (5.5, .4, 100), (6, .4, 104), (6.5, .4, 96), (7, .8, 108)])]
    STAC = [{"pitch": k(i % 4), "start": i * .5, "length": .22, "velocity": 100 if i % 2 == 0 else 86} for i in range(16)]
    PAD = [{"pitch": k(i), "start": i * 2, "length": 1.9, "velocity": 42} for i in range(4)]
    CHIME = "F5:.5 D5:1.5 r:2 | r:4 | F5:.5 D5:1.5 r:2 | r:4"     # B♭장조 안의 딩동(5도·3도) — v1 은 E–C# 로 불협(본인)
    sw = 0.54
    D = lambda pat, fill=None: {"pattern": pat, "swing": sw, "humanize_ms": 5, "humanize_vel": 8, **({"fill": fill} if fill else {})}
    BNC = {"kick": "x..x......x..x..", "snare": "....X..o....X...", "hat": "x-x-x-x-x-x-x-x-", "open_hat": "......x.........."[:16]}
    BNC2 = {"kick": "X..x..x...X..x..", "snare": "....X..o....X..o", "hat": "x-x-x-x-x-x-x-x-", "open_hat": "..............x."}
    HK = {"kick": "X..x..x...X.x.x.", "snare": "....X..o....X..o", "hat": "xxxxxxxxxxxxxxxx", "open_hat": "..........x....."}
    F1 = {"kick": "X.....x...X.....", "snare": "....X.......xoxo", "hat": "x.x.x.x.x.x....."}
    F2 = {"kick": "X.........X.....", "snare": "....X...XoXoXXXX", "hat": "x.x.x.x........."}
    vox_fx = [{"device": "eq", "params": {"Low-pass freq": 95, "Low-pass gain": -14, "Mid freq 1": 420, "Mid gain 1": -2, "Mid Q 1": 0.9, "Mid freq 2": 3200, "Mid gain 2": 3, "Mid Q 2": 0.7, "High-pass freq": 11000, "High-pass gain": 1}},
              {"device": "compressor", "params": {"threshold": -20, "ratio": 4, "attack": 8, "release": 90}}]
    bars, b = {}, 0
    for n, kk in FORM:
        bars[n] = b; b += kk
    total = b
    spec = {
        "name": NAME, "bpm": BPM, "key": "Bb major", "style": "chipmunk-soul", "feel": "laid_back", "intensity": 0.8,
        "brief": "NIGHT SHIFT 04 「Convenience Store Lights」 — 시티팝 펑크 레코드(+3) 위 Graduation 바운스·신스 브라스, 문 차임 전주",
        "sections": [{"name": n, "bars": kk} for n, kk in FORM],
        "tracks": {
            "Sample": {"role": "sample loop (varispeed +3, vinyl)", "fx": [
                {"device": "eq", "params": {"Low-pass freq": 110, "Low-pass gain": -14, "Mid freq 1": 350, "Mid gain 1": -3, "Mid Q 1": 0.9, "High-pass freq": 10500, "High-pass gain": -4}},
                {"device": "lowpass", "params": {"frequency": 20000}}]},
            "Drums": {"sound": "drums_acoustic_basic", "role": "bounce drums", "sends": {"0": -24}, "fx": [
                {"device": "eq", "params": {"Low-pass freq": 62, "Low-pass gain": 3.5, "Mid freq 1": 350, "Mid gain 1": -3, "Mid Q 1": 1.0, "Mid freq 2": 4500, "Mid gain 2": 3}},
                {"device": "compressor", "params": {"threshold": -19, "ratio": 4, "attack": 18, "release": 80, "output gain": 3}}]},
            "Bass": {"sound": "bass_sub", "role": "sub bass", "volume_db": -3, "fx": [{"device": "lowpass", "params": {"frequency": 700}}]},
            "SynthBrass": {"sound": "Brass/Synth Brass 2", "role": "synth brass stabs (Graduation)", "pan": 0.1, "sends": {"0": -9}},
            "DX": {"preset": "keys/dx_ep", "role": "dx electric piano", "pan": -0.2, "sends": {"0": -9}},
            "Chops": {"sound": kit["sfz"], "role": "chipmunk vocal chops", "pan": 0.1, "sends": {"0": -10}},
            "Bell": {"sound": "dexed:city_bell", "role": "door chime / microwave bell", "pan": 0.3, "sends": {"0": -3}},
            "Strings": {"preset": "strings/ensemble", "role": "strings", "pan": -0.25, "sends": {"0": -8}},
            "Rap": {"role": "lead rap vocal", "sends": {"0": -17}, "fx": vox_fx},
            "RapC": {"role": "rap vocal C", "pan": 0.05, "sends": {"0": -17}, "fx": vox_fx},
            "Chant": {"role": "hook chant", "pan": -0.08, "sends": {"0": -15}, "fx": vox_fx},
            "Chant2": {"role": "hook chant double (C)", "pan": 0.12, "sends": {"0": -15}, "fx": vox_fx},
            "Adlib": {"role": "ad-libs", "pan": 0.25, "sends": {"0": -10}, "fx": vox_fx},
        },
        "buses": [{"name": "Verb", "bus": 0, "device": "Dragonfly Plate Reverb", "volume_db": -5}],
        "parts": [
            {"track": "Sample", "in": ["intro"], "audio": {"path": loop["path"], "every": 16, "gain_db": -3}},
            {"track": "Sample", "in": ["verse1", "verse2"], "audio": {"path": loop["path"], "every": 16, "gain_db": -3.5}},
            {"track": "Sample", "in": ["hook1", "hook2", "hook3"], "audio": {"path": loop["path"], "every": 16}},
            {"track": "Sample", "in": ["bridge"], "audio": {"path": loop["path"], "every": 16, "gain_db": -9}},
            {"track": "Sample", "in": ["outro"], "audio": {"path": loop["path"], "every": 16, "gain_db": -4}},
            {"track": "Bell", "in": ["intro"], "melody": {"text": CHIME, "velocity": 96, "repeat": False}},
            {"track": "Bell", "in": ["bridge"], "melody": {"text": "r:3 F5:.25 r:.25 F5:.25 r:.25 | r:4 | r:3 F5:.25 r:.25 F5:.25 r:.25 | r:4", "velocity": 80, "repeat": True}},
            {"track": "Bell", "in": ["outro"], "melody": {"text": "r:8 | F5:.5 D5:1.5 r:2 | r:4", "velocity": 90, "repeat": False}},
            {"track": "Drums", "in": ["intro"], "offset": 16, "drums": D({"kick": "x.........x.....", "snare": "....x.......x...", "hat": "x.x.x.x.x.x.x.x."})},
            {"track": "Drums", "in": ["verse1"], "drums": D(BNC, F1)},
            {"track": "Drums", "in": ["verse2"], "drums": D(BNC2, F1)},
            {"track": "Drums", "in": ["hook1", "hook2", "hook3"], "drums": D(HK, F2)},
            {"track": "Drums", "in": ["outro"], "drums": D({"kick": "X.........x.....", "snare": "................", "hat": "................"})},
            {"track": "Bass", "in": ["verse1", "verse2"], "bass": {"progression": prog, "beats_per_chord": 4, "pattern": [[0, .9, 0], [1.5, .5, 0], [2.5, .45, 0], [3.25, .5, 7]], "velocity": 98, "low": 28, "high": 43}},
            {"track": "Bass", "in": ["hook1", "hook2", "hook3"], "bass": {"progression": prog, "beats_per_chord": 4, "pattern": [[0, .9, 0], [.75, .3, 0], [1.75, .5, 0], [2.5, .4, 12], [3.5, .4, 7]], "velocity": 108, "low": 28, "high": 43}},
            # 신스 브라스 — 훅에서 I7→IV 스탭, 2절 뒤 절반에 살짝
            {"track": "SynthBrass", "in": ["hook1", "hook2", "hook3"], "chords": {"progression": prog, "beats_per_chord": 4, "voicing": "stab", "rhythm": [[0, .5, 1], [1.5, .4, .8], [2.5, .75, .95]], "velocity": 96, "low": 55, "high": 76}},
            {"track": "SynthBrass", "in": ["verse2"], "offset": 32, "chords": {"progression": prog, "beats_per_chord": 4, "voicing": "stab", "rhythm": [[2.5, .5, .8]], "velocity": 70, "low": 55, "high": 76}},
            {"track": "DX", "in": ["verse1", "verse2"], "chords": {"progression": prog, "beats_per_chord": 4, "voicing": "rhodes", "rhythm": [[1, .5, .9], [3, .5, .8]], "velocity": 60}},
            {"track": "DX", "in": ["bridge"], "chords": {"progression": prog, "beats_per_chord": 4, "voicing": "pad", "velocity": 48, "legato": 1.0}},
            {"track": "Chops", "in": ["hook1", "hook2"], "notes": UP, "cycle_beats": 8},
            {"track": "Chops", "in": ["hook3"], "notes": STAC, "cycle_beats": 8},
            {"track": "Chops", "in": ["bridge"], "notes": PAD, "cycle_beats": 8},
            {"track": "Strings", "in": ["hook3"], "chords": {"progression": prog, "beats_per_chord": 4, "voicing": "pad", "velocity": 62}},
            {"track": "Rap", "in": ["verse1"], "rap": {"voice": "bomf-rapper", "lines": flow(VERSE1, FLOW12), "style": "dry, deadpan, a little amused, close to the mic", "lock": 0.75, "seed": 5}},
            {"track": "Chant", "in": ["hook1", "hook2", "hook3"], "rap": {"voice": "bomf-rapper", "lines": [{"text": l, "beats": b_} for l, b_ in HOOK], "style": "chanting a hook, bright, bouncing", "lock": 0.9, "seed": 21}},
            {"track": "RapC", "in": ["bridge"], "rap": {"voice": "gen-rapper-c", "lines": BRIDGE, "beats_per_line": 4, "style": "spoken, quiet, half-smiling, long pauses", "lock": 0.5, "seed": 19, "gain_db": -2}},
        ],
        "events": [{"section": "verse1", "at": 62, "length": 2, "type": "stop", "why": "훅 앞 두 박 정적"}, {"section": "verse2", "at": 62, "length": 2, "type": "stop", "why": "같은 자리"}],
        "automation": [{"track": "Sample", "device": 1, "param": "frequency", "points": [
            {"bar": 0, "value": 700}, {"bar": 4, "value": 1000}, {"bar": 7.9, "value": 1500}, {"bar": 8, "value": 20000},
            {"bar": bars["outro"], "value": 20000}, {"bar": total, "value": 400}]}],
        "mix": {"balance": True, "target_lufs": -11,
                "balance_lu": {"drums": 0, "rap": 1.5, "rapc": 1.5, "chant": 0.5, "adlib": -6, "chant2": -3, "sample": -2.5, "chops": -3.5, "bass": -5, "synthbrass": -6, "dx": -8, "bell": -6, "strings": -8}},
    }
    spec["parts"].append({"track": "Rap", "in": ["verse2"], "rap": {"voice": "bomf-rapper", "lines": flow(VERSE2, FLOW12), "seed": 31, "style": "dry", "lock": 0.75}})
    return spec


if __name__ == "__main__":
    label = sys.argv[1] if len(sys.argv) > 1 else "v1"
    concept_mod.save(NAME, CONCEPT)
    rspec = record()
    print("[1] 레코드 녹음", SRC_BPM, "BPM G major", flush=True)
    rec = arrange.bounce(rspec, stems=True, label="record")
    loop, kit, after = sample(rspec, rec)
    print("[2-3] 샘플", loop["path"], "코드(+3)", after, "찹", len(kit["kit"]), flush=True)
    spec = beat(loop, kit, after)
    from musicoma import album
    s, rep = album.rap_with_lego(spec, label, RAP_CAPTION, log=lambda m: print("[4]", m, flush=True))
    print(json.dumps({k: rep.get(k) for k in ("file", "loudness", "bands_db", "issues")}, ensure_ascii=False, default=str), flush=True)
