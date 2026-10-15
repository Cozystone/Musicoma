"""귀 모듈 — Claude 는 소리를 못 들으니 렌더를 숫자와 그림으로 바꾼다.

python analyze.py render.wav [--ref reference.wav] [--png out.png] [--json]

내는 것
- 음량: 통합 LUFS, 단기 LUFS 최대/최소(다이내믹), 트루피크(4배 오버샘플), 크레스트
- 주파수 밸런스: 6개 대역 에너지(dB, 전체 대비) — sub/low/low-mid/mid/presence/air
- 스테레오: 폭(사이드/미드), 위상 상관, 저역 모노 여부
- 문제 신호: 클리핑, 무음 구간, DC
- 음악: 추정 템포·키(참고용 — 박자는 엔진이 이미 안다)
- 레퍼런스가 있으면 대역별 차이와 LUFS 차이
- PNG: 파형 + 멜 스펙트로그램 + 대역 막대 (Claude 가 Read 로 본다)
"""
import argparse
import json
import sys

import numpy as np
import soundfile as sf
import pyloudnorm as pyln
import librosa
from scipy.signal import resample_poly

BANDS = [("sub", 20, 60), ("low", 60, 250), ("low_mid", 250, 1000),
         ("mid", 1000, 4000), ("presence", 4000, 10000), ("air", 10000, 20000)]
KEYS = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
MAJOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
MINOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])


def db(x):
    return float(20 * np.log10(max(float(x), 1e-12)))


def load(path):
    audio, sr = sf.read(path, always_2d=True, dtype="float32")
    if audio.shape[1] == 1:
        audio = np.repeat(audio, 2, axis=1)
    return audio[:, :2], sr


def band_energy(mono, sr):
    spec = np.abs(np.fft.rfft(mono * np.hanning(len(mono)))) ** 2
    freqs = np.fft.rfftfreq(len(mono), 1 / sr)
    total = spec[(freqs >= 20) & (freqs <= 20000)].sum() + 1e-20
    return {name: round(10 * np.log10(spec[(freqs >= lo) & (freqs < hi)].sum() / total + 1e-20), 1)
            for name, lo, hi in BANDS}


def estimate_key(mono, sr):
    chroma = librosa.feature.chroma_cqt(y=mono, sr=sr).mean(axis=1)
    best = None
    for i in range(12):
        for mode, prof in (("major", MAJOR), ("minor", MINOR)):
            r = np.corrcoef(chroma, np.roll(prof, i))[0, 1]
            if best is None or r > best[0]:
                best = (r, f"{KEYS[i]} {mode}")
    return best[1], round(float(best[0]), 2)


