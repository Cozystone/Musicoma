"""마스터 — 렌더 결과를 목표 음압(LUFS)·트루피크 천장에 정확히 맞춘다.

엔진 렌더러의 LUFS 정규화는 리미터가 없어 트루피크 때문에 목표보다 작게 끝난다.
여기서: 글루 컴프(선택) → 게인 → 리미터 → 측정 → 보정, 두세 번 반복.
"""
from pathlib import Path

import numpy as np
import soundfile as sf
import pyloudnorm as pyln
from scipy.signal import resample_poly


def _tp(y):
    return 20 * np.log10(np.abs(resample_poly(y, 4, 1, axis=0)).max() + 1e-12)


def master(path, lufs=-12.0, ceiling=-1.0, glue=True, out=None, tone=None):
    """tone: {'low_shelf_db':.., 'high_shelf_db':..} 마스터 톤 보정(선택)."""
    from pedalboard import Pedalboard, Compressor, Limiter, Gain, LowShelfFilter, HighShelfFilter
    y, sr = sf.read(str(path), always_2d=True, dtype="float32")
    meter = pyln.Meter(sr)
    chain = []
    if tone:
        if tone.get("low_shelf_db"):
            chain.append(LowShelfFilter(cutoff_frequency_hz=120, gain_db=tone["low_shelf_db"]))
        if tone.get("high_shelf_db"):
            chain.append(HighShelfFilter(cutoff_frequency_hz=8000, gain_db=tone["high_shelf_db"]))
    if glue:
        chain.append(Compressor(threshold_db=-16, ratio=2.0, attack_ms=30, release_ms=200))
    pre = Pedalboard(chain)(y.T, sr).T if chain else y

    gain = lufs - meter.integrated_loudness(pre)
    z = pre
    up = resample_poly(pre, 4, 1, axis=0).astype(np.float32)      # 리미터를 4배 오버샘플에서(10-16 퐁크: 1배 리미터는 모서리를 만들어
    for _ in range(4):                                             # 트루피크가 샘플 피크보다 4.5dB 높아져 곡 전체가 그만큼 작아졌다 -10 LUFS)
        zu = Pedalboard([Gain(gain), Limiter(threshold_db=ceiling - 0.5, release_ms=120)])(up.T, sr * 4).T
        z = resample_poly(zu, 1, 4, axis=0).astype(np.float32)
        z = z * min(1.0, 10 ** ((ceiling - _tp(z)) / 20))      # 오버샘플 피크 안전장치
        got = meter.integrated_loudness(z)
        if abs(got - lufs) < 0.2:
            break
        gain += lufs - got
    out = Path(out) if out else Path(path).with_name(Path(path).stem + "_master.wav")
    sf.write(str(out), z, sr, subtype="PCM_24")
    return {"path": str(out), "lufs": round(meter.integrated_loudness(z), 1), "true_peak": round(_tp(z), 1),
            "gain_applied_db": round(gain, 1)}
