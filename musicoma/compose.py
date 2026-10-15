"""작곡 도우미 — 코드 위의 선율. Claude 가 직접 멜로디를 쓰는 게 기본이고, 이건 초안/기본값용.

규칙(보컬처럼 노래하는 선):
- 강박(1·3박)엔 코드톤, 약박엔 음계 안 경과음/이웃음
- 도약 뒤엔 반대 방향 순차, 음역은 한 옥타브 반 안
- 프레이즈 = 2마디 질문 + 2마디 대답, 대답은 으뜸화음 쪽으로 착지
"""
import random

from . import theory

# 한 마디(4박) 리듬 템플릿: (시작박, 길이)
RHYTHMS = {
    "ballad": [[(0, 1.5), (1.5, 0.5), (2, 2)], [(0.5, 1), (1.5, 1), (2.5, 1.5)], [(0, 3), (3, 1)],
               [(0, 1), (1, 1), (2, 1.5), (3.5, 0.5)]],
    "soul": [[(0, 0.75), (0.75, 0.75), (1.5, 1), (2.5, 1.5)], [(0.5, 0.5), (1, 1), (2, 0.5), (2.5, 1.5)],
             [(0, 2), (2.5, 0.5), (3, 1)], [(0.25, 0.75), (1, 0.5), (1.5, 2.5)]],
    "pop": [[(0, 0.5), (0.5, 0.5), (1, 1), (2, 1), (3, 1)], [(0, 1.5), (1.5, 1.5), (3, 1)],
            [(0.5, 0.5), (1, 0.5), (1.5, 0.5), (2, 2)], [(0, 4)]],
}


def lead_melody(chords, durations, key="C", mode="major", low=60, high=79, style="soul", seed=0, velocity=92):
    rnd = random.Random(seed)
    scale = theory.scale_notes(key, mode, low, high)
    total = sum(durations)
    # 코드 타임라인
    timeline, t = [], 0.0
    for c, d in zip(chords, durations):
        root, ivs, _ = theory.parse_chord(c)
        timeline.append((t, t + d, {(root + i) % 12 for i in ivs}))
        t += d

    def chord_tones_at(x):
        for a, b, tones in timeline:
            if a <= x < b:
                return tones
        return timeline[-1][2]

    notes, prev = [], rnd.choice([n for n in scale if 64 <= n <= 72] or scale)
    bars = int(total // 4)
    templates = RHYTHMS.get(style, RHYTHMS["soul"])
    tonic_pc = theory.pc(key)
    for bar in range(bars):
        tpl = templates[rnd.randrange(len(templates))] if bar % 2 == 0 else templates[(bar * 3 + seed) % len(templates)]
        last_bar_of_phrase = bar % 4 == 3
        for k, (off, ln) in enumerate(tpl):
            x = bar * 4 + off
            strong = off in (0, 2) or ln >= 1.5
            tones = chord_tones_at(x)
            cands = [n for n in scale if abs(n - prev) <= (7 if strong else 3)]
            if strong:
                cands = [n for n in cands if n % 12 in tones] or [n for n in scale if n % 12 in tones]
            if last_bar_of_phrase and k == len(tpl) - 1:
                cands = [n for n in scale if n % 12 in (tonic_pc, (tonic_pc + 4) % 12, (tonic_pc + 7) % 12)
                         and abs(n - prev) <= 7] or cands
            # 순차 선호, 큰 도약 뒤엔 반대 방향
            last_jump = notes[-1]["pitch"] - notes[-2]["pitch"] if len(notes) >= 2 else 0
            def cost(n):
                c = abs(n - prev) * (0.6 if strong else 1.0)
                if abs(last_jump) >= 5 and (n - prev) * last_jump > 0:
                    c += 6
                if n == prev:
                    c += 1.5
                return c + rnd.random() * 2.5
            n = min(cands, key=cost)
            notes.append({"pitch": n, "start": round(x, 4), "length": round(ln * 0.94, 4),
                          "velocity": velocity + (6 if strong else -6) + rnd.randint(-5, 5)})
            prev = n
    return notes


def to_text(notes):
    """노트 → 멜로디 표기(설계서에 넣어 사람이/Claude 가 손보기 쉽게)."""
    out, t = [], 0.0
    for n in sorted(notes, key=lambda n: n["start"]):
        if n["start"] > t + 1e-6:
            out.append(f"r:{round(n['start'] - t, 3)}")
        name = theory.note_name(n["pitch"]).replace("-", "")
        gap = n["length"] / 0.94
        out.append(f"{name}:{round(gap, 3)}")
        t = n["start"] + gap
    return " ".join(out)
