"""동기(모티프) 전개 — 반복 대신 변형. 짧은 동기 하나가 곡 전체를 굴러가게 한다.

    m = parse("A4:.5 C5:.5 E5:1 D5:2")
    develop(m, ["up:2", "augment:2"], key="A minor")      # 연산을 차례로
    fit(notes, chords, key)                                # 강박 음을 그때 화음의 음으로(윤곽 유지)
    phrase(m, bars=4, plan="statement answer")             # 4마디 프레이즈(제시 + 응답)
    section_melody(motif, section_plan, chords, key, bars) # 설계서 'melody' 파트에 넣을 표기

연산(문자열)
  up:n / down:n      음계 위로/아래로 n 칸(조성 유지 이조)         chrom:n   반음 n 개 이동
  invert             첫 음 기준 뒤집기(음계 안에서)                retro     거꾸로
  augment:f          길이 f 배(늘이기)                             diminish:f 길이 1/f
  displace:b         b 박 밀기(당김·엇박)                          fragment:n 앞 n 음만
  sequence:s,k       s 칸씩 올리며 k 번 반복(시퀀스)               tail:n    뒤 n 음만
  octave:n           옥타브 이동                                   rhythm:a,b,..  음 길이를 바꿔 끼우기(같은 음, 다른 리듬)
"""
from . import theory
from .arrange import melody as parse_text


def to_text(notes):
    """노트 → 멜로디 표기. 각 음 길이 = 다음 음까지(레가토), 사이가 비면 쉼표."""
    out, t = [], 0.0
    srt = sorted(notes, key=lambda n: n["start"])
    for j, n in enumerate(srt):
        if n["start"] > t + 1e-4:
            out.append(f"r:{round(n['start'] - t, 4):g}")
        nxt = srt[j + 1]["start"] if j + 1 < len(srt) else n["start"] + n["length"]
        d = round(max(n["length"], min(nxt - n["start"], n["length"] * 1.5)) if nxt > n["start"] else n["length"], 4)
        d = round(min(d, nxt - n["start"]), 4) if nxt > n["start"] else d
        out.append(f"{theory.note_name(n['pitch']).replace('-', '')}:{d:g}")
        t = n["start"] + d
    return " ".join(out)


def parse(text):
    notes, _ = parse_text(text, legato=1.0)
    t0 = min(n["start"] for n in notes) if notes else 0.0
    return [{**n, "start": round(n["start"] - t0, 4)} for n in notes]


def _key(key):
    k, _, m = (key or "C major").partition(" ")
    return k, ("minor" if m.lower().startswith("min") else "major")


def _scale(key):
    k, m = _key(key)
    return theory.scale_notes(k, m, 0, 127)


def _deg(p, scale):
    """음 → (음계 위치, 반음 어긋남). 음계 밖이면 가장 가까운 아래 음 + 어긋남."""
    lower = [i for i, s in enumerate(scale) if s <= p]
    i = lower[-1] if lower else 0
    return i, p - scale[i]


def _from_deg(i, off, scale):
    i = max(0, min(len(scale) - 1, i))
    return scale[i] + off


def length(notes):
    return max((n["start"] + n["length"] for n in notes), default=0.0)


def op(notes, spec, key="C major"):
    name, _, arg = spec.partition(":")
    sc = _scale(key)
    out = [dict(n) for n in notes]
    if name in ("up", "down"):
        k = int(arg or 1) * (1 if name == "up" else -1)
        for n in out:
            i, o = _deg(n["pitch"], sc)
            n["pitch"] = _from_deg(i + k, o, sc)
    elif name == "chrom":
        for n in out:
            n["pitch"] += int(arg)
    elif name == "octave":
        for n in out:
            n["pitch"] += 12 * int(arg)
    elif name == "invert":
        i0, _ = _deg(out[0]["pitch"], sc)
        for n in out:
            i, o = _deg(n["pitch"], sc)
            n["pitch"] = _from_deg(2 * i0 - i, -o, sc)
    elif name == "retro":
        L = length(out)
        out = sorted(({**n, "start": round(L - n["start"] - n["length"], 4)} for n in out), key=lambda n: n["start"])
    elif name == "augment":
        f = float(arg or 2)
        out = [{**n, "start": round(n["start"] * f, 4), "length": round(n["length"] * f, 4)} for n in out]
    elif name == "diminish":
        f = float(arg or 2)
        out = [{**n, "start": round(n["start"] / f, 4), "length": round(n["length"] / f, 4)} for n in out]
    elif name == "displace":
        b = float(arg or 0.5)
        out = [{**n, "start": round(n["start"] + b, 4)} for n in out]
    elif name == "fragment":
        out = sorted(out, key=lambda n: n["start"])[: int(arg or 2)]
    elif name == "tail":
        out = sorted(out, key=lambda n: n["start"])[-int(arg or 2):]
        t0 = out[0]["start"]
        out = [{**n, "start": round(n["start"] - t0, 4)} for n in out]
    elif name == "sequence":
        s, k = (arg or "1,2").split(",")
        s, k = int(s), int(k)
        L = length(out)
        seq = []
        for r in range(k):
            for n in out:
                i, o = _deg(n["pitch"], sc)
                seq.append({**n, "pitch": _from_deg(i + s * r, o, sc), "start": round(n["start"] + L * r, 4)})
        out = seq
    elif name == "rhythm":
        durs = [float(x) for x in arg.split(",")]
        t = 0.0
        srt = sorted(out, key=lambda n: n["start"])
        for j, n in enumerate(srt):
            d = durs[j % len(durs)]
            n["start"], n["length"] = round(t, 4), d
            t += d
        out = srt
    elif name in ("", "original", "same"):
        pass
    else:
        raise ValueError(f"모르는 동기 연산 '{spec}'")
    return out


