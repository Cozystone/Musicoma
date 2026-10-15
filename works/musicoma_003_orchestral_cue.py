"""오케스트라 큐 v3 — 콘셉트 → 동기 전개 → 화음 맞추기 → 비평. (v1·v2: 본인 "화음 안 맞고 진행도 별로")

원인 기록: theory.roman 이 단조에서도 장음계 기준이라 D단조 'i VI III VII' 가 Dm–B–Gb–Db 로 나왔다(→ 수정, 테스트 추가).
선율도 화음과 따로 써서 강박에 화음 밖 음이 많았다(→ motif.fit).
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from musicoma import arrange, concept as concept_mod, critic, motif, theory
from musicoma.knowledge import style

NAME = "musicoma-003-orchestral"
KEY = "D minor"
card = style("orchestral")
PAN = card["mix"]["seating_pan"]

CONCEPT = {
    "thesis": "잊고 지낸 이름을 다시 부르는 순간 — 작게 시작한 한 줄이 끝내 모두의 목소리가 된다",
    "arc": [{"section": "intro", "intent": "빈 방, 첼로 혼자 기억을 더듬음", "energy": 0.15},
            {"section": "A", "intent": "동기가 처음 또렷해짐 — 아직 망설임", "energy": 0.4},
            {"section": "B", "intent": "모두가 같은 동기를 크게 — 호른이 이끔", "energy": 0.95},
            {"section": "end", "intent": "다시 혼자, 그러나 끝 음이 위로 열려 있다(답이 아니라 질문)", "energy": 0.2}],
    "motif": {"melody": "D4:1 E4:.5 F4:.5 A4:2", "why": "위로 올라가는 네 음 = 부르는 몸짓"},
    "collision": ["낭만주의 현악 레가토", "영화 예고편식 금관 강타", "실내악처럼 텅 빈 시작과 끝"],
    "constraints": ["모든 선율은 같은 네 음 동기에서만 나온다", "B 직전 두 박은 완전한 침묵"],
    "events": [{"section": "B", "at": -2, "length": 2, "type": "stop", "why": "숨을 멈췄다가 터지게"}],
    "references": concept_mod.PRINCIPLES,
    "not": ["화음과 따로 노는 선율", "같은 마디 덩어리를 그대로 반복"],
}

PROG = {"A": "i VI III VII", "B": "i VI iv V", "end": "VI VII i i"}
SECTIONS = [{"name": "intro", "bars": 4}, {"name": "A", "bars": 8}, {"name": "B", "bars": 8}, {"name": "end", "bars": 4}]


def chords_for(section, bars):
    ch = theory.progression(PROG.get(section, "i VI III VII"), "D", "minor")
    out = []
    for b in range(bars):
        out.append((b * 4, b * 4 + 4, ch[b % len(ch)]))
    return out


M = CONCEPT["motif"]["melody"]
# 섹션별 동기 전개(같은 네 음에서만) — 4마디 프레이즈 단위
CELLO_A = (motif.section_melody(M, [], chords_for("A", 4), KEY, 4, "statement answer") + " " +
           motif.section_melody(M, ["up:2"], chords_for("A", 4), KEY, 4, "statement question"))
HORN_B = (motif.section_melody(M, ["octave:1"], chords_for("B", 4), KEY, 4, "statement climb") + " " +
          motif.section_melody(M, ["octave:1", "augment:2"], chords_for("B", 4), KEY, 4, "statement answer"))
FLUTE_B = (motif.section_melody(M, ["octave:2", "diminish:2", "invert"], chords_for("B", 4), KEY, 4,
                                "fragment fragment sequence answer") + " " +
           motif.section_melody(M, ["octave:2", "diminish:2"], chords_for("B", 4), KEY, 4, "sequence climb climb answer"))
CELLO_END = motif.section_melody(M, ["augment:2"], chords_for("end", 4), KEY, 4, "question")


def strip(sound, role, name):
    return {"sound": sound, "role": role, "pan": PAN.get(name, 0), "sends": {"0": -4}}


spec = {
    "name": NAME, "bpm": 76, "key": KEY, "style": "orchestral",
    "brief": "오케스트라 큐 v3 — 콘셉트·동기 전개·화음 맞춤(단조 진행 버그 수정 후)",
    "sections": SECTIONS, "feel": "loose", "intensity": 0.8,
    "tracks": {
        "Violins": strip("strings_violins", "strings", "violins"),
        "Violas": strip("strings_violas", "strings", "violas"),
        "Cellos": strip("strings_cello", "strings (melody)", "cellos"),
        "Basses": {**strip("contrabass", "bass", "basses"), "perform_role": "strings"},
        "Horns": strip("horn", "brass (melody)", "horns"),
        "Trumpets": strip("trumpet", "brass", "trumpets"),
        "Trombones": strip("trombone", "brass", "trombones"),
        "Flute": strip("flute", "lead", "flute"),
        "Timpani": {**strip("timpani", "drums", "timpani"), "perform_role": "drums"},
    },
    "buses": [{"name": "Hall", "bus": 0, "device": "Dragonfly Hall Reverb", "volume_db": -3}],
    "parts": [
        # 화음 받침(섹션마다 진행이 다르다)
        {"track": "Violas", "in": ["intro"], "chords": {"progression": PROG["A"], "beats_per_chord": 4, "voicing": "pad", "velocity": 40, "legato": 1.0}, "transpose": -12},
        {"track": "Violins", "in": ["A"], "chords": {"progression": PROG["A"], "beats_per_chord": 4, "voicing": "pad", "velocity": 60, "legato": 1.0}},
        {"track": "Violins", "in": ["B"], "chords": {"progression": PROG["B"], "beats_per_chord": 4, "voicing": "pad", "velocity": 96, "legato": 1.0}, "transpose": 12},
        {"track": "Violins", "in": ["end"], "chords": {"progression": PROG["end"], "beats_per_chord": 4, "voicing": "pad", "velocity": 50, "legato": 1.0}},
        {"track": "Violas", "in": ["A"], "chords": {"progression": PROG["A"], "beats_per_chord": 4, "voicing": "pad", "velocity": 66, "legato": 1.0}, "transpose": -12},
        {"track": "Violas", "in": ["B"], "chords": {"progression": PROG["B"], "beats_per_chord": 4, "voicing": "pad", "velocity": 84, "legato": 1.0}, "transpose": -12},
        {"track": "Basses", "in": ["A"], "bass": {"progression": PROG["A"], "beats_per_chord": 4, "low": 28, "high": 43, "pattern": [[0, 3.9, 0]]}},
        {"track": "Basses", "in": ["B"], "bass": {"progression": PROG["B"], "beats_per_chord": 4, "low": 28, "high": 43, "pattern": [[0, 1.9, 0], [2, 1.9, 0]]}},
        {"track": "Trombones", "in": ["B"], "chords": {"progression": PROG["B"], "beats_per_chord": 4, "voicing": "pad", "velocity": 84}, "transpose": -12},
        {"track": "Trumpets", "in": ["B"], "chords": {"progression": PROG["B"], "beats_per_chord": 4, "voicing": "stab",
                                                     "rhythm": [[0, 1.5, 1.0], [3, 1.0, 0.85]], "velocity": 88}},
        # 선율 — 모두 같은 동기에서(콘셉트 제약)
        {"track": "Cellos", "in": ["intro"], "melody": {"text": motif.section_melody(M, ["augment:2"], chords_for("A", 4), KEY, 4, "statement"), "velocity": 70, "repeat": False}},
        {"track": "Cellos", "in": ["A"], "melody": {"text": CELLO_A, "velocity": 88, "repeat": False}},
        {"track": "Cellos", "in": ["B"], "bass": {"progression": PROG["B"], "beats_per_chord": 4, "low": 38, "high": 55, "pattern": [[0, 1.9, 0], [2, 1.9, 7]]}},
        {"track": "Cellos", "in": ["end"], "melody": {"text": CELLO_END, "velocity": 64, "repeat": False}},
        {"track": "Horns", "in": ["A"], "chords": {"progression": PROG["A"], "beats_per_chord": 4, "voicing": "pad", "velocity": 52}, "transpose": -12},
        {"track": "Horns", "in": ["B"], "melody": {"text": HORN_B, "velocity": 104, "repeat": False}},
        {"track": "Flute", "in": ["B"], "melody": {"text": FLUTE_B, "velocity": 80, "repeat": False}},
        # 팀파니는 화음의 근음·5도를 따라간다(v1: D/A 고정이라 Bb·C 위에서 부딪힘)
        {"track": "Timpani", "in": ["B"], "bass": {"progression": PROG["B"], "beats_per_chord": 4, "low": 40, "high": 55,
                                                  "pattern": [[0, 1, 0], [2, 1, 7]], "velocity": 104}},
    ],
    "events": [{"section": "B", "at": -2, "length": 2, "type": "stop"}],
    "mix": {"balance": True, "target_lufs": card["mix"]["target_lufs"],
            "balance_lu": {"violins": 0, "cellos": 0, "horns": 1, "violas": -4, "basses": -5, "trumpets": -5,
                           "trombones": -6, "flute": -4, "timpani": -4}},
}

if __name__ == "__main__":
    concept_mod.save(NAME, CONCEPT)
    r = critic.critique(spec, CONCEPT)
    print(critic.format_report(r))
    if "--dry" in sys.argv:
        sys.exit(0)
    s, rep = arrange.build(spec, label=sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else "v3")
    print(json.dumps({k: rep[k] for k in ("file", "loudness", "bands_db", "issues", "png")}, ensure_ascii=False, default=str))
