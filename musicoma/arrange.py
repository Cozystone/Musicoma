"""편곡 설계서(spec) → 곡. 장르 무관 — Claude 가 프로듀서처럼 곡 전체를 한 문서로 쓰고, 엔진이 그대로 짓는다.

미세조정 = 설계서의 해당 줄만 고쳐 build() 다시. 설계서는 projects/<name>/spec.json 에 남는다(재현·비교).

spec 예시 (모든 위치는 '섹션 시작 기준 박', 4/4 기준 마디=4박)
{
  "name": "night-drive", "bpm": 104, "key": "Eb major", "style": "city-pop",
  "sections": [{"name": "intro", "bars": 4}, {"name": "verse", "bars": 8}, {"name": "chorus", "bars": 8}],
  "tracks": {
    "Drums": {"sound": "drums_acoustic_basic", "role": "drums",
              "fx": [{"device": "compressor", "params": {"threshold": -18, "ratio": 4, "attack": 20}}],
              "sends": {"0": -20}},
    "Keys":  {"sound": "rhodes", "role": "keys", "pan": -0.2},
    "Bass":  {"sound": "bass_finger", "role": "bass"}
  },
  "buses":  [{"name": "Verb", "bus": 0, "device": "Dragonfly Plate Reverb", "volume_db": -4}],
  "master": [{"device": "eq", "params": {"High-pass gain": 1.0}}],
  "parts": [
    {"track": "Drums", "in": ["verse", "chorus"],
     "drums": {"pattern": {"kick": "x.....x.x.......", "snare": "....x.......x...", "hat": "x-x-x-x-x-x-x-x-"},
               "swing": 0.54, "humanize_ms": 5, "humanize_vel": 8,
               "fill": {"kick": "x.....x...", "snare": "....x...xoxoXXXX"}}},
    {"track": "Keys", "in": ["verse", "chorus"],
     "chords": {"progression": "IVmaj7 iii7 vi7 V7/vi", "beats_per_chord": 4, "voicing": "rhodes",
                "rhythm": [[0, 1.5, 1.0], [2.5, 1.0, 0.8]], "velocity": 76}},
    {"track": "Bass", "in": ["verse", "chorus"],
     "bass": {"progression": "IVmaj7 iii7 vi7 V7/vi", "beats_per_chord": 4,
              "pattern": [[0, 1.5, 0], [1.5, 0.5, 12], [2, 1, 7], [3.5, 0.5, -1]]}},
    {"track": "Lead", "in": ["chorus"], "melody": "Bb4:1 C5:.5 Eb5:1.5 r:1 | G5:2 F5:1 Eb5:1"},
    {"track": "Vox", "in": ["chorus"], "vocal": {"voice": "me", "melody": "Bb4:1 C5:.5 Eb5:1.5 r:1",
                                                 "lyrics": "stay with me", "gain_db": 0}},
    {"track": "Sample", "in": ["verse"], "audio": {"path": "sounds/crate/x/loop.wav", "every": 16}}
  ],
  "automation": [{"track": "Keys", "device": 1, "param": "frequency",
                  "points": [{"bar": 0, "value": 800}, {"bar": 4, "value": 18000}]}],
  "mix": {"balance": true, "target_lufs": -12},
  "feel": "laid_back", "intensity": 0.7        # 연주자 모델(곡 전체 기본). 파트별 "perform": {"role","feel","intensity"} | false
}
"""
import json
import re
from pathlib import Path

from . import groove, perform as perform_mod, theory
from .knowledge import style as load_style
from .song import Song

ROOT = Path(__file__).resolve().parent.parent

_NOTE_RE = re.compile(r"^([A-Ga-g][#b]?)(-?\d)$")


def note_num(token):
    """'Eb4' → 63, '60' → 60"""
    if token.lstrip("-").isdigit():
        return int(token)
    m = _NOTE_RE.match(token)
    if not m:
        raise ValueError(f"bad note '{token}'")
    return 12 * (int(m.group(2)) + 1) + theory.pc(m.group(1))


