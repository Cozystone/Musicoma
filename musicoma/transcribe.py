"""샘플에서 음악 정보 뽑기 — 베이스 라인, 코드. 그 위에 얹을 악기가 샘플과 어긋나지 않게."""
import numpy as np
import librosa

from .theory import NAMES_FLAT

CHORD_TEMPLATES = {
    "": [0, 4, 7], "m": [0, 3, 7], "7": [0, 4, 7, 10], "maj7": [0, 4, 7, 11], "m7": [0, 3, 7, 10],
    "sus4": [0, 5, 7], "dim": [0, 3, 6], "m7b5": [0, 3, 6, 10], "9": [0, 4, 7, 10, 14], "maj9": [0, 4, 7, 11, 14],
    "m9": [0, 3, 7, 10, 14],
}


def _load_mono(path, sr=22050):
    y, _ = librosa.load(str(path), sr=sr, mono=True)
    return y, sr


def bass_notes(path, bpm, beats_per_bar=4, grid=0.5, fmin=30, fmax=300):
    """베이스 스템 → 박 단위 노트 [{pitch, start, length, velocity}]. grid=0.5 → 8분 격자."""
    y, sr = _load_mono(path)
    f0, voiced, prob = librosa.pyin(y, fmin=fmin, fmax=fmax, sr=sr, frame_length=4096, hop_length=512)
    times = librosa.times_like(f0, sr=sr, hop_length=512)
    rms = librosa.feature.rms(y=y, frame_length=4096, hop_length=512)[0]
    beat_sec = 60 / bpm
    step = grid * beat_sec
    n_steps = int(len(y) / sr / step)
    cells = []
    for i in range(n_steps):
        m = (times >= i * step) & (times < (i + 1) * step) & voiced & (prob > 0.3)
        if m.sum() < 2:
            cells.append(None)
            continue
        midi = int(round(np.median(librosa.hz_to_midi(f0[m]))))
        vel = int(np.clip(60 + 600 * np.median(rms[m]), 60, 115))
        cells.append((midi, vel))
    notes = []
    for i, c in enumerate(cells):
        if c is None:
            continue
        if notes and notes[-1]["pitch"] == c[0] and abs(notes[-1]["start"] + notes[-1]["length"] - i * grid) < 1e-6:
            notes[-1]["length"] = round(notes[-1]["length"] + grid, 4)
        else:
            notes.append({"pitch": c[0], "start": round(i * grid, 4), "length": grid, "velocity": c[1]})
    for n in notes:
        while n["pitch"] > 47:
            n["pitch"] -= 12
        while n["pitch"] < 28:
            n["pitch"] += 12
    return notes


def chords(path, bpm, beats_per_chord=2, bass_path=None):
    """오디오 → 코드 이름 목록(beats_per_chord 박마다 하나). 크로마 템플릿 매칭 + 베이스로 근음 보정."""
    y, sr = _load_mono(path)
    hop = 2048
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr, hop_length=hop)
    times = librosa.times_like(chroma, sr=sr, hop_length=hop)
    bass_chroma = None
    if bass_path:
        yb, _ = _load_mono(bass_path)
        bass_chroma = librosa.feature.chroma_cqt(y=yb, sr=sr, hop_length=hop)
    seg = beats_per_chord * 60 / bpm
    out = []
    for i in range(int(len(y) / sr / seg)):
        m = (times >= i * seg) & (times < (i + 1) * seg)
        if not m.any():
            continue
        c = chroma[:, m].mean(axis=1)
        c = c / (c.max() + 1e-9)
        bass_pc = int(np.argmax(bass_chroma[:, m[: bass_chroma.shape[1]]].mean(axis=1))) if bass_chroma is not None else None
        best = None
        for root in range(12):
            for q, ivs in CHORD_TEMPLATES.items():
                tpl = np.zeros(12)
                for k in ivs:
                    tpl[(root + k) % 12] = 1
                score = float(c @ tpl / np.sqrt(len(ivs))) - 0.15 * float(c @ (1 - tpl))
                if bass_pc is not None and bass_pc == root:
                    score += 0.25
                if q in ("9", "maj9", "m9"):
                    score -= 0.05      # 텐션은 확실할 때만
                if best is None or score > best[0]:
                    best = (score, root, q)
        out.append({"beat": round(i * beats_per_chord, 2), "chord": NAMES_FLAT[best[1]] + best[2],
                    "confidence": round(best[0], 2)})
    return out


def simplify(chord_list):
    """연속 같은 코드 합치기 → [(chord, start_beat, length_beats)]"""
    res = []
    for c in chord_list:
        if res and res[-1][0] == c["chord"]:
            continue
        res.append([c["chord"], c["beat"], None])
    for i, r in enumerate(res):
        r[2] = (res[i + 1][1] - r[1]) if i + 1 < len(res) else None
    return [tuple(r) for r in res]

