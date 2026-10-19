"""musicoma-021 「Say It Again」 v2 — 애프터워드 규칙을 지키게 편집.

v1 측정: lego 가 줄 사이를 쉬지 않고 이어 불러 빈자리가 1절 2곳·2절 0곳 → 대답이 거의 안 들어감. 랩 억양 폭도 2~7반음뿐(2절은 G4~A4 셋).
v2:
  - 한 테이크(끊지 않고 녹음한 것)를 줄 경계에서만 나눠 2마디마다 한 줄씩 다시 놓는다 — 줄 = 부름(1마디 남짓) + 대답(나머지).
  - 대답 = 그 줄의 억양을 3배 과장(줄 중앙음 기준 편차 ×3) → 조성에 붙임 → 악기. 리듬은 말 그대로.
  - 훅은 다시 녹음(v1 오류율 35%).
    python works/musicoma_021b_say_it_again_edit.py
"""
import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from musicoma import arrange, lego, master, voice_design as vd
from musicoma_020_escape_velocity import mix
import musicoma_021_say_it_again as W

d = W.ROOT / "projects" / W.NAME
STATE = d / "vocals" / "rap.json"
EXAG = 3.0
norm = lambda w: re.sub(r"[^a-z0-9']", "", w.lower())


def line_cuts(words, lines):
    """ASR 단어 → 가사 줄 경계. 기대 누적 단어 수 근처(±3)에서 가장 긴 틈을 고른다."""
    counts = np.cumsum([len(l.split()) for l in lines])[:-1]
    cuts, last = [], 0
    for c in counts:
        lo, hi = max(last + 1, c - 3), min(len(words) - 1, c + 3)
        best = max(range(lo, hi + 1), key=lambda i: words[i]["s"] - words[i - 1]["e"]) if hi >= lo else c
        cuts.append(best); last = best
    bounds = [0] + cuts + [len(words)]
    return [words[bounds[k]:bounds[k + 1]] for k in range(len(lines))]


def pitch_of(vox, words):
    import librosa
    y, sr = librosa.load(str(vox), sr=16000, mono=True)
    f0, v, _ = librosa.pyin(y, fmin=70, fmax=600, sr=sr, frame_length=1024)
    t = librosa.times_like(f0, sr=sr, hop_length=256)
    midi = librosa.hz_to_midi(np.where(v, f0, np.nan))
    out = []
    for w in words:
        m = midi[(t >= w["s"]) & (t <= w["e"])]; m = m[np.isfinite(m)]
        out.append(float(np.median(m)) if len(m) >= 3 else np.nan)
    return out


def phrase_lines(mono, sr, n_lines):
    """소리 덩어리 → n_lines 개 줄: 덩어리 사이 틈 중 가장 긴 n-1 곳에서 자른다."""
    from musicoma.vocal_align import _chunks
    ch = _chunks(mono, sr, gap=0.12, min_len=0.08, floor_db=-38)
    if not ch:
        return []
    gaps = sorted(range(1, len(ch)), key=lambda i: ch[i][0] - ch[i - 1][1], reverse=True)[:n_lines - 1]
    cuts = sorted(gaps); bounds = [0] + cuts + [len(ch)]
    return [(ch[bounds[k]][0], ch[bounds[k + 1] - 1][1]) for k in range(len(bounds) - 1)]


def syllable_answer(mono, sr, lo, hi, velocity=92):
    """한 줄의 소리 → 음절(어택)마다 음표. 음높이 = 다음 어택까지의 유성 중앙값, 억양 ×EXAG, 조성에 붙임."""
    import librosa
    y = librosa.resample(mono, orig_sr=sr, target_sr=16000)
    on = librosa.onset.onset_detect(y=y, sr=16000, units="time", backtrack=True, delta=0.07)
    f0, v, _ = librosa.pyin(y, fmin=70, fmax=600, sr=16000, frame_length=1024)
    t = librosa.times_like(f0, sr=16000, hop_length=256)
    midi = librosa.hz_to_midi(np.where(v, f0, np.nan))
    raw = []
    edges = list(on) + [len(y) / 16000]
    for i in range(len(on)):
        m = midi[(t >= edges[i]) & (t < edges[i + 1])]; m = m[np.isfinite(m)]
        if len(m) >= 2:
            raw.append((edges[i], float(np.median(m))))
    if len(raw) < 2:
        return []
    med = float(np.median([p for _, p in raw])); center = (lo + hi) / 2
    notes = [{"pitch": max(lo, min(hi, W.snap(center + (p - med) * EXAG))), "start": round(s / W.SPB * 4) / 4, "velocity": velocity} for s, p in raw]
    dedup = []
    for n in notes:                                                         # 같은 16분 칸에 둘이면 하나
        if dedup and dedup[-1]["start"] == n["start"]:
            continue
        dedup.append(n)
    for i, n in enumerate(dedup):
        nxt = dedup[i + 1]["start"] if i + 1 < len(dedup) else n["start"] + 1
        n["length"] = max(.25, min(1.0, nxt - n["start"]))
    return dedup


def answer(line_words, pitches, t_line0, lo, hi, velocity=92):
    """한 줄의 말 → 대답 음표(줄 시작 기준 박). 억양 ×EXAG, 조성 붙임, 옥타브만 악기 음역으로."""
    ok = [p for p in pitches if np.isfinite(p)]
    if len(ok) < 2:
        return []
    med = float(np.median(ok)); center = (lo + hi) / 2
    notes = []
    for w, p in zip(line_words, pitches):
        if not np.isfinite(p):
            continue
        q = W.snap(center + (p - med) * EXAG)
        q = max(lo, min(hi, q))
        notes.append({"pitch": q, "start": round((w["s"] - t_line0) / W.SPB * 4) / 4, "velocity": velocity})
    for i, n in enumerate(notes):
        nxt = notes[i + 1]["start"] if i + 1 < len(notes) else n["start"] + 1
        n["length"] = max(.25, min(1.0, nxt - n["start"]))
    return notes