def melody(text, velocity=96, legato=0.95):
    """'E5:1 G5:.5 r:.5 A5:2@110 [C5,E5]:1' → 노트. 길이=박, r=쉼, @세기, [..]=화음, '|' 는 무시(마디 구분용)."""
    notes, t = [], 0.0
    for tok in text.replace("|", " ").split():
        vel = velocity
        if "@" in tok:
            tok, v = tok.split("@")
            vel = int(v)
        head, _, dur = tok.partition(":")
        dur = float(dur) if dur else 1.0
        if head.lower() != "r":
            pitches = head.strip("[]").split(",") if head.startswith("[") else [head]
            for p in pitches:
                notes.append({"pitch": note_num(p), "start": round(t, 4), "length": round(dur * legato, 4),
                              "velocity": vel})
        t += dur
    return notes, t


class Spec(dict):
    @classmethod
    def load(cls, name_or_path):
        p = Path(name_or_path)
        if not p.suffix:
            p = ROOT / "projects" / name_or_path / "spec.json"
        return cls(json.loads(p.read_text(encoding="utf-8")))

    def save(self):
        d = ROOT / "projects" / self["name"]
        d.mkdir(parents=True, exist_ok=True)
        (d / "spec.json").write_text(json.dumps(self, ensure_ascii=False, indent=1), encoding="utf-8")
        return str(d / "spec.json")


def _sections(spec):
    out, bar = [], 0
    for s in spec["sections"]:
        out.append({**s, "start_bar": s.get("start_bar", bar)})
        bar = out[-1]["start_bar"] + s["bars"]
    return out, bar


def _targets(part, sections):
    want = part.get("in", "all")
    if want == "all":
        return sections
    want = [want] if isinstance(want, str) else want
    res = []
    for w in want:
        if isinstance(w, int):                    # 섹션 순번
            res.append(sections[w])
        elif "#" in w:                            # 'chorus#2' = 두 번째 chorus
            n, k = w.split("#")
            res.append([s for s in sections if s["name"] == n][int(k) - 1])
        else:
            res += [s for s in sections if s["name"] == w]
    return sorted(res, key=lambda s: s["start_bar"])


def _chords_for(cfg, key, mode):
    prog = cfg["progression"]
    return theory.progression(prog, key, mode) if isinstance(prog, str) else list(prog)


def _fill(notes_fn, length_beats, cycle_beats):
    """한 사이클짜리 노트를 섹션 길이만큼 반복."""
    out, t = [], 0.0
    one = notes_fn()
    while t < length_beats - 1e-6:
        out += [{**n, "start": round(n["start"] + t, 4)} for n in one if n["start"] + t < length_beats - 1e-6]
        t += cycle_beats
    return out


def _vocal_name(part, sec, kind):
    """보컬 파일 이름: <트랙>_<섹션>[-<마디>]_<rap|sing>.wav — 폴더만 봐도 어디에 쓰인 건지 알게."""
    slug = lambda t: re.sub(r"[^a-z0-9]+", "-", str(t).lower()).strip("-") or "x"
    off = part.get("offset", 0)
    where = slug(sec["name"]) + (f"-b{int(off // 4) + 1}" if off else "")
    return f"{slug(part['track'])}_{where}_{kind}.wav"


