"""새 엔진 내장 이펙트(core/build-fx/out/<case>.wav, test-fx 가 씀) ↔ 예전 엔진 골든(scratch/golden/fx/<case>.wav) 비교.

    .venv/Scripts/python tests/golden/compare_fx.py   → 표 출력 + core/build-fx/out/report.json

골든에는 마스터 볼륨(-3 dB)과 WAV 클립(±1)이 들어 있다. 그래서 '우리 출력 × (dry/input 게인)' 을 ±1 로 자른 것을
골든과 비교한다(model = clip(ours·g)). 지표:
  eq_* / lowpass_*  스윕 구간 크기 응답 차(30 Hz–16 kHz, 1/12 옥타브) 최대값, 음악 구간 널
  comp_*            노이즈 버스트 4개(-36/-24/-12/-6 dBFS)의 정상 구간 게인 차, 5 ms 게인 곡선 차, 널
  reverb_*          (L+R) → L/R 임펄스 응답을 역합성곱으로 구해 옥타브별 RT60, 초기 에너지(0–80 ms), 좌우 상관, 꼬리 기울기, 널
  delay_*           임펄스에서 반복 간격·반복당 감쇠(dB)·드라이/웻 게인, 널
  chorus / phaser   변조 추정(코러스: 지연 범위·주기, 페이저: 노치 계수 범위·주기), 음악 구간 널
  pitch_*           스윕에서 측정한 피치 비(센트 오차)·지연·톤 순도(SNR), 골든과 우리 각각
첫 0.95 초(임펄스 구간)는 리버브·피치 골든이 예전 엔진 시작 잡음(웻 경로가 임펄스를 놓침)이라 해당 케이스에서는 제외한다.
"""
import json
import sys
from pathlib import Path

import numpy as np
import scipy.signal as ss
import soundfile as sf

ROOT = Path(__file__).resolve().parents[2]
GDIR = ROOT / "scratch" / "golden" / "fx"
ODIR = ROOT / "core" / "build-fx" / "out"
SR = 48000


def rd(p):
    x, sr = sf.read(str(p), dtype="float64", always_2d=True)
    assert sr == SR, (p, sr)
    return x


def db(x):
    return 10 * np.log10(np.maximum(x, 1e-30))


X = rd(GDIR / "input.wav")
DRY = rd(GDIR / "dry.wav")
_seg = slice(6 * SR, 10 * SR)
G = float(np.sum(DRY[_seg] * X[_seg]) / np.sum(X[_seg] ** 2))   # 마스터 게인(≈ -3 dB)
META = json.loads((ODIR / "meta.json").read_text(encoding="utf-8")) if (ODIR / "meta.json").exists() else {}


def to_golden_domain(y):
    return np.clip(y * G, -1.0, 1.0)


def null_db(a, b, s):
    e = a[s] - b[s]
    return float(db(np.sum(e ** 2) / max(np.sum(b[s] ** 2), 1e-30)))


def sec(a, b):
    return slice(int(a * SR), int(b * SR))


# ── 선형 시스템: 스윕 구간 크기 응답 ──
def sweep_response(y, x):
    """1.0–5.4 s 구간을 FFT 로 나눠 전달함수 크기(dB)를 1/12 옥타브로 평균"""
    s = sec(0.95, 5.6)
    n = 1 << int(np.ceil(np.log2(s.stop - s.start)))
    H = np.fft.rfft(y[s], n) / (np.fft.rfft(x[s], n) + 1e-12)
    f = np.fft.rfftfreq(n, 1 / SR)
    centers = 30 * 2 ** (np.arange(0, np.log2(16000 / 30) * 12 + 1) / 12)
    out = []
    for fc in centers:
        m = (f >= fc * 2 ** (-1 / 24)) & (f < fc * 2 ** (1 / 24))
        out.append(10 * np.log10(np.mean(np.abs(H[m]) ** 2)))
    return centers, np.array(out)


def best_lag(a, b, s, maxlag=4000):
    """b 를 기준으로 a 가 몇 샘플 늦은지(교차상관)"""
    x = a[s.start - maxlag: s.stop + maxlag]
    y = b[s]
    c = ss.correlate(x, y, mode="valid", method="fft")
    return int(np.argmax(c)) - maxlag


