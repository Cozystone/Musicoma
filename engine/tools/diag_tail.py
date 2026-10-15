"""잔향·릴리즈 진단: 짧은 노트 하나 → 꼬리가 남는지 본다."""
import sys
import numpy as np
import soundfile as sf
from mc import Engine

S = "D:/0.Musicoma/sounds/sfz"
e = Engine(client="diag")


def tail_report(path, note_end_s):
    a, sr = sf.read(path, always_2d=True)
    m = np.abs(a).mean(axis=1)
    out = []
    for t in [note_end_s - 0.1, note_end_s + 0.05, note_end_s + 0.2, note_end_s + 0.5, note_end_s + 1.0, note_end_s + 2.0]:
        i = int(t * sr)
        seg = m[i:i + int(0.05 * sr)]
        out.append(f"{t:5.2f}s:{20 * np.log10(seg.mean() + 1e-9):6.1f}dB")
    return "  ".join(out)


def run(label, devices, note_len=1.0):
    e.call("edit.new", {"name": "diag", "bpm": 120})
    e.call("track.add", {"name": "T"})
    for d in devices:
        e.call("device.add", {"track": "T", **d})
    e.call("clip.add_midi", {"track": "T", "start": 0, "length": 4,
                             "notes": [{"pitch": 60, "start": 0, "length": note_len, "velocity": 100}]})
    r = e.call("render", {"tail": 3})
    print(f"{label:28s}", tail_report(r["path"], note_len * 0.5))


piano = {"device": "sfz", "sfz": f"{S}/salamander-grand-piano/Salamander Grand Piano V3.sfz"}
run("sfz piano", [piano])
run("4osc", [{"device": "4osc"}])
run("surge", [{"device": "Surge XT"}])
run("sfz piano + dragonfly hall", [piano, {"device": "Dragonfly Hall Reverb"}])
run("sfz piano + builtin reverb", [piano, {"device": "reverb"}])

e.call("edit.new", {"name": "diag", "bpm": 120})
e.call("track.add", {"name": "T"})
e.call("device.add", {"track": "T", "device": "Dragonfly Hall Reverb"})
p = e.call("device.params", {"track": "T", "device": 0})
for x in p["params"]:
    print("  ", x["index"], x["id"], x["name"], x["text"], x["value"])
