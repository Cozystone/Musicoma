"""musicoma-009 「Half Past Three」 — 네오소울, 영어 노래(남자 팔세토·흉성), 처음부터 보컬까지. (10-16 본인: "새 곡으로")

새 흐름(10-16)으로 처음 짓는 곡: 0 레퍼런스(knowledge/references/neo-soul.yaml) → 1 콘셉트 → 동기 → 비평
→ 가이드 → [보컬 구간별 녹음 ∥ 반주 빌드·밸런스] → 보컬 트랙만 재서 맞춤 → 렌더.
보컬은 구간마다 클립(vocals/vox/NN_구간.wav) — NG 구간은 lego.retake 로 그 구간만 다시.

    python works/musicoma_009_half_past_three.py dry      비평만
    python works/musicoma_009_half_past_three.py all v1   전부(보컬 ∥ 반주)
    python works/musicoma_009_half_past_three.py final v2 보컬은 그대로 두고 다시 짓기(retake 뒤)
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from musicoma import arrange, concept as concept_mod, critic, lego, lyrics as lyr_mod, motif

NAME = "musicoma-009-half-past-three"
BPM, KEY = 76, "E minor"
SPB = 60 / BPM

LYR = {
    "verse": "Half past three and the room is blue\nPhone light shaking in my hand for you\n"
             "Typed it out and then I let it go\nEvery word I mean you'll never know",
    "chorus": "So I hold it, hold it in\nLet the morning wash it thin\n"
              "If I called you would you stay\nOr would we fade like yesterday",
    "verse2": "Coffee cold and the record skips\nYour name sitting heavy on my lips\n"
              "One more minute then I'll be brave",
    "bridge": "Maybe love is just a door\nI keep knocking, nothing more",
}

CONCEPT = {
    "thesis": "새벽 세 시 반, 보낼 말을 썼다 지웠다 — 망설임이 그루브가 된다(스네어가 늦게 끌린다)",
    "arc": [{"section": "intro", "intent": "파란 방, 부를리처와 드럼만 · 트럼펫은 공기처럼", "energy": 0.3},
            {"section": "verse", "intent": "두 화음 사이를 오가며 말하듯(On & On)", "energy": 0.4},
            {"section": "chorus", "intent": "삼키는 말 — 팔세토로 올라갔다 내려앉음", "energy": 0.65},
            {"section": "verse2", "intent": "용기 내기 직전, 이야기가 빨라짐(6마디)", "energy": 0.5},
            {"section": "bridge", "intent": "이름 없는 화음 하나(Fmaj7#11) — 문 두드리기", "energy": 0.55},
            {"section": "chorus_last", "intent": "다 쌓는다 — 오르간·트럼펫·기타", "energy": 1.0},
            {"section": "outro", "intent": "소리의 벽 → 뚝(보냈는지 안 보냈는지 모른 채)", "energy": 0.9}],
    "motif": {"melody": "B4:.5 D5:.5 E5:1 D5:.5 B4:1.5", "why": "'hold it in' — 올라갔다가 말을 삼키듯 제자리"},
    "collision": ["90s 소울쿼리언스 라이브 밴드", "로이 하그로브식 뮤트 트럼펫의 공기", "새벽 휴대폰 불빛의 정적"],
    "constraints": ["절은 두 화음(i9 ↔ IV13)만 — 색은 보이싱과 그루브로(On & On)",
                    "브리지에 이름 붙이기 어려운 화음 하나(Get You)", "끝은 쌓고 뚝(Untitled)",
                    "트럼펫은 선율보다 길게 뒤에서"],
    "events": [{"section": "chorus_last", "at": -1, "length": 1, "type": "stop", "why": "보내기 버튼 앞 숨"},
               {"section": "outro", "at": 15, "length": 1, "type": "stop", "why": "소리의 벽이 갑자기 끊김 — 결말을 말하지 않음"}],
    "irregular": [{"what": "2절 6마디", "why": "용기 내기 직전 — 할 말 길이만큼"},
                  {"what": "브리지 4마디, 이름 없는 화음으로 시작", "why": "문 앞의 낯선 순간"},
                  {"what": "끝 박에서 뚝", "why": "보냈는지 모른 채"}],
    "references": "knowledge/references/neo-soul.yaml — Untitled(How Does It Feel) · On & On · Get You · Ex-Factor",
    "not": ["808", "사이드체인", "꽉 찬 스트링", "같은 4마디 복사", "정박 스네어"],
}

SECTIONS = [{"name": "intro", "bars": 4}, {"name": "verse", "bars": 8}, {"name": "chorus", "bars": 8},
            {"name": "verse2", "bars": 6}, {"name": "chorus", "bars": 8}, {"name": "bridge", "bars": 4},
            {"name": "chorus_last", "bars": 8}, {"name": "outro", "bars": 4}]
PROG = {"verse": "i9 IV13", "chorus": "bVImaj7 bVII13sus4 i9 v9", "bridge": "bIImaj7#11 bVImaj7 iv9 V7#9"}
DR = {"main": {"kick": "x.......x..x....", "snare": "....x.......x...", "hat": "x.xox.x.x.xox.x."},
      "half": {"kick": "x.........x.....", "snare": "........x.......", "hat": "x...x...x...x..."},
      "wall": {"kick": "x.x...x.x.x...x.", "snare": "....x..x....x.xx", "hat": "xxxxxxxxxxxxxxxx"},    # 아웃트로: 소리의 벽
      "lift": {"kick": "x.....x.x..x..x.", "snare": "....x..o....x.o.", "hat": "xxoxxxoxxxoxxxox"},   # 마지막 후렴: 킥·고스트·16분 햇
      "fill": {"kick": "x.......", "snare": "....x.xxoxoxXXXX"}}


def drums(p, fill=True):
    return {"pattern": DR[p], "swing": 0.6, "humanize_ms": 7, "humanize_vel": 10, **({"fill": DR["fill"]} if fill else {})}


def chords_for(sec, bars, per=4):
    from musicoma import theory
    ch = theory.progression(PROG[sec], "E", "minor")
    n = len(ch)
    return [(b * 4, b * 4 + 4, ch[(b * 4 // per) % n]) for b in range(bars)]


M = CONCEPT["motif"]["melody"]
TP_AIR = motif.section_melody(M, ["octave:-1", "augment:2"], chords_for("verse", 4, 8), KEY, 4, "statement")
TP_BRIDGE = motif.section_melody(M, ["octave:-1"], chords_for("bridge", 4), KEY, 4, "fragment question answer")
TP_LAST = motif.section_melody(M, [], chords_for("verse", 4, 8), KEY, 4, "statement sequence climb climb")   # 소리의 벽 — 한 옥타브 위로 오르기만
COMP = [[0, 2.0, 1.0], [1.75, 1.0, 0.7], [2.5, 1.75, 0.85]]          # 길게 + 밀어 치기(v2: 음이 겹치게 — v1 인트로·절 빈 공기 34곳)

spec = {
    "name": NAME, "bpm": BPM, "key": KEY, "style": "neo-soul", "feel": "laid_back", "intensity": 0.65,
    "brief": "「Half Past Three」 네오소울 · 영어 노래 · 구간별 보컬 녹음(새 흐름 첫 곡)",
    "sections": SECTIONS,
    "tracks": {
        "Drums": {"preset": "drums/rusty", "role": "drums", "sends": {"0": -22}},
        "Bass": {"preset": "bass/hollow_finger", "role": "bass"},
        "Wurli": {"preset": "keys/wurlitzer", "role": "keys", "pan": -0.15, "sends": {"0": -12}},
        "Organ": {"preset": "keys/organ", "role": "pad", "pan": 0.1, "sends": {"0": -10}},
        "Guitar": {"preset": "guitar/archtop", "role": "guitar", "pan": 0.35, "sends": {"0": -14}},
        "Trumpet": {"preset": "brass/trumpet", "role": "lead", "pan": -0.25, "sends": {"0": -6}},
    },
    "buses": [{"name": "Room", "bus": 0, "device": "Dragonfly Hall Reverb", "volume_db": -6}],
    "parts": [
        {"track": "Drums", "in": ["intro", "verse", "verse2", "chorus"], "drums": drums("main")},
        {"track": "Drums", "in": ["chorus_last"], "drums": drums("lift")},
        {"track": "Drums", "in": ["outro"], "drums": drums("wall", fill=False)},
        {"track": "Drums", "in": ["bridge"], "drums": drums("half", fill=False)},
        {"track": "Wurli", "in": ["intro", "verse", "verse2"], "chords": {"progression": PROG["verse"], "beats_per_chord": 8, "voicing": "rhodes",
                                                                    "rhythm": COMP, "velocity": 70}},
        {"track": "Wurli", "in": ["chorus"], "chords": {"progression": PROG["chorus"], "beats_per_chord": 4, "voicing": "rhodes",
                                                       "rhythm": COMP, "velocity": 74}},
        {"track": "Wurli", "in": ["chorus_last"], "chords": {"progression": PROG["chorus"], "beats_per_chord": 4, "voicing": "rhodes",
                                                                     "rhythm": COMP + [[3.25, 0.25, 0.6], [3.75, 0.25, 0.7]], "velocity": 84}},
        {"track": "Wurli", "in": ["bridge"], "chords": {"progression": PROG["bridge"], "beats_per_chord": 4, "voicing": "rhodes",
                                                       "rhythm": [[0, 3, 1.0], [3.5, 0.5, 0.7]], "velocity": 68}},
        {"track": "Bass", "in": ["verse", "verse2"], "bass": {"progression": PROG["verse"], "beats_per_chord": 8, "low": 28, "high": 50,
                                                             "pattern": [[0, 1.5, 0], [1.75, 0.25, 12], [2, 0.75, 10], [3, 0.5, 7], [3.5, 0.5, 5]]}},
        {"track": "Bass", "in": ["chorus", "chorus_last"], "bass": {"progression": PROG["chorus"], "beats_per_chord": 4, "low": 28, "high": 50,
                                                                            "pattern": [[0, 1.25, 0], [1.5, 0.5, 7], [2, 1, 0], [3.25, 0.25, 12], [3.5, 0.5, 10]]}},
        {"track": "Bass", "in": ["bridge"], "bass": {"progression": PROG["bridge"], "beats_per_chord": 4, "low": 28, "high": 50,
                                                    "pattern": [[0, 2.5, 0], [3, 1, 7]]}},
        {"track": "Organ", "in": ["chorus"], "chords": {"progression": PROG["chorus"], "beats_per_chord": 4, "voicing": "pad",
                                                       "velocity": 56, "legato": 1.0}},
        {"track": "Organ", "in": ["chorus_last"], "chords": {"progression": PROG["chorus"], "beats_per_chord": 4, "voicing": "pad",
                                                                     "velocity": 74, "legato": 1.0}},
        {"track": "Organ", "in": ["bridge"], "chords": {"progression": PROG["bridge"], "beats_per_chord": 4, "voicing": "pad", "velocity": 52, "legato": 1.0}},
        {"track": "Guitar", "in": ["chorus", "chorus_last"], "chords": {"progression": PROG["chorus"], "beats_per_chord": 4, "voicing": "guitar",
                                                                            "rhythm": [[1.5, 0.25, 0.8], [3.5, 0.25, 0.75]], "velocity": 66}},
        # 아웃트로: 절의 두 화음으로 돌아와(처음의 파란 방) 다 같이 크게 → 마지막 박에서 뚝
        {"track": "Wurli", "in": ["outro"], "chords": {"progression": PROG["verse"], "beats_per_chord": 8, "voicing": "rhodes",
                                                      "rhythm": [[0, 0.5, 1.0], [0.5, 0.25, 0.7], [0.75, 0.25, 0.8], [1.5, 0.5, 0.9], [2, 0.25, 0.7], [2.5, 0.5, 1.0], [3, 0.25, 0.8], [3.25, 0.75, 0.9]], "velocity": 100}},
        {"track": "Organ", "in": ["outro"], "chords": {"progression": PROG["verse"], "beats_per_chord": 8, "voicing": "pad", "velocity": 82, "legato": 1.0}},
        {"track": "Bass", "in": ["outro"], "bass": {"progression": PROG["verse"], "beats_per_chord": 8, "low": 28, "high": 52,
                                                   "pattern": [[0, 0.5, 0], [0.5, 0.25, 12], [0.75, 0.5, 10], [1.5, 0.5, 7], [2, 0.5, 0], [2.5, 0.5, 12], [3, 0.5, 14], [3.5, 0.5, 15]]}},
        {"track": "Guitar", "in": ["outro"], "chords": {"progression": PROG["verse"], "beats_per_chord": 8, "voicing": "guitar",
                                                       "rhythm": [[0.5, 0.25, 0.8], [1.5, 0.25, 0.8], [2.5, 0.25, 0.8], [3.5, 0.25, 0.8]], "velocity": 78}},
        {"track": "Trumpet", "in": ["intro"], "melody": {"text": TP_AIR, "velocity": 70, "repeat": False}},
        {"track": "Trumpet", "in": ["bridge"], "melody": {"text": TP_BRIDGE, "velocity": 74, "repeat": False}},
        {"track": "Trumpet", "in": ["chorus_last"], "offset": 16, "melody": {"text": TP_AIR, "velocity": 78, "repeat": False}},   # 후반 4마디에 길게(공기)
        {"track": "Trumpet", "in": ["outro"], "melody": {"text": TP_LAST, "velocity": 104, "repeat": False}},
    ],
    "events": CONCEPT["events"],
    "mix": {"balance": True, "target_lufs": -13,
            "balance_lu": {"drums": 0, "bass": -2, "wurli": -1.5, "organ": -9, "guitar": -7, "trumpet": -4, "vox": 2.5}},
}

VOX = Path(arrange.ROOT) / "projects" / NAME / "vocals" / "vox.wav"
CAPTION = ("male soul vocal, english, neo soul, smooth falsetto and warm chest voice, intimate, laid back behind the beat, "
           "solo lead vocal, no backing vocals")
spec["tracks"]["Vox"] = {"role": "lead vocal (generated over the arrangement)", "sends": {"0": -9},
                         "fx": [{"device": "eq", "params": {"Low-pass freq": 120, "Low-pass gain": -6, "Mid freq 2": 3200, "Mid gain 2": 1.5}},
                                {"device": "compressor", "params": {"threshold": -20, "ratio": 3, "attack": 8, "release": 120}}]}
VOX_PART = {"track": "Vox", "vocal_sections": str(VOX.with_suffix(".json"))}


def vocal_sections():
    """노래 구간(초) — 8마디 이하, 구간마다 조성·가이드 멜로디(동기에서)."""
    from musicoma import theory, vocal_melody
    lyr = {"verse": LYR["verse"], "chorus": LYR["chorus"], "verse2": LYR["verse2"], "bridge": LYR["bridge"], "chorus_last": LYR["chorus"]}
    prog = {"verse": ("verse", 8), "verse2": ("verse", 8), "chorus": ("chorus", 4), "chorus_last": ("chorus", 4), "bridge": ("bridge", 4)}
    out, bar, count = [], 0, {}
    for s_ in SECTIONS:
        name, n = s_["name"], s_["bars"]
        if name in lyr:
            count[name] = count.get(name, 0) + 1
            p, per = prog[name]
            ch = theory.progression(PROG[p], "E", "minor")
            chords = [(bar * 4 + b * 4, bar * 4 + b * 4 + 4, ch[(b * 4 // per) % len(ch)]) for b in range(n)]
            mel = vocal_melody.section_notes(lyr[name], bar * 4, n, M, KEY, chords)
            out.append({"name": f"{name}{count[name]}", "start": round(bar * 4 * SPB, 3), "end": round((bar + n) * 4 * SPB, 3),
                        "tag": {"chorus": "Chorus", "chorus_last": "Chorus", "bridge": "Bridge"}.get(name, "Verse"),
                        "lyrics": lyr[name], "key": KEY, "melody_notes": mel})
        bar += n
    return out


def make_vocals(log=print):
    guide = lego.render_guide(spec)
    _, rep = lego.vocal_track(guide, vocal_sections(), BPM, KEY, CAPTION, VOX, takes=12, guide_wav=guide,
                              pass_wer=0.3, min_key_fit=0.75, log=log)
    for x in rep:
        log(f"{x['section']}: seed {x['chosen']} · 오류율 {x['wer']} · 유사도 {x['voice_sim']} · 조성 {x['key_fit']}")
    return VOX_PART


if __name__ == "__main__":
    step = sys.argv[1] if len(sys.argv) > 1 else "all"
    label = sys.argv[2] if len(sys.argv) > 2 else "v1"
    concept_mod.save(NAME, CONCEPT)
    r = critic.critique({**spec, "tracks": {k: v for k, v in spec["tracks"].items() if k != "Vox"}}, CONCEPT)
    print(critic.format_report(r).split("Claude 가")[0])
    if step == "dry":
        sys.exit(0)
    t0 = time.time()
    stamp = lambda m: print(f"{time.time() - t0:6.0f}s {m}", flush=True)
    if step == "all":
        from concurrent.futures import ThreadPoolExecutor
        lego.render_guide(spec)                  # 엔진을 쓰는 단계는 빌드 전에 끝낸다
        stamp("가이드")
        fut = ThreadPoolExecutor(1).submit(make_vocals, stamp)
        s, rep = arrange.build(spec, label=label, later={"Vox": fut.result}, log=stamp)
    elif step == "final":
        spec["parts"].append(VOX_PART)
        s, rep = arrange.build(spec, label=label, log=stamp)
    else:
        raise SystemExit(f"unknown step {step}")
    stamp("끝")
    print(json.dumps({k: rep[k] for k in ("file", "loudness", "bands_db", "issues")}, ensure_ascii=False, default=str))
