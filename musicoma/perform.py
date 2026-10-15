"""연주자 모델 — 악보(노트)를 '사람이 친 것처럼' 바꾼다. Suno 처럼 소리를 생성하지 않고, 연주를 만든다.

    perform(notes, role="piano", bpm=88, feel="laid_back", intensity=0.7, seed=1)
    → {"notes": [...], "cc": [{cc, beat, value}], "bend": [{beat, value}]}

역할: piano · keys(로즈·오르간) · bass · drums · strings · pad · lead · brass · guitar · pluck
느낌(feel): straight · laid_back(뒤로) · pushed(앞으로) · loose(흔들림 큼) · tight(기계에 가깝게)
모든 시간 계산은 박 단위(4/4). ms → 박 = ms/1000 * bpm/60.
"""
import math
import random
from pathlib import Path

GM_DRUM = {"kick": {35, 36}, "snare": {37, 38, 39, 40}, "hat": {42, 44}, "open_hat": {46}, "tom": {41, 43, 45, 47, 48, 50},
           "cymbal": {49, 51, 52, 53, 55, 57, 59}, "perc": set(range(54, 83)) - {55, 57, 59}}

FEEL_MS = {  # 역할별 미세 타이밍 기본(ms): 양수 = 뒤로
    "straight": {}, "tight": {},
    "laid_back": {"snare": 14, "hat": 6, "kick": -2, "bass": 8, "keys": 10, "piano": 8, "lead": 12},
    "pushed": {"snare": -6, "hat": -8, "kick": -4, "bass": -6, "keys": -5, "lead": -6},
    "loose": {"snare": 10, "hat": 4, "bass": 6, "keys": 8, "lead": 10},
}
JITTER_MS = {"tight": 2, "straight": 5, "laid_back": 7, "pushed": 6, "loose": 12}


def _ms(ms, bpm):
    return ms / 1000.0 * bpm / 60.0


def _clamp_vel(v):
    return max(1, min(127, int(round(v))))


def _groups(notes, tol=0.02):
    """같은 시각(±tol박)에 시작하는 노트 묶음 = 화음"""
    out = []
    for n in sorted(notes, key=lambda n: (n["start"], n["pitch"])):
        if out and abs(out[-1][0]["start"] - n["start"]) <= tol:
            out[-1].append(n)
        else:
            out.append([n])
    return out


def _phrase_arc(t, bars=4, depth=0.12):
    """프레이즈(기본 4마디) 안에서 올라갔다 내려오는 세기 곡선 0.88~1.12"""
    x = (t % (bars * 4)) / (bars * 4)
    return 1.0 + depth * math.sin(math.pi * x) - depth / 2


def _expr_swell(start, length, peak=110, base=70, attack=0.35, release=0.3, steps=6):
    """한 음/화음 위의 익스프레션(CC11) 부풀기"""
    pts = []
    for i in range(steps + 1):
        x = i / steps
        if x < attack:
            v = base + (peak - base) * (x / attack)
        elif x > 1 - release:
            v = peak - (peak - base) * ((x - (1 - release)) / release)
        else:
            v = peak
        pts.append({"cc": 11, "beat": round(start + x * length, 4), "value": int(v)})
    return pts


