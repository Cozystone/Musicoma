"""NIGHT SHIFT · 07 「Vending Machine Heart」 — 시티팝 신스팝 레코드(+4) 위 808s & Heartbreak: 808 베이스가 제일 앞, 드럼 최소, 노래는 기계 튜닝(1.0).
화성 장치: i ↔ bIImaj7 왕복(Flashing Lights). 전주 12마디. 랩 없음 — 래퍼 A 가 '노래'하고 polish.tune 1.0 으로 기계처럼.

    python works/musicoma_016_vending_machine_heart.py v1
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from musicoma import arrange, concept as concept_mod, crate, polish, theory, voice_design as vd
from musicoma.recipes import chipmunk_soul as cs

NAME = "ns-07-vending-machine-heart"
BPM, ST = 100, 4
SRC_BPM = round(BPM / 2 ** (ST / 12), 3)            # 79.4
KEY_AFTER = "E minor"
FORM = [("intro", 12), ("verse1", 16), ("hook1", 8), ("verse2", 16), ("hook2", 8), ("bridge", 8), ("hook3", 8), ("outro", 4)]

REC_PROG = "i7 bIImaj7 i7 bIImaj7 i7 bIImaj7 iv7 V7"               # C minor: Cm7 Dbmaj7 … Fm7 G7
REC_MEL = ("r:1 G4:1 Eb4:1 C4:1 | Db4:2 F4:1 Ab4:1 | r:1 G4:1 Eb4:1 C4:1 | Db4:3 r:1 | "
           "r:1 G4:1 Eb4:1 C4:1 | Db4:2 F4:1 Ab4:1 | r:1 Ab4:1 G4:1 F4:1 | G4:3 r:1")
REC_LYR = "coin goes in no- thing out coin goes in out coin goes in no- thing out lights are on on"   # 20 토큰 = 20 음표

VERSE1 = [                                          # 8줄 = 16마디(줄마다 8박, 말은 3박쯤·나머지는 비움) — 10-18 본인 "가사 또 너무 많다"
    "Two a.m., the gate is down", "The machine's still lit",
    "Coin in, the can gets stuck", "I hit it, it keeps my coin",
    "Your name's at the top of the phone", "I press coin return instead",
    "Out of order, in handwriting", "Most honest sign in the city",
]
VERSE2 = [
    "Three a.m., me and the moths", "You called back once in June",
    "I let it ring, called it strong", "The light goes off, then on",
    "I know that flicker", "I do it when your name comes up",
    "Coin in, nothing out", "That's the whole year",
]
BRIDGE = ["The light goes off", "then on", "like it's deciding", "whether to stay"]
HOOK = [("Vending machine heart, coin in, nothing out", 8), ("Keep the light on, keep the light on, I'm not going home", 8),
        ("Vending machine heart, out of order, still lit", 8), ("Keep the light on, keep the light on, till the first train", 8)]
BRIDGE = ["The light goes off", "then on", "then off", "like it's deciding", "I know that flicker", "I do that flicker", "every time", "your name comes up"]

CONCEPT = {
    "thesis": "셔터 내린 역 앞 자판기 — 동전은 들어가고 아무것도 안 나오지만 불은 켜져 있다. 그 불빛에 등을 기대는 사람. 목소리는 기계처럼 튜닝된다(808s)",
    "arc": [{"section": "intro", "intent": "12마디: 808 한 음 → 레코드 필터 → 9마디째 하이햇·클랩. 보컬 없음", "energy": 0.3},
            {"section": "verse1", "intent": "낮게, 기계 튜닝으로 노래하듯 — 동전·캔·스티커", "energy": 0.5},
            {"section": "hook1", "intent": "찹 'coin goes in' + 튜닝된 훅, 808 글라이드", "energy": 0.8},
            {"section": "bridge", "intent": "808 과 목소리만. 깜빡임을 말한다", "energy": 0.3},
            {"section": "hook3", "intent": "패드·스트링 들어오고 찹 둘 겹침", "energy": 0.95},
            {"section": "outro", "intent": "4마디, 808 한 음이 사라진다", "energy": 0.15}],
    "motif": {"melody": "G4:1 Eb4:1 C4:1 Db4:2", "why": "내려가다 반음 위로 — 꺼졌다 켜지는 불빛"},
    "collision": ["시티팝 신스팝 레코드(DX·게이트 리버브)", "808s & Heartbreak(808·오토튠·빈 공간)", "사람 목소리를 일부러 기계로"],
    "irregular": [{"what": "i ↔ bIImaj7 만으로 거의 전곡", "why": "두 코드 사이에서 깜빡임"}, {"what": "랩이 아니라 튜닝된 노래", "why": "앨범에서 유일하게 차가운 곡"}],
    "constraints": ["100 BPM", "808 베이스가 제일 앞(-2)", "드럼 -8(작게)", "폭 -14", "air -30", "보컬 tune 1.0"],
    "references": "knowledge/references/old-kanye-citypop.yaml — Heartless·Flashing Lights·Street Lights / 真夜中のドア(bII)",
    "not": ["붐뱁 드럼", "따뜻한 로즈", "자연스러운 보컬"],
}


def record():
    spec = cs.record_spec(f"{NAME}-record", SRC_BPM, "C minor", "minor-soul", "rhodes", seed=29,
                          vocal={"voice": "gen-singer-b", "lyrics": REC_LYR, "low": 58, "high": 72})
    for p in spec["parts"]:
        for k in ("chords", "bass"):
            if k in p:
                p[k]["progression"] = REC_PROG
        if "vocal" in p:
            p["vocal"]["melody"], p["vocal"]["lyrics"] = REC_MEL, REC_LYR
        if p["track"] == "Lead":
            p["melody"]["text"] = REC_MEL
    spec["tracks"]["Keys"] = {"preset": "keys/dx_ep", "role": "keys", "pan": -0.15, "sends": {"0": -6}}
    spec["tracks"]["Pad"] = {"preset": "pad/warm", "role": "pad", "sends": {"0": -4}}
    spec["tracks"]["Bass"] = {"preset": "bass/synth_rubber", "role": "bass"}
    spec["parts"] = [p for p in spec["parts"] if p["track"] != "Drums"] + [
        {"track": "Drums", "in": ["A", "B"], "drums": {"pattern": {"kick": "x.......x.......", "snare": "....x.......x...", "hat": "x.x.x.x.x.x.x.x."}, "swing": 0.5, "humanize_ms": 4, "humanize_vel": 6}},
        {"track": "Pad", "in": ["A", "B"], "chords": {"progression": REC_PROG, "beats_per_chord": 4, "voicing": "pad", "velocity": 62, "legato": 1.0}},
    ]
    spec["brief"] = "「Vending Machine Heart」 샘플용 레코드 — 시티팝 신스팝(DX·패드·러버 베이스), i↔bII, gen-singer-b"
    return spec


def sample(rec_spec, rec):
    sections, _ = arrange._sections(rec_spec)
    b = next(s for s in sections if s["name"] == "B")
    spb = 60 / SRC_BPM
    start, end = b["start_bar"] * 4 * spb, (b["start_bar"] + 4) * 4 * spb
    stems = rec["stems"]
    parts_ = [k for k in ("Keys", "Pad", "Strings", "Vox") if k in stems]
    accomp = crate.mix_files([stems[k] for k in parts_], Path(rec["mix"]).with_name(f"{NAME}_accomp.wav"), gains_db=[0, -2, -3, 2][:len(parts_)])
    aged = crate.age(accomp, "vinyl")
    loop = crate.loop_region(aged, start, end, 4, BPM, tag="sample_loop")
    vox_loop = crate.loop_region(stems["Vox"], start, end, 4, BPM, tag="vox_loop")
    chops = crate.chop(vox_loop["path"], mode="onsets", n=8, min_len=0.12, max_len=1.0)
    kit = crate.make_kit(chops, Path(chops[0]["path"]).parent / "chops.sfz")
    after = [theory.transpose_chord(c, ST) for c in theory.progression(REC_PROG, "C", "minor")[:4]]
    return loop, kit, after


def tuned_vocals():
    """래퍼 A 가 낮게 노래하듯 부른 것을 polish.tune 1.0 으로 기계 튜닝 — 808s 의 오토튠."""
    out = Path(arrange.ROOT) / "projects" / NAME / "vocals"
    out.mkdir(parents=True, exist_ok=True)
    files = {}
    FLOW = [8, 8, 8, 8, 8, 8, 8, 8]                                   # 2마디에 한 줄 — 말은 짧게, 뒤는 808 과 레코드만
    VERSE1_F = [{"text": l, "beats": b} for l, b in zip(VERSE1, FLOW)]
    VERSE2_F = [{"text": l, "beats": b} for l, b in zip(VERSE2, FLOW)]
    jobs = {"verse1": (VERSE1_F, 4, "singing softly in a low voice, melodic, sad, steady rhythm, close to the mic", 0.8, 5),
            "verse2": (VERSE2_F, 4, "singing softly in a low voice, melodic, a little more awake, close to the mic", 0.8, 12),
            "hook": ([{"text": l, "beats": b_} for l, b_ in HOOK], 4, "singing a hook, melodic, held notes, sad and warm", 0.9, 21),
            "bridge": (BRIDGE, 8, "spoken-sung, quiet, long pauses, flat", 0.5, 19)}
    for tag, (lines, bpl, style, lock, seed) in jobs.items():
        raw, _ = vd.rap("bomf-rapper", lines, BPM, out / f"{tag}_raw.wav", beats_per_line=bpl, style=style, lock=lock, seed=seed)
        r = polish.tune(raw, KEY_AFTER, out=out / f"{tag}_tuned.wav", strength=1.0, max_semitones=3.0, log=lambda m: None)
        files[tag] = r["out"]
    return files


def beat(loop, kit, after, vox):
    prog = " ".join(after)                                   # Em7 Fmaj7 Em7 Fmaj7
    keys = sorted(kit["kit"].values())
    k = lambda i: keys[i % len(keys)]
    HK_CH = [{"pitch": k(i), "start": s, "length": l, "velocity": v} for i, (s, l, v) in enumerate([(0, .6, 104), (1, .6, 92), (2, .9, 106), (4, .6, 100), (5, .6, 90), (6, 1.4, 108)])]
    HK_CH2 = [{"pitch": k(len(keys) - 1 - i), "start": s + .5, "length": l, "velocity": v - 10} for i, (s, l, v) in enumerate([(0, .6, 104), (1, .6, 92), (2, .9, 106), (4, .6, 100), (5, .6, 90), (6, 1.4, 108)])]
    PAD = [{"pitch": k(i), "start": i * 2, "length": 1.9, "velocity": 36} for i in range(4)]
    D = lambda pat: {"pattern": pat, "swing": 0.5, "humanize_ms": 3, "humanize_vel": 5}
    MIN = {"kick": "x.......x.......", "snare": "....x.......x...", "hat": "..x...x...x...x."}
    MIN2 = {"kick": "x.......x..x....", "snare": "....x.......x...", "hat": "x.x.x.x.x.x.x.x."}
    vox_fx = [{"device": "eq", "params": {"Low-pass freq": 120, "Low-pass gain": -12, "Mid freq 2": 2800, "Mid gain 2": 2.5, "Mid Q 2": 0.8, "High-pass freq": 9000, "High-pass gain": 2}},
              {"device": "compressor", "params": {"threshold": -22, "ratio": 5, "attack": 5, "release": 80}}]
    bars, b = {}, 0
    for n, kk in FORM:
        bars[n] = b; b += kk
    total = b
    spec = {
        "name": NAME, "bpm": BPM, "key": KEY_AFTER, "style": "chipmunk-soul", "feel": "straight", "intensity": 0.5,
        "brief": "NIGHT SHIFT 07 「Vending Machine Heart」 — 시티팝 신스팝 레코드(+4) 위 808s & Heartbreak: 808 앞, 기계 튜닝 노래, i↔bII",
        "sections": [{"name": n, "bars": kk} for n, kk in FORM],
        "tracks": {
            "Sample": {"role": "sample loop (varispeed +4, vinyl)", "fx": [
                {"device": "eq", "params": {"Low-pass freq": 120, "Low-pass gain": -16, "Mid freq 1": 350, "Mid gain 1": -2, "Mid Q 1": 0.9, "High-pass freq": 9500, "High-pass gain": -5}},
                {"device": "lowpass", "params": {"frequency": 20000}}]},
            "Drums": {"preset": "drums/phonk", "role": "808 drums (minimal)", "sends": {"0": -30}},
            "Bass": {"sound": "bass_sub", "role": "808 bass (front)", "volume_db": -6, "fx": [{"device": "lowpass", "params": {"frequency": 900}}]},
            "Pad": {"preset": "pad/airy", "role": "pad", "pan": 0.1, "sends": {"0": -6}},
            "Strings": {"preset": "strings/ensemble", "role": "strings", "pan": -0.25, "sends": {"0": -8}},
            "Chops": {"sound": kit["sfz"], "role": "chipmunk vocal chops", "pan": 0.1, "sends": {"0": -10}},
            "Vox": {"role": "tuned vocal (bomf-rapper, tune 1.0)", "sends": {"0": -12}, "fx": vox_fx},
            "Vox2": {"role": "tuned vocal double", "pan": 0.18, "sends": {"0": -12}, "fx": vox_fx},
        },
        "buses": [{"name": "Verb", "bus": 0, "device": "Dragonfly Plate Reverb", "volume_db": -4}],
        "parts": [
            {"track": "Sample", "in": ["intro"], "offset": 16, "audio": {"path": loop["path"], "every": 16, "gain_db": -8}},
            {"track": "Sample", "in": ["verse1", "verse2"], "audio": {"path": loop["path"], "every": 16, "gain_db": -4}},
            {"track": "Sample", "in": ["hook1", "hook2", "hook3"], "audio": {"path": loop["path"], "every": 16, "gain_db": -1}},
            {"track": "Sample", "in": ["bridge"], "audio": {"path": loop["path"], "every": 16, "gain_db": -12}},
            {"track": "Sample", "in": ["outro"], "audio": {"path": loop["path"], "every": 16, "gain_db": -6}},
            {"track": "Bass", "in": ["intro"], "offset": 16, "bass": {"progression": prog, "beats_per_chord": 4, "pattern": [[0, 1.8, 0]], "velocity": 72, "low": 28, "high": 40}},
            {"track": "Bass", "in": ["verse1", "verse2"], "bass": {"progression": prog, "beats_per_chord": 4, "pattern": [[0, 2.8, 0], [3, .9, 0]], "velocity": 96, "low": 28, "high": 40}},
            {"track": "Bass", "in": ["bridge", "outro"], "bass": {"progression": prog, "beats_per_chord": 4, "pattern": [[0, 1.5, 0]], "velocity": 62, "low": 28, "high": 40}},
            {"track": "Bass", "in": ["hook1", "hook2", "hook3"], "bass": {"progression": prog, "beats_per_chord": 4, "pattern": [[0, 1.4, 0], [1.5, .4, 12], [2, 1.9, 0]], "velocity": 110, "low": 28, "high": 40}},
            {"track": "Drums", "in": ["intro"], "offset": 32, "drums": D({"kick": "................", "snare": "....x.......x...", "hat": "..x...x...x...x."})},
            {"track": "Drums", "in": ["verse1"], "drums": D(MIN)},
            {"track": "Drums", "in": ["verse2", "hook1", "hook2", "hook3"], "drums": D(MIN2)},
            {"track": "Pad", "in": ["intro", "hook1", "hook2", "hook3", "outro"], "chords": {"progression": prog, "beats_per_chord": 4, "voicing": "pad", "velocity": 50, "legato": 1.0}},
            {"track": "Strings", "in": ["hook3"], "chords": {"progression": prog, "beats_per_chord": 4, "voicing": "pad", "velocity": 58, "legato": 1.0}},
            {"track": "Chops", "in": ["hook1", "hook2"], "notes": HK_CH, "cycle_beats": 8},
            {"track": "Chops", "in": ["hook3"], "notes": HK_CH, "cycle_beats": 8},
            {"track": "Chops", "in": ["hook3"], "notes": HK_CH2, "cycle_beats": 8},
            {"track": "Chops", "in": ["bridge"], "notes": PAD, "cycle_beats": 8},
            {"track": "Vox", "in": ["verse1"], "audio": {"path": vox["verse1"]}},
            {"track": "Vox", "in": ["verse2"], "audio": {"path": vox["verse2"]}},
            {"track": "Vox", "in": ["hook1", "hook2", "hook3"], "audio": {"path": vox["hook"]}},
            {"track": "Vox2", "in": ["hook3"], "audio": {"path": vox["hook"], "gain_db": -5}},
            {"track": "Vox", "in": ["bridge"], "audio": {"path": vox["bridge"], "gain_db": -2}},
        ],
        "automation": [{"track": "Sample", "device": 1, "param": "frequency", "points": [
            {"bar": 4, "value": 500}, {"bar": 8, "value": 900}, {"bar": 11.9, "value": 1400}, {"bar": 12, "value": 20000},
            {"bar": bars["outro"], "value": 20000}, {"bar": total, "value": 350}]}],
        "mix": {"balance": True, "target_lufs": -11,
                "balance_lu": {"vox": 0, "bass": -3, "vox2": -5, "drums": -5, "sample": -4, "chops": -5, "pad": -10, "strings": -10}},
    }
    return spec


if __name__ == "__main__":
    label = sys.argv[1] if len(sys.argv) > 1 else "v1"
    concept_mod.save(NAME, CONCEPT)
    rspec = record()
    print("[1] 레코드 녹음", SRC_BPM, "BPM C minor", flush=True)
    rec = arrange.bounce(rspec, stems=True, label="record")
    loop, kit, after = sample(rspec, rec)
    print("[2-3] 샘플", loop["path"], "코드(+4)", after, "찹", len(kit["kit"]), flush=True)
    vox = tuned_vocals()
    print("[3b] 튜닝 보컬", list(vox.values()), flush=True)
    spec = beat(loop, kit, after, vox)
    s, rep = arrange.build(spec, label=label, log=lambda m: print("[4]", m, flush=True) if "balance" in m else None)
    print(json.dumps({k: rep.get(k) for k in ("file", "loudness", "bands_db", "issues")}, ensure_ascii=False, default=str), flush=True)
