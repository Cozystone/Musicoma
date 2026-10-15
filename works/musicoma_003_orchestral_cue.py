"""장르 테스트 — 오케스트라(영화음악) 큐 24마디. 장르 카드 orchestral.yaml 을 따른다. 드럼 비트 없음, 다이내믹으로 쌓기.
intro(현 pp) → A(첼로 선율 + 현 화음 + 호른 받침) → B(호른 영웅 동기 + 트럼펫·트롬본 + 팀파니, ff) → end(현만 남아 사라짐)"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from musicoma import arrange
from musicoma.knowledge import style

card = style("orchestral")
PAN = card["mix"]["seating_pan"]
PROG = "i VI III VII"

CELLO_A = "D3:2 F3:1 A3:1 | D4:3 C4:1 | A3:2 G3:1 F3:1 | E3:3 r:1 | D3:2 F3:1 A3:1 | D4:2 F4:1 E4:1 | C4:2 A3:2 | G3:2 E3:2"
HORN_B = "A4:2 D5:1 E5:1 | F5:3 D5:1 | C5:2 A4:1 C5:1 | G4:4 | A4:2 D5:1 E5:1 | F5:2 G5:1 A5:1 | G5:2 F5:1 E5:1 | E5:4"
FLUTE_B = "r:2 A5:2 | D6:4 | C6:4 | r:2 G5:2 | r:2 A5:2 | F6:4 | E6:4 | E6:4"
TIMP = [{"pitch": 50, "start": 0, "length": 1, "velocity": 104}, {"pitch": 45, "start": 2, "length": 1, "velocity": 84}]
ROLL = [{"pitch": 50, "start": 2 + i * 0.125, "length": 0.12, "velocity": 50 + i * 4} for i in range(16)]


def strip(sound, role, name):
    return {"sound": sound, "role": role, "pan": PAN.get(name, 0), "sends": {"0": -4}}


spec = {
    "name": "musicoma-003-orchestral", "bpm": 76, "key": "D minor", "style": "orchestral",
    "brief": "오케스트라 큐(장르 테스트) — 섹션 쌓기와 다이내믹",
    "sections": [{"name": "intro", "bars": 4}, {"name": "A", "bars": 8}, {"name": "B", "bars": 8}, {"name": "end", "bars": 4}],
    "feel": "loose", "intensity": 0.8,
    "tracks": {
        "Violins": strip("strings_violins", "strings", "violins"),
        "Violas": strip("strings_violas", "strings", "violas"),
        "Cellos": strip("strings_cello", "strings", "cellos"),
        "Basses": {**strip("contrabass", "bass", "basses"), "perform_role": "strings"},
        "Horns": strip("horn", "brass", "horns"),
        "Trumpets": strip("trumpet", "brass", "trumpets"),
        "Trombones": strip("trombone", "brass", "trombones"),
        "Flute": strip("flute", "lead", "flute"),
        "Timpani": {**strip("timpani", "drums", "timpani"), "perform_role": "drums"},
    },
    "buses": [{"name": "Hall", "bus": 0, "device": "Dragonfly Hall Reverb", "volume_db": -3}],
    "parts": [
        {"track": "Violins", "in": ["intro", "A", "B", "end"],
         "chords": {"progression": PROG, "beats_per_chord": 4, "voicing": "pad", "velocity": 62, "legato": 1.0}},
        {"track": "Violins", "in": ["B"],
         "chords": {"progression": PROG, "beats_per_chord": 4, "voicing": "pad", "velocity": 96, "legato": 1.0}, "transpose": 12},
        {"track": "Violas", "in": ["A", "B"],
         "chords": {"progression": PROG, "beats_per_chord": 4, "voicing": "pad", "velocity": 70, "legato": 1.0}, "transpose": -12},
        {"track": "Cellos", "in": ["intro", "end"], "bass": {"progression": PROG, "beats_per_chord": 4, "low": 38, "high": 52,
                                                            "pattern": [[0, 3.9, 0]]}},
        {"track": "Cellos", "in": ["A"], "melody": CELLO_A},
        {"track": "Cellos", "in": ["B"], "bass": {"progression": PROG, "beats_per_chord": 4, "low": 38, "high": 52,
                                                 "pattern": [[0, 1.9, 0], [2, 1.9, 7]]}},
        {"track": "Basses", "in": ["A", "B"], "bass": {"progression": PROG, "beats_per_chord": 4, "low": 28, "high": 43,
                                                       "pattern": [[0, 3.9, 0]]}},
        {"track": "Horns", "in": ["A"], "chords": {"progression": PROG, "beats_per_chord": 4, "voicing": "pad", "velocity": 58}, "transpose": -12},
        {"track": "Horns", "in": ["B"], "melody": HORN_B},
        {"track": "Trumpets", "in": ["B"], "chords": {"progression": PROG, "beats_per_chord": 4, "voicing": "stab",
                                                     "rhythm": [[0, 1.5, 1.0], [3, 1.0, 0.85]], "velocity": 90}},
        {"track": "Trombones", "in": ["B"], "chords": {"progression": PROG, "beats_per_chord": 4, "voicing": "pad", "velocity": 84}, "transpose": -12},
        {"track": "Flute", "in": ["B"], "melody": FLUTE_B},
        {"track": "Timpani", "in": ["B"], "notes": TIMP, "cycle_beats": 4},
        {"track": "Timpani", "in": ["A"], "notes": ROLL, "offset": 28},
    ],
    "mix": {"balance": True, "target_lufs": card["mix"]["target_lufs"], "balance_lu": card["mix"]["balance_lu"]},
}

if __name__ == "__main__":
    s, rep = arrange.build(spec, label=sys.argv[1] if len(sys.argv) > 1 else "v1")
    print(json.dumps({k: rep[k] for k in ("file", "loudness", "bands_db", "issues", "png")}, ensure_ascii=False, default=str))
