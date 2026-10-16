"""파이썬 쪽 DSP — pedalboard(GPL-3, JUCE 포함)를 쓰지 않으려고 직접 쓴 것(10-16, 자체 엔진 교체와 함께).
numpy/scipy 와 numba 만 쓴다. 모든 함수는 y = (프레임,) 또는 (프레임, 채널) float 배열을 받아 같은 모양을 돌려준다.

    shelf · highpass · lowpass · compressor · limiter(트루피크, 오버샘플) · gain · bitcrush · distortion · lofi_resample · time_stretch
"""
import numpy as np
from scipy.signal import butter, sosfilt, resample_poly

try:
    from numba import njit
except Exception:  # numba 가 없으면 느린 그대로
    def njit(*a, **k):
        def deco(f):
            return f
        return deco(a[0]) if a and callable(a[0]) else deco


def _2d(y):
    y = np.asarray(y, dtype=np.float64)
    return (y[:, None], True) if y.ndim == 1 else (y, False)


def _back(z, was1d, like):
    z = z[:, 0] if was1d else z
    return z.astype(like.dtype if hasattr(like, "dtype") and np.issubdtype(like.dtype, np.floating) else np.float32)


def _biquad_sos(b, a):
    b = np.asarray(b, float) / a[0]
    a = np.asarray(a, float) / a[0]
    return np.array([[b[0], b[1], b[2], 1.0, a[1], a[2]]])


def shelf(y, sr, freq, gain_db, kind="low", q=0.7071):
    """RBJ 셸프(저역/고역)."""
    z, one = _2d(y)
    A = 10 ** (gain_db / 40)
    w = 2 * np.pi * min(freq, sr * 0.49) / sr
    c, s = np.cos(w), np.sin(w)
    al = s / (2 * q)
    sq = 2 * np.sqrt(A) * al
    if kind == "low":
        b = [A * ((A + 1) - (A - 1) * c + sq), 2 * A * ((A - 1) - (A + 1) * c), A * ((A + 1) - (A - 1) * c - sq)]
        a = [(A + 1) + (A - 1) * c + sq, -2 * ((A - 1) + (A + 1) * c), (A + 1) + (A - 1) * c - sq]
    else:
        b = [A * ((A + 1) + (A - 1) * c + sq), -2 * A * ((A - 1) + (A + 1) * c), A * ((A + 1) + (A - 1) * c - sq)]
        a = [(A + 1) - (A - 1) * c + sq, 2 * ((A - 1) - (A + 1) * c), (A + 1) - (A - 1) * c - sq]
    out = sosfilt(_biquad_sos(b, a), z, axis=0)
    return _back(out, one, np.asarray(y))


def highpass(y, sr, freq, order=2):
    z, one = _2d(y)
    out = sosfilt(butter(order, min(freq, sr * 0.49), btype="high", fs=sr, output="sos"), z, axis=0)
    return _back(out, one, np.asarray(y))


def lowpass(y, sr, freq, order=2):
    z, one = _2d(y)
    out = sosfilt(butter(order, min(freq, sr * 0.49), btype="low", fs=sr, output="sos"), z, axis=0)
    return _back(out, one, np.asarray(y))


def gain(y, db):
    return (np.asarray(y) * 10 ** (db / 20)).astype(np.asarray(y).dtype)


@njit(cache=True)
def _comp_gain(det, thr, ratio, att, rel):
    g = np.zeros_like(det)
    env = 0.0           # 깎는 양(dB, 양수)
    for i in range(det.shape[0]):
        lvl = 20.0 * np.log10(det[i] + 1e-12)
        over = lvl - thr
        want = over * (1.0 - 1.0 / ratio) if over > 0 else 0.0
        k = att if want > env else rel
        env = want + (env - want) * k
        g[i] = 10.0 ** (-env / 20.0)
    return g


def compressor(y, sr, threshold_db=-16.0, ratio=2.0, attack_ms=30.0, release_ms=200.0, makeup_db=0.0):
    """피드포워드 피크 컴프(채널 묶음 검출, dB 영역 어택/릴리스)."""
    z, one = _2d(y)
    det = np.abs(z).max(axis=1)
    att = np.exp(-1.0 / (max(attack_ms, 0.01) * 1e-3 * sr))
    rel = np.exp(-1.0 / (max(release_ms, 0.01) * 1e-3 * sr))
    g = _comp_gain(det, float(threshold_db), float(max(ratio, 1.0)), att, rel)
    out = z * g[:, None] * 10 ** (makeup_db / 20)
    return _back(out, one, np.asarray(y))