def perform(notes, role="piano", bpm=90, feel="straight", intensity=0.7, seed=1, phrase_bars=4):
    rnd = random.Random(seed)
    role = role.lower()
    jit = _ms(JITTER_MS.get(feel, 5), bpm) * (0.6 + 0.8 * intensity)
    offsets = FEEL_MS.get(feel, {})
    cc, bend = [], []
    notes = [dict(n) for n in notes]

    def shift(n, key):
        n["start"] = max(0.0, n["start"] + _ms(offsets.get(key, 0), bpm) + rnd.gauss(0, jit))

    if role == "drums":
        for n in notes:
            kind = next((k for k, s in GM_DRUM.items() if n["pitch"] in s), "perc")
            shift(n, kind)
            if kind == "hat":                                   # 정박 강, 엇박 약 + 손의 흔들림
                on_beat = abs((n["start"] * 2) - round(n["start"] * 2)) < 0.12 and round(n["start"] * 2) % 2 == 0
                n["velocity"] = _clamp_vel(n["velocity"] * (1.0 if on_beat else 0.82) + rnd.gauss(0, 5))
            elif kind == "snare" and n["velocity"] < 60:        # 고스트는 더 작고 흔들리게
                n["velocity"] = _clamp_vel(n["velocity"] * 0.9 + rnd.gauss(0, 4))
            else:
                n["velocity"] = _clamp_vel(n["velocity"] * _phrase_arc(n["start"], phrase_bars, 0.06) + rnd.gauss(0, 3))
        # 필인(16분 연속 스네어)의 크레셴도
        snares = sorted([n for n in notes if n["pitch"] in GM_DRUM["snare"]], key=lambda n: n["start"])
        run = []
        for n in snares + [None]:
            if n and run and n["start"] - run[-1]["start"] < 0.3:
                run.append(n)
                continue
            if len(run) >= 4:
                for i, m in enumerate(run):
                    m["velocity"] = _clamp_vel(60 + (m["velocity"] - 40) * (i + 1) / len(run))
            run = [n] if n else []
        return {"notes": notes, "cc": cc, "bend": bend}

    if role in ("piano", "keys"):
        groups = _groups(notes)
        for gi, g in enumerate(groups):
            t0 = g[0]["start"]
            arc = _phrase_arc(t0, phrase_bars, 0.10 * intensity)
            roll = _ms(rnd.uniform(6, 18) * intensity, bpm) if len(g) >= 3 else 0.0
            up = rnd.random() < 0.8
            order = sorted(g, key=lambda n: n["pitch"], reverse=not up)
            for k, n in enumerate(order):
                n["start"] = max(0.0, t0 + _ms(offsets.get(role, 0), bpm) + k * roll + rnd.gauss(0, jit * 0.5))
                top = n["pitch"] == max(m["pitch"] for m in g)
                n["velocity"] = _clamp_vel(n["velocity"] * arc * (1.08 if top else 0.94) + rnd.gauss(0, 3))
            # 서스테인 페달: 새 화음 직후 밟고, 다음 화음 직전에 뗀다(레가토 페달링)
            if role == "piano":
                nxt = groups[gi + 1][0]["start"] if gi + 1 < len(groups) else t0 + max(n["length"] for n in g)
                if nxt - t0 >= 0.75:
                    cc.append({"cc": 64, "beat": round(t0 + 0.06, 4), "value": 127})
                    cc.append({"cc": 64, "beat": round(max(t0 + 0.1, nxt - 0.04), 4), "value": 0})
        if role == "keys":                                     # 로즈: 짧은 컴핑은 살짝 더 짧고 또렷하게
            for n in notes:
                if n["length"] <= 0.5:
                    n["length"] *= 0.85
        return {"notes": notes, "cc": cc, "bend": bend}

    if role == "bass":
        notes.sort(key=lambda n: n["start"])
        for i, n in enumerate(notes):
            shift(n, "bass")
            n["length"] *= rnd.uniform(0.82, 0.96) if n["length"] > 0.3 else rnd.uniform(0.7, 0.9)
            beat_pos = n["start"] % 1
            n["velocity"] = _clamp_vel(n["velocity"] * (1.0 if beat_pos < 0.1 else 0.9) * _phrase_arc(n["start"], phrase_bars, 0.05) + rnd.gauss(0, 4))
            # 아래에서 끌어올리는 슬라이드(벤드 범위 ±2반음 가정): 큰 도약 뒤 일부에만
            if i and abs(n["pitch"] - notes[i - 1]["pitch"]) >= 5 and rnd.random() < 0.35 * intensity:
                s = n["start"]
                bend += [{"beat": round(s, 4), "value": -0.5}, {"beat": round(s + 0.08, 4), "value": -0.15},
                         {"beat": round(s + 0.14, 4), "value": 0.0}]
        return {"notes": notes, "cc": cc, "bend": bend}

    if role in ("strings", "pad", "brass"):
        groups = _groups(notes)
        peak = int(85 + 35 * intensity)
        base = 55 if role != "brass" else 75
        atk = 0.45 if role != "brass" else 0.15
        for gi, g in enumerate(groups):
            t0, ln = g[0]["start"], max(n["length"] for n in g)
            for n in g:
                n["start"] = max(0.0, n["start"] + rnd.gauss(0, jit * 0.7))
                n["length"] = n["length"] + (0.06 if role != "brass" else 0.0)      # 레가토로 살짝 겹치기
                n["velocity"] = _clamp_vel(n["velocity"] * _phrase_arc(t0, phrase_bars, 0.08) + rnd.gauss(0, 3))
            # 이어지는 화음(레가토)은 사이에서 바닥까지 꺼지지 않는다 — 활을 바꾸듯 살짝만 숨 쉬고 이어 감.
            # 프레이즈 처음은 아래에서 부풀고, 끝(다음 화음이 없거나 쉼 뒤)만 내려놓는다.
            prev_tied = gi > 0 and t0 - (groups[gi - 1][0]["start"] + max(n["length"] for n in groups[gi - 1])) < 0.15
            next_tied = gi + 1 < len(groups) and groups[gi + 1][0]["start"] - (t0 + ln) < 0.15
            lo_in = int(peak * 0.88) if prev_tied else base
            lo_out = int(peak * 0.88) if next_tied else base
            sw = _expr_swell(t0, ln, peak=peak, base=lo_in, attack=atk if not prev_tied else 0.25,
                             release=0.35 if role != "brass" else 0.2)
            if next_tied:
                sw[-1]["value"] = lo_out
                if len(sw) > 1:
                    sw[-2]["value"] = max(sw[-2]["value"], lo_out)
            cc += sw
            if role == "strings":                               # 모듈레이션(다이내믹 레이어용)도 같은 곡선
                cc += [{**p, "cc": 1, "value": max(1, p["value"] - 5)} for p in sw]
        return {"notes": notes, "cc": cc, "bend": bend}

    if role in ("lead", "vocal_like", "flute"):
        notes.sort(key=lambda n: n["start"])
        for i, n in enumerate(notes):
            shift(n, "lead")
            nxt = notes[i + 1]["start"] if i + 1 < len(notes) else None
            if nxt is not None and 0 < nxt - (n["start"] + n["length"]) < 0.2:
                n["length"] = nxt - n["start"] + 0.03                              # 레가토
            n["velocity"] = _clamp_vel(n["velocity"] * _phrase_arc(n["start"], phrase_bars, 0.12) + rnd.gauss(0, 4))
            if n["length"] >= 1.0 and rnd.random() < 0.5 * intensity:            # 긴 음: 아래서 스쿱
                bend += [{"beat": round(n["start"], 4), "value": -0.12}, {"beat": round(n["start"] + 0.1, 4), "value": 0.0}]
        for g in _groups(notes):
            cc += _expr_swell(g[0]["start"], g[0]["length"], peak=int(95 + 25 * intensity), base=75, attack=0.2, release=0.25, steps=4)
        return {"notes": notes, "cc": cc, "bend": bend}

    if role == "guitar":
        for gi, g in enumerate(_groups(notes)):
            down = gi % 2 == 0
            per = _ms(rnd.uniform(8, 16), 90)
            for k, n in enumerate(sorted(g, key=lambda n: n["pitch"], reverse=not down)):
                n["start"] = max(0.0, g[0]["start"] + k * per + rnd.gauss(0, jit * 0.4))
                n["velocity"] = _clamp_vel(n["velocity"] * (1.0 if down else 0.85) + rnd.gauss(0, 4))
        return {"notes": notes, "cc": cc, "bend": bend}

    # pluck · 기타: 가벼운 흔들림과 프레이즈 곡선만
    for n in notes:
        shift(n, role)
        n["velocity"] = _clamp_vel(n["velocity"] * _phrase_arc(n["start"], phrase_bars, 0.08) + rnd.gauss(0, 3))
    return {"notes": notes, "cc": cc, "bend": bend}


ROLE_GUESS = [("drum", "drums"), ("kick", "drums"), ("perc", "drums"), ("bass", "bass"), ("sub", "bass"),
              ("piano", "piano"), ("rhodes", "keys"), ("keys", "keys"), ("organ", "keys"), ("ep", "keys"),
              ("string", "strings"), ("violin", "strings"), ("cello", "strings"), ("pad", "pad"), ("choir", "pad"),
              ("brass", "brass"), ("horn", "brass"), ("trumpet", "brass"), ("lead", "lead"), ("flute", "lead"),
              ("melod", "lead"), ("guitar", "guitar"), ("pluck", "pluck"), ("bell", "pluck"), ("chop", None),
              ("sample", None)]


def guess_role(track_name, role_text="", sound=""):
    # 이름·역할 글자만 본다(소리 파일 경로에는 'lead_loop' 같은 우연한 단어가 섞인다). 샘플·찹은 연주 모델 없음.
    t = f"{track_name} {role_text}".lower()
    if "chop" in t or "sample" in t:
        return None
    t = f"{t} {Path(str(sound)).stem}".lower() if sound else t
    for key, role in ROLE_GUESS:
        if key in t:
            return role
    return "pluck"
