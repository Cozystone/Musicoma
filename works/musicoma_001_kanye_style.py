"""Musicoma 첫 작품 — 칸예 웨스트 '레이트 레지스트레이션' 시기 스타일(소울 샘플 + 붐뱁 + 오케스트라).
칸예의 목소리·실제 곡은 쓰지 않는다. 샘플 원곡도 Musicoma 가 연주해서 찍는다. 랩 벌스 자리는 비워 둔다."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from musicoma.recipes import chipmunk_soul as cs

FORM = [("intro", 4), ("verse", 16), ("hook", 8), ("verse", 16), ("hook", 8), ("bridge", 4), ("hook", 8), ("outro", 4)]


def customize(spec, notes):
    chords = " ".join(notes["sample"]["chords_after"])
    spec["sections"] = [{"name": n, "bars": b} for n, b in FORM]
    total_bars = sum(b for _, b in FORM)
    spec["feel"], spec["intensity"] = "laid_back", 0.75
    t = spec["tracks"]
    t["Drums"] = {"preset": "drums/boombap", "role": "boom bap drums", "sends": {"0": -22}}
    t["Strings"] = {"preset": "strings/ensemble", "role": "strings", "pan": -0.25, "sends": {"0": -8}}
    t["Cello"] = {"preset": "strings/cello", "role": "strings", "pan": 0.2, "sends": {"0": -10}}
    t["Horns"] = {"preset": "brass/section", "role": "brass", "pan": 0.3, "sends": {"0": -12}}
    t["Choir"] = {"preset": "pad/choir", "role": "pad", "sends": {"0": -6}}
    t["Piano"] = {"preset": "piano/grand_warm", "role": "piano", "pan": -0.1, "sends": {"0": -12}}
    parts = [p for p in spec["parts"] if p["track"] not in ("Keys",)]
    hooks, verses = ["hook"], ["verse"]
    parts += [
        {"track": "Strings", "in": hooks + ["bridge"], "chords": {"progression": chords, "beats_per_chord": 4, "voicing": "pad", "velocity": 72}},
        {"track": "Cello", "in": hooks, "bass": {"progression": chords, "beats_per_chord": 4, "low": 36, "high": 55,
                                                     "pattern": [[0, 3.8, 12]]}},
        {"track": "Horns", "in": hooks, "chords": {"progression": chords, "beats_per_chord": 4, "voicing": "stab",
                                                    "rhythm": [[0, 0.5, 1.0], [2.5, 0.75, 0.9]], "velocity": 92}},
        {"track": "Choir", "in": ["bridge", "outro"], "chords": {"progression": chords, "beats_per_chord": 4, "voicing": "pad", "velocity": 70}},
        {"track": "Piano", "in": verses, "chords": {"progression": chords, "beats_per_chord": 4, "voicing": "piano",
                                                     "rhythm": [[0, 1.5, 0.8], [3.5, 0.5, 0.6]], "velocity": 64}},
    ]
    # 브리지: 드럼·베이스 빠지고 오케스트라만 → 마지막 훅 폭발
    spec["parts"] = [p for p in parts if not (p["track"] in ("Drums", "Bass") and p.get("in") == "bridge")]
    for p in spec["parts"]:
        if p["track"] == "Sample":
            p["in"] = ["intro", "verse", "hook", "outro"]
    spec["automation"] = [{"track": "Sample", "device": 1, "param": "frequency",
                           "points": [{"bar": 0, "value": 700}, {"beat": 15.75, "value": 1100}, {"bar": 4, "value": 20000},
                                      {"bar": total_bars - 4, "value": 20000}, {"bar": total_bars, "value": 500}]}]
    spec["mix"] = {"balance": True, "target_lufs": -10.5,
                   "balance_lu": {"drums": 0, "sample": -1.5, "chops": -2, "bass": -2.5, "strings": -5, "cello": -7,
                                  "horns": -6, "choir": -8, "piano": -8}}
    spec["brief"] = "Musicoma 첫 작품 — 칸예 레이트 레지스트레이션 스타일(소울 칩멍크 샘플 + 붐뱁 + 오케스트라), 랩 벌스 자리 비움"
    return spec


if __name__ == "__main__":
    s, notes, rep = cs.build("musicoma-001", bpm=86, semitones=4, key="Bb major", source_style="soul", lead="violin",
                             seed=23, brief="칸예 스타일 첫 작품", label="v2", customize=customize)
    print({k: rep[k] for k in ("file", "loudness", "bands_db", "issues", "png")})
