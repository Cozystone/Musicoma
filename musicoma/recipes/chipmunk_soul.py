"""칩멍크 소울 레시피 — '올드 칸예 스타일 + 소울/시티팝 샘플링'. AI 파형 생성 없음.

프로듀서가 하듯이:
1 '레코드' 만들기 : 소울/시티팝 발라드를 직접 작곡·편곡·연주(로즈·스트링·리드·드럼·베이스)해서 찍는다.
                    원곡 템포 = 목표 / 2^(반음/12) → 배속하면 정확히 목표 템포·+반음.
                    본인 보컬/음원이 있으면(sounds/inbox) 그걸 원곡으로 쓴다.
2 레코드 늙히기   : vinyl
3 샘플링          : 드럼·베이스 뺀 반주의 후렴 4마디를 배속(칩멍크) → 루프. 리드 스템은 음절처럼 찹 → 패드
4 비트            : 붐뱁 드럼(스윙), 배속된 키에 맞춘 베이스·로즈, 찹 훅, 리버브 버스, 역할 밸런스, 마스터
모든 단계는 설계서(spec.json)로 남아 미세조정 = 설계서 수정 후 다시 짓기.
"""
from pathlib import Path

from .. import arrange, compose, crate, theory
from ..knowledge import style as load_style

ROOT = Path(__file__).resolve().parents[2]

SOURCE_PROGRESSIONS = {
    "city-pop": "IVmaj7 iii7 vi7 V7/vi IVmaj7 V7sus4 Imaj7 vi9",
    "soul": "Imaj7 vi7 ii7 V7 Imaj7 vi7 IVmaj7 V7sus4",
    "gospel": "IVmaj7 V/IV iii7 vi7 ii7 V7 Imaj7 I7",
}
LEAD_SOUNDS = {"flute": "flute", "violin": "solo_violin", "rhodes": "rhodes", "horn": "horn", "trumpet": "trumpet"}


def plan(bpm=None, semitones=None):
    card = load_style("chipmunk-soul")
    bpm = bpm or card["tempo"]["sweet_spot"]
    semitones = semitones if semitones is not None else card["sample"]["varispeed_semitones"]["typical"]
    return {"bpm": bpm, "semitones": semitones, "source_bpm": round(bpm / 2 ** (semitones / 12), 3)}