def part_notes(part, sec, spec):
    """파트 하나가 섹션 하나에서 내는 노트(섹션 시작 기준)."""
    L = sec["bars"] * 4
    key = spec.get("key") or "C major"
    kname, _, kmode = key.partition(" ")
    kmode = "minor" if kmode.lower().startswith("min") else "major"
    bpm = spec["bpm"]
    seed = sec["start_bar"]
    shift = part.get("transpose", 0) + sec.get("transpose", 0)

    if "drums" in part:
        d = part["drums"]
        pat = {k: v for k, v in d["pattern"].items()}
        common = dict(swing=d.get("swing", 0.5), swing_unit=d.get("swing_unit", 16), humanize_ms=d.get("humanize_ms", 0),
                      humanize_vel=d.get("humanize_vel", 0), bpm=bpm, kit=d.get("kit"), seed=seed)
        fill = d.get("fill")
        body_bars = sec["bars"] - (1 if fill and sec["bars"] > 1 else 0)
        notes = groove.pattern_notes(pat, bars=body_bars, **common)
        notes = [n for n in notes if n["start"] < body_bars * 4]
        if fill and sec["bars"] > 1:
            notes += groove.pattern_notes(fill, bars=1, start=body_bars * 4, **common)
        return notes

    if "chords" in part:
        c = part["chords"]
        chords = _chords_for(c, kname, kmode)
        bpc = c.get("beats_per_chord", 4)
        durs = c.get("durations") or [bpc] * len(chords)
        cyc = sum(durs)
        rhythm = [tuple(r) for r in c["rhythm"]] if c.get("rhythm") else None
        voicings = theory.voice(chords, c.get("voicing", "piano"), low=c.get("low"), high=c.get("high"))
        fn = lambda: groove.chord_notes(voicings, durs, velocity=c.get("velocity", 80), strum=c.get("strum", 0.0),
                                        rhythm=rhythm, humanize_vel=c.get("humanize_vel", 6), seed=seed,
                                        legato=c.get("legato", 0.98))
        return groove.shift(_fill(fn, L, cyc), semitones=shift)

    if "bass" in part:
        b = part["bass"]
        chords = _chords_for(b, kname, kmode)
        bpc = b.get("beats_per_chord", 4)
        durs = b.get("durations") or [bpc] * len(chords)
        roots = [theory.bass_note(ch, b.get("low", 28), b.get("high", 47)) for ch in chords]
        pat = [tuple(p) for p in b["pattern"]] if b.get("pattern") else None
        fn = lambda: groove.bass_line(roots, durs, pattern=pat, velocity=b.get("velocity", 100), seed=seed)
        return groove.shift(_fill(fn, L, sum(durs)), semitones=shift)

    if "melody" in part:
        m = part["melody"]
        text = m if isinstance(m, str) else m["text"]
        vel = 96 if isinstance(m, str) else m.get("velocity", 96)
        notes, cyc = melody(text, velocity=vel)
        repeat = True if isinstance(m, str) else m.get("repeat", True)
        res = _fill(lambda: notes, L, max(cyc, 0.25)) if repeat else [n for n in notes if n["start"] < L]
        return groove.shift(res, semitones=shift)

    if "notes" in part:
        cyc = part.get("cycle_beats")
        notes = part["notes"]
        res = _fill(lambda: notes, L, cyc) if cyc else [n for n in notes if n["start"] < L]
        return groove.shift(res, semitones=shift)
    return []


