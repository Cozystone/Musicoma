"""레퍼런스 분석 — 남의 곡을 '흉내 낼 스타일'이 아니라 '측정할 대상'으로. 결과는 우리 곡의 목표치로만 쓴다(소리·가사는 안 씀).

    rep = analyze("sounds/inbox/ref.mp3", name="through-the-wire")   → scratch/refs/<name>/report.json + report.md + timeline.png

재는 것
  tempo / bars      템포, 박 위치, 마디 첫 박 위상
  sections          반복 구조(코드·음색 유사도로 구간 나누기) + 구간 이름 추정(A/B/…)
  arrangement       구간마다 스템(드럼·베이스·기타/샘플·보컬) 에너지 — 무엇이 들어오고 빠지나
  vocal_timing      보컬 음절 시작이 16분 격자에서 몇 ms 벗어나는지(평균 = 뒤로 미는 정도, 표준편차 = 흔들림,
                    ±20ms 안 비율) — "랩은 정박에 안 떨어진다"를 숫자로
  vocal_rate        초당 음절(시작점) 수 — 구간별
  vocal_pitch       보컬 음높이 중앙값·범위 — 하이피치 샘플이 얼마나 올라가 있나
"""
import json
from pathlib import Path

import numpy as np
import librosa
import soundfile as sf

from . import crate, importer

ROOT = Path(__file__).resolve().parent.parent


def _beats(y, sr, bpm_hint=None):
    tempo, beats = librosa.beat.beat_track(y=y, sr=sr, units="time", start_bpm=bpm_hint or 90, tightness=200)
    return float(np.atleast_1d(tempo)[0]), beats


