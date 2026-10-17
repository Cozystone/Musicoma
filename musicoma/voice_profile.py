"""사용자 목소리 등록 — 음역대·편한 음역·밝기를 재서 곡의 조성을 거기에 맞춘다. 10-17 외부 피드백:
"딸깍으로 사용자 목소리를 프로그램에 등록하면 맞는 음역대나 피치를 분석해서".

register(name, wav)  → sounds/voices/<name>/profile.json  (+ clone=True 면 노래하는 목소리로도 등록: voice.add_voice_aligned)
fit(name, notes)     → 멜로디가 편한 음역에 들어오는 이조(반음)와 그때의 조성
"""
import json
from pathlib import Path

import numpy as np
import soundfile as sf
import librosa

from . import theory
from .voice_design import VOICES


def _analyze(wav):
    y, sr = sf.read(str(wav), dtype="float32", always_2d=True)
    mono = y.mean(1)
    mono, _ = librosa.effects.trim(mono, top_db=35)
    if len(mono) < sr * 2:
        raise ValueError("녹음이 2초보다 짧아요 — 편하게 10~20초 불러 주세요(아무 노래나, 낮은 음부터 높은 음까지)")
    f0, voiced, _ = librosa.pyin(mono, fmin=60, fmax=1200, sr=sr, frame_length=2048, hop_length=256)
    f0 = f0[voiced & np.isfinite(f0)] if f0 is not None else np.array([])
    if len(f0) < 50:
        raise ValueError("음높이를 거의 못 잡았어요 — 말이 아니라 노래(음을 끌며)로 불러 주세요")
    midi = librosa.hz_to_midi(f0)
    p = {k: float(np.percentile(midi, v)) for k, v in (("p5", 5), ("p20", 20), ("p50", 50), ("p80", 80), ("p95", 95))}
    cent = librosa.feature.spectral_centroid(y=mono, sr=sr)[0]
    # 음정 안정도: 프레임 음높이가 반음 격자에서 얼마나 떨리는지(센트 표준편차의 중앙값) — 튜닝 세기 추천에 씀
    dev = (midi - np.round(midi)) * 100
    return {
        "sample_rate": sr, "seconds": round(len(mono) / sr, 1), "voiced_ratio": round(float(np.mean(voiced)), 2),
        "range_midi": [round(p["p5"], 1), round(p["p95"], 1)], "comfortable_midi": [round(p["p20"], 1), round(p["p80"], 1)],
        "median_midi": round(p["p50"], 1),
        "range": [theory.note_name(int(round(p["p5"]))), theory.note_name(int(round(p["p95"])))],
        "comfortable": [theory.note_name(int(round(p["p20"]))), theory.note_name(int(round(p["p80"])))],
        "median": theory.note_name(int(round(p["p50"]))),
        "brightness_hz": int(np.median(cent)),
        "pitch_scatter_cents": round(float(np.std(dev)), 1),
        "voice_type": _voice_type(p["p50"]),
    }


def _voice_type(median_midi):
    # 대략의 성부 — 중앙 음높이 기준(남성 테너 ~C4 이하 중앙, 여성 알토 ~G4 안팎, 소프라노 그 위)
    if median_midi < 55:
        return "낮은 남성(바리톤·베이스)"
    if median_midi < 62:
        return "남성(테너)"
    if median_midi < 69:
        return "낮은 여성(알토) / 높은 남성"
    return "여성(소프라노·메조)"


def register(name, wav, clone=False, log=print):
    d = VOICES / name
    d.mkdir(parents=True, exist_ok=True)
    prof = _analyze(wav)
    prof["name"] = name
    prof["source"] = str(Path(wav).resolve())
    (d / "profile.json").write_text(json.dumps(prof, ensure_ascii=False, indent=1), encoding="utf-8")
    log(f"[voice] {name}: 음역 {prof['range'][0]}~{prof['range'][1]} · 편한 음역 {prof['comfortable'][0]}~{prof['comfortable'][1]} "
        f"· 중앙 {prof['median']} · {prof['voice_type']} · 음정 흔들림 {prof['pitch_scatter_cents']}센트")
    if clone:
        from . import voice
        try:
            r = voice.add_voice_aligned(name, wav)
            prof["clone"] = str(r)
            (d / "profile.json").write_text(json.dumps(prof, ensure_ascii=False, indent=1), encoding="utf-8")
        except Exception as ex:
            prof["clone_error"] = f"{type(ex).__name__}: {ex}"
    return prof


def load(name):
    p = VOICES / name / "profile.json"
    if not p.exists():
        raise FileNotFoundError(f"등록된 목소리 없음: {name} (voice_register 로 먼저)")
    return json.loads(p.read_text(encoding="utf-8"))


def profiles():
    return [json.loads(p.read_text(encoding="utf-8")) for p in VOICES.glob("*/profile.json")]


def fit(name, notes, key=None):
    """notes: [{"pitch": midi, ...}] 멜로디. 편한 음역(p20~p80) 안에 가장 많이 들어오는 이조를 찾는다(±12반음).
    반환: {"transpose", "key_after", "in_comfortable", "in_range", "lowest", "highest"}"""
    prof = load(name)
    pitches = np.array([n["pitch"] for n in notes if "pitch" in n], dtype=float)
    if not len(pitches):
        raise ValueError("멜로디 음표가 없음")
    lo, hi = prof["comfortable_midi"]
    rlo, rhi = prof["range_midi"]
    best = None
    for t in range(-12, 13):
        p = pitches + t
        comf = float(np.mean((p >= lo) & (p <= hi)))
        inr = float(np.mean((p >= rlo) & (p <= rhi)))
        score = comf + 0.5 * inr - 0.01 * abs(t)
        if best is None or score > best[0]:
            best = (score, t, comf, inr)
    _, t, comf, inr = best
    return {"voice": name, "transpose": t, "key_after": theory.transpose_key(key, t) if key else None,
            "in_comfortable": round(comf, 2), "in_range": round(inr, 2),
            "lowest": theory.note_name(int(pitches.min() + t)), "highest": theory.note_name(int(pitches.max() + t)),
            "comfortable": prof["comfortable"], "range": prof["range"]}