def linear_case(name, gold, ours):
    res = {}
    worst = 0
    for ch in range(2):
        f, hg = sweep_response(gold[:, ch], X[:, ch] * G)
        f, ho = sweep_response(ours[:, ch], X[:, ch] * G)
        worst = max(worst, float(np.max(np.abs(hg - ho))))
    res["mag_max_diff_db"] = worst
    res["null_music_db"] = max(null_db(ours[:, c], gold[:, c], sec(6, 10)) for c in range(2))
    res["null_all_db"] = max(null_db(ours[:, c], gold[:, c], sec(0, 16)) for c in range(2))
    res["pass"] = bool(worst <= 0.5 and res["null_music_db"] <= -30)
    return res


# ── 컴프레서 ──
def gain_curve(y, x, a, n, hop=240):
    g = []
    for i in range(a, a + n - hop, hop):
        g.append(10 * np.log10((np.sum(y[i:i + hop] ** 2) + 1e-20) / (np.sum((x[i:i + hop] * G) ** 2) + 1e-20)))
    return np.array(g)


def comp_case(name, gold, ours):
    res = {"static_db": {}, "curve_max_diff_db": {}}
    worst_static = 0
    worst_curve = 0
    for i, lvl in enumerate((-36, -24, -12, -6)):
        a = int((10.5 + i * 0.8) * SR)
        st = slice(a + int(0.2 * SR), a + int(0.6 * SR))
        gg = 10 * np.log10(np.sum(gold[st] ** 2) / np.sum((np.clip(X[st] * G, -1, 1)) ** 2))
        go = 10 * np.log10(np.sum(ours[st] ** 2) / np.sum((np.clip(X[st] * G, -1, 1)) ** 2))
        res["static_db"][str(lvl)] = {"golden": round(float(gg), 3), "ours": round(float(go), 3)}
        worst_static = max(worst_static, abs(gg - go))
        cg = gain_curve(gold[:, 0] + gold[:, 1], X[:, 0] + X[:, 1], a, int(0.6 * SR))
        co = gain_curve(ours[:, 0] + ours[:, 1], X[:, 0] + X[:, 1], a, int(0.6 * SR))
        d = float(np.max(np.abs(cg - co)))
        res["curve_max_diff_db"][str(lvl)] = round(d, 3)
        worst_curve = max(worst_curve, d)
    res["static_max_diff_db"] = float(worst_static)
    res["curve_worst_db"] = float(worst_curve)
    res["null_all_db"] = max(null_db(ours[:, c], gold[:, c], sec(0, 16)) for c in range(2))
    res["null_music_db"] = max(null_db(ours[:, c], gold[:, c], sec(6, 10)) for c in range(2))
    res["pass"] = bool(worst_static <= 0.5 and res["null_all_db"] <= -25)
    return res


# ── 리버브 ──
def wet_irs(y, dry_gain, N=6 * SR):
    """(L+R) 입력 → 각 출력 채널의 웻 임펄스 응답(드라이 성분 빼고). 1.0 s 이후 신호로 역합성곱."""
    s = sec(0.95, 16)
    M = X[s, 0] + X[s, 1]
    L = len(M) + N
    Mf = np.fft.rfft(M, L)
    out = []
    for ch in range(2):
        w = y[s, ch] / G - dry_gain * X[s, ch]
        H = np.fft.rfft(w, L) * np.conj(Mf) / (np.abs(Mf) ** 2 + 1e-4 * np.mean(np.abs(Mf) ** 2))
        out.append(np.fft.irfft(H, L)[:N])
    return np.array(out)


def rt60_bands(h):
    out = {}
    for fc in (125, 250, 500, 1000, 2000, 4000, 8000):
        sos = ss.butter(3, [fc / np.sqrt(2), min(fc * np.sqrt(2), SR / 2 * 0.95)], btype="band", fs=SR, output="sos")
        b = ss.sosfilt(sos, h)
        edc = np.cumsum(b[::-1] ** 2)[::-1]
        edc = db(edc / edc[0])
        i5 = np.argmax(edc <= -5)
        i25 = np.argmax(edc <= -25)
        if i25 <= i5:
            out[fc] = float("nan")
            continue
        t = np.arange(i5, i25) / SR
        k = np.polyfit(t, edc[i5:i25], 1)[0]
        out[fc] = float(-60 / k)
    return out


