"""비평가 — 곡을 지은 뒤 '냉정한 A&R' 처럼 다시 본다. 슬롭(평균으로 수렴한 음악)을 숫자로 잡는다.

    report = critique(spec)            # 설계서만으로(엔진 없이) — 연주자 모델 전의 악보 기준
    print(format_report(report))

잡는 것
  repetition  같은 4마디 덩어리가 그대로 반복되는 비율(트랙별·곡 전체). 같은 이름 섹션이 한 음도 안 바뀌면 경고
  contrast    섹션마다 밀도·음역·에너지·활성 트랙·화성 리듬 — 이웃 섹션이 너무 비슷하면 경고
  clashes     선율(lead/vocal/melody 파트)의 강박 음이 그때 화음에 없는 음 — 의도한 긴장(7·9·11·13)은 따로 셈
  motif       콘셉트의 중심 동기가 곡에서 몇 번, 몇 가지 모양으로 나오는지(전위 무관 음정 패턴)
  events      '사건'(정지·비트 체인지·필터 드롭·조바꿈 등)이 있는지
  concept     콘셉트 문서의 제약을 어겼는지(가능한 것만)
질문(qualitative)은 Claude 가 직접 답한다 — 숫자가 못 잡는 것.
"""
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

from . import arrange, theory

MELODIC = ("melody", "vocal")
QUESTIONS = [
    "이 곡을 한 문장으로 말하면? 그 문장이 모든 섹션에서 들리는가",
    "흔한 것으로 바꿔 끼워도 아무도 모를 요소는? (악기·드럼 패턴·진행) — 있으면 교체",
    "사람들이 이야기할 '그 순간'은 어디인가(마디 번호로). 없으면 만든다",
    "2절은 1절과 무엇이 다른가 — '같지만 다른' 변화가 있는가",
    "끝에서 무엇이 달라져 있는가(처음과 같은 상태로 끝나면 이야기가 없다)",
    "본인 취향(TASTE.md·LOG.md)과 어긋나는 결정은?",
]


def timeline(spec):
    """설계서 → 트랙별 절대 박 노트 + 화음 타임라인 + 섹션 목록. (연주자 모델 적용 전)"""
    sections, total_bars = arrange._sections(spec)
    key = spec.get("key") or "C major"
    kname, _, kmode = key.partition(" ")
    kmode = "minor" if kmode.lower().startswith("min") else "major"
    tracks = defaultdict(list)
    roles = {}
    chords = []                          # (start, end, chord_name)
    for part in spec.get("parts", []):
        kind = next((k for k in ("drums", "chords", "bass", "melody", "notes", "vocal", "rap", "audio") if k in part), None)
        for sec in arrange._targets(part, sections):
            b0 = sec["start_bar"] * 4 + part.get("offset", 0)
            L = sec["bars"] * 4
            if kind in ("chords", "bass") and not chords_cover(chords, b0, b0 + L):
                cfg = part[kind]
                ch = arrange._chords_for(cfg, kname, kmode)
                durs = cfg.get("durations") or [cfg.get("beats_per_chord", 4)] * len(ch)
                t = 0.0
                while t < L - 1e-6:
                    for c, d in zip(ch, durs):
                        if t >= L - 1e-6:
                            break
                        chords.append((b0 + t, b0 + min(L, t + d), theory.transpose_chord(c, part.get("transpose", 0) % 12) if part.get("transpose") and kind == "chords" and False else c))
                        t += d
            if kind == "vocal":
                v = part["vocal"]
                notes, _ = arrange.melody(v["melody"])
                roles[part["track"]] = "vocal"
            elif kind in ("rap", "audio") or kind is None:
                roles.setdefault(part["track"], kind or "?")
                continue
            else:
                notes = arrange.part_notes(part, sec, spec)
                roles.setdefault(part["track"], "drums" if kind == "drums" else ("melody" if kind == "melody" else kind))
            tracks[part["track"]] += [{**n, "start": round(n["start"] + b0, 4), "section": sec["name"],
                                       "sec_index": sections.index(sec)} for n in notes]
    chords.sort()
    return {"tracks": dict(tracks), "roles": roles, "chords": chords, "sections": sections, "bars": total_bars,
            "key": key}


