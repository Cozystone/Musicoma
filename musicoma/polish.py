"""딸깍 다듬기 — 튜닝(음정 보정) · 타이트닝(박자 보정) · 마스터. 10-17 외부 피드백: "튜닝·마스터링·믹싱을 딸깍으로", "박자감 이슈".

tune    : 사람 목소리(또는 단선율 악기) 녹음의 음 하나하나를 조성의 가장 가까운 음으로 — strength 0.85 가 '사람답게', 1.0 이 '기계처럼'.
tighten : 소리 덩어리(음절·타격)의 시작을 격자(16분)로 lock 만큼 당긴다. 늘이지 않는다.
master  : 기존 master.master 를 파일 하나에 — 목표 LUFS·천장·접착 컴프·톤.
모두 원본은 그대로 두고 *_tuned / *_tight / *_master 파일을 만든다.
"""
from pathlib import Path

import numpy as np
import soundfile as sf
import librosa

from . import theory


def _scale_pcs(key):
    name, _, mode = (key or "C major").partition(" ")
    root = theory.pc(name.replace("♯", "#").replace("♭", "b"))
    steps = [0, 2, 3, 5, 7, 8, 10] if mode.strip().lower().startswith("min") else [0, 2, 4, 5, 7, 9, 11]
    return {(root + s) % 12 for s in steps}


def _nearest_in_scale(midi, pcs):
    best = None
    for cand in range(int(midi) - 2, int(midi) + 3):
        if cand % 12 in pcs and (best is None or abs(cand - midi) < abs(best - midi)):
            best = cand
    return best if best is not None else int(round(midi))


def _notes_from_f0(f0, voiced, times, min_len=0.08, jump=0.8):
    """프레임 음높이 → 음 구간 [(시작 프레임, 끝 프레임, 중앙 midi)]. 음이 0.8반음 넘게 뛰거나 무성이면 끊는다."""
    midi = librosa.hz_to_midi(np.where(voiced & np.isfinite(f0), f0, np.nan))
    notes, start = [], None
    for i in range(len(midi)):
        ok = voiced[i] and np.isfinite(midi[i])
        if ok and start is None:
            start = i
        elif start is not None and (not ok or abs(midi[i] - np.nanmedian(midi[start:i])) > jump):
            if times[i] - times[start] >= min_len:
                notes.append((start, i, float(np.nanmedian(midi[start:i]))))
            start = i if ok else None
    if start is not None and times[-1] - times[start] >= min_len:
        notes.append((start, len(midi), float(np.nanmedian(midi[start:]))))
    return notes


