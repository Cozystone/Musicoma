"""목소리 손잡이 — 어떤 보컬이든 '캐릭터'를 입힌다. (WORLD 보코더: 음높이 · 성도 · 숨 성분으로 나눠 고친 뒤 다시 합성)

손잡이(모두 0 이 원래 그대로)
  pitch_st      음높이(반음)            −  낮게 / 성숙   +  높게 / 젊게
  formant       성도 길이(반음 단위)    −  큰 체격·굵은 목   +  작은 체격
  breath        숨 섞임 0..1           허스키함
  rasp          거칠기 0..1            갈라짐(성대 불규칙 + 배음 포화)
  brightness    밝기 dB(±)             고역 셸프
  vibrato       비브라토 추가(센트)
  age           나이 느낌 0..1         떨림·숨·고역 감소를 함께

말로 주문 → 손잡이: DESCRIPTORS 사전(Claude 가 조합). 실존 인물을 흉내 내는 설정은 만들지 않는다.
"""
import numpy as np
import pyworld as pw
import soundfile as sf
import librosa

DESCRIPTORS = {
    "허스키": {"breath": 0.45, "brightness": -2},
    "husky": {"breath": 0.45, "brightness": -2},
    "거친": {"rasp": 0.45},
    "raspy": {"rasp": 0.45},
    "gritty": {"rasp": 0.35, "breath": 0.15},
    "중년": {"age": 0.45, "pitch_st": -1.5, "formant": -0.7},
    "middle-aged": {"age": 0.45, "pitch_st": -1.5, "formant": -0.7},
    "노년": {"age": 0.85, "pitch_st": -2, "formant": -0.5, "vibrato": 25},
    "old": {"age": 0.85, "pitch_st": -2, "formant": -0.5, "vibrato": 25},
    "젊은": {"age": 0.0, "pitch_st": 1, "brightness": 1.5},
    "young": {"age": 0.0, "pitch_st": 1, "brightness": 1.5},
    "남성": {"pitch_st": -5, "formant": -2.5},
    "male": {"pitch_st": -5, "formant": -2.5},
    "여성": {"pitch_st": 4, "formant": 2},
    "female": {"pitch_st": 4, "formant": 2},
    "굵은": {"formant": -1.5, "brightness": -1},
    "deep": {"formant": -1.5, "pitch_st": -2, "brightness": -1},
    "밝은": {"brightness": 3},
    "bright": {"brightness": 3},
    "어두운": {"brightness": -3},
    "dark": {"brightness": -3},
    "부드러운": {"breath": 0.2, "rasp": 0.0, "brightness": -1},
    "soft": {"breath": 0.2, "brightness": -1},
    "숨소리": {"breath": 0.6},
    "breathy": {"breath": 0.6},
    "비브라토": {"vibrato": 35},
}


def describe(text):
    """'허스키한 중년 남성' → 손잡이 값 (여러 단어는 더한다, 범위 제한)."""
    k = {"pitch_st": 0.0, "formant": 0.0, "breath": 0.0, "rasp": 0.0, "brightness": 0.0, "vibrato": 0.0, "age": 0.0}
    t = text.lower()
    for word, d in DESCRIPTORS.items():
        if word in t:
            for a, v in d.items():
                k[a] += v
    k["breath"] = min(0.85, k["breath"]); k["rasp"] = min(0.8, k["rasp"]); k["age"] = min(1.0, k["age"])
    return k


def apply(path, out, pitch_st=0.0, formant=0.0, breath=0.0, rasp=0.0, brightness=0.0, vibrato=0.0, age=0.0, seed=0):
    y, sr = sf.read(str(path), always_2d=True)
    mono = y.mean(axis=1).astype(np.float64)
    rnd = np.random.default_rng(seed)
    frame_ms = 5.0
    f0, t = pw.harvest(mono, sr, frame_period=frame_ms, f0_floor=60, f0_ceil=1100)
    sp = pw.cheaptrick(mono, f0, t, sr)
    ap = pw.d4c(mono, f0, t, sr)

    # 음높이 + 나이(미세한 떨림) + 비브라토
    voiced = f0 > 0
    f0n = f0 * 2 ** (pitch_st / 12)
    n = len(f0n)
    tt = np.arange(n) * frame_ms / 1000
    if vibrato or age:
        cents = vibrato * np.sin(2 * np.pi * 5.3 * tt) + age * 18 * np.sin(2 * np.pi * 7.5 * tt + rnd.random() * 6)
        cents += age * 6 * rnd.standard_normal(n)
        f0n = f0n * 2 ** (cents / 1200)
    if rasp:                                    # 성대 불규칙(지터)
        f0n = f0n * (1 + rasp * 0.035 * rnd.standard_normal(n))
    f0n[~voiced] = 0

    # 포먼트: 스펙트럼 포락선을 주파수 축으로 늘이고 줄인다
    if formant:
        ratio = 2 ** (formant / 12)
        bins = sp.shape[1]
        src = np.clip(np.arange(bins) / ratio, 0, bins - 1)
        sp = np.array([np.interp(src, np.arange(bins), row) for row in sp])

    # 숨(허스키): 비주기 성분을 올린다(고역일수록 더)
    if breath or age:
        b = min(0.95, breath + 0.25 * age)
        freq_w = np.linspace(0.4, 1.0, ap.shape[1])
        ap = np.clip(ap + b * freq_w * (1 - ap), 0, 1)

    z = pw.synthesize(f0n, sp, ap, sr, frame_period=frame_ms)

    # 거칠기: 배음 포화 + 고역 손실(나이)
    if rasp:
        drive = 1 + 6 * rasp
        z = np.tanh(z * drive) / np.tanh(drive) * 0.9 + z * 0.1
    from pedalboard import Pedalboard, HighShelfFilter, LowShelfFilter
    chain = []
    tilt = brightness - 3.0 * age
    if tilt:
        chain.append(HighShelfFilter(cutoff_frequency_hz=4000, gain_db=float(tilt)))
    if formant < -1:
        chain.append(LowShelfFilter(cutoff_frequency_hz=250, gain_db=1.5))
    if chain:
        z = Pedalboard(chain)(z.astype(np.float32)[None, :], sr)[0]
    z = z / (np.abs(z).max() + 1e-9) * 0.9
    sf.write(str(out), np.stack([z, z], axis=1), sr, subtype="PCM_24")
    return str(out)


def character(path, out, description, seed=0, **override):
    k = describe(description)
    k.update(override)
    return apply(path, out, seed=seed, **k), k
