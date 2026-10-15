"""Musicoma Core 널 테스트용 곡(샘플러만) — 지금 엔진으로 만들고 scratch/core/ 에 저장한다.

    python tests/core_null_projects.py [names...]

각 곡: edit.new zz-core-<이름> → 트랙/SFZ/MIDI → edit.save scratch/core/<이름>/<이름>.tracktionedit
       → plan.json(core_export) → (엔진) render → scratch/core/<이름>/engine.wav → 임시 projects/zz-core-* 폴더는 지운다.
마스터 이펙트·리버브 센드 없음.
"""
import json
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from musicoma.core_export import export_plan, save_plan  # noqa: E402
from musicoma.engine import connect  # noqa: E402
from musicoma.knowledge import resolve_sound  # noqa: E402
from musicoma.layout import scratch  # noqa: E402

PIANO = resolve_sound("piano_grand")["sfz"]
DRUMS = resolve_sound("drums_rusty")["sfz"]
BASS = resolve_sound("bass_hollow_finger")["sfz"]


def n(pitch, start, length, vel):
    return {"pitch": pitch, "start": start, "length": length, "velocity": vel}


def cal_piano():
    """벨로시티 곡선·릴리스 측정: C4 를 여러 세기로, 2박 누르고 4박 쉼."""
    notes = [n(60, i * 6, 2, v) for i, v in enumerate([10, 26, 40, 64, 80, 100, 127])]
    notes += [n(45, 42, 2, 90), n(84, 48, 2, 90)]
    return 120, [{"name": "Piano", "sfz": PIANO, "clips": [{"start": 0, "length": 56, "notes": notes}]}]


def cal_pan():
    """팬 법칙·볼륨: 같은 음을 트랙마다 다른 시간에 (pan 0 / -1 / +0.5 / vol -6dB)."""
    tr = []
    for i, (name, vol, pan) in enumerate([("C", 0, 0), ("L", 0, -1), ("H", 0, 0.5), ("V", -6, 0)]):
        tr.append({"name": name, "sfz": PIANO, "volume_db": vol, "pan": pan,
                   "clips": [{"start": i * 8, "length": 8, "notes": [n(64, 0, 2, 100)]}]})
    return 120, tr


def cal_bass():
    """베이스: 여러 음·세기·길이 (필터·릴리스·라운드로빈)."""
    notes, t = [], 0
    for p, v, L in [(28, 100, 1), (33, 60, 1), (40, 120, 2), (45, 30, 0.5), (52, 90, 1), (28, 100, 1), (28, 100, 1),
                    (40, 80, 3)]:
        notes.append(n(p, t, L, v))
        t += L + 2
    return 100, [{"name": "Bass", "sfz": BASS, "clips": [{"start": 0, "length": t + 2, "notes": notes}]}]


def cal_drums():
    """드럼: 킥·스네어·하이햇(닫힘/열림 → 초크)·탐·라이드, 라운드로빈 4회."""
    notes, t = [], 0.0
    for p in (36, 38, 42, 46):
        for v in (40, 80, 110, 127):
            notes.append(n(p, t, 0.25, v))
            t += 1
    notes += [n(46, t, 0.25, 100), n(42, t + 0.5, 0.25, 100)]  # 열린 햇 → 닫힌 햇 초크
    t += 2
    for p in (41, 45, 48, 51, 49):
        notes.append(n(p, t, 0.25, 100))
        t += 1.5
    return 110, [{"name": "Drums", "sfz": DRUMS, "clips": [{"start": 0, "length": t + 4, "notes": notes}]}]


