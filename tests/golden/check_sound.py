"""새 엔진 소리 = 옛 엔진 소리? — capture_fx 와 같은 곡을 새 엔진(port)으로 렌더해 골든과 널 테스트.

    .venv/Scripts/python tests/golden/check_sound.py [port=47811] [case,case…]
잔차(dB) = 20·log10(rms(새-옛)/rms(옛)). -60 이하면 사실상 같음, -30 이하면 귀로 구분 어려움.
"""
import json
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).parent))
from musicoma.engine import Engine, EngineError  # noqa: E402
from capture_fx import CASES, MIX  # noqa: E402

G = ROOT / "scratch" / "golden" / "fx"
OUT = ROOT / "scratch" / "golden" / "new_fx"
OUT.mkdir(parents=True, exist_ok=True)
port = int(next((a for a in sys.argv[1:] if a.isdigit()), 47811))
want = set(",".join(a for a in sys.argv[1:] if not a.isdigit()).split(",")) - {""}
inp = str(G / "input.wav")

e = Engine(port=port, client="check-sound")
e.call("edit.new", {"name": "zz-check-sound", "bpm": 120})
names = []
for name, dev, params in CASES:
    if want and name not in want:
        continue
    e.call("track.add", {"name": name})
    e.call("clip.add_audio", {"track": name, "path": inp, "start": 0})
    if dev:
        try:
            e.call("device.add", {"track": name, "device": dev})
            if params:
                e.call("device.set", {"track": name, "device": 0, "params": params})
        except EngineError as ex:
            print(f"{name:20s} SKIP ({ex})")
            continue
    names.append(name)
for name, mix in MIX:
    if want and name not in want:
        continue
    e.call("track.add", {"name": name})
    e.call("clip.add_audio", {"track": name, "path": inp, "start": 0})
    e.call("track.set", {"track": name, **mix})
    names.append(name)
if not want or "send_bus" in want:
    e.call("track.add", {"name": "send_src"})
    e.call("clip.add_audio", {"track": "send_src", "path": inp, "start": 0})
    e.call("device.add", {"track": "send_src", "device": "send", "bus": 0, "level_db": -6})
    e.call("track.add", {"name": "bus"})
    e.call("device.add", {"track": "bus", "device": "return", "bus": 0})


def resid(a, b):
    n = min(len(a), len(b))
    a, b = a[:n], b[:n]
    return 20 * np.log10(np.sqrt(np.mean((a - b) ** 2)) / (np.sqrt(np.mean(b ** 2)) + 1e-12) + 1e-12)


rows = {}
for name in names:
    e.call("render", {"path": str(OUT / f"{name}.wav"), "start": 0, "end": 32, "tail": 0, "tracks": [name]})
if not want or "send_bus" in want:
    e.call("render", {"path": str(OUT / "send_bus.wav"), "start": 0, "end": 32, "tail": 0, "tracks": ["send_src", "bus"]})
    names.append("send_bus")
for name in names:
    a, _ = sf.read(str(OUT / f"{name}.wav"), dtype="float64", always_2d=True)
    b, _ = sf.read(str(G / f"{name}.wav"), dtype="float64", always_2d=True)
    r = resid(a, b)
    la = 20 * np.log10(np.sqrt(np.mean(a ** 2)) + 1e-12)
    lb = 20 * np.log10(np.sqrt(np.mean(b ** 2)) + 1e-12)
    rows[name] = {"residual_db": round(r, 1), "level_new_db": round(la, 2), "level_old_db": round(lb, 2)}
    print(f"{name:20s} residual {r:7.1f} dB   level new {la:6.2f} / old {lb:6.2f}")
(OUT / "report.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
