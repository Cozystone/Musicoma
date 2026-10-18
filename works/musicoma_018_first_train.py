"""NIGHT SHIFT · 09 「First Train」 — 앨범 닫는 곡. 보사·시티팝 레코드(+2, 나일론 기타·로즈) 위 브러시 드럼(거의 없음), 남성 소울 가수 리드 + 여성 화음.
화성 장치: ii7–V7sus4–Imaj7 정통 시티팝, 마지막만 IV 로 끝내 '안 끝난' 느낌(Street Lights). 전주 16마디. 랩은 2절 뒤 8마디뿐.

    python works/musicoma_018_first_train.py v1
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from musicoma import arrange, concept as concept_mod, crate, theory
from musicoma.recipes import chipmunk_soul as cs

NAME = "ns-09-first-train"
BPM, ST = 78, 2
SRC_BPM = round(BPM / 2 ** (ST / 12), 3)            # 69.5
FORM = [("intro", 16), ("verse1", 16), ("hook1", 8), ("verse2", 16), ("rap", 8), ("hook2", 8), ("bridge", 8), ("hook3", 8), ("outro", 8)]

REC_PROG = "ii7 V7sus4 Imaj7 vi7 ii7 V7sus4 Imaj7 IVmaj7"           # C: Dm7 G7sus4 Cmaj7 Am7 | … IVmaj7 로 끝
REC_MEL = ("r:1 E4:1 G4:1 A4:1 | G4:2 E4:1 D4:1 | r:1 C4:1 E4:1 G4:1 | E4:3 r:1 | "
           "r:1 E4:1 G4:1 A4:1 | G4:2 E4:1 D4:1 | r:1 A4:1 G4:1 E4:1 | F4:3 r:1")
REC_LYR = "first train first train take the night a- way now first train first train car- ry me on home now"   # 20 토큰 = 20 음표

# 노래 가사(가수가 부름 — 한 토큰 = 한 음표). 절 16마디 = 4줄 × 4마디
V1_MEL = ("r:2 E4:.5 E4:.5 G4:1 | A4:1.5 G4:.5 E4:2 | r:2 D4:.5 E4:.5 G4:1 | E4:3 r:1 | "
          "r:2 E4:.5 E4:.5 G4:1 | A4:1.5 G4:.5 B4:2 | r:1 A4:.5 G4:.5 E4:1 D4:1 | C4:3 r:1 | "
          "r:2 C4:.5 D4:.5 E4:1 | G4:1.5 E4:.5 D4:2 | r:2 D4:.5 E4:.5 G4:1 | A4:3 r:1 | "
          "r:2 A4:.5 G4:.5 E4:1 | G4:1.5 E4:.5 D4:2 | r:1 E4:.5 D4:.5 C4:1 D4:1 | C4:3 r:1")
V1_LYR = ("the sky goes grey be- hind the yard it's warm "
          "clean- er nods and I nod back the car is mine "
          "win- dow is a win- dow now I see out "
          "badge is in my po- cket and my hands are mine")                       # 42 토큰(10·11·10·11)
V2_LYR = ("the girl from last night she rides this one too "
          "she sleeps on the glass I don't look that's the rule "
          "the kit- chen lights come on a hun- dred suns "
          "some- one left a light on and I know which one")                      # 42 토큰
HOOK_MEL = "r:1 G4:1 A4:1 C5:1 | B4:2 A4:1 G4:1 | r:1 E4:1 G4:1 A4:1 | G4:3 r:1 | r:1 G4:1 A4:1 C5:1 | B4:2 A4:1 G4:1 | r:1 A4:1 G4:1 E4:1 | F4:3 r:1"
HOOK_LYR = "first train first train take the night a- way now first train first train car- ry me on home now"   # 20 토큰
HOOK_HARM = "r:1 E4:1 F4:1 A4:1 | G4:2 F4:1 E4:1 | r:1 C4:1 E4:1 F4:1 | E4:3 r:1 | r:1 E4:1 F4:1 A4:1 | G4:2 F4:1 E4:1 | r:1 F4:1 E4:1 C4:1 | D4:3 r:1"
BRIDGE_MEL = "r:2 C4:1 D4:1 | E4:2 D4:2 | r:2 E4:1 G4:1 | A4:4 | r:2 A4:1 G4:1 | E4:2 D4:2 | r:1 C4:1 D4:1 E4:1 | E4:4"
BRIDGE_LYR = "one of us is go- ing home and this time it's me go- ing home"   # 15 토큰 = 15 음표
RAP8 = ["Night shift's over, the badge is warm, the bag's got nothing in it",             # 래퍼 A, 8마디 — 앨범 전체를 묶는 한 번
        "Passed the pay phone, passed the store, passed the gate with the machine",
        "Last train took somebody home, first train's taking me",
        "Same car, same door, the window's a window again",
        "Kitchen light's still on, she left it, that's the whole album",
        "Mama on the night shift, me on the morning, one of us is going home",
        "I'm not gonna say it's fine, it's just light, light is enough",
        "First train, first train, carry me, carry me home"]

RAP_CAPTION = ("old school hip hop, male rapper, laid back conversational flow, clear words, on the beat, "
               "leaves space between lines, no singing, dry close mic")
CONCEPT = {
    "thesis": "첫차 — 밤이 끝난다. 창은 다시 창이 되고, 부엌 불 하나가 켜져 있다. 앨범의 모든 사물(배지·봉지·공중전화·자판기·셔터)이 창밖으로 지나간다",
    "arc": [{"section": "intro", "intent": "16마디: 나일론 기타 레코드 혼자(필터) → 9마디 브러시 → 13마디 로즈. 보컬 없음", "energy": 0.25},
            {"section": "verse1", "intent": "남성 가수가 낮게, 거의 말하듯", "energy": 0.45},
            {"section": "hook1", "intent": "'first train' — 가수 + 여성 화음 3도 아래", "energy": 0.7},
            {"section": "rap", "intent": "래퍼 A 8마디 — 앨범의 사물을 전부 한 번씩", "energy": 0.6},
            {"section": "bridge", "intent": "드럼 없이 '이번엔 나다'", "energy": 0.4},
            {"section": "hook3", "intent": "다 들어오고 스트링", "energy": 0.85},
            {"section": "outro", "intent": "8마디, IV 에서 멈춤 — 끝나지 않은 채 아침", "energy": 0.3}],
    "motif": {"melody": "G4:1 A4:1 C5:1 B4:2", "why": "Last Train 모티프(올라갔다 한 음 내려옴)를 한 번 더 — 이번엔 내려온 자리가 집"},
    "collision": ["보사·시티팝(부드러움)", "붐뱁은 브러시로만(거의 없음)", "노래가 랩보다 많은 유일한 곡"],
    "irregular": [{"what": "마지막 코드 IV", "why": "안 끝난 느낌 — 아침은 끝이 아니라 다음 교대"}, {"what": "랩 8마디뿐", "why": "닫는 곡은 노래가"}],
    "constraints": ["78 BPM", "폭 -10~-13(앨범에서 가장 넓게)", "air -26~-30", "드럼 -8", "보컬 -4"],
    "references": "knowledge/references/old-kanye-citypop.yaml — Street Lights·Heard 'Em Say / Remember Summer Days",
    "not": ["큰 드럼", "찹 난무", "완전종지"],
}


def record():
    spec = cs.record_spec(f"{NAME}-record", SRC_BPM, "C major", "city-pop", "flute", seed=37,
                          vocal={"voice": "gen-singer-b", "lyrics": REC_LYR, "low": 60, "high": 72})
    for p in spec["parts"]:
        for k in ("chords", "bass"):
            if k in p:
                p[k]["progression"] = REC_PROG
        if "vocal" in p:
            p["vocal"]["melody"], p["vocal"]["lyrics"] = REC_MEL, REC_LYR
        if p["track"] == "Lead":
            p["melody"]["text"] = REC_MEL
    spec["tracks"]["Guitar"] = {"preset": "guitar/archtop", "role": "nylon-ish guitar", "pan": 0.25, "sends": {"0": -8}}
    spec["parts"] = [p for p in spec["parts"] if p["track"] != "Drums"] + [
        {"track": "Drums", "in": ["A", "B"], "drums": {"pattern": {"kick": "x.......x.......", "snare": "....x.......x...", "hat": "x.x.x.x.x.x.x.x."}, "swing": 0.5, "humanize_ms": 10, "humanize_vel": 12}},
        {"track": "Guitar", "in": ["A", "B"], "chords": {"progression": REC_PROG, "beats_per_chord": 4, "voicing": "guitar", "rhythm": [[0, .5, .8], [1, .5, .6], [1.5, .5, .7], [2.5, .5, .75], [3, .5, .6], [3.5, .5, .7]], "velocity": 68}},
    ]
    spec["brief"] = "「First Train」 샘플용 레코드 — 보사·시티팝(아치톱·로즈·플루트·스트링), ii–V–I, gen-singer-b"
    return spec


def sample(rec_spec, rec):
    sections, _ = arrange._sections(rec_spec)
    b = next(s for s in sections if s["name"] == "B")
    spb = 60 / SRC_BPM
    start, end = b["start_bar"] * 4 * spb, (b["start_bar"] + 4) * 4 * spb
    stems = rec["stems"]
    parts_ = [k for k in ("Keys", "Strings", "Guitar", "Vox") if k in stems]
    accomp = crate.mix_files([stems[k] for k in parts_], Path(rec["mix"]).with_name(f"{NAME}_accomp.wav"), gains_db=[0, -2, 0, 1][:len(parts_)])
    aged = crate.age(accomp, "vinyl")
    loop = crate.loop_region(aged, start, end, 4, BPM, tag="sample_loop")
    vox_loop = crate.loop_region(stems["Vox"], start, end, 4, BPM, tag="vox_loop")
    chops = crate.chop(vox_loop["path"], mode="onsets", n=8, min_len=0.15, max_len=1.4)
    kit = crate.make_kit(chops, Path(chops[0]["path"]).parent / "chops.sfz")
    after = [theory.transpose_chord(c, ST) for c in theory.progression(REC_PROG, "C", "major")[:4]]
    return loop, kit, after


def beat(loop, kit, after):
    prog = " ".join(after)                                   # Em7 A7sus4 Dmaj7 Bm7 (D major)
    keys = sorted(kit["kit"].values())
    k = lambda i: keys[i % len(keys)]
    PAD = [{"pitch": k(i), "start": i * 2, "length": 1.9, "velocity": 40} for i in range(4)]
    SOFT = [{"pitch": k(i), "start": s, "length": l, "velocity": v} for i, (s, l, v) in enumerate([(0, 1.2, 84), (2, 1.2, 76), (4, 1.2, 84), (6, 1.8, 80)])]
    D = lambda pat: {"pattern": pat, "swing": 0.52, "humanize_ms": 9, "humanize_vel": 12}
    BRUSH = {"kick": "x.......x.......", "snare": "....x.......x...", "hat": "x.x.x.x.x.x.x.x."}
    BRUSH2 = {"kick": "x.....x.x.......", "snare": "....x..o....x...", "hat": "x.x.x.x.x.x.x.x."}
    vox_fx = [{"device": "eq", "params": {"Low-pass freq": 100, "Low-pass gain": -10, "Mid freq 2": 3000, "Mid gain 2": 2, "High-pass freq": 10000, "High-pass gain": 1.5}},
              {"device": "compressor", "params": {"threshold": -18, "ratio": 3, "attack": 10, "release": 120}}]
    bars, b = {}, 0
    for n, kk in FORM:
        bars[n] = b; b += kk
    total = b
    spec = {
        "name": NAME, "bpm": BPM, "key": "D major", "style": "chipmunk-soul", "feel": "laid_back", "intensity": 0.45,
        "brief": "NIGHT SHIFT 09 「First Train」 — 보사·시티팝 레코드(+2) 위 브러시, 남성 소울 가수 리드 + 여성 화음, IV 로 끝",
        "sections": [{"name": n, "bars": kk} for n, kk in FORM],
        "tracks": {
            "Sample": {"role": "sample loop (varispeed +2, vinyl)", "fx": [
                {"device": "eq", "params": {"Low-pass freq": 110, "Low-pass gain": -12, "Mid freq 1": 350, "Mid gain 1": -2, "Mid Q 1": 0.9, "High-pass freq": 11000, "High-pass gain": -3}},
                {"device": "lowpass", "params": {"frequency": 20000}}]},
            "Drums": {"preset": "drums/vintage", "role": "brush drums", "sends": {"0": -18}},
            "Bass": {"preset": "bass/hollow_finger", "role": "finger bass", "volume_db": -4},
            "Keys": {"preset": "keys/rhodes_classic", "role": "rhodes", "pan": -0.15, "sends": {"0": -8}},
            "Chops": {"sound": kit["sfz"], "role": "chipmunk vocal chops (soft)", "pan": 0.1, "sends": {"0": -8}},
            "Strings": {"preset": "strings/ensemble", "role": "strings", "pan": -0.25, "sends": {"0": -7}},
            "Lead": {"role": "lead vocal (ns-singer-m)", "sends": {"0": -10}, "fx": vox_fx},
            "Harm": {"role": "harmony (gen-singer-b)", "pan": 0.2, "sends": {"0": -9}, "fx": vox_fx},
            "Rap": {"role": "rap (bomf-rapper, 8 bars)", "sends": {"0": -15}, "fx": vox_fx},
        },
        "buses": [{"name": "Verb", "bus": 0, "device": "Dragonfly Hall Reverb", "volume_db": -6}],
        "parts": [
            {"track": "Sample", "in": ["intro"], "audio": {"path": loop["path"], "every": 16, "gain_db": -3}},
            {"track": "Sample", "in": ["verse1", "verse2", "rap"], "audio": {"path": loop["path"], "every": 16, "gain_db": -4}},
            {"track": "Sample", "in": ["hook1", "hook2", "hook3", "outro"], "audio": {"path": loop["path"], "every": 16, "gain_db": -1}},
            {"track": "Sample", "in": ["bridge"], "audio": {"path": loop["path"], "every": 16, "gain_db": -8}},
            {"track": "Drums", "in": ["intro"], "offset": 32, "drums": D(BRUSH)},
            {"track": "Drums", "in": ["verse1", "verse2", "hook1", "rap"], "drums": D(BRUSH)},
            {"track": "Drums", "in": ["hook2", "hook3", "outro"], "drums": D(BRUSH2)},
            {"track": "Bass", "in": ["verse1", "verse2", "rap", "hook1", "hook2", "hook3", "outro"], "bass": {"progression": prog, "beats_per_chord": 4, "pattern": [[0, 1.4, 0], [2, .9, 0], [3, .9, 7]], "velocity": 84, "low": 28, "high": 45}},
            {"track": "Keys", "in": ["intro"], "offset": 48, "chords": {"progression": prog, "beats_per_chord": 4, "voicing": "rhodes", "rhythm": [[1, .5, .9], [3, .5, .8]], "velocity": 58}},
            {"track": "Keys", "in": ["verse1", "verse2", "rap", "hook1", "hook2", "hook3", "outro"], "chords": {"progression": prog, "beats_per_chord": 4, "voicing": "rhodes", "rhythm": [[1, .5, .9], [3, .5, .8]], "velocity": 60}},
            {"track": "Chops", "in": ["hook1", "hook2", "hook3"], "notes": SOFT, "cycle_beats": 8},
            {"track": "Chops", "in": ["bridge", "outro"], "notes": PAD, "cycle_beats": 8},
            {"track": "Strings", "in": ["hook3", "outro"], "chords": {"progression": prog, "beats_per_chord": 4, "voicing": "pad", "velocity": 56, "legato": 1.0}},
            {"track": "Lead", "in": ["verse1"], "vocal": {"voice": "ns-singer-m", "melody": V1_MEL, "lyrics": V1_LYR, "seed": 3}},
            {"track": "Lead", "in": ["verse2"], "vocal": {"voice": "ns-singer-m", "melody": V1_MEL, "lyrics": V2_LYR, "seed": 4}},
            {"track": "Lead", "in": ["hook1", "hook2", "hook3"], "vocal": {"voice": "ns-singer-m", "melody": HOOK_MEL, "lyrics": HOOK_LYR, "seed": 5}},
            {"track": "Harm", "in": ["hook2", "hook3"], "vocal": {"voice": "gen-singer-b", "melody": HOOK_HARM, "lyrics": HOOK_LYR, "seed": 6, "gain_db": -5}},
            {"track": "Lead", "in": ["bridge"], "vocal": {"voice": "ns-singer-m", "melody": BRIDGE_MEL, "lyrics": BRIDGE_LYR, "seed": 7}},
            {"track": "Rap", "in": ["rap"], "rap": {"voice": "bomf-rapper", "lines": RAP8, "beats_per_line": 4, "style": "quiet, warm, finally resting, close to the mic", "lock": 0.7, "seed": 5}},
        ],
        "automation": [{"track": "Sample", "device": 1, "param": "frequency", "points": [
            {"bar": 0, "value": 700}, {"bar": 8, "value": 1200}, {"bar": 15.9, "value": 2000}, {"bar": 16, "value": 20000},
            {"bar": total - 2, "value": 20000}, {"bar": total, "value": 600}]}],
        "mix": {"balance": True, "target_lufs": -12,
                "balance_lu": {"lead": 0, "harm": -5, "rap": -1, "sample": -3.5, "chops": -6, "drums": -8, "bass": -6, "keys": -8, "strings": -8}},
    }
    return spec


if __name__ == "__main__":
    label = sys.argv[1] if len(sys.argv) > 1 else "v1"
    concept_mod.save(NAME, CONCEPT)
    rspec = record()
    print("[1] 레코드 녹음", SRC_BPM, "BPM C major", flush=True)
    rec = arrange.bounce(rspec, stems=True, label="record")
    loop, kit, after = sample(rspec, rec)
    print("[2-3] 샘플", loop["path"], "코드(+2)", after, "찹", len(kit["kit"]), flush=True)
    spec = beat(loop, kit, after)
    from musicoma import album
    s, rep = album.rap_with_lego(spec, label, RAP_CAPTION, log=lambda m: print("[4]", m, flush=True))
    print(json.dumps({k: rep.get(k) for k in ("file", "loudness", "bands_db", "issues")}, ensure_ascii=False, default=str), flush=True)