def tail_tilt(h):
    t = h[int(0.1 * SR):int(0.5 * SR)]
    f, P = ss.welch(t, SR, nperseg=4096)
    ref = np.mean(P[(f > 700) & (f < 1400)])
    return {fc: float(10 * np.log10(np.mean(P[(f > fc / np.sqrt(2)) & (f < fc * np.sqrt(2))]) / ref)) for fc in (125, 250, 500, 2000, 4000, 8000)}


def reverb_case(name, gold, ours, params):
    dry_gain = params.get("dry level", 0.5) * 2
    hg = wet_irs(gold, dry_gain)
    ho = wet_irs(ours, dry_gain)
    res = {"rt60_golden": {}, "rt60_ours": {}, "rt60_max_rel_err": 0.0}
    worst = 0
    for ch in range(2):
        rg, ro = rt60_bands(hg[ch]), rt60_bands(ho[ch])
        if ch == 0:
            res["rt60_golden"] = {k: round(v, 3) for k, v in rg.items()}
            res["rt60_ours"] = {k: round(v, 3) for k, v in ro.items()}
        for k in rg:
            if np.isfinite(rg[k]) and np.isfinite(ro[k]):
                worst = max(worst, abs(ro[k] - rg[k]) / rg[k])
    res["rt60_max_rel_err"] = float(worst)
    e80g = float(db(np.sum(hg[:, :int(0.08 * SR)] ** 2)))
    e80o = float(db(np.sum(ho[:, :int(0.08 * SR)] ** 2)))
    res["early_energy_db"] = {"golden": round(e80g, 2), "ours": round(e80o, 2)}
    cg = float(np.corrcoef(hg[0], hg[1])[0, 1])
    co = float(np.corrcoef(ho[0], ho[1])[0, 1])
    res["lr_corr"] = {"golden": round(cg, 3), "ours": round(co, 3)}
    tg, to = tail_tilt(hg[0]), tail_tilt(ho[0])
    res["tilt_max_diff_db"] = float(max(abs(tg[k] - to[k]) for k in tg))
    res["null_wet_region_db"] = max(null_db(ours[:, c], gold[:, c], sec(1.0, 16)) for c in range(2))
    res["pass"] = bool(worst <= 0.15 and abs(e80g - e80o) <= 1.0 and abs(cg - co) <= 0.1 and res["tilt_max_diff_db"] <= 2)
    return res


# ── 딜레이 ──
def delay_case(name, gold, ours):
    res = {}
    for tag, y in (("golden", gold), ("ours", ours)):
        h = y[10:SR - 100, 0] / (0.5 * G)
        idx = np.nonzero(np.abs(h) > 1e-3)[0]
        taps = [(int(i), float(h[i])) for i in idx[:4]]
        d = {"dry": taps[0][1] if taps else 0}
        if len(taps) >= 3:
            d["delay_samples"] = taps[1][0] - taps[0][0]
            d["delay_ms"] = d["delay_samples"] / SR * 1000
            d["wet_first"] = taps[1][1]
            d["feedback_db_per_repeat"] = float(20 * np.log10(abs(taps[2][1] / taps[1][1])))
        res[tag] = d
    res["null_all_db"] = max(null_db(ours[:, c], gold[:, c], sec(0, 16)) for c in range(2))
    g, o = res["golden"], res["ours"]
    res["pass"] = bool(g.get("delay_samples") == o.get("delay_samples")
                       and abs(g.get("feedback_db_per_repeat", 0) - o.get("feedback_db_per_repeat", 9)) < 0.05
                       and abs(g["dry"] - o["dry"]) < 1e-3 and abs(g.get("wet_first", 0) - o.get("wet_first", 9)) < 1e-3)
    return res


# ── 코러스: 짧은 창마다 지연 추정 ──
def chorus_delays(y, ch=0, dry=0.70710678):
    w = (y[:, ch] / G - dry * X[:, ch]) / dry
    x = X[:, ch]
    ts, ds = [], []
    for a in range(int(6.05 * SR), int(9.9 * SR), 480):
        n = 480
        best = None
        seg = w[a:a + n]
        if np.sum(x[a:a + n] ** 2) < 1e-5:
            continue
        for d in range(850, 1250):
            A = np.stack([x[a - d:a - d + n], x[a - d - 1:a - d - 1 + n]], 1)
            co, *_ = np.linalg.lstsq(A, seg, rcond=None)
            e = np.sum((A @ co - seg) ** 2)
            if best is None or e < best[0]:
                best = (e, d, co)
        e, d, co = best
        ts.append((a + n / 2) / SR)
        ds.append(d + co[1] / (co[0] + co[1] + 1e-12))
    return np.array(ts), np.array(ds)