if __name__ == "__main__":
    log = lambda m: print(m, flush=True)
    st = json.loads(STATE.read_text(encoding="utf-8"))
    hook = next(x for x in st["sections"] if x["name"] == "hook1")
    if hook["wer"] > 0.2 and False:
        lego.retake(str(STATE), "hook1", takes=8, enough=2, log=log)
        st = json.loads(STATE.read_text(encoding="utf-8"))
    by = {x["name"]: x for x in st["sections"]}
    secs, b = {}, 0
    for n, k in W.FORM:
        secs[n] = b * 4; b += k
    total_beats = b * 4
    sr = 48000
    vox = np.zeros((int(total_beats * W.SPB * sr) + sr * 4, 2), np.float32)
    ep, report = [], {}
    plan = (("verse1", W.VERSE1, "Sax", 57, 76, ["verse1"]), ("verse2", W.VERSE2, "Sax", 57, 76, ["verse2"]),
            ("hook1", W.HOOK, "Bell", 69, 88, ["hook1", "hook2", "hook3"]))
    lines_cache = {}
    for name, lines, trk, lo, hi, targets in plan:
        sec = by[name]
        y, s2 = sf.read(sec["file"], dtype="float32", always_2d=True)
        assert s2 == sr, s2
        if y.shape[1] == 1: y = np.repeat(y, 2, 1)
        groups = phrase_lines(y.mean(1), sr, len(lines))                  # 받아쓰기 대신 소리 덩어리로 줄 경계(챈트는 받아쓰기가 놓친다)
        report[name] = [f"{g[0]:.1f}-{g[1]:.1f}" for g in groups]
        lines_cache[name] = []
        for k, (a, e) in enumerate(groups):
            a = max(0.0, a - 0.06); e = min(len(y) / sr, e + 0.15)
            seg = y[int(a * sr):int(e * sr)].copy()
            if len(seg) < int(0.2 * sr):
                continue
            f = int(0.012 * sr); seg[:f] *= np.linspace(0, 1, f)[:, None]; seg[-f:] *= np.linspace(1, 0, f)[:, None]
            ans = syllable_answer(seg.mean(1), sr, lo, hi)
            lines_cache[name].append((k, seg, ans, (e - a) / W.SPB))
        for tgt in targets:
            for k, seg, ans, dur_b in lines_cache[name]:
                slot = secs[tgt] + k * 8                                    # 2마디마다 한 줄
                i = int((slot * W.SPB - 0.06) * sr); n = min(len(seg), len(vox) - i); vox[i:i + n] += seg[:n]
                start = round((dur_b + .5) * 2) / 2                         # 말 끝 다음 반박에서 대답
                room = 8 - start - .25
                sc = min(1.0, room / max(.5, ans[-1]["start"] + ans[-1]["length"])) if ans else 1
                notes = [{**x, "start": round(x["start"] * sc * 4) / 4, "length": max(.25, round(x["length"] * sc * 4) / 4)} for x in ans]
                ep.append({"track": trk, "in": [tgt], "offset": k * 8 + start, "notes": notes})
                if trk == "Bell":
                    ep.append({"track": "Sax", "in": [tgt], "offset": k * 8 + start, "notes": [{**x, "pitch": x["pitch"] - 12, "velocity": 80} for x in notes]})
    # 브리지: 밴드 혼자 1절 앞 네 줄을 '랩'(억양 그대로, 쉼 없이) — 색소폰 + 한 옥타브 아래 바이올린
    t = 0.0; br = []
    for k, seg, ans, dur_b in lines_cache["verse1"][:4]:
        br += [{**x, "start": round(t + x["start"], 2)} for x in ans]; t += max(6.0, dur_b + 2)
    br = [x for x in br if x["start"] < 31.5]
    ep += [{"track": "Sax", "in": ["bridge"], "notes": br}, {"track": "Violin", "in": ["bridge"], "notes": [{**x, "pitch": x["pitch"] - 12} for x in br]}]
    first_hook = lines_cache["hook1"][0][2] if lines_cache["hook1"] else []
    ep.append({"track": "Bell", "in": ["outro"], "offset": 2, "notes": first_hook})
    log("[lines] " + json.dumps(report, ensure_ascii=False)[:900])
    log(f"[echo] 대답 파트 {len(ep)}")
    vw = d / "vocals" / "vox_v2.wav"; sf.write(str(vw), vox, sr, subtype="FLOAT")
    s2, rep2 = arrange.build(W.band_spec(ep), label="band2", fmt="wav", log=lambda m: None)
    mixed = d / "mix_v2.wav"; mix(rep2["file"], [vw], mixed)
    m = master.master(str(mixed), lufs=-11.0, ceiling=-1.0, glue=True, out=str(d / "renders" / f"{W.NAME}_v2.wav"))
    mp3 = Path(m["path"]).with_suffix(".mp3")
    subprocess.run(["ffmpeg", "-nostdin", "-y", "-v", "error", "-i", m["path"], "-b:a", "320k", str(mp3)], check=True)
    log(json.dumps({"file": str(mp3), "lufs": m["lufs"], "true_peak": m["true_peak"]}, ensure_ascii=False))
