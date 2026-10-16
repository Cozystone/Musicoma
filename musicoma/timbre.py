"""악기 보컬로이드 — 음색 변환(10-17). 선율 오디오(흥얼거림·노래·다른 악기 연주)의 음정·세기·비브라토·글라이드를 그대로 두고
음색만 다른 악기로 바꾼다. 외부 모델 없이: 우리가 가진 실제 악기 샘플(SFZ, VSCO2·Karoryfer…)에서 음색 틀을 뽑아
배음 + 숨(노이즈)으로 다시 합성한다(DDSP 의 배음+노이즈 모델을 학습 없이 샘플 분석으로 채운 것).

    timbre.template("alto_sax")                    악기 음색 틀(한 번 만들어 sounds/timbre/<악기>.npz 에 캐시)
    timbre.transfer("hum.wav", "alto_sax", "out.wav", semitones=0, breath=1.0)
                                                    → {"out", "voiced_ratio", "seconds"}

왜 생성 모델이 아닌가: ACE-Step cover 로 플루트 선율을 색소폰으로 바꾸면 음정 추종이 33%(10-17 실측). 이 방식은 음정을
그대로 쓰므로 100% 에 가깝다. 대신 소리는 '진짜 녹음'이 아니라 '배음 합성' — 숨·어택은 샘플에서 가져와 덜 기계적이게.
"""
import json
from pathlib import Path

import numpy as np
import soundfile as sf
import librosa
from scipy import signal

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "sounds" / "timbre"
SR = 48000
HOP = 240                    # 5 ms
FRAME_MS = 5.0
K = 60                       # 배음 수
NOISE_BANDS = 24
PITCHES = list(range(36, 97, 3))   # C2..C7, 3반음 간격


# ─────────────────────────── 악기 음색 틀 ───────────────────────────
def _render_notes(instrument, port=47899):
    """SFZ 악기로 음 하나씩(1.5초 + 0.5초 쉼) 렌더 — 따로 띄운 엔진에서(열린 곡을 건드리지 않게)."""
    from . import engine as eng_mod
    from .knowledge import resolve_sound
    r = resolve_sound(instrument)
    if r.get("device") != "sfz":
        raise ValueError(f"SFZ 악기만 틀을 만들 수 있습니다: {instrument} → {r}")
    eng_mod.start(port=port)
    e = eng_mod.Engine(port=port, client="timbre")
    e.call("edit.new", {"name": "zz-timbre", "bpm": 120})
    e.call("track.add", {"name": "T"})
    e.call("device.add", {"track": "T", "device": "sfz", "sfz": r["sfz"]})
    notes = [{"pitch": p, "start": i * 4.0, "length": 3.0, "velocity": 100} for i, p in enumerate(PITCHES)]   # 120bpm: 4박=2초
    e.call("clip.add_midi", {"track": "T", "start": 0, "length": 4.0 * len(PITCHES), "notes": notes})
    CACHE.mkdir(parents=True, exist_ok=True)
    wav = CACHE / f"_{instrument}_notes.wav"
    e.call("render", {"path": str(wav), "tracks": ["T"], "tail": 1.0, "sample_rate": SR})
    e.close()
    return wav


def _analyze(y, sr):
    import pyworld as pw
    f0, t = pw.harvest(y.astype(np.float64), sr, f0_floor=50, f0_ceil=2200, frame_period=FRAME_MS)
    sp = pw.cheaptrick(y.astype(np.float64), f0, t, sr)
    ap = pw.d4c(y.astype(np.float64), f0, t, sr)
    return f0, sp, ap


def _harmonics(sp_row, f0, sr):
    """스펙트럼 포락선 한 프레임 → 배음 k=1..K 진폭(최대 1)."""
    bins = len(sp_row)
    freqs = np.arange(bins) * (sr / 2) / (bins - 1)
    h = np.zeros(K)
    for k in range(1, K + 1):
        f = k * f0
        if f >= sr / 2:
            break
        h[k - 1] = np.sqrt(np.interp(f, freqs, sp_row))
    return h / (h.max() + 1e-12)