def develop(notes, ops, key="C major"):
    for o in ops or []:
        notes = op(notes, o, key)
    return notes


def fit(notes, chords, key="C major", strong_only=True):
    """강박(정박) 음이 그때 화음에 없으면 가장 가까운 화음 음으로(위아래 중 윤곽에 맞는 쪽). 약박은 음계 안으로.
    chords: [(start, end, 'Am7'), ...] — notes 와 같은 박 기준."""
    sc = set(p % 12 for p in _scale(key)[:12])
    out = []
    prev = None
    for n in sorted(notes, key=lambda n: n["start"]):
        n = dict(n)
        c = next((c for s, e, c in chords if s - 1e-6 <= n["start"] < e - 1e-6), None)
        strong = (abs(n["start"] / 2 - round(n["start"] / 2)) < 0.005 and n["length"] >= 0.2) or n["length"] >= 1.0   # 1·3박 또는 긴 음
        if c and (strong or not strong_only):
            root, ivs, _ = theory.parse_chord(c)
            tones = {(root + i) % 12 for i in ivs}
            if n["pitch"] % 12 not in tones:
                cands = [n["pitch"] + d for d in range(-4, 5) if (n["pitch"] + d) % 12 in tones]
                if prev is not None:      # 윤곽 유지: 앞 음과의 방향이 바뀌지 않는 후보 우선
                    up = n["pitch"] >= prev
                    same_dir = [x for x in cands if (x >= prev) == up]
                    cands = same_dir or cands
                n["pitch"] = min(cands, key=lambda x: abs(x - n["pitch"])) if cands else n["pitch"]
        elif n["pitch"] % 12 not in sc:
            n["pitch"] += min((d for d in (-1, 1) if (n["pitch"] + d) % 12 in sc), key=abs, default=0)
        prev = n["pitch"]
        out.append(n)
    return out


def phrase(m, bars=4, plan="statement answer", key="C major"):
    """동기로 프레이즈 만들기. statement=원형, answer=끝을 바꾼 대답(마지막 음을 으뜸/딸림음으로),
    sequence=한 칸씩 올려 반복, question=끝을 올려 열어 둠, climb=두 번째에 한 옥타브 위."""
    sc = _scale(key)
    tonic = theory.pc(_key(key)[0])
    L = max(1.0, length(m))
    slot = bars * 4 / max(1, len(plan.split()))
    out, t = [], 0.0
    for step in plan.split():
        if step == "statement":
            v = develop(m, [], key)
        elif step == "answer":
            v = develop(m, [], key)
            last = max(v, key=lambda n: n["start"])
            cands = [p for p in sc if p % 12 == tonic and abs(p - last["pitch"]) <= 7]
            if cands:
                last["pitch"] = min(cands, key=lambda p: abs(p - last["pitch"]))
        elif step == "question":
            v = develop(m, [], key)
            last = max(v, key=lambda n: n["start"])
            i, o = _deg(last["pitch"], sc)
            last["pitch"] = _from_deg(i + 2, o, sc)
        elif step == "sequence":
            v = develop(m, ["up:1"], key)
        elif step == "climb":
            v = develop(m, ["up:2"], key)
        elif step == "fragment":
            v = develop(m, ["fragment:3", "sequence:1,2"], key)
        else:
            v = develop(m, step.split("+"), key)
        out += [{**n, "start": round(n["start"] + t, 4)} for n in v if n["start"] < slot]
        t += slot
    return out


def section_melody(motif_text, ops, chords=None, key="C major", bars=4, plan="statement answer", offset=0.0):
    """설계서 melody 파트용 표기. ops = 이 섹션에서 동기에 거는 변형, plan = 프레이즈 모양."""
    m = develop(parse(motif_text), ops, key)
    ph = phrase(m, bars=bars, plan=plan, key=key)
    if chords:
        ph = fit(ph, [(s - offset, e - offset, c) for s, e, c in chords], key)
    ph = [n for n in ph if n["start"] < bars * 4 - 1e-6]
    for n in ph:                                        # 프레이즈 밖으로 넘치는 음은 자른다
        n["length"] = min(n["length"], bars * 4 - n["start"])
    txt = to_text(ph)
    end = max((n["start"] + n["length"] for n in ph), default=0.0)
    if end < bars * 4 - 1e-6:                           # 다음 프레이즈가 제자리(마디 경계)에서 시작하도록 쉼표로 채움
        txt += f" r:{round(bars * 4 - end, 4):g}"
    return txt
