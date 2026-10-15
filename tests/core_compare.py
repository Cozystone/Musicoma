"""Musicoma Core 널 테스트 비교 도구 — 지금 엔진 렌더(정답지) vs musicoma-core 렌더.

    python tests/core_compare.py engine.wav core.wav [--segments 3.0]

지표:
  lufs_engine / lufs_core / lufs_diff   통합 음량 (core - engine, LU)
  bands_diff_db                         옥타브 대역별 에너지 차 (core - engine)
  lag_ms, gain_db                       시간·이득 맞춤 결과 (core 를 얼마나 옮기고 키웠나)
  residual_db                           맞춘 뒤 차이 신호 / 엔진 신호 (dB). -40 이하면 '거의 같음'
  residual_db_raw                       맞추기 전 그대로 뺀 차이
  segments                              구간별 RMS 차(core - engine, dB) — 보정용
"""
import json
import sys

import numpy as np
import pyloudnorm as pyln
import soundfile as sf
from scipy import signal

BANDS = [31.5, 63, 125, 250, 500, 1000, 2000, 4000, 8000, 16000]


def load(path):
    x, sr = sf.read(str(path), always_2d=True, dtype="float64")
    if x.shape[1] == 1:
        x = np.repeat(x, 2, axis=1)
    return x[:, :2], sr


def _db(p):
    return float(10 * np.log10(max(p, 1e-20)))


def band_energy(x, sr):
    mono = x.mean(axis=1)
    f, p = signal.welch(mono, sr, nperseg=8192)
    out = {}
    for c in BANDS:
        lo, hi = c / np.sqrt(2), c * np.sqrt(2)
        m = (f >= lo) & (f < hi)
        out[str(c)] = _db(p[m].sum()) if m.any() else -200.0
    return out


def best_lag(a, b, sr, max_ms=50):
    """b 를 몇 샘플 옮겨야 a 와 맞나 (a[n] ≈ b[n - lag])."""
    n = min(len(a), len(b))
    a, b = a[:n], b[:n]
    m = int(sr * max_ms / 1000)
    c = signal.fftconvolve(a, b[::-1], mode="full")
    mid = n - 1
    seg = c[mid - m: mid + m + 1]
    return int(np.argmax(seg)) - m


def compare(engine_wav, core_wav, segment_sec=None):
    a, sr = load(engine_wav)
    b, sr2 = load(core_wav)
    if sr != sr2:
        raise ValueError(f"sample rate differs {sr} vs {sr2}")
    n = min(len(a), len(b))
    a, b = a[:n], b[:n]
    meter = pyln.Meter(sr)
    la, lb = meter.integrated_loudness(a), meter.integrated_loudness(b)
    ba, bb = band_energy(a, sr), band_energy(b, sr)

    lag = best_lag(a.mean(axis=1), b.mean(axis=1), sr)
    bs = np.roll(b, lag, axis=0)
    if lag > 0:
        bs[:lag] = 0
    elif lag < 0:
        bs[lag:] = 0
    g = float((a * bs).sum() / max((bs * bs).sum(), 1e-20))
    res = a - g * bs
    ea = (a * a).sum()
    out = {
        "seconds": round(n / sr, 3),
        "lufs_engine": round(la, 2), "lufs_core": round(lb, 2), "lufs_diff": round(lb - la, 2),
        "peak_engine_db": round(_db(np.abs(a).max() ** 2), 2), "peak_core_db": round(_db(np.abs(b).max() ** 2), 2),
        "bands_diff_db": {k: round(bb[k] - ba[k], 2) for k in ba},
        "lag_ms": round(lag / sr * 1000, 3), "gain_db": round(20 * np.log10(max(abs(g), 1e-9)), 2),
        "residual_db": round(_db((res * res).sum() / ea), 2),
        "residual_db_raw": round(_db(((a - b) ** 2).sum() / ea), 2),
        "lr_balance_engine_db": round(_db((a[:, 0] ** 2).sum() / max((a[:, 1] ** 2).sum(), 1e-20)), 2),
        "lr_balance_core_db": round(_db((b[:, 0] ** 2).sum() / max((b[:, 1] ** 2).sum(), 1e-20)), 2),
    }
    if segment_sec:
        segs = []
        L = int(segment_sec * sr)
        for i in range(0, n, L):
            sa, sb = a[i:i + L], b[i:i + L]
            pa, pb = (sa * sa).mean(), (sb * sb).mean()
            if pa < 1e-10 and pb < 1e-10:
                continue
            pal, par = (sa[:, 0] ** 2).mean(), (sa[:, 1] ** 2).mean()
            segs.append({"t": round(i / sr, 2), "engine_db": round(_db(pa), 2), "diff_db": round(_db(pb) - _db(pa), 2),
                         "engine_lr_db": round(_db(pal) - _db(par), 2),
                         "core_lr_db": round(_db((sb[:, 0] ** 2).mean()) - _db((sb[:, 1] ** 2).mean()), 2)})
        out["segments"] = segs
    return out


def decay_profile(path, t0, t1, hop=0.05):
    """t0~t1 구간 RMS(dB) 를 hop 간격으로 — 릴리스 곡선 비교용."""
    x, sr = load(path)
    m = x.mean(axis=1)
    out = []
    for t in np.arange(t0, t1, hop):
        s = m[int(t * sr): int((t + hop) * sr)]
        out.append(round(_db((s * s).mean()), 1) if len(s) else None)
    return out


if __name__ == "__main__":
    args = sys.argv[1:]
    seg = None
    if "--segments" in args:
        i = args.index("--segments")
        seg = float(args[i + 1])
        del args[i:i + 2]
    print(json.dumps(compare(args[0], args[1], seg), ensure_ascii=False, indent=1))
