"""musicoma-006 「Last Exit」 — 일본 시티팝, 영어 가사, 처음부터 보컬까지. (10-15 본인: 새 테스트 곡)

절차(CLAUDE.md): 0 레퍼런스(knowledge/references/city-pop.yaml) → 1 콘셉트 → 이야기 구조 → 동기 → 비평
→ 반주 짓기 → 2 보컬: 반주를 '듣고' 부르는 생성(lego, 구간별 테이크 자동 선택) → 최종 믹스.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from musicoma import arrange, concept as concept_mod, critic, lego, lyrics, motif

NAME = "musicoma-006-last-exit"
BPM, KEY = 112, "F major"
SPB = 60 / BPM

LYR = {
    "verse": "Neon on the window, rain is falling slow\nRadio is playing songs we used to know\n"
             "You said meet me at the station after nine\nI've been counting every light along the line",
    "pre": "Don't say it's over, not tonight\nJust drive a little longer through the light",
    "chorus": "One more exit, baby, one more mile\nLet the city keep us for a while\n"
              "Silver highway, take me where you go\nWe're a love song on the radio",
    "verse2": "Every exit sign is whispering goodbye\nBut you're laughing like the summer in July\n"
              "So I keep on driving, never asking why",
}

CONCEPT = {
    "thesis": "끝나 가는 사랑을 고속도로 출구 하나만큼만 미루는 밤 — 슬픈데 춤춘다",
    "arc": [{"section": "intro", "intent": "빗속 차 안, 피아노와 드럼만", "energy": 0.3},
            {"section": "verse", "intent": "기억을 세는 담담함", "energy": 0.45},
            {"section": "pre", "intent": "끝을 미루는 부탁", "energy": 0.6},
            {"section": "chorus", "intent": "한 마일만 더 — 들뜸과 애수", "energy": 0.85},
            {"section": "verse2", "intent": "이야기가 빨라짐(6마디)", "energy": 0.5},
            {"section": "bridge", "intent": "말 대신 색소폰", "energy": 0.65},
            {"section": "chorus_last", "intent": "반음 올라 마지막 출구", "energy": 1.0},
            {"section": "outro", "intent": "출구를 지나쳐 계속 달림", "energy": 0.4}],
    "motif": {"melody": "C5:.5 D5:.5 F5:1 E5:.5 D5:1.5", "why": "'one more mile' — 올라갔다 한 칸 내려앉는 미련"},
    "collision": ["80년대 도쿄 스튜디오 시티팝", "미국 AOR 색소폰", "빗속 드라이브의 정적"],
    "constraints": ["더하기 편곡 — 인트로는 CP80+드럼만, 악기는 하나씩 들어온다(Ride on Time)",
                    "후렴은 IVmaj7 → III7 → vi 로 끌어당김(Stay With Me)", "절은 단조 9화음 쪽 색(Plastic Love)"],
    "events": [{"section": "chorus_last", "at": -1, "length": 1, "type": "stop", "why": "마지막 출구 직전 숨"}],
    "irregular": [{"what": "2절 6마디", "why": "이야기가 빨라짐 — 할 말 길이만큼"},
                  {"what": "마지막 후렴 반음 전조", "why": "시티팝 관례 + 마지막 출구의 고양"},
                  {"what": "브리지는 가사 없이 색소폰", "why": "말로 못 하는 부분"}],
    "references": "knowledge/references/city-pop.yaml — Plastic Love · Stay With Me · Ride on Time · Flyday Chinatown(실측)",
    "not": ["808", "사이드체인", "단순 3화음", "같은 4마디 복사"],
}

SECTIONS = [{"name": "intro", "bars": 4}, {"name": "verse", "bars": 8}, {"name": "pre", "bars": 4},
            {"name": "chorus", "bars": 8}, {"name": "verse2", "bars": 6}, {"name": "pre", "bars": 4},
            {"name": "chorus", "bars": 8}, {"name": "bridge", "bars": 8},
            {"name": "chorus_last", "bars": 8, "transpose": 1}, {"name": "outro", "bars": 4}]
PROG = {"verse": "vi9 ii9 V13 Imaj7", "pre": "IVmaj7 V7sus4 iii7 vi7", "chorus": "IVmaj7 III7 vi7 I7",
        "bridge": "bVImaj7 bVII7 Imaj7 vi9"}
DR = {"main": {"kick": "x.....x.x.......", "snare": "....x.......x...", "hat": "xxxxxxxxxxxxxxxx", "open_hat": "..............x."},
      "groove2": {"kick": "x..x..x...x..x..", "snare": "....x.......x..o", "hat": "x-x-x-x-x-x-x-x-"},
      "fill": {"kick": "x.......", "snare": "....x.xxoxoxXXXX"}}


def drums(p, fill=True):
    return {"pattern": DR[p], "swing": 0.5, "humanize_ms": 5, "humanize_vel": 8, **({"fill": DR["fill"]} if fill else {})}


def chords_for(sec, bars):
    from musicoma import theory
    ch = theory.progression(PROG[sec], "F", "major")
    return [(b * 4, b * 4 + 4, ch[b % len(ch)]) for b in range(bars)]


M = CONCEPT["motif"]["melody"]
SAX = (motif.section_melody(M, ["octave:-1"], chords_for("bridge", 4), KEY, 4, "statement sequence climb answer") + " " +
       motif.section_melody(M, ["octave:-1", "rhythm:.25,.25,.5,.25,1.75"], chords_for("bridge", 4), KEY, 4, "fragment climb question answer"))
BRASS_HOOK = motif.section_melody(M, [], chords_for("chorus", 2), KEY, 2, "statement")

spec = {
    "name": NAME, "bpm": BPM, "key": KEY, "style": "city-pop", "feel": "straight", "intensity": 0.7,
    "brief": "「Last Exit」 시티팝 · 영어 가사 · 반주 조건 생성 보컬",
    "sections": SECTIONS,
    "tracks": {
        "Drums": {"preset": "drums/live_room", "role": "drums", "sends": {"0": -24}},
        "Bass": {"preset": "bass/picked", "role": "bass"},
        "CP80": {"preset": "keys/cp80", "role": "keys", "pan": -0.2, "sends": {"0": -12}},
        "Guitar": {"preset": "guitar/archtop", "role": "guitar", "pan": 0.35, "sends": {"0": -16}},
        "Strings": {"preset": "strings/ensemble", "role": "strings", "pan": -0.1, "sends": {"0": -8}},
        "Brass": {"preset": "brass/synth_80s", "role": "brass", "pan": 0.15, "sends": {"0": -12}},
        "Sax": {"preset": "lead/alto_sax", "role": "lead", "sends": {"0": -10}},
    },
    "buses": [{"name": "Plate", "bus": 0, "device": "Dragonfly Plate Reverb", "volume_db": -5}],
    "parts": [
        # 더하기 편곡: 인트로 = CP80 + 드럼만
        {"track": "Drums", "in": ["intro", "verse", "verse2", "outro"], "drums": drums("main")},
        {"track": "Drums", "in": ["pre", "bridge"], "drums": drums("groove2")},
        {"track": "Drums", "in": ["chorus", "chorus_last"], "drums": drums("main")},
        {"track": "CP80", "in": ["intro", "verse", "verse2"], "chords": {"progression": PROG["verse"], "beats_per_chord": 4, "voicing": "rhodes",
                                                             "rhythm": [[0, 0.5, 1.0], [0.75, 0.5, 0.8], [1.5, 0.25, 0.7], [2.5, 0.5, 0.9], [3.25, 0.5, 0.8]], "velocity": 72}},
        {"track": "CP80", "in": ["pre"], "chords": {"progression": PROG["pre"], "beats_per_chord": 4, "voicing": "rhodes",
                                                   "rhythm": [[0, 1.5, 1.0], [2, 1.5, 0.85]], "velocity": 70}},
        {"track": "CP80", "in": ["chorus", "chorus_last", "outro"], "chords": {"progression": PROG["chorus"], "beats_per_chord": 4, "voicing": "rhodes",
                                                                         "rhythm": [[0, 0.5, 1.0], [0.75, 0.5, 0.8], [1.5, 0.25, 0.7], [2.5, 0.5, 0.9], [3.25, 0.5, 0.8]], "velocity": 76}},
        {"track": "CP80", "in": ["bridge"], "chords": {"progression": PROG["bridge"], "beats_per_chord": 4, "voicing": "rhodes",
                                                      "rhythm": [[0, 2, 1.0], [2.5, 1.5, 0.8]], "velocity": 66}},
        {"track": "Bass", "in": ["verse", "verse2"], "bass": {"progression": PROG["verse"], "beats_per_chord": 4, "low": 29, "high": 50,
                                                             "pattern": [[0, 0.5, 0], [0.75, 0.25, 12], [1.5, 0.5, 0], [2, 0.5, 7], [2.75, 0.25, 12], [3.5, 0.5, 10]]}},
        {"track": "Bass", "in": ["pre"], "bass": {"progression": PROG["pre"], "beats_per_chord": 4, "low": 29, "high": 50,
                                                 "pattern": [[0, 1.5, 0], [1.5, 0.5, 7], [2, 1.5, 0], [3.5, 0.5, 12]]}},
        {"track": "Bass", "in": ["chorus", "chorus_last"], "bass": {"progression": PROG["chorus"], "beats_per_chord": 4, "low": 29, "high": 50,
                                                                   "pattern": [[0, 0.5, 0], [0.5, 0.25, 12], [0.75, 0.25, 0], [1.5, 0.5, 7], [2, 0.5, 0], [2.75, 0.25, 12], [3.25, 0.25, 10], [3.5, 0.5, 7]]}},
        {"track": "Bass", "in": ["bridge"], "bass": {"progression": PROG["bridge"], "beats_per_chord": 4, "low": 29, "high": 50,
                                                    "pattern": [[0, 1.5, 0], [1.5, 0.5, 7], [2.5, 1, 12], [3.5, 0.5, 7]]}},
        {"track": "Guitar", "in": ["verse", "verse2"], "chords": {"progression": PROG["verse"], "beats_per_chord": 4, "voicing": "guitar",
                                                                 "rhythm": [[1, 0.25, 1.0], [1.75, 0.125, 0.6], [3, 0.25, 1.0], [3.75, 0.125, 0.6]], "velocity": 70}},
        {"track": "Guitar", "in": ["chorus", "chorus_last"], "chords": {"progression": PROG["chorus"], "beats_per_chord": 4, "voicing": "guitar",
                                                                       "rhythm": [[1, 0.25, 1.0], [1.75, 0.125, 0.6], [3, 0.25, 1.0], [3.75, 0.125, 0.6]], "velocity": 74}},
        {"track": "Strings", "in": ["pre"], "chords": {"progression": PROG["pre"], "beats_per_chord": 4, "voicing": "pad", "velocity": 64, "legato": 1.0}},
        {"track": "Strings", "in": ["chorus", "chorus_last"], "chords": {"progression": PROG["chorus"], "beats_per_chord": 4, "voicing": "pad", "velocity": 72, "legato": 1.0}},
        {"track": "Brass", "in": ["chorus", "chorus_last"], "chords": {"progression": PROG["chorus"], "beats_per_chord": 4, "voicing": "stab",
                                                                     "rhythm": [[0, 0.25, 1.0], [0.5, 0.25, 0.85], [3.5, 0.5, 1.0]], "velocity": 92}},
        {"track": "Brass", "in": ["pre"], "melody": {"text": "r:12 " + BRASS_HOOK.split(" r:")[0], "velocity": 96, "repeat": False}},
        {"track": "Sax", "in": ["bridge"], "melody": {"text": SAX, "velocity": 96, "repeat": False}},
        {"track": "Sax", "in": ["outro"], "melody": {"text": motif.section_melody(M, ["octave:-1", "augment:2"], chords_for("chorus", 4), KEY, 4, "statement"),
                                                     "velocity": 84, "repeat": False}},
    ],
    "events": CONCEPT["events"],
    "mix": {"balance": True, "target_lufs": -12,
            "balance_lu": {"drums": 0, "bass": -1, "cp80": -2.5, "guitar": -6, "strings": -6, "brass": -4, "sax": -1, "vox": 2.5}},
}


def vocal_sections():
    """보컬이 부를 구간(초). 절+프리를 한 덩어리로(이야기가 이어지게), 후렴은 따로."""
    out, bar = [], 0
    starts = []
    for s in SECTIONS:
        starts.append((s["name"], bar, s["bars"]))
        bar += s["bars"]
    def t(b):
        return round(b * 4 * SPB, 3)
    seen = {}
    i = 0
    while i < len(starts):
        name, b0, n = starts[i]
        k = seen.get(name, 0)
        seen[name] = k + 1
        if name in ("verse", "verse2") and i + 1 < len(starts) and starts[i + 1][0] == "pre":
            nb = n + starts[i + 1][2]
            out.append({"name": f"{name}_pre", "start": t(b0), "end": t(b0 + nb), "tag": "Verse",
                        "lyrics": LYR[name] + "\n\n" + LYR["pre"]})
            seen["pre"] = seen.get("pre", 0) + 1
            i += 2
            continue
        if name in ("chorus", "chorus_last"):
            out.append({"name": f"{name}{k + 1}", "start": t(b0), "end": t(b0 + n), "tag": "Chorus", "lyrics": LYR["chorus"]})
        i += 1
    return out


if __name__ == "__main__":
    step = sys.argv[1] if len(sys.argv) > 1 else "all"
    concept_mod.save(NAME, CONCEPT)
    r = critic.critique(spec, CONCEPT)
    print(critic.format_report(r).split("Claude 가")[0])
    if step == "dry":
        sys.exit(0)
    root = Path(arrange.ROOT) / "projects" / NAME
    inst = root / "renders" / f"{NAME}_inst.wav"
    if step in ("all", "inst"):
        s, rep = arrange.build(spec, label="inst")
        print("반주:", rep["file"], rep["loudness"]["lufs_integrated"])
    if step in ("all", "vocal"):
        # 보컬 생성용 가벼운 반주(드럼·베이스·CP80) — 꽉 찬 편곡에서는 Lego 가 보컬을 안 얹는다(10-15 측정)
        import glob, numpy as np, soundfile as sf
        st = {Path(p).stem.rsplit("_", 1)[0]: p for p in glob.glob(str(root / ".work" / "stems" / "*.wav"))}
        mix = None
        for k, g in [("Drums", 1.0), ("Bass", 1.0), ("CP80", 0.9)]:
            y, sr = sf.read(st[k])
            mix = y * g if mix is None else mix[:len(y)] + y[:len(mix)] * g
        guide = root / ".work" / "vocal_guide.wav"
        sf.write(str(guide), mix / np.abs(mix).max() * 0.8, sr, subtype="PCM_24")
        caption = "female vocals, english, 1980s japanese city pop, clear singing, lead vocal"
        vox, rep_v = lego.vocal_track(inst, vocal_sections(), BPM, KEY, caption, root / "vocals" / "vox_lego.wav",
                                      takes=18, guide_wav=guide, pass_wer=0.35)
        for x in rep_v:
            print(x["section"], "seed", x["chosen"], "오류율", x["wer"], "유사도", x["voice_sim"])
    if step in ("all", "final"):
        spec["tracks"]["Vox"] = {"role": "lead vocal (generated over the arrangement)", "sends": {"0": -10},
                                 "fx": [{"device": "eq", "params": {"Low-pass freq": 140, "Low-pass gain": -6, "Mid freq 2": 3500, "Mid gain 2": 1.5}},
                                        {"device": "compressor", "params": {"threshold": -20, "ratio": 3, "attack": 8, "release": 120}}]}
        total_beats = sum(x["bars"] for x in SECTIONS) * 4
        spec["parts"].append({"track": "Vox", "in": ["intro"], "audio": {"path": str(root / "vocals" / "vox_lego_v3.wav"), "length": total_beats}})
        s, rep = arrange.build(spec, label="v1")
        print(json.dumps({k: rep[k] for k in ("file", "loudness", "bands_db", "issues")}, ensure_ascii=False, default=str))
