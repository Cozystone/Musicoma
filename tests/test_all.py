"""Musicoma 전체 점검 — 엔진 · 파이썬 계층 · 프리셋 전부 · MCP · 화면 서버.
실행: .venv/Scripts/python tests/test_all.py   (결과: tests/report.json)
"""
import json
import sys
import time
import traceback
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from musicoma.engine import connect  # noqa: E402

RESULTS = []


def check(name):
    def deco(fn):
        t0 = time.time()
        try:
            detail = fn()
            RESULTS.append({"test": name, "ok": True, "sec": round(time.time() - t0, 2), "detail": detail})
            print(f"  ok   {name}", flush=True)
        except Exception as ex:
            RESULTS.append({"test": name, "ok": False, "sec": round(time.time() - t0, 2), "error": f"{type(ex).__name__}: {ex}",
                            "trace": traceback.format_exc()[-1200:]})
            print(f"  FAIL {name}: {ex}", flush=True)
        return fn
    return deco


e = connect("test")
S = "D:/0.Musicoma/sounds"


@check("engine.basic")
def _():
    assert e.call("ping")["ok"]
    assert "render" in e.call("help")
    e.call("edit.new", {"name": "zz-test", "bpm": 100})
    t = e.call("track.add", {"name": "T1"})
    assert t["name"] == "T1"
    return "ok"


@check("engine.builtin_devices")
def _():
    out = []
    for d in ["4osc", "sampler", "sfz", "eq", "compressor", "reverb", "delay", "chorus", "phaser", "lowpass", "pitchshift"]:
        r = e.call("device.add", {"track": "T1", "device": d})
        ps = e.call("device.params", {"track": "T1", "device": r["device"]})
        out.append(f"{d}:{len(ps['params'])}")
    return out


@check("engine.vst3_all")
def _():
    av = e.call("device.available")["vst3"]
    e.call("track.add", {"name": "V"})
    names = []
    for p in av:
        r = e.call("device.add", {"track": "V", "device": p["name"]})
        e.call("device.params", {"track": "V", "device": r["device"]})
        names.append(p["name"])
    assert len(names) >= 8, names
    return names


@check("engine.compressor_units")
def _():
    e.call("track.add", {"name": "C"})
    e.call("device.add", {"track": "C", "device": "compressor"})
    r = e.call("device.set", {"track": "C", "device": 0, "params": {"threshold": -18, "ratio": 4}})
    texts = {c["name"]: c["text"] for c in r["changed"]}
    assert "-18" in texts["Threshold"] and "4.00" in texts["Ratio"], texts
    return texts


@check("engine.surge_patch_and_programs")
def _():
    e.call("track.add", {"name": "S"})
    e.call("device.add", {"track": "S", "device": "Surge XT"})
    r = e.call("device.load_file", {"track": "S", "device": 0,
                                    "path": f"{S}/plugins/vst3/Surge Synth Team/SurgeXTData/patches_factory/Keys/EP 1.fxp"})
    e.call("track.add", {"name": "D"})
    e.call("device.add", {"track": "D", "device": "Dexed"})
    progs = e.call("device.programs", {"track": "D", "device": 0})
    e.call("device.program", {"track": "D", "device": 0, "program": 3})
    return [r["loaded"], len(progs["programs"])]


@check("engine.midi_cc_bend_clip_ops")
def _():
    e.call("track.add", {"name": "P"})
    e.call("device.add", {"track": "P", "device": "sfz", "sfz": f"{S}/sfz/salamander-grand-piano/Salamander Grand Piano V3.sfz"})
    e.call("clip.add_midi", {"track": "P", "start": 0, "length": 8, "notes": [{"pitch": 60, "start": 0, "length": 2, "velocity": 90}],
                             "cc": [{"cc": 64, "beat": 0.1, "value": 127}, {"cc": 64, "beat": 1.9, "value": 0}],
                             "bend": [{"beat": 0, "value": -0.2}, {"beat": 0.1, "value": 0}]})
    c = e.call("clip.controllers", {"track": "P", "clip": 0})
    assert len(c["cc"]) == 2 and len(c["bend"]) == 2, c
    e.call("clip.duplicate", {"track": "P", "clip": 0})
    e.call("clip.split", {"track": "P", "clip": 1, "at": 12})
    e.call("clip.set", {"track": "P", "clip": 0, "start": 0, "length": 6})
    n = len(e.call("clip.list", {"track": "P"}))
    e.call("clip.remove", {"track": "P", "clip": n - 1})
    return {"clips_after": n - 1, "cc": c}


