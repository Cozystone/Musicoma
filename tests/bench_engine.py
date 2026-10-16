"""엔진 성능 기준표 — 트랙 수별 오프라인 렌더 속도(실시간 배수)와 장치 버퍼 지연.
자체 엔진(Musicoma Core)이 넘어야 할 기준선. 결과: tests/bench.json
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from musicoma.engine import connect  # noqa: E402

e = connect("bench")
S = "D:/0.Musicoma/sounds"
rows = []
for n in (4, 16, 32, 64):
    e.call("edit.new", {"name": f"zz-bench-{n}", "bpm": 120})
    for i in range(n):
        name = f"T{i}"
        e.call("track.add", {"name": name})
        if i % 4 == 0:
            e.call("device.add", {"track": name, "device": "sfz", "sfz": f"{S}/sfz/salamander-grand-piano/Salamander Grand Piano V3.sfz"})
        elif i % 4 == 1:
            e.call("device.add", {"track": name, "device": "Surge XT"})
        elif i % 4 == 2:
            e.call("device.add", {"track": name, "device": "Dexed"})
        else:
            e.call("device.add", {"track": name, "device": "sfz", "sfz": f"{S}/sfz/virtuosity-drums/Programs/01-basic-kit.sfz"})
        e.call("device.add", {"track": name, "device": "eq"})
        e.call("device.add", {"track": name, "device": "compressor"})
        if i % 2 == 0:
            e.call("device.add", {"track": name, "device": "reverb"})
        notes = [{"pitch": 48 + (k * 7 + i) % 24, "start": k * 0.5, "length": 0.45, "velocity": 90} for k in range(64)]
        e.call("clip.add_midi", {"track": name, "start": 0, "length": 32, "notes": notes})
    seconds = 32 * 60 / 120
    t0 = time.time()
    e.call("render", {"tail": 0.5, "path": str(ROOT / f"renders/zz-bench-{n}.wav")})
    dt = time.time() - t0
    rows.append({"tracks": n, "audio_sec": seconds, "render_sec": round(dt, 2), "x_realtime": round(seconds / dt, 1)})
    print(rows[-1], flush=True)

dev = e.call("audio.devices")
out = {"render": rows, "device": dev.get("current"), "sample_rate": dev.get("sample_rate"), "buffer": dev.get("buffer"),
       "output_latency_ms": round(1000 * dev.get("buffer", 0) / max(1, dev.get("sample_rate", 48000)), 2)}
print(out)
(ROOT / "tests/bench.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