def song_piano():
    """널 테스트 곡 1: 피아노 화성 진행 + 서스테인 페달."""
    chords = [[48, 55, 60, 64, 67], [45, 52, 57, 60, 64], [41, 48, 53, 57, 60], [43, 50, 55, 59, 62]]
    notes, cc = [], []
    for bar, ch in enumerate(chords * 2):
        b = bar * 4
        for k, p in enumerate(ch):
            notes.append(n(p, b + k * 0.12, 3.5, 60 + (k * 9) % 40))
        notes += [n(ch[-1] + 12, b + 2, 0.5, 85), n(ch[-2] + 12, b + 2.5, 0.5, 70), n(ch[-1] + 12, b + 3, 1, 90)]
        cc += [{"cc": 64, "beat": b + 0.05, "value": 127}, {"cc": 64, "beat": b + 3.9, "value": 0}]
    return 84, [{"name": "Piano", "sfz": PIANO, "clips": [{"start": 0, "length": 32, "notes": notes, "cc": cc}]}]


def song_drums():
    """널 테스트 곡 2: 4마디 그루브(킥·스네어·하이햇, 마지막 마디 필인)."""
    notes = []
    for bar in range(4):
        b = bar * 4
        for i in range(8):
            notes.append(n(42 if i != 7 else 46, b + i * 0.5, 0.25, 70 + (i % 2) * 30))
        notes += [n(36, b, 0.25, 115), n(36, b + 1.75, 0.25, 90), n(36, b + 2.5, 0.25, 110),
                  n(38, b + 1, 0.25, 110), n(38, b + 3, 0.25, 120)]
        if bar == 3:
            notes += [n(48, b + 3.25, 0.2, 100), n(45, b + 3.5, 0.2, 100), n(41, b + 3.75, 0.2, 110)]
    notes.append(n(49, 16, 0.5, 110))
    notes.append(n(36, 16, 0.5, 115))
    return 92, [{"name": "Drums", "sfz": DRUMS, "clips": [{"start": 0, "length": 20, "notes": notes}]}]


def song_bass():
    """널 테스트 곡 3: 4마디 베이스 라인 + 피치 벤드 한 번."""
    line = [(40, 0, 0.75), (40, 1, 0.5), (47, 1.5, 0.5), (45, 2, 1), (43, 3, 0.75), (40, 4, 1.5), (38, 5.5, 0.5),
            (36, 6, 1), (35, 7, 0.75), (33, 8, 1.5), (45, 9.5, 0.5), (43, 10, 1), (40, 11, 1), (38, 12, 0.75),
            (40, 13, 0.5), (43, 13.5, 0.5), (45, 14, 1.75)]
    notes = [n(p, s, L, 80 + (i * 13) % 40) for i, (p, s, L) in enumerate(line)]
    bend = [{"beat": 14.0, "value": 0.0}, {"beat": 14.5, "value": 0.5}, {"beat": 15.2, "value": 0.0}]
    return 96, [{"name": "Bass", "sfz": BASS, "clips": [{"start": 0, "length": 16, "notes": notes, "bend": bend}]}]


def song_mix():
    """널 테스트 곡 4: 세 악기 + 볼륨/팬 (믹서 경로 확인)."""
    _, p = song_piano()
    _, d = song_drums()
    _, b = song_bass()
    p[0].update(volume_db=-6, pan=-0.3)
    d[0].update(volume_db=-3)
    b[0].update(volume_db=-2, pan=0.2)
    for t in p + d + b:
        t["clips"] = [dict(c, length=min(c["length"], 16),
                           notes=[x for x in c["notes"] if x["start"] < 16],
                           cc=[x for x in c.get("cc", []) if x["beat"] < 16]) for c in t["clips"]]
    return 92, p + d + b