def _sections(y, sr, beats, min_bars=4):
    """마디 단위 특징(크로마+MFCC) 자기유사도 → 경계 → 비슷한 구간끼리 같은 글자."""
    bars = beats[::4]
    if len(bars) < 3:
        return []
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
    feats = []
    for a, b in zip(bars[:-1], bars[1:]):
        fa, fb = librosa.time_to_frames([a, b], sr=sr)
        fb = max(fb, fa + 1)
        feats.append(np.concatenate([chroma[:, fa:fb].mean(1), mfcc[1:, fa:fb].mean(1) / 50]))
    F = np.array(feats)
    F = (F - F.mean(0)) / (F.std(0) + 1e-9)
    k = max(2, min(10, len(F) // min_bars))
    bounds = librosa.segment.agglomerative(F.T, k)
    bounds = sorted(set([0] + list(bounds) + [len(F)]))
    segs = []
    for a, b in zip(bounds[:-1], bounds[1:]):
        if b > a:
            segs.append({"bar_start": int(a) + 1, "bars": int(b - a), "start": round(float(bars[a]), 2),
                         "end": round(float(bars[min(b, len(bars) - 1)]), 2), "vec": F[a:b].mean(0)})
    labels, protos = [], []
    for s in segs:
        best = None
        for i, p in enumerate(protos):
            d = np.linalg.norm(s["vec"] - p) / np.sqrt(len(p))
            if d < 0.55 and (best is None or d < best[1]):
                best = (i, d)
        if best is None:
            protos.append(s["vec"])
            labels.append(chr(ord("A") + len(protos) - 1))
        else:
            labels.append(chr(ord("A") + best[0]))
    for s, l in zip(segs, labels):
        s["label"] = l
        del s["vec"]
    return segs


def _rms_db(path, sr, a, b):
    y, _ = librosa.load(path, sr=sr, mono=True, offset=a, duration=max(0.05, b - a))
    return round(float(20 * np.log10(np.sqrt(np.mean(y ** 2)) + 1e-9)), 1)


def _vocal_timing(vocal_path, sr, beats, sections):
    y, _ = librosa.load(vocal_path, sr=sr, mono=True)
    on = librosa.onset.onset_detect(y=y, sr=sr, units="time", backtrack=True, delta=0.08)
    rms = librosa.feature.rms(y=y)[0]
    thr = np.percentile(rms, 60)
    on = [t for t in on if rms[min(len(rms) - 1, librosa.time_to_frames(t, sr=sr))] > thr * 0.5]
    if len(beats) < 2 or not on:
        return {}
    grid = []
    for a, b in zip(beats[:-1], beats[1:]):
        grid += list(np.linspace(a, b, 4, endpoint=False))
    grid = np.array(grid)
    beat_len = float(np.median(np.diff(beats)))
    offs = []
    for t in on:
        i = np.searchsorted(grid, t)
        cands = [g for g in grid[max(0, i - 1):i + 1]]
        if not cands:
            continue
        g = min(cands, key=lambda g: abs(t - g))
        offs.append((t, (t - g) * 1000))
    offs = np.array(offs)
    out = {"onsets": int(len(offs)), "sixteenth_ms": round(beat_len / 4 * 1000, 1),
           "mean_offset_ms": round(float(offs[:, 1].mean()), 1), "std_ms": round(float(offs[:, 1].std()), 1),
           "within_20ms": round(float(np.mean(np.abs(offs[:, 1]) <= 20)), 2),
           "histogram_ms": np.histogram(offs[:, 1], bins=[-80, -40, -20, -10, 0, 10, 20, 40, 80])[0].tolist()}
    per = []
    for s in sections:
        m = (offs[:, 0] >= s["start"]) & (offs[:, 0] < s["end"])
        dur = max(0.1, s["end"] - s["start"])
        if m.sum() >= 4:
            per.append({"section": f"{s['label']}@{s['bar_start']}", "onsets_per_sec": round(float(m.sum() / dur), 2),
                        "mean_offset_ms": round(float(offs[m, 1].mean()), 1), "std_ms": round(float(offs[m, 1].std()), 1)})
    out["per_section"] = per
    return out


def _vocal_pitch(vocal_path, sections):
    y, sr = librosa.load(vocal_path, sr=16000, mono=True)
    f0, vflag, _ = librosa.pyin(y, fmin=70, fmax=1200, sr=sr, frame_length=1024)
    t = librosa.times_like(f0, sr=sr, hop_length=256)
    res = []
    for s in sections:
        m = (t >= s["start"]) & (t < s["end"]) & vflag & ~np.isnan(f0)
        if m.sum() > 20:
            v = f0[m]
            res.append({"section": f"{s['label']}@{s['bar_start']}", "median_hz": round(float(np.median(v)), 1),
                        "p10_hz": round(float(np.percentile(v, 10)), 1), "p90_hz": round(float(np.percentile(v, 90)), 1)})
    return res


def _drum_pattern(drum_path, beats, sr=22050):
    """드럼 스템 → 마디별 16칸 킥/스네어/햇 패턴(가장 흔한 것) + 스윙(8분 안 엇박 위치, 0.5 = 곧음)."""
    from collections import Counter
    y, _ = librosa.load(drum_path, sr=sr, mono=True)
    on = librosa.onset.onset_detect(y=y, sr=sr, units="samples", backtrack=False, delta=0.06)
    bars = beats[::4]
    pats, offs = {}, []
    for o in on:
        t = o / sr
        seg = y[o: o + int(0.06 * sr)]
        if len(seg) < 256:
            continue
        spec = np.abs(np.fft.rfft(seg * np.hanning(len(seg))))
        f = np.fft.rfftfreq(len(seg), 1 / sr)
        low, mid, high = spec[f < 150].sum(), spec[(f >= 150) & (f < 2500)].sum(), spec[f >= 5000].sum()
        tot = low + mid + high + 1e-9
        kind = "kick" if low / tot > 0.45 else "hat" if high / tot > 0.35 else "snare"
        bi = np.searchsorted(bars, t) - 1
        if 0 <= bi < len(bars) - 1:
            step = int(round((t - bars[bi]) / (bars[bi + 1] - bars[bi]) * 16)) % 16
            pats.setdefault(bi, {"kick": ["."] * 16, "snare": ["."] * 16, "hat": ["."] * 16})[kind][step] = "x"
        bj = np.searchsorted(beats, t) - 1
        if 0 <= bj < len(beats) - 1:
            within8 = ((t - beats[bj]) / (beats[bj + 1] - beats[bj]) * 2) % 1
            if 0.3 < within8 < 0.8:
                offs.append(within8)
    rows = {k: Counter("".join(p[k]) for p in pats.values()).most_common(3) for k in ("kick", "snare", "hat")}
    bpm = 60.0 / float(np.median(np.diff(beats)))
    return {"bpm": round(bpm, 2), "common": {k: [{"pattern": p, "bars": n} for p, n in v] for k, v in rows.items()},
            "swing_8th_ratio": round(float(np.median(offs)), 3) if offs else None, "bars_seen": len(pats)}


def _loop_period(path, beats, sr=22050, max_bars=8):
    """샘플(other 스템)이 몇 마디마다 되풀이되나 — 마디 크로마 자기상관."""
    y, _ = librosa.load(path, sr=sr, mono=True)
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
    bars = beats[::4]
    vecs = []
    for a, b in zip(bars[:-1], bars[1:]):
        fa, fb = librosa.time_to_frames([a, b], sr=sr)
        vecs.append(chroma[:, fa:max(fb, fa + 1)].mean(1))
    V = np.array(vecs)
    V = (V - V.mean(1, keepdims=True)) / (V.std(1, keepdims=True) + 1e-9)
    scores = {}
    for lag in range(1, max_bars + 1):
        if len(V) > lag + 2:
            scores[lag] = round(float(np.mean([np.dot(V[i], V[i + lag]) / V.shape[1] for i in range(len(V) - lag)])), 3)
    best = max(scores, key=scores.get) if scores else None
    return {"loop_bars": best, "similarity_by_lag": scores}


def _voices_by_pitch(vocal_path, sections, split_hz=300):
    """보컬 스템 안의 두 목소리: 높은(칩멍크 샘플) / 낮은(랩) — 구간별 비율과 음높이."""
    y, sr = librosa.load(vocal_path, sr=16000, mono=True)
    f0, vflag, _ = librosa.pyin(y, fmin=70, fmax=1200, sr=sr, frame_length=1024)
    t = librosa.times_like(f0, sr=sr, hop_length=256)
    rows = []
    for s in sections:
        m = (t >= s["start"]) & (t < s["end"]) & vflag & ~np.isnan(f0)
        n = int(m.sum())
        row = {"section": f"{s['label']}@{s['bar_start']}", "voiced_frames": n}
        if n >= 20:
            hi = f0[m] >= split_hz
            row.update({"high_share": round(float(hi.mean()), 2),
                        "high_median_hz": round(float(np.median(f0[m][hi])), 1) if hi.any() else None,
                        "low_median_hz": round(float(np.median(f0[m][~hi])), 1) if (~hi).any() else None})
        rows.append(row)
    return rows


def _transitions(stems, sections, sr=22050):
    """구간 경계마다 직전 1마디 → 직후 1마디 스템 에너지 변화 + 드럼이 비는 순간(브레이크)."""
    out = []
    for s0, s1 in zip(sections[:-1], sections[1:]):
        b = s1["start"]
        bar = (s1["end"] - s1["start"]) / max(1, s1["bars"])
        row = {"at": f"{s0['label']}→{s1['label']} ({b:.1f}s)"}
        for k, p in stems.items():
            row[k] = round(_rms_db(p, sr, b, b + bar) - _rms_db(p, sr, max(0, b - bar), b), 1)
        out.append(row)
    breaks = []
    if "drums" in stems:
        y, _ = librosa.load(stems["drums"], sr=sr, mono=True)
        rms = librosa.feature.rms(y=y, hop_length=512)[0]
        t = librosa.times_like(rms, sr=sr, hop_length=512)
        med = np.median(rms[rms > 0])
        start = None
        for i, q in enumerate(rms < med * 0.1):
            if q and start is None:
                start = t[i]
            elif not q and start is not None:
                if t[i] - start > 0.4 and start > 2:
                    breaks.append({"start": round(float(start), 2), "length": round(float(t[i] - start), 2)})
                start = None
    return {"boundaries": out, "drum_breaks": breaks}


def analyze(path, name=None, log=print):
    name = name or Path(path).stem
    out_dir = ROOT / "scratch" / "refs" / name
    out_dir.mkdir(parents=True, exist_ok=True)
    wav = importer.to_wav(path, out_dir=out_dir)
    y, sr = librosa.load(wav, sr=22050, mono=True)
    tempo, beats = _beats(y, sr)
    log(f"[1] 템포 {tempo:.1f} BPM, 박 {len(beats)}")
    sections = _sections(y, sr, beats)
    log(f"[2] 구간 {len(sections)}: " + " ".join(f"{s['label']}({s['bars']})" for s in sections))
    stems = crate.separate(wav)
    log(f"[3] 스템 {list(stems)}")
    arrangement = []
    for s in sections:
        row = {"section": f"{s['label']}@{s['bar_start']}", "bars": s["bars"]}
        for k, p in stems.items():
            row[k] = _rms_db(p, sr, s["start"], s["end"])
        arrangement.append(row)
    timing = _vocal_timing(stems["vocals"], sr, beats, sections) if "vocals" in stems else {}
    pitch = _vocal_pitch(stems["vocals"], sections) if "vocals" in stems else []
    drums = _drum_pattern(stems["drums"], beats) if "drums" in stems else {}
    loop = _loop_period(stems["other"], beats) if "other" in stems else {}
    voices = _voices_by_pitch(stems["vocals"], sections) if "vocals" in stems else []
    trans = _transitions(stems, sections)
    chords = []
    try:
        from . import transcribe
        chords = transcribe.simplify(transcribe.chords(stems["other"], tempo, beats_per_chord=4,
                                                       bass_path=stems.get("bass")))[:16]
    except Exception as ex:
        log(f"   코드 채보 건너뜀: {ex}")
    log(f"[3b] 드럼 스윙 {drums.get('swing_8th_ratio')} · 샘플 루프 {loop.get('loop_bars')}마디 · 브레이크 {len(trans['drum_breaks'])}")
    rep = {"source": str(path), "tempo": round(tempo, 2), "seconds": round(len(y) / sr, 1), "sections": sections,
           "arrangement": arrangement, "vocal_timing": timing, "vocal_pitch": pitch, "drums": drums, "loop": loop,
           "voices": voices, "transitions": trans, "chords": chords}
    (out_dir / "report.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    _timeline_png(rep, stems, sr, out_dir / "timeline.png")
    (out_dir / "report.md").write_text(to_markdown(rep), encoding="utf-8")
    log(f"[4] 보고서 {out_dir}")
    return rep


def to_markdown(r):
    L = [f"# 레퍼런스 분석 — {Path(r['source']).name}", "", f"- 템포 {r['tempo']} BPM · 길이 {r['seconds']}초", "",
         "## 구조", "| 구간 | 시작 마디 | 마디 수 | 시작(초) |", "|---|---|---|---|"]
    L += [f"| {s['label']} | {s['bar_start']} | {s['bars']} | {s['start']} |" for s in r["sections"]]
    L += ["", "## 구간별 악기 에너지(dB)", "| 구간 | 드럼 | 베이스 | 샘플/기타 | 보컬 |", "|---|---|---|---|---|"]
    L += [f"| {a['section']} | {a.get('drums')} | {a.get('bass')} | {a.get('other')} | {a.get('vocals')} |" for a in r["arrangement"]]
    t = r.get("vocal_timing") or {}
    if t:
        L += ["", "## 보컬 타이밍(16분 격자 기준)",
              f"- 16분 = {t['sixteenth_ms']}ms · 평균 어긋남 {t['mean_offset_ms']}ms(+ = 뒤로) · 흔들림 ±{t['std_ms']}ms · ±20ms 안 {int(t['within_20ms'] * 100)}%",
              f"- 분포(ms 구간 -80…80): {t['histogram_ms']}"]
        L += [f"- {p['section']}: 초당 {p['onsets_per_sec']}음절 · 평균 {p['mean_offset_ms']}ms · ±{p['std_ms']}ms" for p in t.get("per_section", [])]
    d = r.get("drums") or {}
    if d:
        L += ["", "## 비트", f"- 드럼 템포 {d['bpm']} · 스윙(8분 안 엇박 위치, 0.5 = 곧음) {d['swing_8th_ratio']}"]
        for k, v in d["common"].items():
            L += [f"- {k}: " + " / ".join(f"`{x['pattern']}`×{x['bars']}" for x in v)]
    if r.get("loop"):
        L += [f"- 샘플 루프: {r['loop']['loop_bars']}마디마다 반복(마디 간 유사도 {r['loop']['similarity_by_lag']})"]
    if r.get("chords"):
        L += ["- 코드(4박 단위 채보): " + " ".join(c[0] for c in r["chords"])]
    if r.get("voices"):
        L += ["", "## 보컬 — 높은 목소리(샘플) / 낮은 목소리(랩)"]
        L += [f"- {v['section']}: 높은 비율 {v.get('high_share')} · 높은 {v.get('high_median_hz')}Hz · 낮은 {v.get('low_median_hz')}Hz"
              for v in r["voices"]]
    tr = r.get("transitions") or {}
    if tr:
        L += ["", "## 전환(경계 직전 1마디 → 직후 1마디, dB 변화)"]
        L += [f"- {b['at']}: " + " · ".join(f"{k} {v:+}" for k, v in b.items() if k != "at") for b in tr["boundaries"]]
        if tr["drum_breaks"]:
            L += ["- 드럼이 비는 순간: " + ", ".join(f"{x['start']}s({x['length']}s)" for x in tr["drum_breaks"][:12])]
    if r.get("vocal_pitch"):
        L += ["", "## 보컬 음높이"] + [f"- {p['section']}: 중앙 {p['median_hz']}Hz ({p['p10_hz']}~{p['p90_hz']})" for p in r["vocal_pitch"]]
    return "\n".join(L) + "\n"


def _timeline_png(rep, stems, sr, out):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(len(stems) + 1, 1, figsize=(14, 1.4 * (len(stems) + 1)), sharex=True)
    for ax, (k, p) in zip(axes[:-1], stems.items()):
        y, _ = librosa.load(p, sr=sr, mono=True)
        rms = librosa.feature.rms(y=y)[0]
        ax.plot(librosa.times_like(rms, sr=sr), 20 * np.log10(rms + 1e-6), lw=0.6)
        ax.set_ylabel(k, rotation=0, ha="right")
        ax.set_ylim(-60, 0)
    ax = axes[-1]
    for s in rep["sections"]:
        ax.axvspan(s["start"], s["end"], alpha=0.25, color=f"C{ord(s['label']) - 65}")
        ax.text(s["start"], 0.5, s["label"], fontsize=9)
    ax.set_yticks([])
    ax.set_xlabel("sec")
    fig.tight_layout()
    fig.savefig(out, dpi=90)
    plt.close(fig)


if __name__ == "__main__":
    import sys
    print(to_markdown(analyze(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)))