def chords_cover(chords, a, b):
    return any(s <= a + 1e-6 and e >= b - 1e-6 for s, e, _ in chords) or \
        sum(max(0, min(e, b) - max(s, a)) for s, e, _ in chords) >= (b - a) - 1e-6


def _block_hash(notes, a, b):
    sig = sorted((round(n["start"] - a, 3), n["pitch"], round(n["length"], 2)) for n in notes if a <= n["start"] < b)
    return hashlib.md5(json.dumps(sig).encode()).hexdigest() if sig else None


def repetition(tl):
    out = {}
    all_hashes = []
    for name, notes in tl["tracks"].items():
        hs = [_block_hash(notes, b * 4, b * 4 + 16) for b in range(0, tl["bars"], 4)]
        hs = [h for h in hs if h]
        if not hs:
            continue
        c = Counter(hs)
        repeats = sum(v - 1 for v in c.values())
        out[name] = {"blocks": len(hs), "unique": len(c), "repeat_ratio": round(repeats / len(hs), 2)}
        all_hashes.append(hs)
    # 곡 전체: 모든 트랙을 합친 4마디가 똑같은 경우
    merged = []
    for b in range(0, tl["bars"], 4):
        merged.append(tuple(_block_hash(n, b * 4, b * 4 + 16) for n in tl["tracks"].values()))
    mc = Counter(m for m in merged if any(m))
    song_rep = round(sum(v - 1 for v in mc.values()) / max(1, len(merged)), 2)
    return {"tracks": out, "song_repeat_ratio": song_rep}


def contrast(tl):
    rows = []
    for i, s in enumerate(tl["sections"]):
        a, b = s["start_bar"] * 4, (s["start_bar"] + s["bars"]) * 4
        ns = [n for t in tl["tracks"].values() for n in t if a <= n["start"] < b]
        active = [name for name, t in tl["tracks"].items() if any(a <= n["start"] < b for n in t)]
        pitched = [n["pitch"] for name, t in tl["tracks"].items() if tl["roles"].get(name) != "drums"
                   for n in t if a <= n["start"] < b]
        ch = [c for c in tl["chords"] if a <= c[0] < b]
        rows.append({"section": s["name"], "bars": s["bars"],
                     "density": round(len(ns) / max(1, s["bars"]), 1),
                     "energy": round(sum(n["velocity"] for n in ns) / max(1, s["bars"]) / 100, 1),
                     "register": round(sum(pitched) / len(pitched), 1) if pitched else None,
                     "span": (min(pitched), max(pitched)) if pitched else None,
                     "tracks": len(active), "chord_changes_per_bar": round(len(ch) / max(1, s["bars"]), 2)})
    flags = []
    for r1, r2 in zip(rows, rows[1:]):
        same = (abs(r1["density"] - r2["density"]) < 0.15 * max(1, r1["density"]) and r1["tracks"] == r2["tracks"]
                and (r1["register"] or 0) - (r2["register"] or 0) < 2 and abs(r1["energy"] - r2["energy"]) < 0.15 * max(0.1, r1["energy"]))
        if same and r1["section"] != r2["section"]:
            flags.append(f"{r1['section']} → {r2['section']}: 밀도·트랙 수·음역·에너지가 거의 같다(전환이 안 느껴짐)")
    return {"sections": rows, "flags": flags}


def _chord_at(chords, t):
    for s, e, c in chords:
        if s - 1e-6 <= t < e - 1e-6:
            return c
    return None


def clashes(tl):
    """선율 트랙의 강박(정박) 음 중 화음 밖 음. 7·9·11·13 은 '색깔'로 따로 센다."""
    out = {}
    for name, notes in tl["tracks"].items():
        if tl["roles"].get(name) not in MELODIC:
            continue
        strong, bad, color, detail = 0, 0, 0, []
        for n in notes:
            on13 = abs(n["start"] / 2 - round(n["start"] / 2)) < 0.005          # 1·3박(강박)
            if not ((on13 and n["length"] >= 0.2) or (n["length"] >= 1.0 and abs(n["start"] - round(n["start"])) < 0.01)):
                continue                                     # 강박 음 또는 정박의 긴 음만
            c = _chord_at(tl["chords"], n["start"])
            if not c:
                continue
            strong += 1
            root, ivs, _ = theory.parse_chord(c)
            rel = (n["pitch"] - root) % 12
            core = {i % 12 for i in ivs[:3]}                 # 1·3·5
            ext = {i % 12 for i in ivs[3:]}
            if rel in core:
                continue
            if rel in ext or rel in (2, 9, 5 if 3 in core else 6):  # 9·13·11(단화음) 은 색깔
                color += 1
                continue
            bad += 1
            if len(detail) < 6:
                detail.append(f"{n['section']} {int(n['start'] // 4) + 1}마디 {theory.note_name(n['pitch'])} / {c}")
        if strong:
            out[name] = {"strong_notes": strong, "clash": bad, "color": color, "clash_ratio": round(bad / strong, 2),
                         "examples": detail}
    return out


