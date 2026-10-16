"""보컬 스타일 프리셋 — 설계서 vocal 파트의 "style" 한 단어로 음악에 맞는 보컬 성격을 바꾼다(10-17).

    "natural"   사람처럼(기본): 포르타멘토·스쿱·늦은 비브라토·흔들림
    "vocaloid"  보컬로이드 느낌: 음정을 격자처럼 딱 맞추고(비브라토·미끄러짐 없음), 포먼트 살짝 위, 밝게, 더블링으로 '합성' 광택
    "robot"     더 기계적으로: 비브라토 0 + 포먼트 더 위 + 숨 0 + 비트크러시 살짝
    "whisper"   속삭임: 숨 많이, 어둡게
    "idol"      아이돌 팝: 자연스럽되 비브라토 얕고 빠르게, 밝게, 더블링

서브컬처(보컬로이드·동인 음악) 요청에 AI 가 바로 쓸 수 있게 — 모델을 바꾸는 게 아니라 같은 가수에게 '부르는 방식'과 후처리만 바꾼다.
"""
import numpy as np
import soundfile as sf

from . import voice_character, dsp

# human_f0 인자(음정 곡선) + voice_character.apply 인자(음색) + 후처리
STYLES = {
    "natural": {"humanize": None, "character": {}, "post": {}},
    "vocaloid": {"humanize": {"vibrato_cents": 0, "glide_ms": 8, "drift_cents": 0, "scoop_cents": 0, "fall_cents": 0},
                 "character": {"formant": 1.5, "brightness": 2.5, "vibrato": 0.0},
                 "post": {"double_ms": 14, "double_db": -7, "air_db": 2.0}},
    "robot": {"humanize": {"vibrato_cents": 0, "glide_ms": 0, "drift_cents": 0, "scoop_cents": 0, "fall_cents": 0},
              "character": {"formant": 3.0, "brightness": 1.0, "breath": 0.0},
              "post": {"bitcrush_bits": 10, "double_ms": 9, "double_db": -4}},
    "whisper": {"humanize": {"vibrato_cents": 10, "drift_cents": 14}, "character": {"breath": 0.7, "brightness": -2.0}, "post": {}},
    "idol": {"humanize": {"vibrato_cents": 18, "vibrato_hz": 6.2, "vibrato_delay": 0.18, "scoop_cents": 20},
             "character": {"brightness": 1.5}, "post": {"double_ms": 18, "double_db": -9}},
}


def names():
    return list(STYLES)


def humanize_for(style, user=None):
    """설계서에 humanize 를 따로 주면 그게 우선."""
    if user is not None:
        return user
    return (STYLES.get(style or "natural") or STYLES["natural"])["humanize"]


def _post(path, p, seed=0):
    y, sr = sf.read(str(path), dtype="float32", always_2d=True)
    m = y.mean(1)
    if p.get("bitcrush_bits"):
        m = dsp.bitcrush(m, bits=p["bitcrush_bits"]) if hasattr(dsp, "bitcrush") else m
    L, R = m.copy(), m.copy()
    if p.get("double_ms"):                       # 더블링: 한쪽은 몇 ms 늦게 + 살짝 음정 흔들린 복사본 — 합성 보컬 특유의 광택
        d = int(sr * p["double_ms"] / 1000)
        g = 10 ** (p.get("double_db", -8) / 20)
        dup = np.concatenate([np.zeros(d, np.float32), m[:-d]]) if d < len(m) else m
        L = L + g * dup
        R = R + g * np.concatenate([np.zeros(d // 2, np.float32), m[:-(d // 2)]]) if d // 2 < len(m) else R
    if p.get("air_db"):
        L = dsp.shelf(L, sr, 8000, float(p["air_db"]), kind="high")
        R = dsp.shelf(R, sr, 8000, float(p["air_db"]), kind="high")
    out = np.stack([L, R], 1)
    out = out / (np.abs(out).max() + 1e-9) * 0.89
    sf.write(str(path), out, sr, subtype="PCM_24")
    return str(path)


def apply(style, wav_path, seed=0):
    """노래 파일에 스타일의 음색·후처리를 입힌다(같은 파일에 덮어씀). natural 은 손대지 않는다."""
    st = STYLES.get(style or "natural")
    if not st or (not st["character"] and not st["post"]):
        return str(wav_path)
    if st["character"]:
        voice_character.apply(wav_path, wav_path, seed=seed, **st["character"])
    if st["post"]:
        _post(wav_path, st["post"], seed)
    return str(wav_path)