def mod_period(ts, v):
    """자기상관으로 변조 주기(초)"""
    v = v - np.mean(v)
    dt = ts[1] - ts[0]
    c = np.correlate(v, v, "full")[len(v) - 1:]
    c /= c[0]
    lo = int(0.3 / dt)
    k = lo + int(np.argmax(c[lo:]))
    return float(k * dt)


def chorus_case(name, gold, ours):
    res = {}
    for tag, y in (("golden", gold), ("ours", ours)):
        ts, ds = chorus_delays(y)
        res[tag] = {"delay_min_ms": round(float(np.percentile(ds, 2)) / SR * 1000, 3),
                    "delay_max_ms": round(float(np.percentile(ds, 98)) / SR * 1000, 3),
                    "period_s": round(mod_period(ts, ds), 3)}
    res["null_music_db"] = max(null_db(ours[:, c], gold[:, c], sec(6, 10)) for c in range(2))
    res["null_all_db"] = max(null_db(ours[:, c], gold[:, c], sec(0, 16)) for c in range(2))
    g, o = res["golden"], res["ours"]
    res["pass"] = bool(abs(g["delay_min_ms"] - o["delay_min_ms"]) < 0.1 and abs(g["delay_max_ms"] - o["delay_max_ms"]) < 0.1
                       and abs(g["period_s"] - o["period_s"]) < 0.05)
    return res


# ── 페이저: 창마다 올패스 계수 추정 ──
def phaser_track(y, ch=0):
    def Hm(a, f):
        z = np.exp(-1j * 2 * np.pi * f / SR)
        A = ((-a + z) / (1 - a * z)) ** 4
        return 1 + A / (1 - 0.7 * z * A)
    ts, fs = [], []
    for a0 in list(range(6 * SR, int(9.1 * SR), 1920)):
        n = 4096
        x = X[a0:a0 + n, ch] * G
        yy = y[a0:a0 + n, ch]
        if np.sum(x ** 2) < 1e-4:
            continue
        f, Pxy = ss.csd(x, yy, SR, nperseg=1024)
        f, Pxx = ss.welch(x, SR, nperseg=1024)
        H = Pxy / Pxx
        m = (f > 40) & (f < 16000) & (Pxx > 1e-3 * Pxx.max())
        cand = np.linspace(0.5, 0.9999, 1500)
        errs = [np.sum(np.abs(Hm(a, f[m]) - H[m]) ** 2 * Pxx[m]) for a in cand]
        a = cand[int(np.argmin(errs))]
        ts.append((a0 + n / 2) / SR)
        fs.append((1 - a) / (1 + a) * SR / 2)
    return np.array(ts), np.array(fs)


def phaser_case(name, gold, ours):
    res = {}
    for tag, y in (("golden", gold), ("ours", ours)):
        ts, fs = phaser_track(y)
        res[tag] = {"f_min_hz": round(float(np.min(fs)), 1), "f_max_hz": round(float(np.max(fs)), 1),
                    "period_s": round(2 * abs(ts[int(np.argmax(fs))] - ts[int(np.argmin(fs))]), 3)}
    res["null_all_db"] = max(null_db(ours[:, c], gold[:, c], sec(0, 16)) for c in range(2))
    res["null_music_db"] = max(null_db(ours[:, c], gold[:, c], sec(6, 10)) for c in range(2))
    g, o = res["golden"], res["ours"]
    res["pass"] = bool(abs(np.log(g["f_min_hz"] / o["f_min_hz"])) < 0.1 and abs(np.log(g["f_max_hz"] / o["f_max_hz"])) < 0.1)
    return res


# ── 피치 시프터 ──
def sweep_freq(t):
    f0, f1, T = 20.0, 20000.0, 4.0
    return f0 * (f1 / f0) ** (t / T)