def analyze(path):
    audio, sr = load(path)
    mono = audio.mean(axis=1)
    meter = pyln.Meter(sr)
    out = {"file": path, "seconds": round(len(mono) / sr, 2), "sample_rate": sr}

    # 음량
    integrated = meter.integrated_loudness(audio)
    win, hop = int(3 * sr), int(1 * sr)
    short = [meter.integrated_loudness(audio[i:i + win]) for i in range(0, max(1, len(audio) - win), hop)]
    short = [s for s in short if np.isfinite(s) and s > -70]
    over = resample_poly(audio, 4, 1, axis=0)
    peak = np.abs(audio).max()
    rms = np.sqrt(np.mean(mono ** 2))
    out["loudness"] = {
        "lufs_integrated": round(integrated, 1),
        "lufs_short_max": round(max(short), 1) if short else None,
        "lufs_short_min": round(min(short), 1) if short else None,
        "true_peak_dbtp": round(db(np.abs(over).max()), 1),
        "sample_peak_dbfs": round(db(peak), 1),
        "crest_db": round(db(peak) - db(rms), 1),
    }

    # 주파수 밸런스
    out["bands_db"] = band_energy(mono, sr)

    # 스테레오
    mid, side = (audio[:, 0] + audio[:, 1]) / 2, (audio[:, 0] - audio[:, 1]) / 2
    corr = np.corrcoef(audio[:, 0], audio[:, 1])[0, 1] if audio[:, 0].std() > 0 and audio[:, 1].std() > 0 else 1.0
    f = np.fft.rfftfreq(len(side), 1 / sr)
    side_low = np.abs(np.fft.rfft(side)[f < 150]).sum()
    mid_low = np.abs(np.fft.rfft(mid)[f < 150]).sum() + 1e-12
    out["stereo"] = {
        "width_side_to_mid_db": round(db(np.sqrt(np.mean(side ** 2))) - db(np.sqrt(np.mean(mid ** 2))), 1),
        "correlation": round(float(corr), 2),
        "low_end_side_ratio_db": round(db(side_low / mid_low), 1),
    }

    # 문제 신호
    clipped = int((np.abs(audio) >= 0.999).sum())
    frame = int(0.05 * sr)
    frames = mono[: len(mono) // frame * frame].reshape(-1, frame)
    silent = (np.sqrt((frames ** 2).mean(axis=1)) < 10 ** (-60 / 20)).astype(int)
    longest, run = 0, 0
    for s in silent:
        run = run + 1 if s else 0
        longest = max(longest, run)
    issues = []
    if clipped:
        issues.append(f"clipping: {clipped} samples at full scale")
    if out["loudness"]["true_peak_dbtp"] > -1.0:
        issues.append(f"true peak {out['loudness']['true_peak_dbtp']} dBTP > -1 (streaming risk)")
    if longest * 0.05 > 1.0:
        issues.append(f"silence: longest gap {longest * 0.05:.1f}s")
    # 곡 중간의 급락(노트가 다 끊기고 잔향도 없는 순간) — 처음·끝 1초는 뺀다.
    hop = int(0.01 * sr)
    fr = mono[: len(mono) // hop * hop].reshape(-1, hop)
    env = 20 * np.log10(np.sqrt((fr ** 2).mean(axis=1)) + 1e-9)
    median = np.median(env[env > -90]) if (env > -90).any() else -90
    loud = np.where(env > median - 30)[0]
    if len(loud) > 100:
        first, last = loud[0], loud[-1]
        low = env[first:last] < median - 24
        dips, run_start = [], None
        for i, v in enumerate(low):
            if v and run_start is None:
                run_start = i
            if not v and run_start is not None:
                if i - run_start >= 2:
                    dips.append(round(float((first + run_start) * 0.01), 2))
                run_start = None
        if dips:
            issues.append(f"dead air: {len(dips)} drops >24 dB below median inside the music "
                          f"(at {dips[:8]} s) - notes end with no sustain/reverb/overlap")
    if abs(mono.mean()) > 0.01:
        issues.append(f"DC offset {mono.mean():.3f}")
    if corr < 0.2:
        issues.append(f"low L/R correlation {corr:.2f} (mono compatibility risk)")
    if out["stereo"]["low_end_side_ratio_db"] > -12:
        issues.append("wide low end (<150 Hz has side energy)")
    out["issues"] = issues

    # 음악
    tempo, _ = librosa.beat.beat_track(y=mono, sr=sr)
    key, conf = estimate_key(mono, sr)
    out["music"] = {"tempo_est": round(float(np.atleast_1d(tempo)[0]), 1), "key_est": key, "key_confidence": conf}
    return out, audio, sr


def compare(a, b):
    return {
        "lufs_diff": round(a["loudness"]["lufs_integrated"] - b["loudness"]["lufs_integrated"], 1),
        "bands_diff_db": {k: round(a["bands_db"][k] - b["bands_db"][k], 1) for k in a["bands_db"]},
        "width_diff_db": round(a["stereo"]["width_side_to_mid_db"] - b["stereo"]["width_side_to_mid_db"], 1),
        "crest_diff_db": round(a["loudness"]["crest_db"] - b["loudness"]["crest_db"], 1),
    }


def draw(result, audio, sr, png, ref=None):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import librosa.display  # noqa: F401

    mono = audio.mean(axis=1)
    fig = plt.figure(figsize=(12, 7), dpi=100)
    gs = fig.add_gridspec(3, 2, width_ratios=[3, 1], height_ratios=[1, 2, 0.1])

    ax = fig.add_subplot(gs[0, 0])
    t = np.arange(len(mono)) / sr
    step = max(1, len(mono) // 4000)
    ax.fill_between(t[::step], audio[::step, 0], -audio[::step, 1], color="#4a7", lw=0)
    ax.set_xlim(0, t[-1]); ax.set_ylim(-1, 1); ax.set_title("waveform (L up / R down)")

    ax = fig.add_subplot(gs[1, 0])
    S = librosa.feature.melspectrogram(y=mono, sr=sr, n_mels=128, fmax=sr // 2)
    librosa.display.specshow(librosa.power_to_db(S, ref=np.max), sr=sr, x_axis="time", y_axis="mel", ax=ax, cmap="magma")
    ax.set_title("mel spectrogram")

    ax = fig.add_subplot(gs[:, 1])
    names = list(result["bands_db"].keys())
    vals = [result["bands_db"][n] for n in names]
    ax.barh(names, vals, color="#58a", label="this")
    if ref is not None:
        ax.barh(names, [ref["bands_db"][n] for n in names], fill=False, edgecolor="#e74", lw=2, label="reference")
        ax.legend(loc="lower right")
    ax.invert_yaxis(); ax.set_title("band energy (dB of total)")
    L = result["loudness"]
    fig.suptitle(f"{result['file'].split('/')[-1].split(chr(92))[-1]}  |  {L['lufs_integrated']} LUFS  "
                 f"TP {L['true_peak_dbtp']} dBTP  crest {L['crest_db']} dB  |  {result['music']['key_est']}", fontsize=11)
    fig.tight_layout()
    fig.savefig(png)
    plt.close(fig)


def main():
    import librosa.display  # noqa: F401  (specshow 등록)
    ap = argparse.ArgumentParser()
    ap.add_argument("wav")
    ap.add_argument("--ref")
    ap.add_argument("--png")
    a = ap.parse_args()

    result, audio, sr = analyze(a.wav)
    ref = None
    if a.ref:
        ref, _, _ = analyze(a.ref)
        result["vs_reference"] = compare(result, ref)
    if a.png:
        draw(result, audio, sr, a.png, ref)
        result["png"] = a.png
    sys.stdout.reconfigure(encoding="utf-8")
    json.dump(result, sys.stdout, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
