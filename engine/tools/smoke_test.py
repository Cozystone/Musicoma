"""엔진 동작 확인용 8마디: 피아노(SFZ) + 드럼(SFZ) + 베이스(Surge XT) + 홀 리버브."""
import random
from mc import Engine

S = "D:/0.Musicoma/sounds/sfz"
random.seed(7)
e = Engine(client="smoke")

e.call("edit.new", {"name": "smoke-test", "bpm": 92})

# 트랙
for name in ["Piano", "Drums", "Bass"]:
    e.call("track.add", {"name": name})

e.call("device.add", {"track": "Piano", "device": "sfz", "sfz": f"{S}/salamander-grand-piano/Salamander Grand Piano V3.sfz"})
e.call("device.add", {"track": "Piano", "device": "Dragonfly Hall Reverb"})
e.call("device.add", {"track": "Drums", "device": "sfz", "sfz": f"{S}/virtuosity-drums/Programs/01-basic-kit.sfz"})
e.call("device.add", {"track": "Bass", "device": "Surge XT"})

# Am - F - C - G, 마디당 4박, 2바퀴
chords = [[57, 60, 64], [53, 57, 60], [48, 55, 60, 64], [55, 59, 62]]
roots = [45, 41, 36, 43]
piano, bass, drums = [], [], []

for bar in range(8):
    c = chords[bar % 4]
    b0 = bar * 4
    for i, p in enumerate(c):
        piano.append({"pitch": p, "start": b0 + i * 0.03, "length": 1.9, "velocity": random.randint(62, 74)})
        piano.append({"pitch": p, "start": b0 + 2.5 + i * 0.02, "length": 1.4, "velocity": random.randint(52, 62)})
    piano.append({"pitch": c[-1] + 12, "start": b0 + 1.5, "length": 0.5, "velocity": 58})

    r = roots[bar % 4]
    for beat, length in [(0, 1.5), (1.5, 0.5), (2, 1.0), (3, 0.75)]:
        bass.append({"pitch": r if beat != 3 else r + 7, "start": b0 + beat, "length": length, "velocity": 96})

    for step in range(8):
        t = b0 + step * 0.5
        drums.append({"pitch": 42, "start": t, "length": 0.25, "velocity": 78 if step % 2 == 0 else 54})
    for t in (0, 2.5):
        drums.append({"pitch": 36, "start": b0 + t, "length": 0.5, "velocity": 108})
    for t in (1, 3):
        drums.append({"pitch": 38, "start": b0 + t, "length": 0.5, "velocity": 100})
    if bar % 4 == 3:
        drums.append({"pitch": 38, "start": b0 + 3.75, "length": 0.25, "velocity": 70})

drums.append({"pitch": 49, "start": 0, "length": 2, "velocity": 96})

e.call("clip.add_midi", {"track": "Piano", "start": 0, "length": 32, "name": "chords", "notes": piano})
e.call("clip.add_midi", {"track": "Bass", "start": 0, "length": 32, "name": "bass", "notes": bass})
e.call("clip.add_midi", {"track": "Drums", "start": 0, "length": 32, "name": "groove", "notes": drums})

e.call("track.set", {"track": "Bass", "volume_db": -10})
e.call("track.set", {"track": "Drums", "volume_db": -2})
e.call("track.set", {"track": "Piano", "volume_db": -3, "pan": -0.1})

e.call("edit.save")
info = e.call("edit.info")
for t in info["tracks"]:
    print(t["name"], [d["name"] + (f" ({d.get('regions')} regions)" if "regions" in d else "") for d in t["devices"]],
          [c["notes"] for c in t["clips"]])

r = e.call("render", {"tail": 3, "lufs": -14})
print(r)
