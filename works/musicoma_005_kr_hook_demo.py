"""musicoma-005 — 개선 확인용 데모(16마디): 새 실제 샘플 악기 + 한국어로 '노래하는' 훅(SVC 경로) + 영어 랩.
verse(8) = 래퍼 A, hook(8) = 여성 소울 싱어가 한국어로 부름 + 래퍼 A 애드립 없음(보컬 겹침 피함)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from musicoma import arrange

PROG = "ii9 V13sus4 Imaj9 vi9"
HOOK_MEL = ("E4:.5 F#4:.5 A4:1 r:.5 B4:.5 A4:.5 F#4:.5 E4:.5 F#4:.5 A4:1 r:.5 B4:.5 C#5:.5 B4:.5 A4:.5 A4:1.5 r:4 "
            "E4:.5 F#4:.5 A4:1 r:.5 B4:.5 A4:.5 F#4:.5 E4:.5 F#4:.5 A4:1 r:.5 C#5:.5 B4:.5 A4:.5 F#4:.5 E4:1.5 r:4")
HOOK_LYR = "오늘 밤 도시의 불빛이 나를 부르네 + 너와 나 둘이서 이 밤을 걸어가 +"
VERSE = ["Woke up in the city with the vinyl on repeat", "Mama in the kitchen humming something kind of sweet",
         "Dusty little record from a summer in Tokyo", "Speed it up a little now the angels sing soprano",
         "I was in the basement with a sampler and a dream", "Everybody laughing saying that is not a team",
         "Now I got the strings and I got the horns on top", "Turn the city pop into a hip-hop shop"]

spec = {
    "name": "musicoma-005-kr-hook", "bpm": 86, "key": "A major", "style": "neo-soul", "feel": "laid_back", "intensity": 0.75,
    "sections": [{"name": "intro", "bars": 2}, {"name": "verse", "bars": 8}, {"name": "hook", "bars": 8}, {"name": "outro", "bars": 2}],
    "tracks": {
        "Drums": {"preset": "drums/rusty", "role": "drums", "sends": {"0": -22}},
        "Bass": {"preset": "bass/hollow_finger", "role": "bass"},
        "Keys": {"preset": "keys/wurlitzer", "role": "keys", "pan": -0.2, "sends": {"0": -10}},
        "Guitar": {"preset": "guitar/archtop", "role": "guitar", "pan": 0.3, "sends": {"0": -12}},
        "Rap": {"role": "rap vocal", "sends": {"0": -20},
                "fx": [{"device": "eq", "params": {"Low-pass freq": 120, "Low-pass gain": -8, "Mid freq 2": 3200, "Mid gain 2": 3}},
                       {"device": "compressor", "params": {"threshold": -20, "ratio": 4, "attack": 8, "release": 90}}]},
        "Vox": {"role": "sung hook vocal (Korean)", "sends": {"0": -12},
                "fx": [{"device": "eq", "params": {"Low-pass freq": 150, "Low-pass gain": -6, "Mid freq 2": 3500, "Mid gain 2": 2.5}},
                       {"device": "compressor", "params": {"threshold": -18, "ratio": 3, "attack": 10, "release": 120}}]},
    },
    "buses": [{"name": "Verb", "bus": 0, "device": "Dragonfly Plate Reverb", "volume_db": -4}],
    "parts": [
        {"track": "Drums", "in": ["verse", "hook"], "drums": {"pattern": {"kick": "x.....x...x.....", "snare": "....x.......x...",
                                                                          "hat": "x-x-x-x-x-x-x-x-"}, "swing": 0.58,
                                                              "humanize_ms": 6, "humanize_vel": 8}},
        {"track": "Bass", "in": ["verse", "hook"], "bass": {"progression": PROG, "beats_per_chord": 4, "low": 28, "high": 50,
                                                            "pattern": [[0, 1.5, 0], [1.75, 0.5, 7], [2.5, 1, 0], [3.5, 0.5, 12]]}},
        {"track": "Keys", "in": "all", "chords": {"progression": PROG, "beats_per_chord": 4, "voicing": "rhodes",
                                                 "rhythm": [[0, 1.5, 1.0], [2.5, 1.0, 0.8]], "velocity": 72}},
        {"track": "Guitar", "in": ["hook"], "chords": {"progression": PROG, "beats_per_chord": 4, "voicing": "guitar",
                                                      "rhythm": [[1, 0.25, 0.8], [3, 0.25, 0.8]], "velocity": 66}},
        {"track": "Rap", "in": ["verse"], "rap": {"voice": "gen-rapper-a", "lines": VERSE, "beats_per_line": 4, "seed": 11}},
        {"track": "Vox", "in": ["hook"], "vocal": {"voice": "gen-singer-b", "melody": HOOK_MEL, "lyrics": HOOK_LYR,
                                                   "lang": "ko", "takes": 3, "seed": 5}},
    ],
    "mix": {"balance": True, "target_lufs": -12, "balance_lu": {"drums": 0, "rap": 1.5, "vox": 1.5, "bass": -2, "keys": -5, "guitar": -8}},
}

if __name__ == "__main__":
    s, rep = arrange.build(spec, label=sys.argv[1] if len(sys.argv) > 1 else "v1")
    print(json.dumps({k: rep[k] for k in ("file", "loudness", "bands_db", "issues", "png")}, ensure_ascii=False, default=str))
