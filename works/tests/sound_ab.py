"""음색 A/B — 같은 붐뱁/소울 8마디를 옛 소리(A) vs 새 실제 샘플(B)로. 다른 건 전부 같다."""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from musicoma import arrange

PROG = "ii9 V13sus4 Imaj9 vi9"
def spec(name, drums, bass, keys, gtr):
    return {
        "name": name, "bpm": 88, "key": "Eb major", "style": "boom-bap", "feel": "laid_back", "intensity": 0.75,
        "sections": [{"name": "A", "bars": 8}],
        "tracks": {"Drums": {"preset": drums, "role": "drums", "sends": {"0": -22}},
                   "Bass": {"preset": bass, "role": "bass"},
                   "Keys": {"preset": keys, "role": "keys", "pan": -0.2, "sends": {"0": -10}},
                   "Guitar": {"preset": gtr, "role": "guitar", "pan": 0.3, "sends": {"0": -12}}},
        "buses": [{"name": "Verb", "bus": 0, "device": "Dragonfly Plate Reverb", "volume_db": -4}],
        "parts": [
            {"track": "Drums", "in": ["A"], "drums": {"pattern": {"kick": "x.....x...x.....", "snare": "....x.......x...", "hat": "x-x-x-x-x-x-x-x-"},
                                                    "swing": 0.58, "humanize_ms": 6, "humanize_vel": 8}},
            {"track": "Bass", "in": ["A"], "bass": {"progression": PROG, "beats_per_chord": 4, "low": 28, "high": 50,
                                                  "pattern": [[0, 1.5, 0], [1.75, 0.5, 7], [2.5, 1, 0], [3.5, 0.5, 12]]}},
            {"track": "Keys", "in": ["A"], "chords": {"progression": PROG, "beats_per_chord": 4, "voicing": "rhodes",
                                                     "rhythm": [[0, 1.5, 1.0], [2.5, 1.0, 0.8]], "velocity": 74}},
            {"track": "Guitar", "in": ["A"], "chords": {"progression": PROG, "beats_per_chord": 4, "voicing": "guitar",
                                                       "rhythm": [[1, 0.25, 0.8], [3, 0.25, 0.8]], "velocity": 70}},
        ],
        "mix": {"balance": True, "target_lufs": -12, "balance_lu": {"drums": 0, "bass": -2, "keys": -4, "guitar": -7}},
    }

if __name__ == "__main__":
    out = {}
    for tag, args in {"A_old": ("drums/boombap", "bass/finger", "keys/rhodes_classic", "guitar/clean"),
                      "B_new": ("drums/rusty", "bass/hollow_finger", "keys/wurlitzer", "guitar/archtop")}.items():
        s, rep = arrange.build(spec(f"zz-sound-ab-{tag}", *args), label=tag, log=lambda m: None)
        out[tag] = {k: rep[k] for k in ("file", "loudness", "bands_db", "issues")}
    print(json.dumps(out, ensure_ascii=False, default=str, indent=1))