def cal_cc():
    """CC 동작: 피아노 CC11/CC1/CC7/CC10 변화, 베이스 피치 벤드 (sfizz 기본 매핑 확인)."""
    notes = [n(60, i * 2, 1.5, 90) for i in range(8)]
    cc = [{"cc": 11, "beat": 2, "value": 64}, {"cc": 11, "beat": 4, "value": 127},
          {"cc": 1, "beat": 6, "value": 127}, {"cc": 1, "beat": 8, "value": 0},
          {"cc": 7, "beat": 8, "value": 64}, {"cc": 7, "beat": 10, "value": 100},
          {"cc": 10, "beat": 12, "value": 0}, {"cc": 10, "beat": 14, "value": 64}]
    bnotes = [n(40, 0, 3, 100), n(45, 4, 3, 100), n(40, 8, 6, 100)]
    bend = [{"beat": 1, "value": 1.0}, {"beat": 2, "value": 0.0}, {"beat": 5, "value": -1.0}, {"beat": 6, "value": 0.0},
            {"beat": 9, "value": 0.25}, {"beat": 10, "value": 0.5}, {"beat": 11, "value": 0.75}, {"beat": 12, "value": 0.0}]
    return 120, [{"name": "Piano", "sfz": PIANO, "clips": [{"start": 0, "length": 16, "notes": notes, "cc": cc}]},
                 {"name": "Bass", "sfz": BASS, "volume_db": -4, "clips": [{"start": 0, "length": 16, "notes": bnotes, "bend": bend}]}]


def cal_audio():
    """오디오 클립: 게인·페이드·오프셋·리버스 + 트랙 팬 (C1 오디오 경로 확인)."""
    f = str(ROOT / "sounds/crate/accomp/accomp_vinyl_sample_loop4bar_88bpm.wav")
    return 120, [{"name": "A", "audio": [{"path": f, "start": 0, "length": 8, "gain_db": -3, "fade_in": 0.5, "fade_out": 1.0}]},
                 {"name": "B", "pan": 0.4, "volume_db": -2,
                  "audio": [{"path": f, "start": 10, "offset": 1.25, "length": 6, "reverse": True}]}]


ALL = {"cal-cc": cal_cc, "cal-audio": cal_audio, "cal-piano": cal_piano, "cal-pan": cal_pan, "cal-bass": cal_bass, "cal-drums": cal_drums,
       "piano": song_piano, "drums": song_drums, "bass": song_bass, "mix": song_mix}


def build(e, name, fn, render=True):
    bpm, tracks = fn()
    proj = f"zz-core-{name}"
    out_dir = scratch("core", name)
    e.call("edit.new", {"name": proj, "bpm": bpm})
    for t in tracks:
        e.call("track.add", {"name": t["name"]})
        if t.get("sfz"):
            e.call("device.add", {"track": t["name"], "device": "sfz", "sfz": t["sfz"]})
        for a in t.get("audio", []):
            e.call("clip.add_audio", {"track": t["name"], **a})
        mix = {k: t[k] for k in ("volume_db", "pan") if k in t}
        if mix:
            e.call("track.set", {"track": t["name"], **mix})
        for c in t.get("clips", []):
            prm = {"track": t["name"], "start": c["start"], "length": c["length"], "notes": c["notes"]}
            if c.get("cc"):
                prm["cc"] = c["cc"]
            if c.get("bend"):
                prm["bend"] = c["bend"]
            e.call("clip.add_midi", prm)
    edit_path = out_dir / f"{name}.tracktionedit"
    e.call("edit.save", {"path": str(edit_path)})
    shutil.rmtree(ROOT / "projects" / proj, ignore_errors=True)   # 임시 폴더(규칙: projects/ 에 zz-* 남기지 않음)
    save_plan(export_plan(e), out_dir / "plan.json")          # 렌더 계획(엔진에 열린 상태 그대로)
    info = {"name": name, "edit": str(edit_path), "bpm": bpm}
    if render:
        wav = out_dir / "engine.wav"
        r = e.call("render", {"path": str(wav), "tail": 2.0})
        info.update(engine_wav=r["path"], engine_render_ms=r["render_ms"], seconds=r["seconds"])
    (out_dir / "build.json").write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
    return info


if __name__ == "__main__":
    names = sys.argv[1:] or [k for k in ALL if k not in ("cal-cc", "cal-audio")]
    e = connect("core-null")
    for nm in names:
        t0 = time.time()
        print(nm, build(e, nm, ALL[nm]), f"{time.time() - t0:.1f}s", flush=True)