def _intervals(notes):
    ps = [n["pitch"] for n in sorted(notes, key=lambda n: n["start"])]
    return [b - a for a, b in zip(ps, ps[1:])]


def motif_use(tl, motif_text, tolerance=1):
    """중심 동기(멜로디 표기)가 어디서 몇 번 나오는지 — 음정 패턴(이조 무관), 전위(뒤집기)·한 음 바뀜 허용."""
    if not motif_text:
        return None
    m, _ = arrange.melody(motif_text)
    iv = _intervals(m)
    if not iv:
        return None
    k = len(iv)
    hits = []
    for name, notes in tl["tracks"].items():
        if tl["roles"].get(name) == "drums":
            continue
        seq = sorted(notes, key=lambda n: n["start"])
        mono = []
        for n in seq:                                         # 같은 시각이면 맨 위 음(선율)
            if mono and abs(mono[-1]["start"] - n["start"]) < 0.02:
                if n["pitch"] > mono[-1]["pitch"]:
                    mono[-1] = n
            else:
                mono.append(n)
        ivs = _intervals(mono)
        for i in range(len(ivs) - k + 1):
            w = ivs[i:i + k]
            sgn = lambda x: (x > 0) - (x < 0)
            exact = sum(1 for a, b in zip(w, iv) if a != b)
            dist = sum(abs(a - b) for a, b in zip(w, iv))
            dist_inv = sum(abs(a + b) for a, b in zip(w, iv))
            same_contour = all(sgn(a) == sgn(b) for a, b in zip(w, iv))
            inv_contour = all(sgn(a) == -sgn(b) for a, b in zip(w, iv))
            # 원형 = 음정 그대로 · 변형 = 윤곽 같고 음정 합 차이 ≤ 4반음(화음 맞추기·조성 이조로 바뀐 것) · 전위 = 뒤집힌 윤곽
            if exact == 0 or (same_contour and dist <= 4) or (inv_contour and dist_inv <= 4):
                hits.append({"track": name, "section": mono[i]["section"], "bar": int(mono[i]["start"] // 4) + 1,
                             "form": "원형" if exact == 0 else "변형" if same_contour else "전위"})
    sections = sorted({h["section"] for h in hits})
    forms = Counter(h["form"] for h in hits)
    return {"hits": len(hits), "sections": sections, "forms": dict(forms), "tracks": sorted({h["track"] for h in hits})}


def events_of(spec):
    ev = list(spec.get("events", []))
    for a in spec.get("automation", []):
        if a.get("param") in ("frequency",):
            ev.append({"type": "filter", "track": a["track"]})
    return ev


def regularity(spec, concept=None):
    """정형성 검사 — '틀에 너무 맞는' 곡을 잡는다(10-15 본인: "칸예 곡은 정형적이지 않고 그게 매력").
    무작위로 흩뜨리라는 게 아니라, 콘셉트에 근거한 비정형 결정이 최소 하나는 있어야 한다는 것."""
    concept = concept or {}
    secs = spec.get("sections", [])
    issues, notes = [], []
    bars = [s["bars"] for s in secs]
    if secs and all(b % 4 == 0 for b in bars) and len(secs) >= 4:
        issues.append("정형: 모든 구간이 4의 배수 마디 — 이야기 길이에 맞춘 구간(예 15·23마디)이나 1마디 전환이 없다")
    by_name = defaultdict(list)
    for s in secs:
        by_name[s["name"]].append(s["bars"])
    same = [n for n, v in by_name.items() if len(v) >= 2 and len(set(v)) == 1]
    if len(same) >= 2 and not spec.get("events"):
        notes.append(f"반복 구간({', '.join(same)})이 길이·사건 모두 같다")
    locks = [p["rap"].get("lock", 0.75) for p in spec.get("parts", []) if "rap" in p]
    if locks and min(locks) > 0.6:
        issues.append(f"정형: 랩을 박자 격자에 {int(min(locks) * 100)}% 이상 당긴다 — 사람 래퍼는 ±20ms 안이 약 20%뿐"
                      "(Through The Wire 분석). 생성 보컬(비트 조건)을 쓰거나 lock ≤ 0.4")
    irr = concept.get("irregular") or []
    if concept and not irr:
        issues.append("정형: 콘셉트에 '비정형 결정'(irregular: [{what, why}])이 하나도 없다 — 예: 벌스를 이야기 길이만큼, "
                      "훅 앞 1마디 전환, 비트 체인지, 마지막 훅만 다르게")
    return {"issues": issues, "notes": notes, "section_bars": bars}


def critique(spec, concept=None):
    concept = concept or spec.get("concept") or {}
    tl = timeline(spec)
    rep = repetition(tl)
    con = contrast(tl)
    cl = clashes(tl)
    mot = motif_use(tl, (concept.get("motif") or {}).get("melody") if isinstance(concept.get("motif"), dict) else concept.get("motif"))
    ev = events_of(spec)
    issues = []
    for name, r in rep["tracks"].items():
        if r["blocks"] >= 4 and r["repeat_ratio"] >= 0.75 and tl["roles"].get(name) != "drums":
            issues.append(f"반복: {name} 4마디 덩어리 {r['blocks']}개 중 서로 다른 게 {r['unique']}개뿐")
    if rep["song_repeat_ratio"] >= 0.5:
        issues.append(f"반복: 곡 전체 4마디 단위가 {int(rep['song_repeat_ratio'] * 100)}% 그대로 반복")
    issues += ["대비: " + f for f in con["flags"]]
    for name, c in cl.items():
        if c["clash_ratio"] > 0.15:
            issues.append(f"화성: {name} 강박 음 {c['strong_notes']}개 중 {c['clash']}개가 화음 밖 — 예: {', '.join(c['examples'][:3])}")
    if concept.get("motif") and (not mot or len(mot["sections"]) < 2):
        issues.append("동기: 중심 동기가 곡에서 거의 안 들린다(2개 섹션 미만)")
    if mot and mot["hits"] and len(mot["forms"]) == 1 and "원형" in mot["forms"]:
        issues.append("동기: 원형 그대로만 반복 — 변형(리듬·전위·재화성)이 없다")
    if not ev:
        issues.append("사건: 정지·비트 체인지·필터 드롭·조바꿈 같은 '그 순간'이 하나도 없다")
    reg = regularity(spec, concept)
    issues += reg["issues"]
    score = max(0, 100 - 12 * len(issues))
    return {"score": score, "issues": issues, "repetition": rep, "contrast": con, "clashes": cl, "motif": mot,
            "events": ev, "questions": QUESTIONS}


def format_report(r):
    L = [f"비평 점수 {r['score']}/100"]
    L += [f"  - {x}" for x in r["issues"]] or ["  (숫자로 잡히는 문제 없음)"]
    L.append("섹션 대비:")
    for s in r["contrast"]["sections"]:
        L.append(f"  {s['section']:<8} {s['bars']:>2}마디 · 밀도 {s['density']:>5} · 에너지 {s['energy']:>5} · 음역 {s['register']} · 트랙 {s['tracks']} · 화성리듬 {s['chord_changes_per_bar']}")
    if r["motif"]:
        L.append(f"동기: {r['motif']['hits']}회 · 섹션 {r['motif']['sections']} · 모양 {r['motif']['forms']}")
    L.append("Claude 가 직접 답할 질문:")
    L += [f"  ? {q}" for q in r["questions"]]
    return "\n".join(L)


def critique_project(name):
    p = Path(arrange.ROOT) / "projects" / name / "spec.json"
    spec = json.loads(p.read_text(encoding="utf-8"))
    cpath = p.with_name("concept.json")
    concept = json.loads(cpath.read_text(encoding="utf-8")) if cpath.exists() else None
    return critique(spec, concept)


if __name__ == "__main__":
    import sys
    for n in sys.argv[1:]:
        print(f"== {n}")
        print(format_report(critique_project(n)))
