"""musicoma-022 「Relay」 — 새 장르 '호켓 홉(hocket hop)'. 10-20 본인: "색소폰이 그냥 막 연주하는 느낌, 어렵다. 새 장르로.
항상 단선율로 시작해 배경이 하나씩 들어오는 형식적 구조 — 악기·리듬·음·pause 의 다양성을 색다르게."

호켓 홉 선언
  1. 아무 악기도 선율을 혼자 연주하지 않는다. 내가 쓴 한 선율을 음표 하나씩 여러 악기가 나눠 친다(호켓 — 중세·가믈란·안데스 기법).
     마림바·피치카토·글로켄·하프·플루트·실로폰·오보에가 한 음씩 → 선율이 방 안을 돌아다닌다. 악기마다 옥타브가 달라 음역이 넓다.
  2. 베이스도 호켓: 서브·콘트라베이스 피치카토·바순이 근음을 나눠 친다.
  3. 층을 쌓으며 시작하지 않는다 — 첫 박부터 전원(콜드 오픈). 끝도 페이드 없이 엇박에서 끊고 종 하나만 운다.
  4. 박자가 바뀐다: 4/4 → 7/8(2+2+3) 간주 → 4/4 → 5/4 브리지 → 4/4.
  5. 쉼이 매번 다르다: 1.5박 페르마타 / 베이스만 남는 2박 / 전원 3박 정적 / 훅 안의 반 마디 쉼 / 갑작스러운 끝.
  6. 랩은 lego 한 호흡(구간째). 가사도 호켓: 잃어버린 장갑 한 짝이 지하철에서 한 정거장씩 사람 손을 건너간다.

    python works/musicoma_022_relay.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from musicoma import album, concept as concept_mod

NAME = "musicoma-022-relay"
BPM, KEY = 92, "D minor"
# 구간(4/4 마디 단위). brk7 = 7/8 × 8마디 = 28박 = 7, br5 = 5/4 × 4마디 = 20박 = 5
FORM = [("open", 4), ("verse1", 8), ("hook1", 8), ("brk7", 7), ("verse2", 8), ("hook2", 8), ("br5", 5), ("hook3", 8), ("end", 1)]

# ───────── 호켓 선율(직접 씀, D 도리안, 4마디 = 16박) — (박, 음) ─────────
MEL = [(0, 74), (.75, 69), (1.5, 77), (2, 76), (2.75, 72), (3.5, 69),
       (4, 74), (4.5, 77), (5.25, 79), (6, 81), (6.75, 79), (7.5, 76),
       (8, 77), (8.75, 72), (9.5, 74), (10, 69), (10.75, 71), (11.5, 72),
       (12, 74), (12.5, 76), (13, 77), (13.75, 76), (14.5, 72), (15, 74)]
# 악기 순서 — 같은 악기가 연달아 치지 않게, 옥타브는 악기마다(음의 다양성)
HOCKET = [("Marimba", 0), ("Pizz", 0), ("Glock", 12), ("Harp", -12), ("Flute", 0), ("Xylo", 12), ("Oboe", 0)]
BASS_ROOTS = [38, 43, 36, 45]                          # Dm7 G7 Cmaj7 Am7 (마디마다)
PROG = "i7 IV7 bVIImaj7 v7"

VERSE1 = ["Somebody dropped a glove at Jongno, red, the left one",
          "A kid picks it up, hands it to his mother",
          "She sets it on the rail, a man in a suit takes it",
          "Two stops later he gives it to a girl with headphones",
          "She doesn't look up, she just holds it like a ticket",
          "Nobody's going where the owner went"]
VERSE2 = ["Grandma by the door puts it in her bag, then takes it out",
          "Says it isn't hers, says it's somebody's winter",
          "A delivery guy wears it one stop to warm his hand",
          "Leaves it on the seat the way you'd leave a note",
          "By the end of the line it's been everybody's",
          "And the right hand's still out there, cold, waiting"]
HOOK = ["Pass it on, pass it on", "Nobody holds it long", "Pass it on, pass it on", "One stop and then it's gone"]

CONCEPT = {
    "thesis": "잃어버린 빨간 장갑 한 짝이 지하철에서 한 정거장씩 낯선 손을 건너간다 — 선율도 음표 하나씩 악기를 건너간다",
    "genre": "hocket hop — 선율·베이스를 음 하나씩 여러 악기가 나눠 침, 박자 바뀜, 쉼마다 다른 모양, 콜드 오픈·급정지",
    "arc": [{"section": "open", "intent": "첫 박부터 전원 — 호켓 선율 + 드럼, 마지막 1.5박 페르마타", "energy": 0.9},
            {"section": "verse1", "intent": "드럼·호켓 베이스만, 선율은 짝수 마디에만 반쪽", "energy": 0.55},
            {"section": "hook1", "intent": "호켓 전부 + 챈트, 7박째 반 마디 쉼", "energy": 0.9},
            {"section": "brk7", "intent": "7/8 간주 — 드럼 없이 말렛·현만, 2+2+3", "energy": 0.6},
            {"section": "verse2", "intent": "킥 없음, 림·셰이커, 바순이 베이스 / 끝 3박 전원 정적", "energy": 0.5},
            {"section": "br5", "intent": "5/4 — 팀파니·하프 아르페지오·플루트 긴 음, 랩 없음", "energy": 0.45},
            {"section": "hook3", "intent": "전부 + 튜블러 벨·팀파니", "energy": 1.0},
            {"section": "end", "intent": "엇박 16분에서 전원 한 방, 종 하나만 남음", "energy": 0.3}],
    "motif": {"melody": "D5 A4 F5 E5 C5 A4", "why": "도리안 6음 — 위아래로 크게 뛰어 악기가 바뀔 때마다 방향이 바뀐다"},
    "collision": ["붐뱁", "호켓(중세·가믈란)", "변박(7/8·5/4)"],
    "irregular": [{"what": "층 쌓기 전주 없음", "why": "본인: 단선율로 시작해 하나씩 들어오는 형식 탈피"}, {"what": "쉼 다섯 종류", "why": "pause 의 다양성"}],
    "constraints": ["한 악기가 선율을 두 음 연속으로 치지 않는다", "랩은 lego 한 호흡"],
    "not": ["전주 빌드업", "페이드아웃", "같은 쉼 반복"],
}


def hocket(mel, scale_vel=1.0, only=None, cycle=16, shift=0, octave_extra=0):
    """선율 → 악기별 notes 파트(cycle 박 반복). only=(lo,hi) 박 범위만."""
    per = {}
    for i, (b, p) in enumerate(mel):
        if only and not (only[0] <= b < only[1]):
            continue
        trk, octv = HOCKET[i % len(HOCKET)]
        per.setdefault(trk, []).append({"pitch": p + octv + shift + octave_extra, "start": b, "length": .35, "velocity": int(96 * scale_vel)})
    return per


def parts_for(sections, per, cycle=16):
    return [{"track": t, "in": sections, "notes": ns, "cycle_beats": cycle} for t, ns in per.items()]


def bass_hocket(sections, cycle=16, vel=100):
    sub, cb, bsn = [], [], []
    for bar, r in enumerate(BASS_ROOTS):
        o = bar * 4
        sub.append({"pitch": r, "start": o, "length": 1.4, "velocity": vel})
        cb.append({"pitch": r + 12 + 7, "start": o + 1.5, "length": .3, "velocity": vel - 8})
        bsn.append({"pitch": r + 12, "start": o + 2.75, "length": .6, "velocity": vel - 12})
        cb.append({"pitch": r + 12, "start": o + 3.5, "length": .3, "velocity": vel - 10})
    return [{"track": "Sub", "in": sections, "notes": sub, "cycle_beats": cycle},
            {"track": "CBass", "in": sections, "notes": cb, "cycle_beats": cycle},
            {"track": "Bassoon", "in": sections, "notes": bsn, "cycle_beats": cycle}]


def drum_notes(spec_list, cycle):
    """[(박, 소리, 세기)] → notes. 36 킥 38 스네어 37 림 42 햇 46 오픈햇 70 셰이커."""
    return [{"pitch": p, "start": b, "length": .1, "velocity": v} for b, p, v in spec_list]


def spec():
    sw = 0.55
    D = lambda pat, fill=None: {"pattern": pat, "swing": sw, "humanize_ms": 6, "humanize_vel": 9, **({"fill": fill} if fill else {})}
    OPEN = {"kick": "X..x..x...X..x..", "snare": "....X..o....X..o", "hat": "x-x-x-x-x-x-x-x-", "open_hat": "..............x."}
    V1 = {"kick": "x.....x...x..x..", "snare": "....X.......X...", "hat": "x.x.x.x.x.x.x.x."}
    HK = {"kick": "X..x......X.x...", "snare": "....X..o....X...", "hat": "xxxxxxxxxxxxxxxx"}
    F = {"kick": "X.........X.....", "snare": "....X...XoXoXXXX", "hat": "x.x.x.x........."}
    # 7/8(2+2+3): 3.5박 마디 — 킥 0, 림 1, 킥 2, 스네어 2.5, 셰이커 8분
    D7 = drum_notes([(0, 36, 110), (1, 37, 80), (2, 36, 100), (2.5, 38, 104)] + [(i * .5, 42, 60 + (20 if i in (0, 2, 4) else 0)) for i in range(7)], 3.5)
    # 2절: 킥 없음 — 림·셰이커만
    V2 = drum_notes([(1, 37, 90), (3, 37, 96), (2.75, 37, 60)] + [(i * .25, 42, 50 + (25 if i % 4 == 0 else 0)) for i in range(16)], 4)
    # 5/4: 팀파니 1·4박
    T5 = [{"pitch": 38, "start": 0, "length": 1.5, "velocity": 96}, {"pitch": 45, "start": 3, "length": 1.5, "velocity": 88}]
    harp5 = [{"pitch": [62, 65, 69, 72, 74, 72, 69, 65, 62, 69][i], "start": i * .5, "length": .45, "velocity": 70} for i in range(10)]
    flute5 = [{"pitch": 81, "start": 0, "length": 4.8, "velocity": 70}]
    parts = []
    # open: 전원, 마지막 1.5박 페르마타(이벤트)
    parts += parts_for(["open", "hook1", "hook2", "hook3"], hocket(MEL))
    parts += bass_hocket(["open", "verse1", "hook1", "hook2", "hook3"])
    parts += [{"track": "Drums", "in": ["open", "hook3"], "drums": D(OPEN, F)},
              {"track": "Drums", "in": ["verse1"], "drums": D(V1, F)},
              {"track": "Drums", "in": ["hook1", "hook2"], "drums": D(HK, F)},
              {"track": "Drums", "in": ["verse2"], "notes": V2, "cycle_beats": 4},
              {"track": "Drums", "in": ["brk7"], "notes": D7, "cycle_beats": 3.5}]
    # verse1: 선율은 짝수 마디(2·4)에만 — 절반만 들린다
    parts += parts_for(["verse1"], hocket(MEL, .8, only=(4, 8)), cycle=16)
    parts += parts_for(["verse1"], hocket(MEL, .8, only=(12, 16)), cycle=16)
    # brk7: 7/8 — 선율 앞 7음을 3.5박 마디에 다시 맞춘(8분 간격) 호켓, 마디마다 반음 아래로 떨어지지 않게 도리안 안에서 두 갈래
    m7 = [(i * .5, p) for i, (_, p) in enumerate(MEL[:7])]
    m7b = [(i * .5, p) for i, (_, p) in enumerate(MEL[6:13])]
    parts += parts_for(["brk7"], hocket(m7, .9), cycle=7)
    parts += [{"track": t, "in": ["brk7"], "offset": 3.5, "notes": ns, "cycle_beats": 7} for t, ns in hocket(m7b, .9).items()]
    parts += [{"track": "CBass", "in": ["brk7"], "notes": [{"pitch": 50, "start": 0, "length": .3, "velocity": 96}, {"pitch": 57, "start": 2, "length": .3, "velocity": 90}], "cycle_beats": 3.5}]
    # verse2: 바순이 베이스, 하프가 2마디마다 화음 한 번
    parts += [{"track": "Bassoon", "in": ["verse2"], "bass": {"progression": PROG, "beats_per_chord": 4, "pattern": [[0, 1.5, 0], [2.5, .5, 7], [3, .9, 0]], "velocity": 90, "low": 36, "high": 52}},
              {"track": "Harp", "in": ["verse2"], "chords": {"progression": PROG, "beats_per_chord": 4, "voicing": "spread", "rhythm": [[0, 2, .8]], "velocity": 64}}]
    # br5: 5/4
    parts += [{"track": "Timpani", "in": ["br5"], "notes": T5, "cycle_beats": 5},
              {"track": "Harp", "in": ["br5"], "notes": harp5, "cycle_beats": 5},
              {"track": "Flute", "in": ["br5"], "notes": flute5, "cycle_beats": 5},
              {"track": "Bells", "in": ["br5"], "notes": [{"pitch": 74, "start": 0, "length": 4, "velocity": 70}], "cycle_beats": 10}]
    # hook3: 종·팀파니 더함
    parts += [{"track": "Bells", "in": ["hook3"], "notes": [{"pitch": 74, "start": 0, "length": 3, "velocity": 84}, {"pitch": 69, "start": 8, "length": 3, "velocity": 78}], "cycle_beats": 16},
              {"track": "Timpani", "in": ["hook3"], "notes": [{"pitch": 38, "start": 0, "length": 1, "velocity": 100}], "cycle_beats": 8}]
    # end: 엇박(0.75박)에서 전원 한 방 + 종 하나
    hit = lambda trk, p, v=110: {"track": trk, "in": ["end"], "notes": [{"pitch": p, "start": .75, "length": .25, "velocity": v}]}
    parts += [hit("Marimba", 74), hit("Pizz", 62), hit("Glock", 86), hit("Harp", 50), hit("Xylo", 86), hit("Sub", 38), hit("CBass", 50), hit("Bassoon", 50),
              {"track": "Drums", "in": ["end"], "notes": [{"pitch": 36, "start": .75, "length": .1, "velocity": 120}, {"pitch": 49, "start": .75, "length": .1, "velocity": 110}]},
              {"track": "Bells", "in": ["end"], "notes": [{"pitch": 62, "start": .75, "length": 3.2, "velocity": 96}]}]
    # 랩·챈트(lego 한 호흡)
    parts += [{"track": "Rap", "in": ["verse1"], "rap": {"voice": "bomf-rapper", "lines": [{"text": l, "beats": 32 / 6} for l in VERSE1]}},
              {"track": "Rap", "in": ["verse2"], "rap": {"voice": "bomf-rapper", "lines": [{"text": l, "beats": 32 / 6} for l in VERSE2]}},
              {"track": "Chant", "in": ["hook1", "hook2", "hook3"], "rap": {"voice": "bomf-rapper", "lines": [{"text": l, "beats": 8} for l in HOOK]}}]
    return {
        "name": NAME, "bpm": BPM, "key": KEY, "style": "chipmunk-soul", "feel": "straight", "intensity": 0.8,
        "brief": "「Relay」 호켓 홉 — 선율을 음 하나씩 일곱 악기가 나눠 침, 변박·다섯 가지 쉼·콜드 오픈·급정지",
        "sections": [{"name": n, "bars": b} for n, b in FORM],
        "tracks": {
            "Drums": {"sound": "drums_acoustic_basic", "role": "drums", "sends": {"0": -22}, "fx": [
                {"device": "eq", "params": {"Low-pass freq": 62, "Low-pass gain": 3, "Mid freq 1": 350, "Mid gain 1": -3, "Mid Q 1": 1.0, "Mid freq 2": 4500, "Mid gain 2": 2.5}},
                {"device": "compressor", "params": {"threshold": -19, "ratio": 4, "attack": 18, "release": 80, "output gain": 3}}]},
            "Sub": {"sound": "bass_sub", "role": "sub bass", "fx": [{"device": "lowpass", "params": {"frequency": 600}}]},
            "CBass": {"sound": "contrabass", "role": "contrabass pizz (bass hocket)", "pan": -0.1},
            "Bassoon": {"sound": "bassoon", "role": "bassoon (bass hocket)", "pan": 0.15, "sends": {"0": -10}},
            "Marimba": {"preset": "pluck/marimba", "role": "hocket", "pan": -0.45, "sends": {"0": -10}},
            "Pizz": {"preset": "strings/pizzicato", "role": "hocket", "pan": 0.4, "sends": {"0": -9}},
            "Glock": {"preset": "lead/bell", "role": "hocket", "pan": 0.2, "sends": {"0": -8}},
            "Harp": {"preset": "pluck/harp", "role": "hocket", "pan": -0.25, "sends": {"0": -8}},
            "Flute": {"preset": "lead/flute", "role": "hocket", "pan": 0.3, "sends": {"0": -7}},
            "Xylo": {"sound": "xylophone", "role": "hocket", "pan": -0.35, "sends": {"0": -9}},
            "Oboe": {"sound": "oboe", "role": "hocket", "pan": 0.1, "sends": {"0": -8}},
            "Timpani": {"sound": "timpani", "role": "timpani", "sends": {"0": -9}},
            "Bells": {"sound": "tubular_bells", "role": "tubular bells", "pan": 0.05, "sends": {"0": -5}},
            "Rap": {"role": "lead rap vocal", "sends": {"0": -18}},
            "Chant": {"role": "hook chant", "pan": -0.05, "sends": {"0": -15}},
        },
        "buses": [{"name": "Room", "bus": 0, "device": "Dragonfly Room Reverb", "volume_db": -6}],
        "parts": parts,
        "events": [{"section": "open", "at": 14.5, "length": 1.5, "type": "stop", "why": "페르마타 1.5박"},
                   {"section": "verse1", "at": 30, "length": 2, "type": "stop", "keep": ["Sub", "Rap"], "why": "베이스만 남는 2박"},
                   {"section": "hook1", "at": 14, "length": 2, "type": "stop", "keep": ["Chant"], "why": "훅 안 반 마디 쉼(챈트만)"},
                   {"section": "verse2", "at": 29, "length": 3, "type": "stop", "why": "전원 3박 정적"}],
        "mix": {"balance": True, "target_lufs": -11,
                "balance_lu": {"drums": 0, "rap": 1.5, "chant": 0.5, "sub": -3, "cbass": -5, "bassoon": -6, "marimba": -5, "pizz": -5, "glock": -7,
                               "harp": -6, "flute": -6, "xylo": -7, "oboe": -6, "timpani": -5, "bells": -6}},
    }


if __name__ == "__main__":
    log = lambda m: print(m, flush=True)
    concept_mod.save(NAME, CONCEPT)
    cap = ("old school hip hop, male rapper, warm storyteller, conversational flow, clear words, on the beat, "
           "hook chanted by the same rapper, dry close mic")
    s, rep = album.rap_with_lego(spec(), "v1", cap, tracks=("Rap", "Chant"), log=lambda m: log("[4] " + m) if "lego rap" in m else None)
    log(json.dumps({k: rep.get(k) for k in ("file", "loudness", "bands_db", "issues")}, ensure_ascii=False, default=str))
