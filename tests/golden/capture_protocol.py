"""골든 기록 ① — 지금 엔진(Tracktion 판)의 명령·응답을 그대로 적어 둔다(10-16, 자체 엔진 교체 전).
새 엔진은 이 응답의 '모양'(키·자료형·단위)을 따라야 한다. 코드를 읽는 게 아니라 바깥에서 본 동작을 기록 — 클린룸 기준.

    .venv/Scripts/python tests/golden/capture_protocol.py   → tests/golden/protocol.json
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from musicoma.engine import connect, EngineError  # noqa: E402

OUT = Path(__file__).with_name("protocol.json")
S = ROOT / "sounds"
log = []
e = connect("golden")


def call(method, params=None, note=""):
    t0 = time.time()
    try:
        r = e.call(method, params or {})
        log.append({"method": method, "params": params or {}, "ok": True, "result": r, "ms": round((time.time() - t0) * 1000), "note": note})
        return r
    except EngineError as ex:
        log.append({"method": method, "params": params or {}, "ok": False, "error": str(ex), "note": note})
        return None


call("ping")
call("help")
call("edit.new", {"name": "zz-golden", "bpm": 96})
call("edit.set", {"bpm": 100, "time_sig": "3/4"})
call("edit.set", {"time_sig": "4/4"})
call("device.available")
call("audio.devices")
call("inputs.list")

# 트랙·악기
call("track.add", {"name": "Piano"})
call("device.add", {"track": "Piano", "device": "sfz", "sfz": str(S / "sfz/salamander-grand-piano/Salamander Grand Piano V3.sfz")})
call("track.add", {"name": "Synth"})
call("device.add", {"track": "Synth", "device": "Surge XT"})
call("device.load_file", {"track": "Synth", "device": 0, "path": str(S / "plugins/vst3/Surge Synth Team/SurgeXTData/patches_factory/Keys/EP 1.fxp")})
call("device.programs", {"track": "Synth", "device": 0})
call("device.params", {"track": "Synth", "device": 0, "filter": "volume"})
call("track.add", {"name": "FM"})
call("device.add", {"track": "FM", "device": "Dexed"})
call("device.params", {"track": "FM", "device": 0, "filter": "cutoff"})

# 내장 이펙트 전부 — 파라미터 이름·범위·기본값·표시 문자열
fx = ["eq", "compressor", "reverb", "delay", "chorus", "phaser", "lowpass", "pitchshift"]
call("track.add", {"name": "FX"})
for i, name in enumerate(fx):
    call("device.add", {"track": "FX", "device": name})
for i, name in enumerate(fx):
    call("device.params", {"track": "FX", "device": i}, note=name)
call("device.set", {"track": "FX", "device": 0, "params": {"Low-pass freq": 110, "Low-pass gain": -6, "Mid freq 2": 3200, "Mid gain 2": 1.5, "Mid Q 2": 0.7}})
call("device.set", {"track": "FX", "device": 1, "params": {"threshold": -20, "ratio": 4, "attack": 8, "release": 100, "output gain": 3}})
call("device.set", {"track": "FX", "device": 6, "params": {"frequency": 1800}})
call("device.set", {"track": "FX", "device": 1, "enabled": False})
call("device.params", {"track": "FX", "device": 1}, note="compressor after set")

# 버스(센드·리턴)
call("track.add", {"name": "Hall"})
call("device.add", {"track": "Hall", "device": "return", "bus": 0})
call("device.add", {"track": "Hall", "device": "Dragonfly Hall Reverb"})
call("device.add", {"track": "Piano", "device": "send", "bus": 0, "level_db": -12})
call("device.add", {"track": "master", "device": "compressor"})
call("track.set", {"track": "Piano", "volume_db": -3, "pan": -0.3})
call("track.set", {"track": "Synth", "mute": True})
call("track.set", {"track": "Synth", "mute": False, "solo": False, "name": "Synth"})

# 클립
call("clip.add_midi", {"track": "Piano", "start": 0, "length": 8, "name": "chords",
                       "notes": [{"pitch": 60, "start": 0, "length": 1, "velocity": 100}, {"pitch": 64, "start": 1, "length": 1, "velocity": 90},
                                 {"pitch": 67, "start": 2, "length": 2, "velocity": 80}],
                       "cc": [{"cc": 64, "beat": 0, "value": 127}, {"cc": 64, "beat": 3.9, "value": 0}],
                       "bend": [{"beat": 2, "value": 0.5}]})
call("clip.list", {"track": "Piano"})
call("clip.notes", {"track": "Piano", "clip": 0})
call("clip.controllers", {"track": "Piano", "clip": 0})
call("clip.set_notes", {"track": "Piano", "clip": 0, "notes": [{"pitch": 62, "start": 0.5, "length": 0.5, "velocity": 70}], "replace": False})
call("clip.duplicate", {"track": "Piano", "clip": 0})
call("clip.split", {"track": "Piano", "clip": 1, "at": 12})
call("clip.set", {"track": "Piano", "clip": 0, "name": "intro", "mute": False})
wav = next((S / "crate").rglob("*.wav"), None) or next(S.rglob("*.wav"))
call("track.add", {"name": "Audio"})
call("clip.add_audio", {"track": "Audio", "path": str(wav), "start": 4, "length": 8, "gain_db": -3, "fade_in": 0.1, "fade_out": 0.2})
call("clip.set", {"track": "Audio", "clip": 0, "gain_db": -1.5, "pan": 0.2, "reverse": True})
call("clip.list", {"track": "Audio"})
call("automation.set", {"track": "FX", "device": 6, "param": "frequency", "points": [{"beat": 0, "value": 400}, {"beat": 8, "value": 8000, "curve": 0.5}]})
call("edit.info")
call("transport.state")
call("meters")
call("transport.metronome", {"enabled": False})

# 저장·렌더·되돌리기
call("edit.save")
out = ROOT / "scratch" / "golden" / "render.wav"
out.parent.mkdir(parents=True, exist_ok=True)
call("render", {"path": str(out), "end": 8, "tail": 1})
call("render", {"path": str(out.with_name("piano_only.wav")), "end": 4, "tail": 0.5, "tracks": ["Piano"]})
call("track.remove", {"track": "Audio"})
call("edit.undo")
call("edit.redo")
call("device.preset_save", {"track": "FM", "device": 0, "name": "golden_fm"})
call("device.preset_load", {"track": "FM", "device": 0, "name": "golden_fm"})
call("device.remove", {"track": "FX", "device": 7})

# 오류 모양
call("clip.notes", {"track": "Nope", "clip": 0}, note="error: unknown track")
call("device.add", {"track": "FX", "device": "NoSuchPlugin"}, note="error: unknown device")
call("nonsense.method", {}, note="error: unknown method")

OUT.write_text(json.dumps({"captured": time.strftime("%Y-%m-%d %H:%M"), "engine": "Tracktion Engine 3.5 + JUCE 8 (old)",
                           "calls": log}, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
print("calls", len(log), "errors", sum(not c["ok"] for c in log), "->", OUT)