@njit(cache=True)
def _lim_gain(need, look, rel):
    n = need.shape[0]
    # 앞으로 look 샘플 안의 최소 필요 이득(미리 보기) → 그 값으로 바로 내리고, 천천히 회복
    out = np.ones(n)
    g = 1.0
    from_q = np.empty(n)
    # 단조 덱으로 구간 최소
    dq = np.empty(n, dtype=np.int64)
    head = 0
    tail = 0
    for i in range(n + look):
        if i < n:
            while tail > head and need[dq[tail - 1]] >= need[i]:
                tail -= 1
            dq[tail] = i
            tail += 1
        j = i - look
        if j >= 0:
            while dq[head] < j:
                head += 1
            from_q[j] = need[dq[head]]
    for i in range(n):
        t = from_q[i]
        if t < g:
            g = t
        else:
            g = t + (g - t) * rel
        out[i] = g
    return out


def limiter(y, sr, ceiling_db=-1.0, release_ms=120.0, lookahead_ms=1.5, oversample=4):
    """미리 보기 브릭월 리미터. 오버샘플(기본 4배)에서 잡아 샘플 사이 피크(트루피크)까지 천장 아래로."""
    z, one = _2d(y)
    n0 = z.shape[0]
    u = resample_poly(z, oversample, 1, axis=0) if oversample > 1 else z.copy()
    usr = sr * oversample
    thr = 10 ** (ceiling_db / 20)
    peak = np.abs(u).max(axis=1)
    need = np.minimum(1.0, thr / np.maximum(peak, 1e-12))
    look = max(1, int(lookahead_ms * 1e-3 * usr))
    rel = np.exp(-1.0 / (release_ms * 1e-3 * usr))
    g = _lim_gain(need, look, rel)
    # 미리 보기만큼 지연된 신호에 이득을 곱하는 대신, 이득을 같은 위치에 정렬(need 를 앞당겨 봤으므로 그대로 곱함)
    uo = u * g[:, None]
    out = resample_poly(uo, 1, oversample, axis=0)[:n0] if oversample > 1 else uo
    return _back(out, one, np.asarray(y))


def bitcrush(y, bits):
    q = 2 ** (bits - 1)
    return (np.round(np.asarray(y) * q) / q).astype(np.asarray(y).dtype)


def distortion(y, drive_db):
    k = 10 ** (drive_db / 20)
    return np.tanh(np.asarray(y) * k).astype(np.asarray(y).dtype)


def lofi_resample(y, sr, rate):
    """낮은 샘플레이트로 내렸다가(앨리어싱 없이) 원래로 — 옛 샘플러의 먹먹함."""
    from math import gcd
    rate = int(rate)
    g = gcd(int(sr), rate)
    z, one = _2d(y)
    down = resample_poly(z, rate // g, int(sr) // g, axis=0)
    up = resample_poly(down, int(sr) // g, rate // g, axis=0)[: z.shape[0]]
    if up.shape[0] < z.shape[0]:
        up = np.pad(up, ((0, z.shape[0] - up.shape[0]), (0, 0)))
    return _back(up, one, np.asarray(y))


def time_stretch(y, sr, rate=1.0, semitones=0.0):
    """길이·음높이 바꾸기(librosa 위상 보코더). rate > 1 = 빠르게(짧게)."""
    import librosa
    z, one = _2d(y)
    chans = []
    for c in range(z.shape[1]):
        x = z[:, c].astype(np.float32)
        if abs(rate - 1.0) > 1e-6:
            x = librosa.effects.time_stretch(x, rate=rate)
        if abs(semitones) > 1e-6:
            x = librosa.effects.pitch_shift(x, sr=sr, n_steps=semitones)
        chans.append(x)
    L = min(len(c) for c in chans)
    out = np.stack([c[:L] for c in chans], 1)
    return _back(out, one, np.asarray(y))
