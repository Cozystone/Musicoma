"""그루브 — 문자열 패턴 → 노트. 스윙·휴머나이즈·킷 매핑.

패턴 한 줄 = 한 마디(기본 16칸). '|' 로 마디를 이어 쓸 수 있다.
  X 강세(118)  x 보통(100)  o 고스트(48)  - 약하게(72)  1~9 세기(14*n)  . 쉼
  예) {"kick": "x.....x...x.....", "snare": "....x.......x...", "hat": "x-x-x-x-x-x-x-x-"}

swing: 0.5 = 정박, 0.54~0.58 = MPC 스윙 느낌, 0.66 = 셔플(3연)
"""
import random

GM = {
    "kick": 36, "kick2": 35, "snare": 38, "rim": 37, "sidestick": 37, "snare2": 40, "clap": 39,
    "hat": 42, "hh": 42, "closed_hat": 42, "pedal_hat": 44, "open_hat": 46, "oh": 46,
    "tom_low": 41, "tom_mid": 45, "tom_high": 48, "crash": 49, "ride": 51, "ride_bell": 53,
    "tamb": 54, "cowbell": 56, "shaker": 82, "conga_hi": 63, "conga_low": 64, "clave": 75,
}

VEL = {"X": 118, "x": 100, "-": 72, "o": 48}


def _steps(line):
    return [c for c in line.replace(" ", "") if c != "|"]


def pattern_notes(pattern, bars=1, steps_per_bar=16, beats_per_bar=4, swing=0.5, swing_unit=16,
                  humanize_ms=0.0, humanize_vel=0, bpm=90, kit=None, length=0.25, seed=0, start=0.0):
    """패턴 dict → 노트 리스트 [{pitch, start, length, velocity}] (박 단위).

    패턴 줄이 여러 마디 길이면 그대로, 1마디면 bars 만큼 반복.
    kit: 이름→노트 매핑 (기본 GM). 숫자 키도 허용.
    """
    rnd = random.Random(seed)
    kit = {**GM, **(kit or {})}
    step_beats = beats_per_bar / steps_per_bar
    notes = []
    for name, line in pattern.items():
        pitch = int(name) if str(name).isdigit() else kit.get(name)
        if pitch is None:
            raise ValueError(f"unknown drum '{name}' (kit has: {sorted(kit)})")
        steps = _steps(line)
        line_bars = max(1, round(len(steps) / steps_per_bar))
        total = max(bars, line_bars) * steps_per_bar
        for i in range(total):
            c = steps[i % len(steps)]
            if c == ".":
                continue
            vel = VEL.get(c, 14 * int(c) if c.isdigit() else 100)
            t = start + i * step_beats
            # 스윙: 스윙 단위(16분/8분) 쌍의 뒤쪽 칸을 뒤로 민다
            if swing != 0.5:
                pair = (4 / swing_unit) * 2          # 박 단위: 16분 쌍 = 0.5박, 8분 쌍 = 1박
                pos = (i * step_beats) % pair
                if abs(pos - pair / 2) < 1e-6:
                    t += (swing - 0.5) * pair
            if humanize_ms:
                t += rnd.gauss(0, humanize_ms / 1000 * bpm / 60)
            if humanize_vel:
                vel += rnd.randint(-humanize_vel, humanize_vel)
            notes.append({"pitch": pitch, "start": round(max(0.0, t), 4), "length": length,
                          "velocity": max(1, min(127, int(vel)))})
    return sorted(notes, key=lambda n: n["start"])


def chord_notes(voicings, durations, start=0.0, velocity=82, strum=0.0, humanize_vel=6, seed=0, legato=0.98,
                rhythm=None):
    """보이싱 묶음 → 노트. durations: 코드마다 박 수 (숫자 하나면 전부 같게).

    rhythm: 코드 하나 안에서 치는 위치 [(시작박, 길이박, 세기배수)] — 없으면 길게 한 번.
    """
    rnd = random.Random(seed)
    if not isinstance(durations, (list, tuple)):
        durations = [durations] * len(voicings)
    notes, t = [], start
    for v, d in zip(voicings, durations):
        hits = rhythm or [(0.0, d, 1.0)]
        for (off, ln, vm) in hits:
            if off >= d:
                continue
            for k, p in enumerate(v):
                notes.append({"pitch": p, "start": round(t + off + k * strum, 4),
                              "length": round(min(ln, d - off) * legato, 4),
                              "velocity": max(1, min(127, int(velocity * vm + rnd.randint(-humanize_vel, humanize_vel))))})
        t += d
    return notes


def bass_line(roots, durations, start=0.0, pattern=None, velocity=100, octave_jump=False, seed=0):
    """근음 목록 → 베이스. pattern: 한 코드 안 [(시작박, 길이박, 반음오프셋)]."""
    rnd = random.Random(seed)
    if not isinstance(durations, (list, tuple)):
        durations = [durations] * len(roots)
    notes, t = [], start
    for r, d in zip(roots, durations):
        hits = pattern or [(0.0, d * 0.95, 0)]
        for (off, ln, semi) in hits:
            if off >= d:
                continue
            p = r + semi + (12 if octave_jump and rnd.random() < 0.15 else 0)
            notes.append({"pitch": p, "start": round(t + off, 4), "length": round(min(ln, d - off), 4),
                          "velocity": velocity + rnd.randint(-6, 6)})
        t += d
    return notes


def shift(notes, beats=0.0, semitones=0):
    return [{**n, "start": round(n["start"] + beats, 4), "pitch": n["pitch"] + semitones} for n in notes]


def scale_velocity(notes, factor=1.0, add=0):
    return [{**n, "velocity": max(1, min(127, int(n["velocity"] * factor + add)))} for n in notes]
