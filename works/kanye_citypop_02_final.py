"""kanye-citypop-02 최종 — 본인 "비트 레전드, 이 비트에 랩 얹어서 마무리" (10-15).

비트 = kanye-citypop-02_v1.wav 를 한 샘플도 바꾸지 않고 오디오 트랙으로(88 BPM, A major, 40마디).
그 위에 생성 래퍼 두 명: 벌스1 = A(허스키 중년), 훅 = A 챈트 + C 더블, 벌스2 = A·C 2마디씩 주고받기.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from musicoma import arrange

SUNG = str(Path(__file__).resolve().parents[1] / "projects/kanye-citypop-02/vocals/hook_A_human.wav")   # 본인 "보컬로이드 같아도 매력" — 하이톤 유지
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
                      "So I raise a glass to the ones who matter most"]),
    ("gen-rapper-c", ["Midnight in the city and we running out of time",
                      "Speed it up and slow it down and let the city shine"]),
]
HOOK = [("City lights, city lights, take me higher", 8), ("Chipmunk soul and a midnight fire", 8),
        ("City lights, city lights, never tired", 8), ("Play it back till the night retires", 8)]
LOCK = 0.88          # v2: 박자 격자에 더 단단히(0.75 → 0.88) — 본인 "2% 부족한 싱크"
HOOK_STYLE = "chanting a catchy hip-hop hook, rhythmic, energetic"

VOX_FX = [{"device": "eq", "params": {"Low-pass freq": 120, "Low-pass gain": -8, "Mid freq 2": 3200, "Mid gain 2": 3.5,
                                      "High-pass freq": 9000, "High-pass gain": 2.5}},
          {"device": "compressor", "params": {"threshold": -20, "ratio": 4, "attack": 8, "release": 90}}]

spec = {
    "name": "kanye-citypop-02-final", "bpm": 88, "key": "A major", "style": "chipmunk-soul",
    "brief": "kanye-citypop-02 v1 비트(그대로) + 하이톤 노래 훅(인트로 티저·훅) → 남자 랩(더블) · 벌스2 듀엣",
    "sections": [{"name": "intro", "bars": 4}, {"name": "verse", "bars": 8}, {"name": "hook", "bars": 8},
                 {"name": "verse2", "bars": 8}, {"name": "hook", "bars": 8}, {"name": "outro", "bars": 4}],
    "tracks": {
        "Beat": {"role": "beat (kanye-citypop-02 v1, untouched)",
                 # v2: 보컬 자리만 살짝 — 3kHz -1.5dB(넓게). 비트 자체는 그대로
                 "fx": [{"device": "eq", "params": {"Mid freq 2": 3000, "Mid gain 2": -1.5, "Mid Q 2": 0.7}}]},
        "Rap A": {"role": "rap vocal A", "sends": {"0": -20}, "fx": VOX_FX},
        "Rap C": {"role": "rap vocal C", "sends": {"0": -20}, "fx": VOX_FX},
        "Sung": {"role": "sung hook vocal (high, kanye-citypop-02 v2 A_human)", "sends": {"0": -10},
                 "fx": [{"device": "eq", "params": {"Low-pass freq": 160, "Low-pass gain": -6, "Mid freq 1": 320, "Mid gain 1": -2.5,
                                                    "Mid Q 1": 1.0, "Mid freq 2": 6500, "Mid gain 2": -2.0, "Mid Q 2": 2.0,
                                                    "High-pass freq": 11000, "High-pass gain": 1.5}},
                        {"device": "compressor", "params": {"threshold": -20, "ratio": 3, "attack": 12, "release": 140}}]},
        "Rap A dbl": {"role": "rap double A", "pan": 0.35, "sends": {"0": -24}, "fx": VOX_FX},
    },
    "buses": [{"name": "Verb", "bus": 0, "device": "Dragonfly Plate Reverb", "volume_db": -6}],
    "parts": [
        {"track": "Beat", "in": ["intro"], "audio": {"path": BEAT, "length": 163.7}},   # 처음 한 번, 파일 전체(111.6초 = 163.7박)
        {"track": "Rap A", "in": ["verse"], "rap": {"voice": "gen-rapper-a", "lines": VERSE1, "beats_per_line": 4, "seed": 11, "lock": LOCK}},
        {"track": "Sung", "in": ["intro"], "audio": {"path": SUNG, "gain_db": -3, "length": 16}},
        {"track": "Sung", "in": ["hook"], "audio": {"path": SUNG, "length": 16}},
        {"track": "Sung", "in": ["hook"], "offset": 16, "audio": {"path": SUNG, "length": 16}},
        {"track": "Rap A dbl", "in": ["verse"], "rap": {"voice": "gen-rapper-a", "lines": VERSE1, "beats_per_line": 4, "seed": 12,
                                                        "lock": LOCK, "gain_db": -4, "tail_words": 2}},   # 줄 끝 두 단어(운)만 더블
    ],
    "mix": {"balance": True, "target_lufs": -10.5,
            "balance_lu": {"beat": 0, "rap a dbl": -4.0, "rap a": 3.0, "rap c": 3.0, "sung": 2.0}},   # v3: 하이톤 훅 + 더블
}
for i, (v, lines) in enumerate(VERSE2):
    spec["parts"].append({"track": "Rap A" if v == "gen-rapper-a" else "Rap C", "in": ["verse2"], "offset": i * 8,
                          "rap": {"voice": v, "lines": lines, "beats_per_line": 4, "seed": 31 + i, "lock": LOCK}})

if __name__ == "__main__":
    s, rep = arrange.build(spec, label=sys.argv[1] if len(sys.argv) > 1 else "v1")
    print(json.dumps({k: rep[k] for k in ("file", "loudness", "bands_db", "issues", "png")}, ensure_ascii=False, default=str))
