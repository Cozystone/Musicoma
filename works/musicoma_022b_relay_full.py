"""musicoma-022 「Relay」 v3 — 더 풍성하게(10-20 본인 "좋은데 좀 더 풍성하게 채워지면 좋겠다").
호켓 정체성(선율을 한 음씩 나눠 치기)·쉼 다섯 종·변박은 그대로 두고, 아래·위로 층을 더한다:
  - 3도 아래 화음 호켓(대선율): 같은 선율을 도리안 3도 아래로, 악기 순서를 한 칸 밀어 → 매 음이 두 악기의 화음이 된다
  - 지속층: 스트링 패드(훅·오픈·7/8), 콰이어(훅·5/4), 로즈 컴핑(절), 첼로 긴 베이스 라인(훅)
  - 절에서도 선율 전부(작게) — v1·v2 는 짝수 마디 절반만이라 비었다
  - 셰이커 대신 16분 햇 + 탬버린 느낌(오픈햇)으로 리듬 밀도
랩은 v1 그대로(같은 테이크).
"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1])); sys.path.insert(0, str(Path(__file__).resolve().parent))
import musicoma_022_relay as m
from musicoma import arrange

DOR = [62, 64, 65, 67, 69, 71, 72]                     # D 도리안
def third_below(p):
    pcs = [x % 12 for x in DOR]
    pc = p % 12
    i = pcs.index(pc) if pc in pcs else min(range(7), key=lambda k: abs(pcs[k] - pc))
    j = (i - 2) % 7
    q = p - ((pc - pcs[j]) % 12)
    return q if q < p else q - 12

def counter_parts(sections, mel, vel=.75, cycle=16):
    per = {}
    for i, (b, p) in enumerate(mel):
        trk, octv = m.HOCKET[(i + 1) % len(m.HOCKET)]       # 한 칸 밀린 악기 = 원래 음과 다른 악기가 3도 아래를 같이
        per.setdefault(trk, []).append({"pitch": third_below(p) + octv, "start": b, "length": .35, "velocity": int(96 * vel)})
    return [{"track": t, "in": sections, "notes": ns, "cycle_beats": cycle} for t, ns in per.items()]

sp = m.spec()
sp["name"] = m.NAME
parts = [p for p in sp["parts"] if "rap" not in p]
H = ["open", "hook1", "hook2", "hook3"]
parts += counter_parts(H, m.MEL)
parts += m.parts_for(["verse1", "verse2"], m.hocket(m.MEL, .6))                     # 절에서도 선율 전부(작게)
parts += counter_parts(["verse2"], m.MEL, vel=.5)
sp["tracks"].update({
    "Strings": {"preset": "strings/ensemble", "role": "strings pad", "pan": -0.2, "sends": {"0": -6}},
    "Choir": {"preset": "pad/choir", "role": "choir pad", "sends": {"0": -5}},
    "Keys": {"preset": "keys/rhodes_dark", "role": "rhodes comp", "pan": 0.25, "sends": {"0": -9}},
    "Cello": {"preset": "strings/cello", "role": "cello line", "pan": 0.15, "sends": {"0": -8}},
})
parts += [
    {"track": "Strings", "in": H + ["brk7"], "chords": {"progression": m.PROG, "beats_per_chord": 4, "voicing": "pad", "velocity": 62, "legato": 1.0}},
    {"track": "Strings", "in": ["verse1", "verse2"], "chords": {"progression": m.PROG, "beats_per_chord": 4, "voicing": "pad", "velocity": 46, "legato": 1.0}},
    {"track": "Choir", "in": ["hook1", "hook2", "hook3", "br5"], "chords": {"progression": m.PROG, "beats_per_chord": 4, "voicing": "pad", "velocity": 56, "legato": 1.0}},
    {"track": "Keys", "in": ["verse1", "verse2", "open"], "chords": {"progression": m.PROG, "beats_per_chord": 4, "voicing": "rhodes", "rhythm": [[0, 1.5, .9], [1.75, .5, .7], [2.5, 1, .8], [3.5, .5, .6]], "velocity": 60}},
    {"track": "Cello", "in": H, "bass": {"progression": m.PROG, "beats_per_chord": 4, "pattern": [[0, 3.8, 12]], "velocity": 72, "low": 36, "high": 55}},
    {"track": "Drums", "in": ["verse1", "hook1", "hook2"], "notes": [{"pitch": 42, "start": i * .25, "length": .1, "velocity": 40 + (18 if i % 2 else 0)} for i in range(16)], "cycle_beats": 4},
    {"track": "Drums", "in": ["hook1", "hook2", "hook3"], "notes": [{"pitch": 46, "start": 1.5, "length": .2, "velocity": 70}, {"pitch": 46, "start": 3.5, "length": .2, "velocity": 64}], "cycle_beats": 4},
]
parts.append({"track": "Rap", "vocal_sections": str(arrange.ROOT / "projects" / m.NAME / "vocals" / "rap_lego_v1.json")})
sp["parts"] = parts
for t, db in {"Marimba": 8, "Pizz": 8, "Glock": 12, "Harp": 6, "Flute": 8, "Xylo": 10, "Oboe": 8, "CBass": 10, "Bassoon": 4, "Bells": 6, "Timpani": 6}.items():
    sp["tracks"][t]["volume_db"] = db
sp["mix"]["balance_lu"].update({"marimba": -1, "pizz": -1, "glock": -2, "harp": -2, "flute": -2, "xylo": -2, "oboe": -2, "cbass": -3, "bassoon": -4,
                                "bells": -4, "timpani": -4, "strings": -6, "choir": -7, "keys": -6, "cello": -7})
sp["brief"] += " · v3 더 풍성하게(3도 대선율 호켓·스트링·콰이어·로즈·첼로)"
s, rep = arrange.build(sp, label="v3", log=lambda x: print(x, flush=True) if "balance" in x else None)
print(json.dumps({k: rep.get(k) for k in ("file", "loudness", "bands_db")}, ensure_ascii=False)[:400])