def build(spec, render=True, balance=None, label=None, log=print):
    """설계서대로 곡을 새로 짓는다(같은 이름이면 덮어씀). 돌려줌: (Song, report|None)"""
    spec = Spec(spec)
    spec.save()
    sections, total_bars = _sections(spec)
    total = total_bars * 4
    s = Song.new(spec["name"], bpm=spec["bpm"], key=spec.get("key"), style=spec.get("style"),
                 time_sig=spec.get("time_sig", "4/4"), brief=spec.get("brief", ""))
    for sec in sections:
        s.section(sec["name"], sec["start_bar"], sec["bars"])

    # 프리셋 펼치기: tracks.<이름>.preset = "역할/키" → sound · fx · perform 을 채운다(직접 적은 값이 우선)
    from .knowledge import presets as load_presets
    _pre = load_presets()
    for name, t in spec.get("tracks", {}).items():
        if t.get("preset"):
            role, key = t["preset"].split("/", 1)
            pr = _pre[role][key]
            t.setdefault("sound", pr["sound"])
            t["fx"] = pr.get("fx", []) + t.get("fx", [])
            if pr.get("perform"):
                t.setdefault("perform_role", pr["perform"].get("role"))
                t.setdefault("perform", {k: v for k, v in pr["perform"].items() if k != "role"})

    # 트랙 · 디바이스
    for name, t in spec.get("tracks", {}).items():
        tr = s.track(name, t.get("sound"), role=t.get("role"), volume_db=t.get("volume_db"), pan=t.get("pan"))
        if t.get("program") is not None:
            s.e.call("device.program", {"track": name, "device": 0, "program": t["program"]})
        if t.get("patch"):
            s.e.call("device.load_file", {"track": name, "device": 0, "path": str(ROOT / t["patch"])})
        if t.get("instrument_params"):
            tr.set(0, t["instrument_params"])
        for fx in t.get("fx", []):
            tr.fx(fx["device"], fx.get("params"))
    for b in spec.get("buses", []):
        s.bus(b["name"], b.get("device", "Dragonfly Hall Reverb"), bus=b.get("bus", 0), params=b.get("params"),
              volume_db=b.get("volume_db", 0.0))
    for name, t in spec.get("tracks", {}).items():
        for bus, db in (t.get("sends") or {}).items():
            s[name].send(int(bus), db)
    for fx in spec.get("master", []):
        s.master_fx(fx["device"], fx.get("params"))

    # 파트 → 트랙별 노트 모으기(트랙당 MIDI 클립 하나), 오디오는 클립으로
    per_track = {}
    for part in spec.get("parts", []):
        for sec in _targets(part, sections):
            b0 = sec["start_bar"] * 4 + part.get("offset", 0)
            if "vocal" in part:
                # 보컬: 멜로디+가사를 가수에게 부르게 해서 오디오로 놓는다 (섹션마다 같은 노래면 한 번만 부름)
                from . import voice as voice_mod
                v = part["vocal"]
                key_ = json.dumps([v.get("voice"), v.get("melody"), v.get("lyrics"), spec["bpm"], v.get("seed", 0)])
                cache = per_track.setdefault("__vocal_cache", {})
                if key_ not in cache:
                    out = ROOT / "projects" / spec["name"] / "vocals" / _vocal_name(part, sec, "sing")
                    lang = v.get("lang") or ("ko" if any("가" <= ch <= "힣" for ch in v["lyrics"]) else "en")
                    if v.get("engine", "svc" if lang != "en" else "svs") == "svc":
                        from . import sing_svc
                        cache[key_] = sing_svc.sing_svc(v["voice"], v["lyrics"], spec["bpm"], melody=v["melody"], out=out,
                                                        lang=lang, seed=v.get("seed", 0), humanize=v.get("humanize"),
                                                        takes=v.get("takes", 3))
                        log(f"{part['track']}: sang(svc, {lang}) {cache[key_]}")
                        s[part["track"]].audio(cache[key_], start=b0, gain_db=v.get("gain_db", 0))
                        continue
                    cache[key_] = voice_mod.sing(v["voice"], v["lyrics"], spec["bpm"], melody=v["melody"], out=out,
                                                 language=v.get("language", "English"),
                                                 humanize=v.get("humanize"), seed=v.get("seed", 0),
                                                 control=v.get("control", "score"))
                    log(f"{part['track']}: sang {cache[key_]}")
                s[part["track"]].audio(cache[key_], start=b0, gain_db=v.get("gain_db", 0))
                continue
            if "rap" in part:
                # 랩: 생성된 목소리(voice_design)가 가사 줄을 말하고, 단어 시작을 박자 격자에 맞춰 늘인다
                from . import voice_design as vd
                v = part["rap"]
                key_ = json.dumps(["rap", v.get("voice"), v.get("lines"), spec["bpm"], v.get("seed", 0), v.get("lock"), v.get("tail_words", 0)])
                cache = per_track.setdefault("__vocal_cache", {})
                if key_ not in cache:
                    out = ROOT / "projects" / spec["name"] / "vocals" / _vocal_name(part, sec, "rap")
                    cache[key_], _ = vd.rap(v["voice"], v["lines"], spec["bpm"], out,
                                            beats_per_line=v.get("beats_per_line", 4),
                                            style=v.get("style", "confident rhythmic hip-hop rap delivery"),
                                            lock=v.get("lock", 0.75), seed=v.get("seed", 0), lang=v.get("lang", "en"),
                                            tail_words=v.get("tail_words", 0))
                    log(f"{part['track']}: rapped {cache[key_]}")
                s[part["track"]].audio(cache[key_], start=b0, gain_db=v.get("gain_db", 0))
                continue
            if "audio" in part:
                a = part["audio"]
                path = a["path"] if Path(a["path"]).is_absolute() else str(ROOT / a["path"])
                every = a.get("every")
                L = sec["bars"] * 4
                t = 0
                while t < L - 1e-6:
                    ln = a.get("length") or min(every or L, L - t)      # length: 섹션을 넘어 이어지는 긴 오디오(완성 비트 등)
                    s[part["track"]].audio(path, start=b0 + t, length=ln,
                                           **{k: a[k] for k in ("gain_db", "pan", "fade_in", "fade_out", "offset", "reverse")
                                              if k in a})
                    if not every:
                        break
                    t += every
                continue
            notes = part_notes(part, sec, spec)
            # 연주자 모델: 파트 > 트랙 > 곡 설정 순. false 면 악보 그대로
            pf = part.get("perform", spec.get("perform", True))
            cc, bd = [], []
            if pf and notes:
                tinfo = spec.get("tracks", {}).get(part["track"], {})
                cfg = {**(tinfo.get("perform") or {}), **(pf if isinstance(pf, dict) else {})}
                role = cfg.get("role") or tinfo.get("perform_role") or perform_mod.guess_role(
                    part["track"], tinfo.get("role", ""), str(tinfo.get("sound", "")))
                if "drums" in part:
                    role = "drums"
                if role:
                    out = perform_mod.perform(notes, role=role, bpm=spec["bpm"], feel=cfg.get("feel", spec.get("feel", "straight")),
                                              intensity=cfg.get("intensity", spec.get("intensity", 0.7)),
                                              seed=sec["start_bar"] * 31 + len(part["track"]))
                    notes, cc, bd = out["notes"], out["cc"], out["bend"]
            bucket = per_track.setdefault(part["track"], {"notes": [], "cc": [], "bend": []})
            bucket["notes"] += groove.shift(notes, beats=b0)
            bucket["cc"] += [{**c, "beat": round(c["beat"] + b0, 4)} for c in cc]
            bucket["bend"] += [{**b, "beat": round(b["beat"] + b0, 4)} for b in bd]
    per_track.pop("__vocal_cache", None)
    for name, b in per_track.items():
        if b["notes"]:
            s[name].midi(sorted(b["notes"], key=lambda n: n["start"]), start=0, length=total, name=name,
                         cc=sorted(b["cc"], key=lambda c: c["beat"]) or None, bend=sorted(b["bend"], key=lambda c: c["beat"]) or None)
        log(f"{name}: {len(b['notes'])} notes, {len(b['cc'])} cc, {len(b['bend'])} bend")

    # 오토메이션 (bar 또는 beat)
    for a in spec.get("automation", []):
        pts = [{"beat": p.get("beat", p.get("bar", 0) * 4), "value": p["value"], **({"curve": p["curve"]} if "curve" in p else {})}
               for p in a["points"]]
        s[a["track"]].automate(a["device"], a["param"], pts)

    for ev in spec.get("events", []):
        _apply_event(s, ev, sections, log)

    s.meta["spec"] = str(ROOT / "projects" / spec["name"] / "spec.json")
    s.save()

    mix = spec.get("mix", {})
    do_balance = balance if balance is not None else mix.get("balance", False)
    if do_balance:
        targets = mix.get("balance_lu") or (load_style(spec["style"]).get("mix", {}).get("balance_lu") if spec.get("style") else None)
        if targets:
            r = s.balance(targets)
            log("balance: " + ", ".join(f"{m['track']} {m['moved_db']:+.1f}" for m in r["moves"]))
    report = s.render(lufs=mix.get("target_lufs"), label=label) if render else None
    try:
        from .layout import write_readme
        write_readme(spec["name"])                     # 곡 폴더 안내서 갱신(무엇을 들으면 되는지)
    except Exception:
        pass
    return s, report