def tune(path, key="C major", out=None, strength=0.85, max_semitones=2.0, log=print, region=None):
    """음정 보정. region=(시작초, 끝초) 이면 그 구간의 음만 손댄다(나머지는 그대로 — 10-17 칸예 시티팝 훅 고음만).
    반환: {"out", "notes", "corrected", "mean_cents_before", "mean_cents_after"}"""
    from . import dsp
    y, sr = sf.read(str(path), dtype="float32", always_2d=True)
    mono = y.mean(1)
    hop = 256
    f0, voiced, _ = librosa.pyin(mono, fmin=60, fmax=1200, sr=sr, frame_length=2048, hop_length=hop)
    times = librosa.frames_to_time(np.arange(len(f0)), sr=sr, hop_length=hop)
    pcs = _scale_pcs(key)
    notes = _notes_from_f0(f0, voiced, times)
    res = y.copy()
    fade = int(0.015 * sr)
    before, after, done = [], [], 0
    for a, b, m in notes:
        if region and not (region[0] <= times[a] <= region[1]):
            continue
        target = _nearest_in_scale(m, pcs)
        shift = (target - m) * strength
        before.append(abs(target - m) * 100)
        after.append(abs(target - m - shift) * 100)
        if abs(shift) < 0.03 or abs(shift) > max_semitones:
            continue
        i0, i1 = max(0, int(times[a] * sr) - fade), min(len(mono), int(times[min(b, len(times) - 1)] * sr) + fade)
        seg = y[i0:i1]
        if len(seg) < 4 * fade:
            continue
        shifted = dsp.time_stretch(seg, sr, rate=1.0, semitones=float(shift))
        shifted = np.asarray(shifted, dtype=np.float32)
        if shifted.ndim == 1:
            shifted = shifted[:, None]
        n = min(len(shifted), i1 - i0)
        w = np.ones(n, np.float32)
        w[:fade] = np.linspace(0, 1, fade); w[-fade:] = np.linspace(1, 0, fade)
        res[i0:i0 + n] = res[i0:i0 + n] * (1 - w[:, None]) + shifted[:n] * w[:, None]
        done += 1
    out = Path(out) if out else Path(path).with_name(Path(path).stem + "_tuned.wav")
    sf.write(str(out), res, sr)
    r = {"out": str(out), "key": key, "notes": len(notes), "corrected": done,
         "mean_cents_before": round(float(np.mean(before)), 1) if before else 0.0,
         "mean_cents_after": round(float(np.mean(after)), 1) if after else 0.0}
    log(f"[tune] {out.name}: 음 {len(notes)}개 중 {done}개 보정 · 평균 어긋남 {r['mean_cents_before']}→{r['mean_cents_after']}센트")
    return r


def tighten(path, bpm, out=None, grid=0.25, lock=0.7, offset_s=0.0, log=print):
    """박자 보정: 소리 덩어리 시작을 격자(grid 박)로 lock 만큼. offset_s = 녹음의 0초가 곡의 어느 박인지(초) — 보통 0."""
    from .vocal_align import _chunks
    y, sr = sf.read(str(path), dtype="float32", always_2d=True)
    mono = y.mean(1)
    chunks = _chunks(mono, sr, gap=0.12, min_len=0.06, floor_db=-40)
    step = grid * 60.0 / bpm
    res = np.zeros((len(mono) + sr, y.shape[1]), np.float32)
    fade = int(0.008 * sr)
    moves, last_end = [], -1.0
    for a, b in chunks:
        g = round((a - offset_s) / step) * step + offset_s
        d = (g - a) * lock
        start = max(a + d, last_end + 0.005) if last_end >= 0 else max(0.0, a + d)
        seg = y[int(max(0, a - 0.01) * sr):int(min(len(mono) / sr, b + 0.02) * sr)].copy()
        if len(seg) > 2 * fade:
            seg[:fade] *= np.linspace(0, 1, fade)[:, None]; seg[-fade:] *= np.linspace(1, 0, fade)[:, None]
        j0 = int(max(0.0, start - 0.01) * sr)
        res[j0:j0 + len(seg)] += seg[:max(0, len(res) - j0)]
        last_end = start + (b - a)
        moves.append(round((start - a) * 1000))
    out = Path(out) if out else Path(path).with_name(Path(path).stem + "_tight.wav")
    sf.write(str(out), res[:len(mono)], sr)
    r = {"out": str(out), "bpm": bpm, "grid": grid, "lock": lock, "chunks": len(chunks),
         "moved_ms_mean": round(float(np.mean(np.abs(moves))), 1) if moves else 0.0}
    log(f"[tighten] {out.name}: 덩어리 {len(chunks)}개, 평균 {r['moved_ms_mean']} ms 이동")
    return r


def master_file(path, out=None, lufs=-12.0, ceiling=-1.0, tone=None, log=print):
    from . import master as m
    out = Path(out) if out else Path(path).with_name(Path(path).stem + "_master.wav")
    r = m.master(str(path), lufs=lufs, ceiling=ceiling, glue=True, out=str(out), tone=tone)
    log(f"[master] {out.name}: {lufs} LUFS 목표")
    return {"out": str(out), "result": r}
