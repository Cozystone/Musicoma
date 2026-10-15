"""kanye-citypop-02 최종 — 본인 "비트 레전드, 이 비트에 랩 얹어서 마무리" (10-15).

비트 = kanye-citypop-02_v1.wav 를 한 샘플도 바꾸지 않고 오디오 트랙으로(88 BPM, A major, 40마디).
그 위에 생성 래퍼 두 명: 벌스1 = A(허스키 중년), 훅 = A 챈트 + C 더블, 벌스2 = A·C 2마디씩 주고받기.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from musicoma import arrange

BEAT = str(Path(__file__).resolve().parents[1] / "projects/kanye-citypop-02/renders/kanye-citypop-02_v1.wav")

VERSE1 = [
    "Woke up in the city with the vinyl on repeat",
    "Mama in the kitchen humming something kind of sweet",
    "Dusty little record from a summer in Tokyo",
    "Speed it up a little now the angels sing soprano",
    "I was in the basement with a sampler and a dream",
    "Everybody laughing saying that is not a team",
    "Now I got the strings and I got the horns on top",
    "Turn the city pop into a hip-hop shop",
]
VERSE2 = [  # 2마디씩 A → C → A → C
    ("gen-rapper-a", ["Back then I was broke with a keyboard and a hope",
                      "Writing on a napkin with a pencil and a quote"]),
    ("gen-rapper-c", ["Yo I am the new kid with the old soul in the bag",
                      "Pitch it up a third and let the chorus wave a flag"]),
    ("gen-rapper-a", ["Now the lights are blinking from the Shibuya to the coast",
                      "And I raise a little glass to the ones who matter most"]),
    ("gen-rapper-c", ["Midnight in the city and we running out of time",
                      "Speed it up and slow it down and let the city shine"]),
]
HOOK = [("City lights, city lights, take me higher", 8), ("Chipmunk soul and a midnight fire", 8),
        ("City lights, city lights, never tired", 8), ("Play it back till the night retires", 8)]
HOOK_STYLE = "chanting a catchy hip-hop hook, rhythmic, energetic"

VOX_FX = [{"device": "eq", "params": {"Low-pass freq": 120, "Low-pass gain": -8, "Mid freq 2": 3200, "Mid gain 2": 3.5,
                                      "High-pass freq": 9000, "High-pass gain": 2.5}},
          {"device": "compressor", "params": {"threshold": -20, "ratio": 4, "attack": 8, "release": 90}}]

spec = {
    "name": "kanye-citypop-02-final", "bpm": 88, "key": "A major", "style": "chipmunk-soul",
    "brief": "kanye-citypop-02 v1 비트(그대로) + 생성 래퍼 2명 랩",
    "sections": [{"name": "intro", "bars": 4}, {"name": "verse", "bars": 8}, {"name": "hook", "bars": 8},
                 {"name": "verse2", "bars": 8}, {"name": "hook", "bars": 8}, {"name": "outro", "bars": 4}],
    "tracks": {
        "Beat": {"role": "beat (kanye-citypop-02 v1, untouched)"},
        "Rap A": {"role": "rap vocal A", "sends": {"0": -20}, "fx": VOX_FX},
        "Rap C": {"role": "rap vocal C", "sends": {"0": -20}, "fx": VOX_FX},
        "Hook A": {"role": "hook vocal A", "pan": -0.12, "sends": {"0": -16}, "fx": VOX_FX},
        "Hook C": {"role": "hook double C", "pan": 0.12, "sends": {"0": -16}, "fx": VOX_FX},
    },
    "buses": [{"name": "Verb", "bus": 0, "device": "Dragonfly Plate Reverb", "volume_db": -6}],
    "parts": [
        {"track": "Beat", "in": ["intro"], "audio": {"path": BEAT, "length": 163.7}},   # 처음 한 번, 파일 전체(111.6초 = 163.7박)
        {"track": "Rap A", "in": ["verse"], "rap": {"voice": "gen-rapper-a", "lines": VERSE1, "beats_per_line": 4, "seed": 11}},
        {"track": "Hook A", "in": ["hook"], "rap": {"voice": "gen-rapper-a", "lines": [{"text": l, "beats": b} for l, b in HOOK],
                                                    "style": HOOK_STYLE, "lock": 0.9, "seed": 21}},
        {"track": "Hook C", "in": ["hook"], "rap": {"voice": "gen-rapper-c", "lines": [{"text": l, "beats": b} for l, b in HOOK],
                                                    "style": HOOK_STYLE, "lock": 0.9, "seed": 22, "gain_db": -4}},
    ],
    "mix": {"balance": True, "target_lufs": -10.5,
            "balance_lu": {"beat": 0, "rap a": 1.0, "rap c": 1.0, "hook a": 0.5, "hook c": -3.5}},
}
for i, (v, lines) in enumerate(VERSE2):
    spec["parts"].append({"track": "Rap A" if v == "gen-rapper-a" else "Rap C", "in": ["verse2"], "offset": i * 8,
                          "rap": {"voice": v, "lines": lines, "beats_per_line": 4, "seed": 31 + i}})

if __name__ == "__main__":
    s, rep = arrange.build(spec, label=sys.argv[1] if len(sys.argv) > 1 else "v1")
    print(json.dumps({k: rep[k] for k in ("file", "loudness", "bands_db", "issues", "png")}, ensure_ascii=False, default=str))