def _event_window(ev, sections):
    """사건 위치: section(이름) + occurrence(몇 번째, 1부터) + at(섹션 시작 기준 박, 음수 = 그 전) + length(박)."""
    occ = [x for x in sections if x["name"] == ev["section"]]
    if not occ:
        raise ValueError(f"event: 섹션 '{ev['section']}' 없음")
    sec = occ[min(len(occ), ev.get("occurrence", 1)) - 1]
    a = sec["start_bar"] * 4 + ev.get("at", 0)
    return a, a + ev.get("length", 1)


def _cut(track, a, b):
    """트랙의 클립에서 [a, b) 박을 비운다(자르고 가운데를 뺀다)."""
    for _ in range(64):
        hit = next((c for c in track.clips() if c["start"] < b - 1e-6 and c["end"] > a + 1e-6), None)
        if hit is None:
            return
        if hit["start"] < a - 1e-6:
            track.e.call("clip.split", {"track": track.name, "clip": hit["clip"], "at": a})
        elif hit["end"] > b + 1e-6:
            track.e.call("clip.split", {"track": track.name, "clip": hit["clip"], "at": b})
        else:
            track.e.call("clip.remove", {"track": track.name, "clip": hit["clip"]})


def _apply_event(s, ev, sections, log=print):
    """곡의 '그 순간' — 본인 기준곡(On Sight 의 비트 체인지 등)에서 온 장치.
    stop   : [section, at, length] 동안 keep 에 없는 트랙을 모두 비운다(숨 멈춤 → 다음 섹션 폭발)
    filter : tracks(기본 = 보컬·버스 빼고 전부)에 로우패스를 걸어 to(Hz)까지 닫았다가 섹션에서 연다(필터 드롭)"""
    a, b = _event_window(ev, sections)
    names = [t["name"] for t in s.e.call("edit.info")["tracks"]]
    meta = s.meta.get("tracks", {})
    def skip(n):
        role = (meta.get(n, {}).get("role") or "").lower()
        return "return" in role or n in ev.get("keep", [])
    if ev["type"] == "stop":
        for n in names:
            if not skip(n):
                _cut(s[n], a, b)
        log(f"event stop: {a}~{b}박 (유지: {ev.get('keep', [])})")
    elif ev["type"] == "filter":
        targets = ev.get("tracks") or [n for n in names if not skip(n) and not any(k in (meta.get(n, {}).get("role") or "").lower()
                                                                                     for k in ("vocal", "rap"))]
        ramp = ev.get("ramp", min(2.0, (b - a) / 2))
        for n in targets:
            d = s[n].fx("lowpass", {"frequency": 20000})
            s[n].automate(d, "frequency", [{"beat": 0, "value": 20000}, {"beat": a, "value": 20000},
                                           {"beat": a + ramp, "value": ev.get("to", 450)},
                                           {"beat": max(a + ramp, b - 0.05), "value": ev.get("to", 450)},
                                           {"beat": b, "value": 20000}])
        log(f"event filter: {a}~{b}박 → {ev.get('to', 450)}Hz ({len(targets)}트랙)")
    else:
        raise ValueError(f"모르는 event type '{ev['type']}' (stop | filter)")


def bounce(spec, age=None, stems=False, label="bounce"):
    """설계서를 '레코드'로 찍는다(샘플 소스용). age='vinyl'|'dusty'|'tape' 면 늙힌 파일도. stems=True 면 트랙별 파일도.

    직접 작곡·연주한 것이라 스템이 완벽하게 분리돼 있다(AI 분리 불필요)."""
    from . import crate
    s, rep = build(spec, render=True, label=label)
    out = {"mix": rep["file"]}
    if stems:
        out["stems"] = {}
        for t in s.e.call("edit.info")["tracks"]:
            p = s.dir / "renders" / f"stem_{t['name']}.wav"
            try:
                r = s.e.call("render", {"tracks": [t["name"]], "tail": 2.0, "path": str(p)})
                out["stems"][t["name"]] = r["path"]
            except Exception:
                pass
    if age:
        out["aged"] = crate.age(out["mix"], age)
    return out