def template(instrument, force=False):
    CACHE.mkdir(parents=True, exist_ok=True)
    npz = CACHE / f"{instrument}.npz"
    if npz.exists() and not force:
        d = np.load(npz, allow_pickle=True)
        return {k: d[k] for k in d.files}
    wav = _render_notes(instrument)
    y, sr = sf.read(str(wav), dtype="float32", always_2d=True)
    y = y.mean(1)
    pitches, harm, noise, attack, noise_shape = [], [], [], [], []
    for i, p in enumerate(PITCHES):
        seg = y[int(i * 2.0 * sr): int((i * 2.0 + 1.9) * sr)]
        if np.abs(seg).max() < 1e-3:
            continue
        f0, sp, ap = _analyze(seg, sr)
        voiced = f0 > 0
        if voiced.sum() < 20:
            continue
        rms = librosa.feature.rms(y=seg, frame_length=1024, hop_length=HOP)[0]
        ldb = 20 * np.log10(rms + 1e-9)
        n = min(len(f0), len(ldb))
        sus = slice(int(0.25 * 1000 / FRAME_MS), int(0.9 * 1000 / FRAME_MS))     # 0.25~0.9초 = 지속부
        rows = [_harmonics(sp[j], f0[j], sr) for j in range(*sus.indices(n)) if f0[j] > 0]
        if not rows:
            continue
        H = np.median(np.array(rows), 0)
        # 노이즈: 비주기 성분의 비율(지속부 평균)과 대역 모양
        apm = ap[sus].mean(0)
        spm = sp[sus].mean(0)
        edges = np.linspace(0, len(apm), NOISE_BANDS + 1).astype(int)
        shape = np.array([np.sqrt((spm * apm)[a:b].mean() + 1e-12) for a, b in zip(edges[:-1], edges[1:])])
        noise_ratio = float(np.clip(np.sqrt((spm * apm).sum() / (spm.sum() + 1e-12)), 0, 1))
        # 어택: 처음 0.3초 라우드니스 곡선(지속부 대비 dB)
        ref = np.median(ldb[sus])
        att = ldb[: int(0.3 * 1000 / FRAME_MS)] - ref
        att = np.pad(att, (0, max(0, 60 - len(att))), constant_values=0)[:60]
        pitches.append(p); harm.append(H); noise.append(noise_ratio); attack.append(att); noise_shape.append(shape / (shape.max() + 1e-12))
    if len(pitches) < 3:
        raise RuntimeError(f"{instrument}: 분석할 음이 너무 적음({len(pitches)}) — 악기 음역 밖이거나 샘플이 비어 있음")
    out = {"pitches": np.array(pitches, dtype=np.float32), "harm": np.array(harm, dtype=np.float32),
           "noise": np.array(noise, dtype=np.float32), "attack": np.array(attack, dtype=np.float32),
           "noise_shape": np.array(noise_shape, dtype=np.float32), "instrument": np.array(instrument)}
    np.savez(npz, **out)
    try:
        wav.unlink()
    except OSError:
        pass
    return out


# ─────────────────────────── 변환 ───────────────────────────
def _interp_rows(tpl, key, midi):
    """음고(MIDI 실수)에 따라 틀의 행을 선형 보간."""
    p = tpl["pitches"]
    rows = tpl[key]
    midi = np.clip(midi, p[0], p[-1])
    i = np.searchsorted(p, midi) - 1
    i = np.clip(i, 0, len(p) - 2)
    w = (midi - p[i]) / (p[i + 1] - p[i] + 1e-9)
    return rows[i] * (1 - w) + rows[i + 1] * w