@check("engine.automation_sends_undo")
def _():
    e.call("device.add", {"track": "P", "device": "lowpass"})
    e.call("automation.set", {"track": "P", "device": 1, "param": "frequency", "points": [{"beat": 0, "value": 500}, {"beat": 4, "value": 18000}]})
    e.call("track.add", {"name": "Bus"})
    e.call("device.add", {"track": "Bus", "device": "return", "bus": 0})
    e.call("device.add", {"track": "Bus", "device": "reverb"})
    e.call("device.add", {"track": "P", "device": "send", "bus": 0, "level_db": -10})
    before = e.call("track.set", {"track": "P", "volume_db": -3})["volume_db"]
    e.call("edit.undo")
    after = [t for t in e.call("edit.info")["tracks"] if t["name"] == "P"][0]["volume_db"]
    assert abs(before + 3) < 0.01 and abs(after + 3) > 0.01, (before, after)
    return "undo ok"


@check("engine.transport_meters")
def _():
    e.call("transport.play", {"from": 0})
    time.sleep(0.6)
    e.call("meters")
    time.sleep(0.4)
    m = e.call("meters")
    st = e.call("transport.state")
    e.call("transport.stop")
    assert st["playing"]
    return {"P": m["tracks"].get("P"), "device": st.get("audio_device")}


@check("engine.render_save_load")
def _():
    r = e.call("render", {"tail": 1, "path": str(ROOT / "renders/zz-test.wav")})
    assert Path(r["path"]).stat().st_size > 10000
    e.call("edit.save")
    path = e.call("ping")["edit"]
    e.call("edit.load", {"path": path})
    return r["render_ms"]


@check("engine.audio_devices")
def _():
    d = e.call("audio.devices")
    return d.get("current")


@check("python.theory_groove_perform")
def _():
    from musicoma import theory, groove, perform
    ch = theory.progression("ii7 V7/vi vi7 bVIImaj7", "Eb")
    v = theory.voice(ch, "rhodes")
    notes = groove.chord_notes(v, 4)
    roles = ["piano", "keys", "bass", "drums", "strings", "pad", "brass", "lead", "guitar", "pluck"]
    out = {}
    for r in roles:
        src = notes if r != "drums" else groove.pattern_notes({"kick": "x...x...", "snare": "....x...", "hat": "x-x-x-x-"}, bars=2)
        res = perform.perform(src, role=r, bpm=90, feel="laid_back")
        out[r] = (len(res["notes"]), len(res["cc"]), len(res["bend"]))
    return {"chords": ch, "perform": out}


@check("python.arrange_all_presets")
def _():
    from musicoma import arrange
    from musicoma.knowledge import presets
    tracks, parts = {}, []
    for role, d in presets().items():
        for key in d:
            name = f"{role}_{key}"[:30]
            tracks[name] = {"preset": f"{role}/{key}", "role": role}
            if role == "drums":
                parts.append({"track": name, "drums": {"pattern": {"kick": "x.......x.......", "snare": "....x.......x...", "hat": "x-x-x-x-x-x-x-x-"}}})
            elif role == "bass":
                parts.append({"track": name, "bass": {"progression": "I vi IV V", "beats_per_chord": 1}})
            else:
                parts.append({"track": name, "chords": {"progression": "I vi IV V", "beats_per_chord": 1, "voicing": "piano"}})
    spec = {"name": "zz-presets", "bpm": 110, "key": "C major", "sections": [{"name": "a", "bars": 1}],
            "tracks": tracks, "parts": parts, "perform": True, "mix": {}}
    s, rep = arrange.build(spec, render=False, log=lambda m: None)
    info = e.call("edit.info")
    empty = [t["name"] for t in info["tracks"] if not t["devices"]]
    assert not empty, empty
    return {"tracks": len(info["tracks"])}


@check("python.render_stems_balance_master")
def _():
    from musicoma.song import Song
    s = Song("zz-presets", e)
    rep = s.render(lufs=-12, label="t")
    assert abs(rep["loudness"]["lufs_integrated"] + 12) < 1.0, rep["loudness"]
    return rep["loudness"]


@check("python.crate_ops")
def _():
    from musicoma import crate
    src = str(ROOT / "renders/zz-test.wav")
    a = crate.analyze(src)
    v = crate.varispeed(src, semitones=3)
    st = crate.stretch(src, rate=1.1)
    c = crate.cut(src, 0.2, 1.2)
    ch = crate.chop(src, n=4)
    kit = crate.make_kit(ch, ROOT / "sounds/crate/zz/kit.sfz") if ch else None
    ag = crate.age(src, "dusty")
    return {"bpm": a["bpm"], "chops": len(ch), "files": [Path(x).name for x in (v, st, c, ag)], "kit": bool(kit)}


