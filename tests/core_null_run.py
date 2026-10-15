"""scratch/core/<이름>/plan.json 을 musicoma-core 로 렌더하고 engine.wav 와 비교 (엔진은 안 씀).

    python tests/core_null_run.py [names...] [--tune key=value ...] [--seg 0.5]
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
from core_compare import compare  # noqa: E402

EXE = ROOT / "core/build/musicoma-core.exe"
SCR = ROOT / "scratch/core"


def run(name, tunes=(), seg=None, quiet=False):
    d = SCR / name
    cmd = [str(EXE), "render", str(d / "plan.json"), str(d / "core.wav"), "--stats", str(d / "core_stats.json")]
    for t in tunes:
        cmd += ["--tune", t]
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    if p.returncode != 0:
        raise RuntimeError(p.stderr)
    st = json.loads((d / "core_stats.json").read_text(encoding="utf-8"))
    c = compare(d / "engine.wav", d / "core.wav", seg)
    c["core_render_sec"] = st["render_sec"]
    c["core_realtime_x"] = st["realtime_x"]
    c["core_peak_ram_mb"] = st["peak_ram_mb"]
    b = json.loads((d / "build.json").read_text(encoding="utf-8"))
    c["engine_render_sec"] = round(b.get("engine_render_ms", 0) / 1000, 3)
    return c


if __name__ == "__main__":
    args = sys.argv[1:]
    tunes, names, seg = [], [], None
    i = 0
    while i < len(args):
        if args[i] == "--tune":
            tunes.append(args[i + 1]); i += 2
        elif args[i] == "--seg":
            seg = float(args[i + 1]); i += 2
        else:
            names.append(args[i]); i += 1
    names = names or ["cal-piano", "cal-pan", "cal-bass", "cal-drums", "piano", "drums", "bass", "mix"]
    for n in names:
        c = run(n, tunes, seg)
        segs = c.pop("segments", None)
        print(n, json.dumps({k: c[k] for k in ("lufs_diff", "residual_db", "residual_db_raw", "lag_ms", "gain_db",
                                                  "core_realtime_x", "core_peak_ram_mb")}),
              json.dumps(c["bands_diff_db"]), flush=True)
        if segs:
            print("   ", " ".join(f"{s['t']}:{s['diff_db']:+.1f}" for s in segs))
