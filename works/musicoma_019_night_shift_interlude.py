"""NIGHT SHIFT · 06 「Night Shift (Interlude)」 — 1분. 비트 없이 레코드(Last Train 의 레코드, 배속 전 원속도!)만 깔고 래퍼 A 가 말한다.
앨범 제목 자리: 배속 전의 레코드를 그대로 들려 주는 유일한 순간(= 우리가 샘플링한 '음반'의 정체). 끝에 한국어 한 줄.

    python works/musicoma_019_night_shift_interlude.py v1
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from musicoma import arrange, concept as concept_mod, crate

NAME = "ns-06-night-shift-interlude"
BPM = 70                                            # Last Train 레코드 원속도(69.85)에 가깝게
REC = Path(arrange.ROOT) / "projects" / "ns-01-last-train-record" / "renders" / "ns-01-last-train-record_record.wav"
FORM = [("record", 8), ("talk", 12), ("tail", 4)]

TALK = [{"text": "Night shift.", "beats": 6}, {"text": "That's the name of it.", "beats": 6},
        {"text": "Everybody on this record is working while you're asleep, or walking home while you're waking up.", "beats": 12},
        {"text": "This is what the music sounded like before we sped it up.", "beats": 10},
        {"text": "Slow. Somebody singing in a room.", "beats": 8},
        {"text": "We just turned the speed up until it sounded like it was missing something.", "beats": 10},
        {"text": "That's the whole trick.", "beats": 6}]
TALK_KO = [{"text": "밤에 일하는 사람들한테.", "beats": 8}]          # 한국어는 따로(받아쓰기 정렬 언어가 다름)

CONCEPT = {
    "thesis": "앨범의 '음반'을 원속도로 한 번 들려 주고, 그 위에서 트릭을 고백한다 — 느린 걸 빨리 돌려 뭔가 빠진 소리로 만든 것",
    "arc": [{"section": "record", "intent": "레코드 원속도, 비닐 — 아무도 말하지 않음", "energy": 0.25},
            {"section": "talk", "intent": "래퍼 A 가 낮게 말함, 레코드는 뒤로", "energy": 0.35},
            {"section": "tail", "intent": "한국어 한 줄 뒤 레코드가 필터로 닫힘", "energy": 0.2}],
    "motif": {"melody": "A4:.5 C5:.5 D5:1 C5:1", "why": "Last Train 레코드의 'stay on the last' — 배속 전 원래 높이로"},
    "collision": ["배속 전 레코드(느림·사람)", "말(영어)", "한국어 한 줄"],
    "irregular": [{"what": "비트 없음", "why": "인터루드"}, {"what": "한국어", "why": "앨범에서 유일한 한국어 — 누구에게 바치는지"}],
    "constraints": ["1분 안팎", "-14 LUFS(앨범보다 작게)"],
    "references": "—", "not": ["드럼", "찹"],
}


def build(label):
    aged = crate.age(REC, "vinyl", out=Path(arrange.ROOT) / "sounds" / "crate" / f"{NAME}_record_vinyl.wav")
    spec = {
        "name": NAME, "bpm": BPM, "key": "F major", "style": "chipmunk-soul", "feel": "laid_back", "intensity": 0.3,
        "brief": "NIGHT SHIFT 06 인터루드 — Last Train 레코드 원속도 + 래퍼 A 의 말 + 한국어 한 줄",
        "sections": [{"name": n, "bars": k} for n, k in FORM],
        "tracks": {
            "Record": {"role": "the record, original speed, vinyl", "fx": [{"device": "lowpass", "params": {"frequency": 20000}}]},
            "Talk": {"role": "spoken (bomf-rapper)", "sends": {"0": -14}, "fx": [
                {"device": "eq", "params": {"Low-pass freq": 90, "Low-pass gain": -12, "Mid freq 2": 2800, "Mid gain 2": 2, "High-pass freq": 10000, "High-pass gain": -2}},
                {"device": "compressor", "params": {"threshold": -22, "ratio": 3.5, "attack": 10, "release": 120}}]},
        },
        "buses": [{"name": "Verb", "bus": 0, "device": "Dragonfly Plate Reverb", "volume_db": -6}],
        "parts": [
            {"track": "Record", "in": ["record"], "audio": {"path": str(aged), "length": 96, "offset": 0}},
            {"track": "Talk", "in": ["talk"], "rap": {"voice": "bomf-rapper", "lines": TALK, "style": "spoken, low, calm, like liner notes read out loud, long pauses", "lock": 0.3, "seed": 61}},
            {"track": "Talk", "in": ["tail"], "rap": {"voice": "bomf-rapper", "lines": TALK_KO, "lang": "ko", "style": "spoken, low, calm, Korean", "lock": 0.3, "seed": 62}},
        ],
        "automation": [{"track": "Record", "device": 0, "param": "frequency", "points": [{"bar": 0, "value": 20000}, {"bar": 8, "value": 20000}, {"bar": 9, "value": 4000}, {"bar": 20, "value": 4000}, {"bar": 24, "value": 350}]}],
        "mix": {"balance": True, "target_lufs": -14, "balance_lu": {"record": 0, "talk": 2}},
    }
    s, rep = arrange.build(spec, label=label, log=lambda m: print("[4]", m, flush=True) if "rapped" in m or "balance" in m else None)
    return rep


if __name__ == "__main__":
    label = sys.argv[1] if len(sys.argv) > 1 else "v1"
    concept_mod.save(NAME, CONCEPT)
    rep = build(label)
    print(json.dumps({k: rep.get(k) for k in ("file", "loudness", "issues")}, ensure_ascii=False, default=str), flush=True)