def transfer(src, instrument, out, semitones=0.0, breath=1.0, strength=1.0, vibrato_keep=1.0, gain_db=0.0):
    """src(선율 오디오) → instrument 음색. semitones: 이조(옥타브 = ±12). breath: 숨·노이즈 양(0~2).
    strength: 세기 추종(1 = 입력 다이내믹 그대로, 0.5 = 절반으로 눌러 고르게)."""
    tpl = template(instrument)
    y, sr = sf.read(str(src), dtype="float32", always_2d=True)
    y = y.mean(1)
    if sr != SR:
        y = librosa.resample(y, orig_sr=sr, target_sr=SR)
        sr = SR
    f0, _, ap_src = _analyze(y, sr)
    rms = librosa.feature.rms(y=y, frame_length=1024, hop_length=HOP)[0]
    n = min(len(f0), len(rms))
    f0, rms = f0[:n], rms[:n]
    voiced = f0 > 0
    # 음정: 반음 단위로 틀을 고르고, 미세 음정(비브라토·글라이드)은 그대로
    midi = np.where(voiced, librosa.hz_to_midi(np.maximum(f0, 1e-3)) + semitones, 0)
    if vibrato_keep != 1.0 and voiced.any():
        sm = signal.medfilt(midi, 31)
        midi = np.where(voiced, sm + (midi - sm) * vibrato_keep, 0)
    f0_out = np.where(voiced, librosa.midi_to_hz(np.maximum(midi, 1)), 0.0)
    # 세기: 입력 라우드니스(dB) → 진폭. strength 로 다이내믹 폭 조절
    ldb = 20 * np.log10(rms + 1e-9)
    top = np.percentile(ldb[voiced], 97) if voiced.any() else 0
    amp = 10 ** (((ldb - top) * strength) / 20)
    amp = np.where(voiced, np.clip(amp, 0, 1.2), 0)
    # 어택: 유성 시작점 또는 6 dB 이상 빠른 상승
    onset = np.zeros(n, bool)
    for j in range(1, n):
        if voiced[j] and (not voiced[j - 1] or (ldb[j] - ldb[max(0, j - 10)] > 6 and ldb[j] - ldb[j - 1] > 1.5)):
            onset[j] = True
    att_gain = np.zeros(n)
    for j in np.where(onset)[0]:
        att = _interp_rows(tpl, "attack", midi[j])
        L = min(len(att), n - j)
        att_gain[j: j + L] = np.maximum(att_gain[j: j + L], att[:L])
    amp = amp * 10 ** (att_gain / 20)
    # 배음 진폭 프레임열 (n × K)
    H = np.array([_interp_rows(tpl, "harm", m) if v else np.zeros(K) for m, v in zip(midi, voiced)], dtype=np.float32)
    # 프레임 → 샘플 보간
    N = n * HOP
    tf = np.arange(n) * HOP
    ts = np.arange(N)
    f0s = np.interp(ts, tf, f0_out)
    amps = np.interp(ts, tf, amp)
    # 무성 구간에서 f0 가 0 으로 뚝 떨어지지 않게: 마지막 유성 f0 유지(진폭이 0 이라 안 들림)
    last = 0.0
    for j in range(n):
        if f0_out[j] > 0:
            last = f0_out[j]
        elif last > 0:
            f0_out[j] = last
    f0s = np.interp(ts, tf, f0_out)
    phase = np.cumsum(2 * np.pi * f0s / sr)
    outv = np.zeros(N, np.float32)
    nyq = sr / 2
    # 배음 합성(블록 단위로 메모리 제한)
    B = 48000 * 4
    for s0 in range(0, N, B):
        s1 = min(N, s0 + B)
        ph = phase[s0:s1]
        fr = (np.arange(s0, s1) / HOP)
        j0 = np.clip(fr.astype(int), 0, n - 1); j1 = np.clip(j0 + 1, 0, n - 1); w = (fr - j0)[:, None]
        Hs = H[j0] * (1 - w) + H[j1] * w                      # (len, K)
        fk = f0s[s0:s1][:, None] * np.arange(1, K + 1)[None, :]
        Hs = np.where(fk < nyq, Hs, 0)                           # 에일리어싱 방지
        outv[s0:s1] = (np.sin(ph[:, None] * np.arange(1, K + 1)[None, :]) * Hs).sum(1) * amps[s0:s1]
    # 숨·노이즈: 틀의 노이즈 비율 × 입력의 비주기성 × 세기, 대역 모양으로 필터
    nr = np.array([float(_interp_rows(tpl, "noise", m)) if v else 0.3 for m, v in zip(midi, voiced)])
    ap_mean = ap_src[:n].mean(1) if ap_src.ndim == 2 else np.ones(n)
    nlev = np.interp(ts, tf, nr * np.clip(ap_mean, 0.2, 1.0) * amp) * breath
    onset_s = np.zeros(N)
    for j in np.where(onset)[0]:                                   # 어택 숨(짧은 노이즈 돌풍)
        a, b = j * HOP, min(N, j * HOP + int(0.06 * sr))
        onset_s[a:b] = np.maximum(onset_s[a:b], np.linspace(1, 0, b - a) * amp[j])
    shape = _interp_rows(tpl, "noise_shape", float(np.median(midi[voiced])) if voiced.any() else 60)
    freqs = np.linspace(0, 1, NOISE_BANDS)
    fir = signal.firwin2(255, np.concatenate([[0], freqs[1:-1], [1]]), np.concatenate([[shape[0]], shape[1:-1], [shape[-1] * 0.5]]))
    noise = signal.lfilter(fir, 1.0, np.random.default_rng(0).standard_normal(N).astype(np.float32))
    noise = noise / (np.abs(noise).max() + 1e-9)
    outv += (noise * (nlev * 0.35 + onset_s * 0.8 * breath)).astype(np.float32)
    # 마무리: 살짝 공기감 + 정규화
    outv = outv / (np.abs(outv).max() + 1e-9) * 0.85 * 10 ** (gain_db / 20)
    sf.write(str(out), np.stack([outv, outv], 1), sr, subtype="PCM_24")
    return {"out": str(out), "instrument": instrument, "seconds": round(N / sr, 2), "voiced_ratio": round(float(voiced.mean()), 2),
            "note": "음정·세기·비브라토는 입력 그대로, 음색만 바뀜. 입력이 다성(화음)이면 안 됨 — 선율 하나만"}