@check("python.als_import")
def _():
    from musicoma import als
    f = ROOT / "research/ableton/demo-format-ref Project/demo-format-ref.als"
    if not f.exists():
        return "skip (no .als)"
    s, rep = als.import_als(f, name="zz-als", log=lambda m: None)
    return {"tracks": len(rep["tracks"])}


@check("mcp.tools")
def _():
    import asyncio
    from musicoma import mcp_server as m
    names = [t.name for t in asyncio.run(m.mcp.list_tools())]
    m.knowledge_style("올드칸예 시티팝")
    m.knowledge_tweak("킥 좀 더 펀치있게")
    m.presets_list("bass")
    m.compose("perform", {"notes": [{"pitch": 60, "start": 0, "length": 1, "velocity": 90}], "role": "lead"})
    return {"count": len(names)}


@check("ui.server_endpoints")
def _():
    base = "http://127.0.0.1:47802"
    out = {}
    for path in ["/", "/app.js", "/api/projects", "/api/sounds", "/api/presets", "/api/styles", "/api/ai-status",
                 "/api/song?name=zz-presets", "/api/renders?name=zz-presets"]:
        with urllib.request.urlopen(base + path, timeout=30) as r:
            out[path] = r.status
    return out


@check("voice.wsola_and_flow")
def _():
    import numpy as np
    from musicoma import voice_design as vd
    sr = 48000
    t = np.arange(sr) / sr
    x = (0.3 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)
    y = vd.wsola(x, 1.25)
    assert abs(len(y) - 1.25 * sr) < 2, len(y)
    # 음높이 유지 확인(영점 교차로 주파수 추정)
    zc = np.sum((y[:-1] < 0) & (y[1:] >= 0)) / (len(y) / sr)
    assert abs(zc - 220) < 6, zc
    ws = [{"w": "a", "s": 0.0, "e": 0.2}, {"w": "b", "s": 0.31, "e": 0.5}, {"w": "c", "s": 0.77, "e": 1.0}]
    ms, md = vd.flow(ws, 1.1, bpm=90, beats=2, lock=1.0)
    spb = 60 / 90
    for d in md[1:-1]:
        assert abs((d / (spb / 4)) - round(d / (spb / 4))) < 1e-6, md
    assert md[-1] <= 2 * spb + 1e-6
    return {"len": len(y), "f0": round(float(zc), 1), "marks": [round(v, 3) for v in md]}


@check("voice.designed_voices_present")
def _():
    from musicoma import voice_design as vd
    out = {}
    for v in ("gen-rapper-a", "gen-singer-b", "gen-rapper-c"):
        d = vd.VOICES / v
        if (d / "voice.json").exists():
            out[v] = {"seed": vd.info(v)["seed"], "singer": (d / "prompt.json").exists()}
    assert out, "no designed voices"
    return out


@check("styles.orchestral_card")
def _():
    from musicoma.knowledge import style
    c = style("orchestral")
    assert c["mix"]["balance_lu"]["violins"] == 0
    return {"sections": len(c["orchestration"])}


@check("theory.minor_key_romans")
def _():
    from musicoma import theory
    assert theory.progression("i VI III VII", "D", "minor") == ["Dm", "Bb", "F", "C"]
    assert theory.progression("bVI bVII i", "A", "minor") == ["F", "G", "Am"]
    assert theory.progression("i iv VI V", "A", "minor") == ["Am", "Dm", "F", "E"]
    assert theory.progression("I V vi IV", "C", "major") == ["C", "G", "Am", "F"]
    return "ok"


@check("critic.runs")
def _():
    from musicoma import critic
    spec = {"name": "t", "bpm": 90, "key": "C major", "sections": [{"name": "a", "bars": 4}, {"name": "b", "bars": 4}],
            "tracks": {"K": {}, "L": {}},
            "parts": [{"track": "K", "in": "all", "chords": {"progression": "I vi IV V", "beats_per_chord": 4}},
                      {"track": "L", "in": ["a"], "melody": "C5:1 E5:1 G5:1 C5:1 | A4:2 C5:2 | F5:4 | B4:4"},
                      {"track": "L", "in": ["b"], "melody": "C#5:1 D#5:1 F#5:2 | A#4:4 | F#5:4 | C#5:4"}]}
    r = critic.critique(spec, {"motif": {"melody": "C5:1 E5:1 G5:1"}})
    assert r["clashes"]["L"]["clash"] >= 3, r["clashes"]
    return {"score": r["score"], "issues": len(r["issues"])}


if __name__ == "__main__":
    ok = sum(r["ok"] for r in RESULTS)
    print(f"\n{ok}/{len(RESULTS)} passed")
    (ROOT / "tests/report.json").write_text(json.dumps(RESULTS, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
