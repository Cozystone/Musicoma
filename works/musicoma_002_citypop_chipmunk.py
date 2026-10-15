"""Musicoma 두 번째 작품(기능 테스트) — 올드 칸예식 칩멍크 소울 × 80년대 일본 시티팝 샘플링.

1 레코드   : 시티팝 발라드를 Musicoma 가 직접 작곡·연주. B 구간 보컬 = 매번 새로 '생성한' 여성 소울 목소리(VoxCPM2 → SoulX)
2 샘플링   : 레코드 후렴 4마디를 +4반음 배속(칩멍크) + 비닐, 보컬 스템을 찹 → 패드
3 비트     : 붐뱁 + 오케스트라(스트링·첼로·호른·콰이어)
4 랩       : 생성한 래퍼 두 명(A 허스키 중년 / C 젊은 테너). 벌스1 = A, 벌스2 = A·C 4마디씩 주고받기(듀엣),
             훅 = A 챈트 + C 더블(겹목소리)
실존 인물의 목소리·가사·녹음은 쓰지 않는다. 가사는 새로 씀.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from musicoma import voice, voice_design as vd
from musicoma.recipes import chipmunk_soul as cs

NAME = "musicoma-002"
BPM = 88
FORM = [("intro", 4), ("verse", 16), ("hook", 8), ("verse2", 16), ("hook", 8), ("bridge", 4), ("hook", 8), ("outro", 4)]

VOICES = {
    "gen-singer-b": ("A warm female soul singer in her late twenties, smooth mellow alto, gentle and soulful, "
                     "a little breathy, nostalgic 1980s city-pop ballad feel", 771,
                     "Ooh, baby, the city lights are shining just for you tonight, so hold me close and never let me go, "
                     "I will be there for you."),
    "gen-rapper-a": ("A husky middle-aged man, deep gravelly baritone, confident hip-hop rapper, relaxed swagger", 4210, None),
    "gen-rapper-c": ("A young man in his early twenties, bright energetic tenor, hungry and fast, playful hip-hop flow, "
                     "slightly nasal", 5531, None),
}

RECORD_LYRICS = ("midnight drive in the city lights you and me tonight hold me close baby "
                 "never let go of this love so bright shining on and on")

VERSE1 = [
    "Woke up in the city with the vinyl on repeat",
    "Mama in the kitchen humming something kind of sweet",
    "Dusty little record from a summer in Tokyo",
    "Speed it up a little now the angels sing soprano",
    "I was in the basement with a sampler and a dream",
    "Everybody laughing saying that is not a team",
    "Now I got the strings and I got the horns on top",
    "Turn the city pop into a hip-hop shop",
    "Never had a plan B never had a backup",
    "Every time they doubt me I just turn the track up",
    "Chipmunk choir in the background going high",
    "Heaven on a loop and I am never asking why",
    "Sunday morning soul with a Monday kind of grind",
    "Leave the past behind but I keep it in the rhyme",
    "Every single sample got a story in the beat",
    "So I play it back and put the city on its feet",
]
VERSE2 = [  # 4마디씩 A → C → A → C
    ("gen-rapper-a", ["Back then I was broke with a keyboard and a hope",
                      "Writing on a napkin with a pencil and a quote",
                      "Now the lights are blinking from the Shibuya to the coast",
                      "And I raise a little glass to the ones who matter most"]),
    ("gen-rapper-c", ["Yo I am the new kid with the old soul in the bag",
                      "Pitch it up a third and let the chorus wave a flag",
                      "Cut it on the one and let the snare drag",
                      "Two voices on a record never sounding like a drag"]),
    ("gen-rapper-a", ["Keep it on the vinyl keep it warm keep it real",
                      "Every little crackle is a feeling you can feel",
                      "City lights shining like a diamond in the steel",
                      "Spin it one more time because the moment is the deal"]),
    ("gen-rapper-c", ["Midnight in the city and we running out of time",
                      "Every single dollar going back into the rhyme",
                      "Two generations on a sample so divine",
                      "Speed it up and slow it down and let the city shine"]),
]
HOOK = [
    ("City lights, city lights, take me higher", 8),
    ("Chipmunk soul and a midnight fire", 8),
    ("City lights, city lights, never tired", 8),
    ("Play it back till the night retires", 8),
]


def ensure_voices():
    for name, (desc, seed, sample) in VOICES.items():
        if not (vd.VOICES / name / "design.wav").exists() or vd.info(name).get("seed") != seed:
            vd.design(desc, seed=seed, name=name, sample_text=sample)
            print("designed", name)
    if not (voice.VOICES / "gen-singer-b" / "prompt.json").exists():
        print(voice.add_voice_aligned("gen-singer-b", vd.VOICES / "gen-singer-b" / "design.wav"))


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
    vox_fx = [{"device": "eq", "params": {"Low-pass freq": 120, "Low-pass gain": -8, "Mid freq 2": 3200, "Mid gain 2": 3.5,
                                           "High-pass freq": 9000, "High-pass gain": 2.5}},
              {"device": "compressor", "params": {"threshold": -20, "ratio": 4, "attack": 8, "release": 90}}]
    t["Rap A"] = {"role": "rap vocal A", "pan": 0.0, "sends": {"0": -20}, "fx": vox_fx}
    t["Rap C"] = {"role": "rap vocal C", "pan": 0.0, "sends": {"0": -20}, "fx": vox_fx}
    t["Hook A"] = {"role": "hook vocal A", "pan": -0.12, "sends": {"0": -16}, "fx": vox_fx}
    t["Hook C"] = {"role": "hook double C", "pan": 0.12, "sends": {"0": -16}, "fx": vox_fx}

    verses = ["verse", "verse2"]
    parts = [p for p in spec["parts"] if p["track"] not in ("Keys",)]
    for p in parts:                                  # 레시피 기본 파트를 새 섹션 이름에도
        if p.get("in") == ["verse"]:
            p["in"] = verses
        elif isinstance(p.get("in"), list) and "verse" in p["in"]:
            p["in"] = p["in"] + ["verse2"]
    parts += [
        {"track": "Strings", "in": ["hook", "bridge"], "chords": {"progression": chords, "beats_per_chord": 4, "voicing": "pad", "velocity": 72}},
        {"track": "Cello", "in": ["hook"], "bass": {"progression": chords, "beats_per_chord": 4, "low": 36, "high": 55, "pattern": [[0, 3.8, 12]]}},
        {"track": "Horns", "in": ["hook"], "chords": {"progression": chords, "beats_per_chord": 4, "voicing": "stab",
                                                       "rhythm": [[0, 0.5, 1.0], [2.5, 0.75, 0.9]], "velocity": 92}},
        {"track": "Choir", "in": ["bridge", "outro"], "chords": {"progression": chords, "beats_per_chord": 4, "voicing": "pad", "velocity": 70}},
        # 랩
        {"track": "Rap A", "in": ["verse"], "rap": {"voice": "gen-rapper-a", "lines": VERSE1, "beats_per_line": 4, "seed": 11}},
        {"track": "Hook A", "in": ["hook"], "rap": {"voice": "gen-rapper-a", "lines": [{"text": l, "beats": b} for l, b in HOOK],
                                                    "style": "chanting a catchy hip-hop hook, rhythmic, energetic", "lock": 0.9, "seed": 21}},
        {"track": "Hook C", "in": ["hook"], "rap": {"voice": "gen-rapper-c", "lines": [{"text": l, "beats": b} for l, b in HOOK],
                                                    "style": "chanting a catchy hip-hop hook, rhythmic, energetic", "lock": 0.9, "seed": 22, "gain_db": -4}},
    ]
    for i, (v, lines) in enumerate(VERSE2):          # 듀엣: 4마디씩 주고받기
        parts.append({"track": "Rap A" if v == "gen-rapper-a" else "Rap C", "in": ["verse2"], "offset": i * 16,
                      "rap": {"voice": v, "lines": lines, "beats_per_line": 4, "seed": 31 + i}})
    spec["parts"] = [p for p in parts if not (p["track"] in ("Drums", "Bass") and p.get("in") == "bridge")]
    for p in spec["parts"]:
        if p["track"] == "Sample":
            p["in"] = ["intro", "verse", "hook", "verse2", "outro"]
        if p["track"] == "Chops":
            p["in"] = ["hook", "bridge"]
    spec["automation"] = [{"track": "Sample", "device": 1, "param": "frequency",
                           "points": [{"bar": 0, "value": 700}, {"beat": 15.75, "value": 1100}, {"bar": 4, "value": 20000},
                                      {"bar": total_bars - 4, "value": 20000}, {"bar": total_bars, "value": 500}]}]
    spec["mix"] = {"balance": True, "target_lufs": -10.5,
                   "balance_lu": {"drums": 0, "rap a": 1.5, "rap c": 1.5, "hook a": 1.0, "hook c": -3, "sample": -2.5,
                                  "chops": -4, "bass": -2.5, "strings": -6, "cello": -8, "horns": -7, "choir": -8}}
    spec["brief"] = "칩멍크 소울 × 시티팝 샘플(직접 연주 + 생성 여성 보컬), 래퍼 2명 듀엣(생성 목소리)"
    return spec


if __name__ == "__main__":
    label = sys.argv[1] if len(sys.argv) > 1 else "v1"
    ensure_voices()
    s, notes, rep = cs.build(NAME, bpm=BPM, semitones=4, key="F major", source_style="city-pop", lead="rhodes",
                             seed=37, brief="칩멍크 소울 × 시티팝, 생성 보컬 듀엣", label=label, customize=customize,
                             vocal={"voice": "gen-singer-b", "lyrics": RECORD_LYRICS, "low": 57, "high": 72})
    print(json.dumps({k: rep[k] for k in ("file", "loudness", "bands_db", "issues", "png")}, ensure_ascii=False, default=str))