def fit_lyrics(text, n):
    """가사 단어 수를 음표 수 n 에 맞춘다(모자라면 처음부터 되풀이 — 후렴처럼, 남으면 자름)."""
    words = text.split()
    return " ".join((words * (n // max(1, len(words)) + 1))[:n])


def record_spec(name, src_bpm, key="F major", style="city-pop", lead="flute", seed=7, vocal=None):
    """샘플로 쓸 '옛날 레코드' 설계서 — 느린 소울/시티팝 발라드, 18마디(intro 2 · A 8 · B 8).
    vocal={"voice", "lyrics", "low", "high"} 이면 B 구간을 가수(생성된 목소리)가 부른다 → 배속하면 칩멍크 보컬."""
    prog = SOURCE_PROGRESSIONS.get(style, SOURCE_PROGRESSIONS["soul"])
    kname, _, kmode = key.partition(" ")
    chords = theory.progression(prog, kname, "minor" if kmode.startswith("min") else "major")
    lo, hi = (vocal.get("low", 57), vocal.get("high", 74)) if vocal else (62, 81)
    mel = compose.lead_melody(chords, [4] * len(chords), kname, "major", low=lo, high=hi, style="soul", seed=seed)
    spec = {
        "name": name, "bpm": src_bpm, "key": key, "style": style,
        "brief": "샘플 소스용 레코드 (직접 작곡·연주)",
        "sections": [{"name": "intro", "bars": 2}, {"name": "A", "bars": 8}, {"name": "B", "bars": 8}],
        "tracks": {
            "Drums": {"sound": "drums_acoustic_basic", "role": "drums",
                      "fx": [{"device": "lowpass", "params": {"frequency": 7000}}]},
            "Bass": {"sound": "bass_finger", "role": "bass"},
            "Keys": {"sound": "rhodes", "role": "keys", "pan": -0.15, "sends": {"0": -10}},
            "Strings": {"sound": "strings_violins", "role": "strings", "pan": 0.2, "sends": {"0": -6}},
            "Lead": {"sound": LEAD_SOUNDS.get(lead, lead), "role": "lead", "sends": {"0": -8}},
        },
        "buses": [{"name": "Room", "bus": 0, "device": "Dragonfly Hall Reverb", "volume_db": -6}],
        "parts": [
            {"track": "Drums", "in": ["A", "B"],
             "drums": {"pattern": {"kick": "x.......x.x.....", "snare": "....x.......x...", "hat": "x-x-x-x-x-x-x-x-"},
                       "swing": 0.54, "humanize_ms": 8, "humanize_vel": 10}},
            {"track": "Bass", "in": ["A", "B"],
             "bass": {"progression": prog, "beats_per_chord": 4,
                      "pattern": [[0, 1.5, 0], [1.5, 0.5, 7], [2, 1.5, 0], [3.5, 0.5, 12]]}},
            {"track": "Keys", "in": "all",
             "chords": {"progression": prog, "beats_per_chord": 4, "voicing": "rhodes",
                        "rhythm": [[0, 1.5, 1.0], [1.5, 1.0, 0.75], [2.5, 1.5, 0.85]], "velocity": 74}},
            {"track": "Strings", "in": ["B"],
             "chords": {"progression": prog, "beats_per_chord": 4, "voicing": "pad", "velocity": 70, "legato": 1.0}},
            {"track": "Lead", "in": ["B"], "melody": {"text": compose.to_text(mel), "velocity": 96}},
            {"track": "Lead", "in": ["A"], "melody": {"text": compose.to_text(mel), "velocity": 84}, "transpose": -12},
        ],
        "mix": {"balance": True, "balance_lu": {"keys": 0, "lead": 2, "strings": -2, "drums": -3, "bass": -3}},
    }
    if vocal:
        mtext = compose.to_text(mel)
        n = sum(1 for tok in mtext.split() if not tok.startswith("r:"))
        spec["tracks"]["Vox"] = {"role": "lead vocal (generated voice)", "sends": {"0": -9},
                                 "fx": [{"device": "compressor", "params": {"threshold": -18, "ratio": 3}}]}
        spec["parts"] = [p for p in spec["parts"] if not (p["track"] == "Lead" and p["in"] == ["B"])]
        spec["parts"].append({"track": "Vox", "in": ["B"], "vocal": {"voice": vocal["voice"], "melody": mtext,
                              "lyrics": fit_lyrics(vocal["lyrics"], n), "seed": seed}})
        spec["mix"]["balance_lu"]["vox"] = 3
    return spec


def beat_spec(name, bpm, key, chords_after, sample_loop, chop_kit, card, brief=""):
    pats = card["drums"]["patterns"]
    sw = card["swing"]["amount"]

    def clean(p):
        return {k: v for k, v in p.items() if k != "note"}

    def drum(p, fill=True):
        return {"pattern": clean(pats[p]), "swing": sw, "humanize_ms": 6, "humanize_vel": 8,
                **({"fill": clean(pats["fill_end"])} if fill else {})}

    prog = " ".join(chords_after)
    spec = {
        "name": name, "bpm": bpm, "key": key, "style": "chipmunk-soul", "brief": brief,
        "sections": [{"name": "intro", "bars": 4}, {"name": "verse", "bars": 8}, {"name": "hook", "bars": 8},
                     {"name": "verse", "bars": 8}, {"name": "hook", "bars": 8}, {"name": "outro", "bars": 4}],
        "tracks": {
            "Sample": {"role": "sample loop (varispeed, vinyl)", "fx": [
                {"device": "eq", "params": {"Low-pass freq": 110, "Low-pass gain": -14, "Mid freq 1": 350,
                                            "Mid gain 1": -3.5, "Mid Q 1": 0.9, "High-pass freq": 11000,
                                            "High-pass gain": -3}},
                {"device": "lowpass", "params": {"frequency": 20000}}]},
            "Drums": {"sound": "drums_acoustic_basic", "role": "boom bap drums", "sends": {"0": -22}, "fx": [
                {"device": "eq", "params": {"Low-pass freq": 60, "Low-pass gain": 3, "Mid freq 1": 350,
                                            "Mid gain 1": -3, "Mid Q 1": 1.0, "Mid freq 2": 4500, "Mid gain 2": 2.5}},
                {"device": "compressor", "params": {"threshold": -20, "ratio": 4, "attack": 20, "release": 80,
                                                    "output gain": 3}}]},
            "Bass": {"sound": "bass_sub", "role": "sub bass", "fx": [{"device": "lowpass", "params": {"frequency": 700}}]},
            "Keys": {"sound": "rhodes", "role": "rhodes layer", "pan": -0.15, "sends": {"0": -8}},
        },
        "buses": [{"name": "Verb", "bus": 0, "device": "Dragonfly Plate Reverb", "volume_db": -4}],
        "parts": [
            {"track": "Sample", "in": "all", "audio": {"path": sample_loop, "every": 16}},
            {"track": "Drums", "in": ["verse"], "drums": drum("main")},
            {"track": "Drums", "in": ["hook"], "drums": drum("bounce")},
            {"track": "Drums", "in": ["outro"], "drums": drum("sparse_intro", fill=False)},
            {"track": "Bass", "in": ["verse", "hook"],
             "bass": {"progression": prog, "beats_per_chord": 4,
                      "pattern": [[0, 1.4, 0], [1.5, 0.9, 0], [2.5, 0.6, 0], [3.25, 0.6, 7]]}},
            {"track": "Keys", "in": ["hook"],
             "chords": {"progression": prog, "beats_per_chord": 4, "voicing": "rhodes",
                        "rhythm": [[1.0, 0.5, 1.0], [3.0, 0.5, 0.9]], "velocity": 70}},
        ],
        "automation": [{"track": "Sample", "device": 1, "param": "frequency",
                        "points": [{"bar": 0, "value": 750}, {"beat": 15.75, "value": 1100},
                                   {"bar": 4, "value": 20000}, {"bar": 40, "value": 20000},
                                   {"bar": 44, "value": 500}]}],
        "mix": {"balance": True, "target_lufs": card["mix"]["target_lufs"]},
    }
    if chop_kit:
        keys = list(chop_kit["kit"].values())
        hook = [{"pitch": keys[k % len(keys)], "start": off, "length": 0.7, "velocity": 100 if off == 0 else 88}
                for off, k in [(0.0, 0), (0.75, 1), (1.5, 0), (2.0, 2), (3.0, 1), (3.5, 3)]]
        spec["tracks"]["Chops"] = {"sound": chop_kit["sfz"], "role": "chop hook", "pan": 0.1, "sends": {"0": -10}}
        spec["parts"].append({"track": "Chops", "in": ["hook"], "notes": hook, "cycle_beats": 4})
    return spec


def build(name, bpm=None, semitones=None, key="F major", source_style="city-pop", lead="flute", seed=7,
          source=None, brief="", log=print, label="v1", customize=None, vocal=None, double=True,
          region_override=None):
    """source: 본인 음원 경로(있으면 그걸 샘플링). 없으면 레코드를 직접 작곡·연주해서 만든다.
    double: 원곡 8마디를 배속해 4마디로(빠른 원곡 → 하프타임 붐뱁). bpm 을 안 주면 배속 결과로 정한다."""
    bpm_given = bpm
    p = plan(bpm, semitones)
    bpm, st = p["bpm"], p["semitones"]
    card = load_style("chipmunk-soul")
    notes = {"plan": p}

    if source is None:
        rspec = record_spec(f"{name}-record", p["source_bpm"], key, source_style, lead, seed, vocal=vocal)
        log(f"[1] 레코드 작곡·녹음: {source_style}, {key}, {p['source_bpm']} BPM, 리드={lead}")
        rec = arrange.bounce(rspec, stems=True, label="record")
        notes["record"] = {"spec": str(ROOT / "projects" / rspec["name"] / "spec.json"), "mix": rec["mix"]}
        sections, _ = arrange._sections(rspec)
        b = next(s for s in sections if s["name"] == "B")
        spb = 60 / p["source_bpm"]
        start, end = b["start_bar"] * 4 * spb, (b["start_bar"] + 4) * 4 * spb
        stems = rec["stems"]
        parts_ = ["Keys", "Strings", "Lead"] + (["Vox"] if "Vox" in stems else [])
        accomp = crate.mix_files([stems[k] for k in parts_], Path(rec["mix"]).with_name("accomp.wav"),
                                 gains_db=[0, -1, 1, 2][:len(parts_)])
        aged = crate.age(accomp, "vinyl")
        loop = crate.loop_region(aged, start, end, 4, bpm, tag="sample_loop")
        lead_loop = crate.loop_region(stems.get("Vox") or stems["Lead"], start, end, 4, bpm, tag="lead_loop")
        src_chords = theory.progression(SOURCE_PROGRESSIONS.get(source_style, SOURCE_PROGRESSIONS["soul"]),
                                        key.split()[0], "major")[:4]
        key_after = theory.transpose_key(key, round(st))
        chords_after = [theory.transpose_chord(c, round(st)) for c in src_chords]
        log(f"[2-3] 후렴 4마디 늙히고 → {bpm} BPM, 배속 x{loop['varispeed_ratio']:.4f} "
            f"({loop['semitones']:+.2f}반음) → {key_after}, 코드 {' '.join(chords_after)}")
    else:
        # 본인 음원 샘플링: 원곡 8마디(배속 후 4마디, 하프타임 비트) 또는 4마디. 템포는 배속 결과에서 정한다.
        from .. import transcribe, importer
        wav = importer.to_wav(source)
        info = crate.analyze(wav)
        src_bars = 8 if double else 4
        ratio = 2 ** (st / 12)
        if bpm_given is None:
            bpm = round(info["bpm"] * ratio / (2 if double else 1), 2)
        beats, phase = info["beats_all"], info["downbeat_phase"]
        stems = crate.separate(wav)
        region = crate.best_bars(stems["vocals"], bars=src_bars, beats=beats, phase=phase)
        if region_override:
            region = region_override
        log(f"[1] 본인 음원: {info['bpm']} BPM {info['key']} · 루프 {region['start']:.2f}~{region['end']:.2f}s "
            f"(원곡 {src_bars}마디) → 비트 {bpm} BPM")
        accomp = crate.mix_files([stems["vocals"], stems["other"]], Path(stems["vocals"]).with_name("sample.wav"))
        aged = crate.age(accomp, "vinyl")
        loop = crate.loop_region(aged, region["start"], region["end"], 4, bpm, tag="sample_loop")
        lead_loop = crate.loop_region(stems["vocals"], region["start"], region["end"], 4, bpm, tag="vocal_loop")
        other = crate.loop_region(stems["other"], region["start"], region["end"], 4, bpm, tag="other_loop")
        bass_l = crate.loop_region(stems["bass"], region["start"], region["end"], 4, bpm, tag="bass_loop")
        ch = transcribe.simplify(transcribe.chords(other["path"], bpm, beats_per_chord=4, bass_path=bass_l["path"]))
        chords_after = [c[0] for c in ch][:4] or ["C"]
        key_after = crate.analyze(loop["path"])["key"]
        notes["source"] = {"path": str(source), "bpm": info["bpm"], "key": info["key"], "region": region,
                           "double": double}
        log(f"[2-3] 배속 x{loop['varispeed_ratio']:.4f} ({loop['semitones']:+.2f}반음) → {key_after}, 코드 {chords_after}")
    notes["sample"] = {"loop": loop["path"], "semitones": loop["semitones"], "key_after": key_after,
                       "chords_after": chords_after}

    chops = crate.chop(lead_loop["path"], mode="onsets", n=8, min_len=0.15, max_len=1.2)
    kit = crate.make_kit(chops, Path(chops[0]["path"]).parent / "chops.sfz") if chops else None
    log(f"[3] 리드 찹 {len(chops)}개 → 패드")

    spec = beat_spec(name, bpm, key_after, chords_after, loop["path"], kit, card, brief)
    if customize:
        spec = customize(spec, notes) or spec        # 편곡 확장(오케스트라·랩 자리 등)
    s, report = arrange.build(spec, label=label, log=lambda m: log("[4] " + m))
    notes["beat_spec"] = str(ROOT / "projects" / name / "spec.json")
    s.log(brief or "chipmunk soul", {"recipe": "chipmunk_soul", "notes": notes})
    return s, notes, report
