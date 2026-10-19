"""musicoma-021 「Say It Again」 — 새 장르 '애프터워드(afterword)'의 첫 곡. 10-19 본인: "또 다른 새 장르".

애프터워드 선언
  1. 말이 끝나면 밴드가 그 말을 '다시 말한다' — 가사 없이, 말의 억양(음높이·리듬) 그대로 악기가 연주한다.
  2. 악기 선율은 작곡하지 않는다. 래퍼가 실제로 말한 소리에서 음높이를 재어(pyin) 조성에 붙이고 박에 맞춘 것뿐이다.
  3. 대답은 말의 빈자리(1박 이상 쉬는 곳)에만 들어간다 — 래퍼가 숨 쉬는 곳이 밴드가 말하는 곳.
  4. 브리지는 래퍼 없이 밴드 혼자 1절을 '랩'한다(1절의 억양을 색소폰·바이올린이 그대로).
  5. 훅은 사람이 한 번, 종·색소폰이 한 번.
라이징 테이프(속도=형식)와 축이 다르다: 이번엔 '말=선율'.

    python works/musicoma_021_say_it_again.py
"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from musicoma import arrange, concept as concept_mod, lego, master, voice_design as vd
from musicoma_020_escape_velocity import mix, RAP_REF

NAME = "musicoma-021-say-it-again"
BPM, KEY = 86, "A minor"
SPB = 60 / BPM
SCALE = {9, 11, 0, 2, 4, 5, 7}
FORM = [("intro", 4), ("verse1", 16), ("hook1", 8), ("verse2", 16), ("hook2", 8), ("bridge", 8), ("hook3", 8), ("outro", 4)]
ROOT = Path(arrange.ROOT)

VERSE1 = ["Dad calls on Sundays at nine", "Asks about the weather here", "I say it's fine, he says good",
          "That's the call, that's the whole call", "He used to sing in the car", "Now he just says drive safe",
          "I hear the TV behind him", "Some game that nobody's winning"]
VERSE2 = ["I wanted to say I'm tired", "I said the rent went up instead", "He wanted to say he's lonely",
          "He said the dog's getting old", "We're two men reading a weather report", "To each other, every week",
          "Somewhere under all the small talk", "There's a song we both forgot the words to"]
HOOK = ["Say it again", "Without the words", "Say it again", "So I can hear it"]

CONCEPT = {
    "thesis": "일요일 아홉 시 아버지와의 통화 — 날씨 얘기만 하는 두 남자. 하지 못한 말을 밴드가 가사 없이 말의 억양으로 다시 말한다",
    "genre": "afterword — 말이 끝난 자리에 밴드가 그 말의 억양을 그대로 연주한다(작곡 없음, 측정한 억양)",
    "arc": [{"section": "verse1", "intent": "짧은 줄, 빈자리마다 색소폰이 마지막 말을 다시", "energy": 0.5},
            {"section": "hook", "intent": "'say it again' — 사람 한 번, 종·색소폰 한 번", "energy": 0.85},
            {"section": "bridge", "intent": "래퍼 없음 — 밴드가 1절을 랩한다(억양만)", "energy": 0.55},
            {"section": "outro", "intent": "마지막 대답만 남는다", "energy": 0.2}],
    "motif": {"melody": "(측정)", "why": "선율을 쓰지 않는다 — 말에서 잰다"},
    "collision": ["붐뱁", "말의 억양(음성학)", "콜 앤 리스폰스(가스펠·재즈)"],
    "constraints": ["대답은 1박 이상 빈자리에만", "악기 선율은 측정값만(손으로 고치지 않음)", "랩 줄 ≤8음절"],
    "not": ["작곡한 리프", "빈자리 없는 랩"],
}


def band_spec(echo_parts=()):
    sw = 0.56
    D = lambda pat, fill=None: {"pattern": pat, "swing": sw, "humanize_ms": 7, "humanize_vel": 9, **({"fill": fill} if fill else {})}
    MAIN = {"kick": "x.....x...x..x..", "snare": "....X.......X...", "hat": "x-x-x-x-x-x-x-x-"}
    MAIN2 = {"kick": "X.....x...X..x..", "snare": "....X..o....X..o", "hat": "x-x-x-x-x-x-x-x-", "open_hat": "..........x....."}
    HK = {"kick": "X..x......X..x..", "snare": "....X..o....X...", "hat": "x-x-x-x-x-x-x-x-", "open_hat": "..............x."}
    BR = {"kick": "x.........x.....", "snare": "....x.......x...", "hat": "..x...x...x...x."}
    F1 = {"kick": "X.....x...X.....", "snare": "....X.......xoxo", "hat": "x.x.x.x.x.x....."}
    V = "i7 VImaj7 iv7 V7sus4"
    H = "VImaj7 VII7 i7 i7"
    parts = [
        {"track": "Keys", "in": ["intro", "verse1", "verse2", "bridge", "outro"], "chords": {"progression": V, "beats_per_chord": 4, "voicing": "rhodes", "rhythm": [[0, 1.5, .9], [2.5, 1, .75]], "velocity": 58}},
        {"track": "Keys", "in": ["hook1", "hook2", "hook3"], "chords": {"progression": H, "beats_per_chord": 4, "voicing": "rhodes", "rhythm": [[0, 1.5, 1], [2, 1.5, .85]], "velocity": 66}},
        {"track": "Drums", "in": ["verse1"], "drums": D(MAIN, F1)},
        {"track": "Drums", "in": ["verse2"], "drums": D(MAIN2, F1)},
        {"track": "Drums", "in": ["hook1", "hook2", "hook3"], "drums": D(HK, F1)},
        {"track": "Drums", "in": ["bridge"], "drums": D(BR)},
        {"track": "Bass", "in": ["verse1", "verse2", "bridge"], "bass": {"progression": V, "beats_per_chord": 4, "pattern": [[0, .9, 0], [1.5, .5, 0], [2.5, .45, 0], [3.25, .5, 7]], "velocity": 96}},
        {"track": "Bass", "in": ["hook1", "hook2", "hook3"], "bass": {"progression": H, "beats_per_chord": 4, "pattern": [[0, 1.1, 0], [1.75, .5, 0], [2.5, .4, 12], [3.25, .5, 7]], "velocity": 104}},
        {"track": "Pad", "in": ["hook1", "hook2", "hook3", "bridge"], "chords": {"progression": H, "beats_per_chord": 4, "voicing": "pad", "velocity": 50, "legato": 1.0}},
    ]
    return {
        "name": NAME, "bpm": BPM, "key": KEY, "style": "chipmunk-soul", "feel": "laid_back", "intensity": 0.6,
        "brief": "「Say It Again」 애프터워드 — 말이 끝난 자리에 밴드가 그 억양을 연주",
        "sections": [{"name": n, "bars": b} for n, b in FORM],
        "tracks": {
            "Drums": {"sound": "drums_acoustic_basic", "role": "drums", "sends": {"0": -22}, "fx": [
                {"device": "eq", "params": {"Low-pass freq": 62, "Low-pass gain": 3, "Mid freq 1": 350, "Mid gain 1": -3, "Mid Q 1": 1.0, "Mid freq 2": 4500, "Mid gain 2": 2.5}},
                {"device": "compressor", "params": {"threshold": -19, "ratio": 4, "attack": 18, "release": 80, "output gain": 3}}]},
            "Bass": {"sound": "bass_sub", "role": "sub bass", "volume_db": -3, "fx": [{"device": "lowpass", "params": {"frequency": 700}}]},
            "Keys": {"preset": "keys/rhodes_dark", "role": "keys", "pan": -0.2, "sends": {"0": -9}},
            "Pad": {"preset": "pad/warm", "role": "pad", "sends": {"0": -6}},
            "Sax": {"preset": "lead/alto_sax", "role": "echo (speech melody)", "pan": 0.25, "sends": {"0": -7}},
            "Bell": {"preset": "lead/bell", "role": "echo bell (hook)", "pan": 0.35, "sends": {"0": -5}},
            "Violin": {"preset": "strings/solo_violin", "role": "echo violin (bridge)", "pan": -0.3, "sends": {"0": -6}},
        },
        "buses": [{"name": "Room", "bus": 0, "device": "Dragonfly Plate Reverb", "volume_db": -5}],
        "parts": parts + list(echo_parts),
        "mix": {"balance": True, "target_lufs": -14,
                "balance_lu": {"drums": 0, "bass": -3, "keys": -7, "pad": -10, "sax": -3, "bell": -6, "violin": -5}},
    }


def snap(m):
    m = int(round(m))
    for d in (0, -1, 1, -2, 2):
        if (m + d) % 12 in SCALE:
            return m + d
    return m


def speech_notes(vox_file, place_s, lo=57, hi=76):
    """보컬 파일 → 단어별 음표 [{'pitch','start'(곡 박),'length','word','end'}]. 음높이 = 단어 안 유성 프레임 중앙값, 옥타브만 악기 음역으로."""
    import librosa
    words = vd.words(vox_file, "en")
    y, sr = librosa.load(str(vox_file), sr=16000, mono=True)
    f0, v, _ = librosa.pyin(y, fmin=70, fmax=600, sr=sr, frame_length=1024)
    t = librosa.times_like(f0, sr=sr, hop_length=256)
    midi = librosa.hz_to_midi(np.where(v, f0, np.nan))
    raw = []
    for w in words:
        m = midi[(t >= w["s"]) & (t <= w["e"])]
        m = m[np.isfinite(m)]
        if len(m) >= 3:
            raw.append((w, float(np.median(m))))
    if not raw:
        return []
    med = np.median([m for _, m in raw])
    shift = 12 * round(((lo + hi) / 2 - med) / 12)                           # 억양 모양은 그대로, 옥타브만 옮김
    out = []
    for (w, m) in raw:
        p = snap(m + shift)
        while p < lo: p += 12
        while p > hi: p -= 12
        s = (place_s + w["s"]) / SPB; e = (place_s + w["e"]) / SPB
        out.append({"pitch": p, "start": round(s * 4) / 4, "end": e, "word": w["w"]})
    for i, n in enumerate(out):
        nxt = out[i + 1]["start"] if i + 1 < len(out) else n["start"] + 1
        n["length"] = max(.25, min(1.0, round((nxt - n["start"]) * 4) / 4))
    return out


def echoes(notes, sec_start_beat, track, min_gap=1.0, velocity=92):
    """말의 빈자리(≥ min_gap 박)마다 바로 앞 프레이즈의 마지막 말들을 그 자리에 다시."""
    parts = []
    phrases, cur = [], []
    for i, n in enumerate(notes):
        cur.append(n)
        gap = (notes[i + 1]["start"] - n["end"]) if i + 1 < len(notes) else 8.0
        if gap >= min_gap:
            phrases.append((cur, n["end"], gap)); cur = []
    for ph, end, gap in phrases:
        room = gap - .5
        tail = []
        for n in reversed(ph):
            if (end - n["start"]) > room or len(tail) >= 6:
                break
            tail.insert(0, n)
        if len(tail) < 2:
            continue
        t0 = tail[0]["start"]; at = round((end + .25) * 4) / 4
        parts.append({"track": track, "in": ["intro"], "offset": round(at, 2),
                      "notes": [{"pitch": n["pitch"], "start": round(n["start"] - t0, 2), "length": n["length"], "velocity": velocity} for n in tail]})
    return parts


if __name__ == "__main__":
    log = lambda m: print(m, flush=True)
    concept_mod.save(NAME, CONCEPT)
    d = ROOT / "projects" / NAME; (d / "vocals").mkdir(parents=True, exist_ok=True)
    spec = band_spec()
    s, rep = arrange.build(spec, label="band0", fmt="wav", log=lambda m: None)
    beat = rep["file"]; guide = lego.render_guide(spec)
    secs, b = {}, 0
    for n, k in FORM:
        secs[n] = b * 4; b += k
    cap = ("old school hip hop, male rapper, tired and tender, talking more than rapping, clear words, on the beat, "
           "short lines with long pauses between them, no singing, dry close mic")
    sections = [{"name": n, "start": round(secs[n] * SPB, 3), "end": round((secs[n] + len(L) * 8) * SPB, 3), "tag": tag, "lyrics": "\n".join(L), "key": KEY}
                for n, L, tag in (("verse1", VERSE1, "Verse"), ("verse2", VERSE2, "Verse"))]
    sections.append({"name": "hook1", "start": round(secs["hook1"] * SPB, 3), "end": round((secs["hook1"] + 32) * SPB, 3), "tag": "Chorus", "lyrics": "\n".join(HOOK), "key": KEY})
    out = d / "vocals" / "rap"
    _, rp = lego.vocal_track(beat, sections, BPM, KEY, cap, out, takes=10, guide_wav=guide, pass_wer=0.3, min_key_fit=0.0, lang="en", reference=str(RAP_REF), log=log)
    st = json.loads(out.with_suffix(".json").read_text(encoding="utf-8"))
    by = {x["name"]: x for x in st["sections"]}
    log("[rap] " + " · ".join(f"{r['section']} 오류율 {r['wer']}" for r in rp))
    # 억양 측정 → 대답
    v1 = speech_notes(by["verse1"]["file"], by["verse1"]["place_s"])
    v2 = speech_notes(by["verse2"]["file"], by["verse2"]["place_s"])
    h1 = speech_notes(by["hook1"]["file"], by["hook1"]["place_s"], lo=67, hi=86)
    rel = lambda notes, sec: [{**n, "start": n["start"] - secs[sec], "end": n["end"] - secs[sec]} for n in notes]
    ep = []
    for notes, sec, trk in ((v1, "verse1", "Sax"), (v2, "verse2", "Sax")):
        for p in echoes(notes, secs[sec], trk):
            ep.append({**p, "offset": p["offset"] - secs[sec], "in": [sec]})
    hk = rel(h1, "hook1")
    for sec in ("hook1", "hook2", "hook3"):
        for p in echoes(hk, 0, "Bell", velocity=100):
            ep.append({**p, "in": [sec]}); ep.append({**p, "track": "Sax", "in": [sec]})
    # 브리지: 밴드가 1절 앞 32박을 랩한다(억양 그대로)
    v1r = rel(v1, "verse1")
    br = [{"pitch": n["pitch"], "start": round(n["start"], 2), "length": n["length"], "velocity": 90} for n in v1r if n["start"] < 31.5]
    ep += [{"track": "Sax", "in": ["bridge"], "notes": br}, {"track": "Violin", "in": ["bridge"], "notes": [{**n, "pitch": n["pitch"] - 12} for n in br]}]
    ep += [{"track": "Bell", "in": ["outro"], "notes": [{"pitch": n["pitch"], "start": round(n["start"], 2), "length": n["length"], "velocity": 84} for n in hk if n["start"] < 15.5]}]
    log(f"[echo] 측정 음표 1절 {len(v1)} · 2절 {len(v2)} · 훅 {len(h1)} → 대답 파트 {len(ep)}")
    (d / "speech_melody.json").write_text(json.dumps({"verse1": v1, "verse2": v2, "hook": h1}, ensure_ascii=False, indent=1), encoding="utf-8")
    s2, rep2 = arrange.build(band_spec(ep), label="band1", fmt="wav", log=lambda m: None)
    # 보컬: 1·2절 + 훅(한 테이크를 세 번)
    import soundfile as _sf
    full = np.zeros((int(_sf.info(rep2["file"]).frames) + 48000, 2), np.float32)
    def put(f, at):
        v, sr = _sf.read(f, dtype="float32", always_2d=True)
        if v.shape[1] == 1: v = np.repeat(v, 2, 1)
        i = int(at * sr); n = min(len(v), len(full) - i); full[i:i + n] += v[:n]
    put(by["verse1"]["file"], by["verse1"]["place_s"]); put(by["verse2"]["file"], by["verse2"]["place_s"])
    for sec in ("hook1", "hook2", "hook3"):
        put(by["hook1"]["file"], by["hook1"]["place_s"] - secs["hook1"] * SPB + secs[sec] * SPB)
    vw = d / "vocals" / "vox_full.wav"; _sf.write(str(vw), full, 48000, subtype="FLOAT")
    mixed = d / "mix.wav"; mix(rep2["file"], [vw], mixed)
    m = master.master(str(mixed), lufs=-11.0, ceiling=-1.0, glue=True, out=str(d / "renders" / f"{NAME}_v1.wav"))
    mp3 = Path(m["path"]).with_suffix(".mp3")
    subprocess.run(["ffmpeg", "-nostdin", "-y", "-v", "error", "-i", m["path"], "-b:a", "320k", str(mp3)], check=True)
    log(json.dumps({"file": str(mp3), "lufs": m["lufs"], "true_peak": m["true_peak"]}, ensure_ascii=False))
