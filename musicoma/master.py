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
    from . import dsp                                   # pedalboard(GPL) 대신 자체 DSP(10-16)
    y, sr = sf.read(str(path), always_2d=True, dtype="float32")
    meter = pyln.Meter(sr)
    pre = y
    if tone:
        if tone.get("low_shelf_db"):
            pre = dsp.shelf(pre, sr, 120, tone["low_shelf_db"], kind="low")
        if tone.get("high_shelf_db"):
            pre = dsp.shelf(pre, sr, 8000, tone["high_shelf_db"], kind="high")
    if glue:
        pre = dsp.compressor(pre, sr, threshold_db=-16, ratio=2.0, attack_ms=30, release_ms=200)

    gain = lufs - meter.integrated_loudness(pre)
    z = pre
    for _ in range(4):                                  # 리미터는 4배 오버샘플에서(트루피크까지 천장 아래)
        z = dsp.limiter(dsp.gain(pre, gain), sr, ceiling_db=ceiling - 0.5, release_ms=120, oversample=4)
        z = z * min(1.0, 10 ** ((ceiling - _tp(z)) / 20))      # 오버샘플 피크 안전장치
        got = meter.integrated_loudness(z)
        if abs(got - lufs) < 0.2:
            break
        gain += lufs - got
    out = Path(out) if out else Path(path).with_name(Path(path).stem + "_master.wav")
    sf.write(str(out), z, sr, subtype="PCM_24")
    return {"path": str(out), "lufs": round(float(meter.integrated_loudness(z)), 1), "true_peak": round(float(_tp(z)), 1),
            "gain_applied_db": round(float(gain), 1)}
