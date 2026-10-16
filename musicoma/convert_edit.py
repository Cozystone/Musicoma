"""옛 편집 파일(.tracktionedit, Tracktion 엔진) → 새 엔진 편집 파일(.edit.json) 옮기기 (10-16 자체 엔진 교체).

옛 엔진이 떠 있어야 한다(그 엔진으로 곡을 열어 트랙·클립·디바이스·파라미터 값을 읽는다 — core_export 사용).
VST3 플러그인 상태는 파라미터 값(정규화, id 별)으로 옮긴다(state_params) — 파라미터가 아닌 내부 상태는 빠질 수 있다.
오토메이션은 옛 엔진이 명령으로 내주지 않아 옮기지 못한다(곡은 spec.json 으로 다시 지으면 그대로 생김).

    python -m musicoma.convert_edit                 projects/* 전부(이미 .edit.json 이 있으면 건너뜀)
    python -m musicoma.convert_edit <곡 이름|경로> [--force]
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _slot(dev, e, track_ref, index, uid):
    k = dev.get("kind")
    s = {"uid": uid, "enabled": dev.get("enabled", True)}
    vals = dev.get("params") or {}
    if k == "sfz":
        s.update(kind="sfz", sfz=dev.get("sfz"), state={"volume": dev.get("volume_db", 0.0)})
    elif k == "vst3":
        s.update(kind="vst3", vst3={"name": dev.get("plugin") or dev.get("name")})
        try:
            r = e.call("device.params", {"track": track_ref, "device": index})
            ps = r.get("params", r) if isinstance(r, dict) else r
            # 새 엔진의 VST3 파라미터 id 는 ParamID(옛 엔진은 플러그인 순번) → 이름으로 옮긴다
            s["state_params"] = [{"name": p["name"], "index": p["id"], "value": p["value"]} for p in ps]
        except Exception:
            pass
    elif k == "send":
        s.update(kind="send", bus=dev.get("bus", 0), level_db=dev.get("level_db", -12))
    elif k == "return":
        s.update(kind="return", bus=dev.get("bus", 0))
    elif k == "compressor":
        s.update(kind="builtin", builtin="compressor",
                 state={"threshold": dev.get("threshold_db", -6), "ratio": dev.get("ratio", 2), "attack": dev.get("attack_ms", 100),
                        "release": dev.get("release_ms", 100), "output gain": dev.get("output_db", 0)})
    elif k == "lowpass":
        s.update(kind="builtin", builtin="lowpass", state={"frequency": dev.get("frequency", 4000), "mode": dev.get("mode", "lowpass")})
    elif k in ("eq", "reverb", "delay", "chorus", "phaser", "pitchshift"):
        s.update(kind="builtin", builtin=k, state={kk: v for kk, v in vals.items() if isinstance(v, (int, float))})
    else:
        return None
    return s


def convert(project, force=False, log=print):
    from .core_export import export_plan
    from .engine import connect
    proj_dir = ROOT / "projects" / project
    old = proj_dir / f"{project}.tracktionedit"
    new = proj_dir / f"{project}.edit.json"
    if new.exists() and not force:
        return {"project": project, "skipped": "exists"}
    if not old.exists():
        return {"project": project, "skipped": "no .tracktionedit"}
    e = connect("convert")
    plan = export_plan(project=project)
    uid = [1]

    def next_uid():
        uid[0] += 1
        return uid[0]

    out = {"format": "musicoma-edit", "version": 1, "name": project, "bpm": plan.get("bpm", 120),
           "time_sig": plan.get("time_sig", "4/4"), "master_volume_db": plan["master"].get("volume_db", -3), "master": [], "tracks": [],
           "converted_from": str(old)}
    for i, d in enumerate(plan["master"].get("chain", [])):
        s = _slot(d, e, "master", i, next_uid())
        if s:
            out["master"].append(s)
    warn = []
    for t in plan["tracks"]:
        to = {"name": t["name"], "volume_db": t.get("volume_db", 0), "pan": t.get("pan", 0), "mute": t.get("mute", False),
              "solo": t.get("solo", False), "slots": [], "clips": []}
        for i, d in enumerate(t.get("chain", [])):
            s = _slot(d, e, t["index"], i, next_uid())
            if s:
                to["slots"].append(s)
            else:
                warn.append(f"{t['name']}: device {d.get('name')} ({d.get('kind')}) not converted")
        clips = [(c["index"], "midi", c) for c in t.get("midi_clips", [])] + [(c["index"], "audio", c) for c in t.get("audio_clips", [])]
        for _, kind, c in sorted(clips, key=lambda x: x[0]):
            base = {"name": c.get("name") or "", "start": c["start_beat"], "length": c["end_beat"] - c["start_beat"], "mute": c.get("mute", False)}
            if kind == "midi":
                base.update(midi=True, notes=[[n["pitch"], n["start"], n["length"], n["velocity"]] for n in c.get("notes", [])],
                            cc=[[x["cc"], x["beat"], x["value"]] for x in c.get("cc", [])],
                            bend=[[x["beat"], x["value"]] for x in c.get("bend", [])])
            else:
                base.update(midi=False, path=c.get("file"), offset_sec=c.get("offset_sec", 0), gain_db=c.get("gain_db", 0),
                            pan=c.get("pan", 0), fade_in=c.get("fade_in_sec", 0), fade_out=c.get("fade_out_sec", 0),
                            reverse=c.get("reverse", False))
            to["clips"].append(base)
        # 옛 엔진에서 잘린 클립(비트 스톱 등)은 원래 시퀀스 전체를 들고 '오프셋'으로 가린다 → 노트를 옮기고 범위 밖은 버림
        seen = {}
        for c in to["clips"]:
            if not c.get("midi") or not c["notes"]:
                continue
            key = json.dumps(c["notes"][:8])
            if key in seen and len(seen[key]["notes"]) == len(c["notes"]):
                shift = c["start"] - seen[key]["start"]
                c["notes"] = [[p, st - shift, ln, v] for p, st, ln, v in c["notes"] if 0 <= st - shift < c["length"]]
                c["cc"] = [[n, b - shift, v] for n, b, v in c["cc"] if 0 <= b - shift < c["length"]]
                c["bend"] = [[b - shift, v] for b, v in c["bend"] if 0 <= b - shift < c["length"]]
            else:
                seen[key] = dict(c)
                c["notes"] = [n for n in c["notes"] if n[1] < c["length"]]
        out["tracks"].append(to)
    new.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    if warn:
        log(f"{project}: " + "; ".join(warn))
    return {"project": project, "path": str(new), "tracks": len(out["tracks"]), "warnings": warn}


def main(argv):
    force = "--force" in argv
    names = [a for a in argv if not a.startswith("--")]
    if not names:
        names = sorted(p.parent.name for p in (ROOT / "projects").glob("*/*.tracktionedit")
                       if not p.parent.name.startswith(("zz-", "probe", "diag", "smoke")))
    for n in names:
        n = Path(n).stem.replace(".tracktionedit", "") if n.endswith(".tracktionedit") else n
        try:
            print(json.dumps(convert(n, force), ensure_ascii=False))
        except Exception as ex:
            print(json.dumps({"project": n, "error": str(ex)[:300]}, ensure_ascii=False))


if __name__ == "__main__":
    main(sys.argv[1:])
