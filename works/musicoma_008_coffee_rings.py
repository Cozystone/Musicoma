"""musicoma-008 「Coffee Rings」 — 누자베스 계열 재즈힙합, 영어 랩(신나는 재즈힙합 랩, Luv(sic) 바이브). Claude 기획.

0 레퍼런스: knowledge/references/jazz-hop.yaml (Luv(sic) Hexalogy · Aruarian Dance · Feather)
1 콘셉트 → 이야기 구조(벌스 12·14마디) → 동기(플루트) → 비평
2 반주 → 랩 = 반주를 '듣고' 생성(lego, 가이드 전용 악기 트랙 합, 구간 8마디 이하, 같은 목소리 참조, 조성 적합도)
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from musicoma import arrange, concept as concept_mod, critic, lego, lyrics as lyr_mod, motif

NAME = "musicoma-008-coffee-rings"
BPM, KEY = 92, "D minor"
SPB = 60 / BPM

VERSE1 = ["Morning in the city and the coffee's getting cold", "Beat on the speaker and a story to be told",
          "Piano on a loop like a river in the spring", "Every little note is a thing I wanna bring",
          "Walking through the market with a rhythm in my feet", "Saying hello to the vendors on the street",
          "Saxophone is calling from a window up above", "Every little sample is a letter of love",
          "I don't need a lot, just a pen and a page", "And a crate full of records from a different age",
          "Life is like a sample, gotta flip it till it's new", "So I play it back and give it all to you"]
HOOK = ["Coffee rings on the table, little circles of the days", "We keep spinning like a record in a hundred different ways",
        "Turn it up a little, let the morning carry on", "Every loop is a promise till the melody is gone"]
VERSE2 = ["Sunset on the rooftop and the city's turning gold", "Friend on the corner with a story getting old",
          "Talk about the future like it's waiting at the door", "Laugh about the past and we don't need more",
          "Bass line on the floor and it's walking like a man", "Who knows where he's going and he got a little plan",
          "Drummer in the basement, time behind the beat", "That's the way it should feel, loose and sweet",
          "Flute up in the clouds and a rhodes in the rain", "Every chord a window, looking through the pane",
          "I don't chase the money, I just follow the sound", "From the tape to the turntable spinning round and round",
          "If you hear this later on a morning of your own", "Know the loop is still playing and you're never alone"]

CONCEPT = {
    "thesis": "아침 커피 자국처럼 하루하루가 남기는 작은 원들 — 샘플을 뒤집듯 삶을 다시 틀어 보는, 들뜨지만 서두르지 않는 고백",
    "arc": [{"section": "intro", "intent": "피아노 루프와 플루트, 아침 공기", "energy": 0.3},
            {"section": "verse", "intent": "도시를 걸으며 이야기 — 가볍게 신남", "energy": 0.6},
            {"section": "hook", "intent": "커피 자국 = 반복되는 날들, 함께 흥얼거림", "energy": 0.8},
            {"section": "verse2", "intent": "해 질 녘 옥상, 친구와 음악", "energy": 0.65},
            {"section": "bridge", "intent": "비트가 빠지고 플루트·로즈만 — 숨", "energy": 0.3},
            {"section": "hook_last", "intent": "다시 돌아온 그루브, 약속", "energy": 0.9},
            {"section": "outro", "intent": "루프는 계속 돈다", "energy": 0.4}],
    "motif": {"melody": "A4:.5 C5:.5 D5:.5 F5:1 E5:.5 D5:1", "why": "커피잔 가장자리를 도는 원 — 올라갔다 제자리로"},
    "collision": ["90년대 일본 재즈힙합 피아노 루프", "라틴 재즈 플루트", "동네 아침 시장의 리듬"],
    "constraints": ["드럼 틀은 곡 내내 같다 — 화음과 악기만 장마다 바뀐다(Luv(sic))", "MPC 스윙 0.57", "훅도 랩 톤(멜로딕 랩)"],
    "events": [{"section": "hook_last", "at": -1, "length": 1, "type": "stop", "why": "돌아오기 직전 숨"}],
    "irregular": [{"what": "벌스 12·14마디", "why": "이야기 길이만큼"},
                  {"what": "브리지 비트 체인지 — 드럼·베이스가 빠지고 플루트·로즈만", "why": "On Sight 의 세계 전환"},
                  {"what": "마지막 훅 직전 1박 정지", "why": "돌아오는 순간을 크게"}],
    "references": "knowledge/references/jazz-hop.yaml",
    "not": ["808", "트랩 하이햇", "기계적으로 곧은 리듬", "같은 4마디 복사"],
}

SECTIONS = [{"name": "intro", "bars": 4}, {"name": "verse", "bars": 12}, {"name": "hook", "bars": 8},
            {"name": "verse2", "bars": 14}, {"name": "hook", "bars": 8}, {"name": "bridge", "bars": 4},
            {"name": "hook_last", "bars": 8}, {"name": "outro", "bars": 8}]
PROG = {"loop": "i9 iv9 VII7 IIImaj7", "hook": "VImaj7 VII7 i9 i9", "bridge": "VImaj7 v7 iv9 VII7"}
DRUM = {"kick": "x.....x...x..x..", "snare": "....x.......x...", "hat": "x-x-x-x-x-x-x-xx"}


def drums(fill=True):
    return {"pattern": DRUM, "swing": 0.57, "humanize_ms": 8, "humanize_vel": 10,
            **({"fill": {"kick": "x.....x.", "snare": "....x..xoxo.x.xx"}} if fill else {})}


def chords_for(prog, bars):
    from musicoma import theory
    ch = theory.progression(PROG[prog], "D", "minor")
    return [(b * 4, b * 4 + 4, ch[b % len(ch)]) for b in range(bars)]


M = CONCEPT["motif"]["melody"]
FLUTE_INTRO = motif.section_melody(M, [], chords_for("loop", 4), KEY, 4, "statement answer")
FLUTE_HOOK = motif.section_melody(M, ["octave:1"], chords_for("hook", 4), KEY, 4, "statement sequence climb answer")
FLUTE_BRIDGE = motif.section_melody(M, ["augment:2"], chords_for("bridge", 4), KEY, 4, "statement question")
SAX_V2 = motif.section_melody(M, ["octave:-1", "rhythm:.75,.25,.5,1,.5,1"], chords_for("loop", 4), KEY, 4, "fragment sequence climb answer")

spec = {
    "name": NAME, "bpm": BPM, "key": KEY, "style": "lofi-hiphop", "feel": "laid_back", "intensity": 0.75,
    "brief": "「Coffee Rings」 재즈힙합 · 영어 랩 · Claude 기획",
    "sections": SECTIONS,
    "tracks": {
        "Drums": {"preset": "drums/rusty", "role": "drums", "sends": {"0": -24}},
        "Bass": {"preset": "bass/upright_real", "role": "bass"},
        "Piano": {"preset": "piano/grand_warm", "role": "piano", "pan": -0.15, "sends": {"0": -14}},
        "Rhodes": {"preset": "keys/rhodes_classic", "role": "keys", "pan": 0.25, "sends": {"0": -12}, "fx": [{"device": "chorus"}]},
        "Flute": {"preset": "lead/flute", "role": "lead", "pan": 0.1, "sends": {"0": -8}},
        "Sax": {"preset": "lead/alto_sax", "role": "lead", "pan": -0.2, "sends": {"0": -10}},
        "Strings": {"preset": "strings/ensemble", "role": "strings", "sends": {"0": -6}},
    },
    "buses": [{"name": "Room", "bus": 0, "device": "Dragonfly Plate Reverb", "volume_db": -6}],
    "parts": [
        # 드럼 틀은 곡 내내 같다(브리지만 빠짐)
        {"track": "Drums", "in": ["verse", "hook", "verse2", "hook_last", "outro"], "drums": drums()},
        {"track": "Drums", "in": ["intro"], "drums": {"pattern": {"hat": "x-x-x-x-x-x-x-xx"}, "swing": 0.57, "humanize_ms": 8}},
        {"track": "Bass", "in": ["verse", "verse2", "outro"], "bass": {"progression": PROG["loop"], "beats_per_chord": 4, "low": 28, "high": 50,
                                                                    "pattern": [[0, 1.5, 0], [1.75, 0.5, 7], [2.5, 1, 0], [3.5, 0.5, 10]]}},
        {"track": "Bass", "in": ["hook", "hook_last"], "bass": {"progression": PROG["hook"], "beats_per_chord": 4, "low": 28, "high": 50,
                                                               "pattern": [[0, 1, 0], [1, 0.5, 7], [1.75, 0.75, 12], [2.5, 1, 0], [3.5, 0.5, 7]]}},
        # 피아노 루프(절) — 화음은 장마다 바뀐다
        {"track": "Piano", "in": ["intro", "verse", "verse2", "outro"], "chords": {"progression": PROG["loop"], "beats_per_chord": 4, "voicing": "piano",
                                                                               "rhythm": [[0, 1.5, 1.0], [1.75, 0.5, 0.7], [2.5, 1.25, 0.85]], "velocity": 70}},
        {"track": "Piano", "in": ["hook", "hook_last"], "chords": {"progression": PROG["hook"], "beats_per_chord": 4, "voicing": "piano",
                                                                  "rhythm": [[0, 0.75, 1.0], [0.75, 0.75, 0.8], [2, 1.5, 0.9]], "velocity": 74}},
        {"track": "Rhodes", "in": ["bridge"], "chords": {"progression": PROG["bridge"], "beats_per_chord": 4,
                                                                  "voicing": "rhodes", "rhythm": [[0, 2, 1.0], [2.5, 1.5, 0.8]], "velocity": 66}},
        {"track": "Rhodes", "in": ["hook", "hook_last"], "chords": {"progression": PROG["hook"], "beats_per_chord": 4, "voicing": "rhodes",
                                                                   "rhythm": [[1, 0.5, 0.8], [3, 0.5, 0.8]], "velocity": 60}},
        {"track": "Strings", "in": ["hook", "hook_last", "outro"], "chords": {"progression": PROG["hook"], "beats_per_chord": 4, "voicing": "pad", "velocity": 58, "legato": 1.0}},
        {"track": "Flute", "in": ["intro"], "melody": {"text": FLUTE_INTRO, "velocity": 84, "repeat": False}},
        {"track": "Flute", "in": ["hook", "hook_last"], "melody": {"text": FLUTE_HOOK, "velocity": 72, "repeat": True}},
        {"track": "Flute", "in": ["bridge"], "melody": {"text": FLUTE_BRIDGE, "velocity": 90, "repeat": False}},
        {"track": "Sax", "in": ["verse2"], "offset": 32, "melody": {"text": SAX_V2, "velocity": 76, "repeat": False}},
        {"track": "Flute", "in": ["outro"], "melody": {"text": FLUTE_INTRO, "velocity": 76, "repeat": True}},
    ],
    "events": CONCEPT["events"],
    "mix": {"balance": True, "target_lufs": -12,
            "balance_lu": {"drums": 0, "bass": -2, "piano": -3, "rhodes": -7, "flute": -5, "sax": -6, "strings": -9, "rap": 2.5}},
}


def rap_sections():
    """랩 구간 — 8마디 이하. 한 줄 = 1마디. 훅도 랩(멜로딕)."""
    out, bar = [], 0
    starts = {}
    for s in SECTIONS:
        starts.setdefault(s["name"], []).append((bar, s["bars"]))
        bar += s["bars"]
    def t(b):
        return round(b * 4 * SPB, 3)
    v1 = starts["verse"][0][0]
    out += [{"name": "verse_a", "start": t(v1), "end": t(v1 + 6), "tag": "Verse", "lyrics": "\n".join(VERSE1[:6])},
            {"name": "verse_b", "start": t(v1 + 6), "end": t(v1 + 12), "tag": "Verse", "lyrics": "\n".join(VERSE1[6:])}]
    v2 = starts["verse2"][0][0]
    out += [{"name": "verse2_a", "start": t(v2), "end": t(v2 + 7), "tag": "Verse", "lyrics": "\n".join(VERSE2[:7])},
            {"name": "verse2_b", "start": t(v2 + 7), "end": t(v2 + 14), "tag": "Verse", "lyrics": "\n".join(VERSE2[7:])}]
    for i, (b0, n) in enumerate(starts["hook"] + starts["hook_last"]):
        out.append({"name": f"hook{i + 1}", "start": t(b0), "end": t(b0 + n), "tag": "Chorus", "lyrics": "\n".join(HOOK)})
    return sorted(out, key=lambda x: x["start"])


if __name__ == "__main__":
    step = sys.argv[1] if len(sys.argv) > 1 else "all"
    label = sys.argv[2] if len(sys.argv) > 2 else "v1"
    concept_mod.save(NAME, CONCEPT)
    r = critic.critique(spec, CONCEPT)
    print(critic.format_report(r).split("Claude 가")[0])
    for l in (VERSE1, HOOK, VERSE2):
        for row in lyr_mod.check_rap(l, BPM, 4 if l is not HOOK else 8):
            if row["problems"]:
                print("가사:", row["line"][:40], row["problems"])
    if step == "dry":
        sys.exit(0)
    root = Path(arrange.ROOT) / "projects" / NAME
    if step in ("all", "inst"):
        s, rep = arrange.build(spec, label="inst")
        print("반주:", rep["file"], rep["loudness"]["lufs_integrated"])
    if step in ("all", "vocal"):
        guide = lego.render_guide(spec)
        caption = ("male rap vocals, english, upbeat jazz hip-hop, conversational storytelling flow, smooth and clear, "
                   "slightly behind the beat, warm mid-range voice")
        vox, rep_v = lego.vocal_track(root / "renders" / f"{NAME}_inst.wav", rap_sections(), BPM, KEY, caption,
                                      root / "vocals" / "rap_lego.wav", takes=10, guide_wav=guide, pass_wer=0.3, min_key_fit=0.0)
        for x in rep_v:
            print(x["section"], "seed", x["chosen"], "오류율", x["wer"], "유사도", x["voice_sim"])
    if step in ("all", "final"):
        import glob
        vox = sorted(glob.glob(str(root / "vocals" / "rap_lego*.wav")))[-1]
        spec["tracks"]["Rap"] = {"role": "rap vocal (generated over the arrangement)", "sends": {"0": -20},
                                 "fx": [{"device": "eq", "params": {"Low-pass freq": 110, "Low-pass gain": -6, "Mid freq 2": 3200, "Mid gain 2": 1.5}},
                                        {"device": "compressor", "params": {"threshold": -20, "ratio": 3, "attack": 8, "release": 100}}]}
        total = sum(x["bars"] for x in SECTIONS) * 4
        spec["parts"].append({"track": "Rap", "in": ["intro"], "audio": {"path": vox, "length": total}})
        s, rep = arrange.build(spec, label=label)
        print(json.dumps({k: rep[k] for k in ("file", "loudness", "bands_db", "issues")}, ensure_ascii=False, default=str))