def pitch_analysis(y, semis, latency):
    """스윕 구간 STFT(4096) 최대 피크 주파수 ÷ (같은 시각 입력 주파수 × 비율) → 센트 오차, 톤 순도(목표 ±2 반음 대역 대 나머지)"""
    yy = y[:, 0]
    nper = 4096
    f, t, Z = ss.stft(yy, SR, nperseg=nper, noverlap=nper - 512)
    mag = np.abs(Z)
    ratio = 2 ** (semis / 12)
    cents, snr = [], []
    for j, tt in enumerate(t):
        ts = tt - latency / SR - 1.0
        if ts < 0.3 or ts > 3.7:
            continue
        ftarget = sweep_freq(ts) * ratio
        if ftarget < 150 or ftarget > 12000:
            continue
        band = (f > ftarget * 2 ** (-2 / 12)) & (f < ftarget * 2 ** (2 / 12))
        kk = np.nonzero(band)[0]
        k = kk[int(np.argmax(mag[kk, j]))]
        a, b, c = np.log(mag[k - 1:k + 2, j] + 1e-12)
        p = 0.5 * (a - c) / (a - 2 * b + c)
        fp = (k + p) * SR / nper
        cents.append(1200 * np.log2(fp / ftarget))
        snr.append(10 * np.log10(np.sum(mag[band, j] ** 2) / max(np.sum(mag[~band, j] ** 2), 1e-20)))
    return float(np.median(cents)), float(np.percentile(np.abs(cents), 90)), float(np.median(snr))


