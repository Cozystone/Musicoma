"""보컬 가이드 멜로디 — 가사 한 줄 → 음절 수만큼의 음(리듬·음높이). AI 보컬(lego)에게 '부를 거리'를 들려주는 용도.
10-15 측정: 가이드 멜로디를 넣으면 가사 정확도가 크게 오른다(12 테이크 중 7개 통과, 최고 오류율 0) — 이전 16 중 3.

    line_notes("One more exit, baby, one more mile", start=0, bars=2, motif="C5:.5 D5:.5 F5:1", key="F major")
리듬: 8분 위주, 줄 첫 음은 반 박 뒤(픽업), 마지막 음절은 남는 길이를 가져감(숨 반 박 남김).
음높이: 동기 윤곽에서 출발, 줄마다 조금씩 다르게(2·4번째 줄은 한 칸 위), 강박은 화음 음(motif.fit).
"""
from . import motif as motif_mod
from .lyrics import syllables


def line_notes(line, start, bars, motif, key, chords=None, lift=0, register=(62, 79)):
    n = max(1, syllables(line))
    beats = bars * 4
    pickup = 0.5
    step = 0.5 if n * 0.5 <= beats - pickup - 1.0 else 0.25
    durs = [step] * (n - 1)
    last = max(step, beats - pickup - step * (n - 1) - 0.5)
    durs.append(last)
    base = [x["pitch"] for x in motif_mod.parse(motif)]
    lo, hi = register
    notes, t = [], start + pickup
    for k, d in enumerate(durs):
        p = base[k % len(base)]
        p = motif_mod.op([{"pitch": p, "start": 0, "length": 1, "velocity": 90}], f"up:{lift}" if lift >= 0 else f"down:{-lift}", key)[0]["pitch"] if lift else p
        while p > hi:
            p -= 12
        while p < lo:
            p += 12
        notes.append({"pitch": p, "start": round(t, 4), "length": round(d * 0.92, 4), "velocity": 90})
        t += d
    if chords:
        notes = motif_mod.fit(notes, chords, key)
    return notes


def section_notes(text, start_beat, bars, motif, key, chords=None):
    """구간 가사(줄바꿈) → 노트(곡 박 기준). 줄마다 같은 길이로 나누고, 짝수 줄은 한 칸 위."""
    lines = [l for l in text.splitlines() if l.strip()]
    if not lines:
        return []
    per = bars / len(lines)
    out = []
    for i, l in enumerate(lines):
        s = start_beat + i * per * 4
        ch = [(a - s, b - s, c) for a, b, c in chords] if chords else None
        out += [{**n, "start": round(n["start"] + s, 4)} for n in
                line_notes(l, 0, per, motif, key, ch, lift=1 if i % 2 else 0)]
    return out


def synth(notes, bpm, sr, length):
    """가이드용 부드러운 건반 소리(사인 + 2배음, 짧은 감쇠). 최종 믹스에는 안 들어간다."""
    import numpy as np
    spb = 60.0 / bpm
    out = np.zeros(length, np.float32)
    for n in notes:
        f = 440 * 2 ** ((n["pitch"] - 69) / 12)
        a = int(n["start"] * spb * sr)
        L = int(n["length"] * spb * sr)
        if a >= length or L <= 0:
            continue
        t = np.arange(min(L, length - a)) / sr
        env = np.minimum(1, t / 0.01) * np.exp(-t * 1.5)
        out[a:a + len(t)] += ((0.5 * np.sin(2 * np.pi * f * t) + 0.2 * np.sin(4 * np.pi * f * t)) * env).astype(np.float32)
    return out
