"""연주하는 랩 — 말소리(또렷함) + 작곡한 플로우(리듬·음높이) → SVC 로 '부르듯' 랩. (10-15 본인: "나레이션 같다, 노래 부르는 느낌이 아니다")

    flow_line("Woke up in the city with the vinyl on repeat", bpm=88, base_midi=50)  → 음절별 노트 + 가사 토큰
    rap_flow(voice, lines, bpm, out, prosody=0.35)                                   → 한 벌스 wav

플로우 규칙(기본): 한 줄 = 4박(16칸). 음절은 16분 위주, 줄 끝 운은 길게, 마지막 1칸은 숨.
강세(내용어 첫 음절·운)는 정박/8분 위에 오도록 밀고 당긴다. 음높이 = 목소리 평소 음높이 둘레 좁은 폭(래퍼의 '멜로디'),
강세 +2, 줄 끝은 내림(문장) 또는 올림(이어지는 줄). prosody = 말소리 원래 억양을 섞는 비율(0 = 악보대로, 오토튠처럼 들림).
"""
import re

import numpy as np

from .lyrics import syllables_en

FUNCTION_WORDS = set("a an the and or but to of in on at for with from by is are was were be been am i you he she it we they "
                     "my your his her its our their me him us them this that these those so up as if then than".split())


def split_word(w):
    """영어 단어를 음절 조각으로(철자 기준 근사 — SVC 는 개수만 정확하면 된다)."""
    clean = re.sub(r"[^A-Za-z']", "", w)
    n = syllables_en(clean) if clean else 1
    if n <= 1 or len(clean) < 3:
        return [w]
    vow = [m.start() for m in re.finditer(r"[aeiouyAEIOUY]+", clean)]
    cuts = []
    for k in range(1, n):
        if k >= len(vow):
            break
        a = vow[k - 1]
        b = vow[k]
        # 모음 사이 자음 덩어리의 가운데에서 자른다(VCCV → VC-CV, VCV → V-CV)
        cons = b - a
        cut = b - 1 if cons <= 2 else b - cons // 2
        cuts.append(max(1, cut))
    parts, prev = [], 0
    for c in cuts:
        if c > prev:
            parts.append(clean[prev:c])
            prev = c
    parts.append(clean[prev:])
    parts = [p for p in parts if p]
    return [p + "-" for p in parts[:-1]] + [parts[-1]]


def flow_line(text, bpm, base_midi, start_beat=0.0, beats=4, seed=0, end="fall", grid=0.25):
    """한 줄 → (노트들, 토큰들). 노트 시작은 start_beat 기준 박."""
    rnd = np.random.default_rng(seed)
    words = text.split()
    toks, stress = [], []
    for w in words:
        parts = split_word(w)
        content = re.sub(r"[^a-z']", "", w.lower()) not in FUNCTION_WORDS
        for j, p in enumerate(parts):
            toks.append(p)
            stress.append(content and j == 0)
    n = len(toks)
    slots = int(round(beats / grid))
    breath = 1
    usable = slots - breath
    # 기본: 모두 16분, 마지막(운) 음절이 남는 칸을 가져간다
    durs = [grid] * n
    extra = usable * grid - grid * n
    if extra < 0:                                    # 빽빽: 약박 음절부터 32분으로
        need = -extra
        for i in range(n - 1):
            if need <= 1e-9:
                break
            if not stress[i]:
                durs[i] = grid / 2
                need -= grid / 2
        for i in range(n - 1):
            if need <= 1e-9:
                break
            if durs[i] == grid:
                durs[i] = grid / 2
                need -= grid / 2
    else:
        durs[-1] += extra * 0.6                      # 운을 길게
        # 나머지 여유는 강세 음절 앞에 반 칸씩 — 강세가 박 쪽으로 밀리게
        spare = extra * 0.4
        for i in range(1, n - 1):
            if spare < grid / 2 - 1e-9:
                break
            if stress[i]:
                durs[i - 1] += grid / 2
                spare -= grid / 2
    # 음높이: 좁은 폭의 랩 멜로디
    notes, t = [], start_beat
    last = base_midi
    for i, (tok, d) in enumerate(zip(toks, durs)):
        on_beat = abs((t - start_beat) * 2 - round((t - start_beat) * 2)) < 1e-3
        p = base_midi
        if stress[i]:
            p += 2 if on_beat else 1
        else:
            p += int(rnd.choice([0, 0, -1, 1]))
        if i == n - 1:
            p = base_midi - 2 if end == "fall" else base_midi + 3
        if abs(p - last) > 4:
            p = last + (4 if p > last else -4)
        notes.append({"pitch": int(p), "start": round(t, 4), "length": round(d * 0.98, 4), "velocity": 96 if stress[i] else 82})
        last = p
        t += d
    return notes, toks


def rap_flow(voice, lines, bpm, out, beats_per_line=4, prosody=0.35, seed=0, base_midi=None, takes=2):
    """벌스 전체를 한 번에: 줄마다 플로우를 짓고 이어 붙여 sing_svc 로 부른다."""
    from . import sing_svc, voice_design as vd
    import soundfile as sf
    import pyworld as pw
    if base_midi is None:
        y, sr = sf.read(str(vd.VOICES / voice / "design.wav"))
        y = y.mean(1) if y.ndim > 1 else y
        f0, _ = pw.harvest(y.astype(np.float64), sr, frame_period=10, f0_floor=70, f0_ceil=500)
        base_midi = int(round(69 + 12 * np.log2(np.median(f0[f0 > 0]) / 440)))
    notes, toks = [], []
    for i, line in enumerate(lines):
        text = line["text"] if isinstance(line, dict) else line
        b = line.get("beats", beats_per_line) if isinstance(line, dict) else beats_per_line
        n, t = flow_line(text, bpm, base_midi, start_beat=i * beats_per_line, beats=b, seed=seed + i,
                         end="fall" if i % 2 else "rise")
        notes += n
        toks += t
    lyrics = " ".join(toks)
    return sing_svc.sing_svc(voice, lyrics, bpm, notes=notes, out=out, lang="en", seed=seed, takes=takes,
                             prosody=prosody)