def music_shift_cents(y):
    """음악 구간 평균 로그 스펙트럼(로그 주파수 축)을 입력과 교차상관 → 피치 이동(센트)"""
    s = sec(6, 10)
    def logspec(v):
        f, P = ss.welch(v, SR, nperseg=16384)
        grid = 100 * 2 ** (np.arange(0, 6 * 1200, 5) / 1200)      # 100 Hz ~ 6.4 kHz, 5 센트 간격
        return np.interp(grid, f, 10 * np.log10(P + 1e-20))
    def whiten(v):   # 1 옥타브 이동평균을 빼서 배음 피크만 남김
        k = np.ones(240) / 240
        return v - np.convolve(v, k, mode="same")
    a = whiten(logspec(X[s, 0] + X[s, 1]))[120:-120]
    b = whiten(logspec(y[s, 0] + y[s, 1]))[120:-120]
    lags = np.arange(-2600 // 5, 2600 // 5)
    cc = [np.mean(a[max(0, -l):len(a) - max(0, l)] * b[max(0, l):len(b) - max(0, -l)]) for l in lags]
    return float(lags[int(np.argmax(cc))] * 5)


def onset_lag(y):
    """스윕 시작(1.0 s) 기준 출력이 처음 -60 dBFS 를 넘는 시각(샘플)"""
    a = int(0.97 * SR)
    e = np.abs(y[a:int(1.5 * SR), 0])
    return int(np.argmax(e > 1e-3)) + a - SR


def env_lag(y):
    """음악 구간 엔벨로프 교차상관으로 입력 대비 지연(샘플)"""
    s = sec(6, 10)
    e_in = np.abs(ss.hilbert(X[:, 0] + X[:, 1]))
    e_y = np.abs(ss.hilbert(y[:, 0] + y[:, 1]))
    b, a = ss.butter(2, 50, fs=SR)
    e_in = ss.filtfilt(b, a, e_in)
    e_y = ss.filtfilt(b, a, e_y)
    return best_lag(e_y, e_in, s, 6000)


def pitch_case(name, gold, ours, semis, latency):
    res = {}
    for tag, y in (("golden", gold), ("ours", ours)):
        lat = env_lag(y)
        med, p90, snr = pitch_analysis(y, semis, lat)
        res[tag] = {"latency_env_samples": int(lat), "sweep_onset_samples": onset_lag(y),
                    "music_shift_cents": music_shift_cents(y) - semis * 100,
                    "sweep_err_cents_median": round(med, 2), "sweep_err_cents_p90": round(p90, 2), "tone_snr_db": round(snr, 1),
                    "level_music_db": round(float(10 * np.log10(np.sum(y[sec(6, 10)] ** 2) / np.sum((X[sec(6, 10)] * G) ** 2))), 2)}
    res["ours"]["latency_reported"] = latency
    o = res["ours"]
    res["pass"] = bool(abs(o["sweep_err_cents_median"]) < 5 and abs(o["music_shift_cents"]) <= 10)
    return res


def main():
    cases = json.loads((GDIR / "cases.json").read_text(encoding="utf-8"))["cases"]
    report = {"master_gain": G, "cases": {}}
    rows = []
    for c in cases:
        dev = c.get("device")
        if not dev:
            continue
        name = c["name"]
        op = ODIR / f"{name}.wav"
        if not op.exists():
            print("missing", op)
            continue
        gold = rd(GDIR / f"{name}.wav")
        ours = to_golden_domain(rd(op))
        params = c.get("params", {})
        if dev in ("eq", "lowpass"):
            r = linear_case(name, gold, ours)
            summary = f"|ΔH| max {r['mag_max_diff_db']:.3f} dB, null music {r['null_music_db']:.1f} dB, all {r['null_all_db']:.1f} dB"
        elif dev == "compressor":
            r = comp_case(name, gold, ours)
            summary = (f"static Δ max {r['static_max_diff_db']:.3f} dB, curve Δ max {r['curve_worst_db']:.2f} dB, "
                       f"null all {r['null_all_db']:.1f} dB")
        elif dev == "reverb":
            r = reverb_case(name, gold, ours, params | {"dry level": params.get("dry level", 0.5)})
            summary = (f"RT60 err max {r['rt60_max_rel_err'] * 100:.1f}%, early {r['early_energy_db']['golden']:.2f}/{r['early_energy_db']['ours']:.2f} dB, "
                       f"LR corr {r['lr_corr']['golden']:.3f}/{r['lr_corr']['ours']:.3f}, tilt Δ {r['tilt_max_diff_db']:.2f} dB, null {r['null_wet_region_db']:.1f} dB")
        elif dev == "delay":
            r = delay_case(name, gold, ours)
            g, o = r["golden"], r["ours"]
            summary = (f"delay {g.get('delay_ms')}/{o.get('delay_ms')} ms, fb {g.get('feedback_db_per_repeat', 0):.2f}/{o.get('feedback_db_per_repeat', 0):.2f} dB, "
                       f"dry {g['dry']:.4f}/{o['dry']:.4f}, wet {g.get('wet_first', 0):.4f}/{o.get('wet_first', 0):.4f}, null {r['null_all_db']:.1f} dB")
        elif dev == "chorus":
            r = chorus_case(name, gold, ours)
            g, o = r["golden"], r["ours"]
            summary = (f"delay {g['delay_min_ms']}–{g['delay_max_ms']} / {o['delay_min_ms']}–{o['delay_max_ms']} ms, period {g['period_s']}/{o['period_s']} s, "
                       f"null music {r['null_music_db']:.1f} dB, all {r['null_all_db']:.1f} dB")
        elif dev == "phaser":
            r = phaser_case(name, gold, ours)
            g, o = r["golden"], r["ours"]
            summary = (f"f {g['f_min_hz']}–{g['f_max_hz']} / {o['f_min_hz']}–{o['f_max_hz']} Hz, period {g['period_s']}/{o['period_s']} s, "
                       f"null music {r['null_music_db']:.1f} dB, all {r['null_all_db']:.1f} dB")
        elif dev == "pitchshift":
            semis = params.get("semitones up", 0)
            lat = int(META.get(name, {}).get("latency", 0))
            r = pitch_case(name, gold, ours, semis, lat)
            g, o = r["golden"], r["ours"]
            summary = (f"sweep cents med {g['sweep_err_cents_median']}/{o['sweep_err_cents_median']} p90 {g['sweep_err_cents_p90']}/{o['sweep_err_cents_p90']}, "
                       f"music shift err {g['music_shift_cents']:+.0f}/{o['music_shift_cents']:+.0f} c, tone SNR {g['tone_snr_db']}/{o['tone_snr_db']} dB, "
                       f"level {g['level_music_db']}/{o['level_music_db']} dB, onset {g['sweep_onset_samples']}/{o['sweep_onset_samples']}, env lag {g['latency_env_samples']}/{o['latency_env_samples']} (reported {lat})")
        else:
            continue
        report["cases"][name] = r
        rows.append((name, "PASS" if r.get("pass") else "----", summary))
    w = max(len(r[0]) for r in rows)
    print(f"master gain {20 * np.log10(G):.3f} dB   (golden/ours 순서)")
    for name, ok, s in rows:
        print(f"{name:<{w}}  {ok}  {s}")
    ODIR.mkdir(parents=True, exist_ok=True)
    (ODIR / "report.json").write_text(json.dumps(report, indent=1, ensure_ascii=False, default=float), encoding="utf-8")
    print("->", ODIR / "report.json")


if __name__ == "__main__":
    sys.exit(main())
