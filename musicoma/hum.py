"""흥얼거림 → 비트. 사용자가 "동딩띵!"처럼 부르거나 비트박스한 소리를 알아듣고, 곡의 박자·조성에 '찰떡같이' 맞춰 노트로.
(10-15 본인: "개떡같이 불러도 찰떡같이 알아듣고 바로 비트에 반영", Suno 와의 차별점 — 사람이 직접 부른 걸로 편집)

    r = listen("sounds/inbox/hum.wav", bpm=92, key="D minor")             # 무엇을 불렀나
    r["notes"]   음표(박 기준, 0 = 녹음 첫 소리) · r["mode"] melody | drums · r["confidence"]
    place(song, r, track="Hum", at="1:20", repeat=4, sound="dexed:city_bell")  # 곡의 1분 20초부터 4번 반복

알아듣기
  리듬   onset(소리 시작) → 박 격자(16분)로 당기되 lock 만큼만(사람 느낌 남김). 녹음 템포가 곡과 다르면 자동 추정해서 맞춤
  음정   pYIN 음높이 → 음표 구간마다 중앙값 → 곡 조성의 음계로 가장 가까운 음(멜로디 모드)
  비트박스 스펙트럼 무게(저역=킥, 중역 잡음=스네어, 고역=햇)로 분류(드럼 모드)
  모드는 자동: 음높이가 잡히는 비율이 낮으면 드럼 모드
"""
import numpy as np
import librosa
import soundfile as sf

_PC = {"C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3, "E": 4, "F": 5, "F#": 6, "Gb": 6, "G": 7, "G#": 8, "Ab": 8,
       "A": 9, "A#": 10, "Bb": 10, "B": 11}


def _scale(key):
    t, _, m = key.partition(" ")
    base = [0, 2, 3, 5, 7, 8, 10] if m.lower().startswith("min") else [0, 2, 4, 5, 7, 9, 11]
    return {(_PC.get(t, 0) + x) % 12 for x in base}


def _snap_pitch(midi, scale):
    c = int(round(midi))
    for d in (0, -1, 1, -2, 2):
        if (c + d) % 12 in scale:
            return c + d
    return c


def listen(path, bpm, key="C major", mode="auto", grid=0.25, lock=0.8, tempo_from_recording=False):
    y, sr = librosa.load(str(path), sr=22050, mono=True)
    y, _ = librosa.effects.trim(y, top_db=35)
    if len(y) < sr * 0.2:
        raise ValueError("소리가 너무 짧거나 작아요")
    on = librosa.onset.onset_detect(y=y, sr=sr, units="time", backtrack=True, delta=0.05)
    head = y[:int(0.05 * sr)]
    if len(on) == 0 or (on[0] > 0.04 and np.sqrt(np.mean(head ** 2)) > 0.1 * np.sqrt(np.mean(y ** 2))):
        on = np.concatenate([[0.0], on])                                 # 첫 소리가 녹음 맨 앞이면 시작점으로 안 잡힌다
    # (on 은 절대 시간 그대로 — 음높이 시간과 같은 기준. 첫 음을 0 으로 옮기는 건 맨 끝에서)
    # 녹음 템포: 곡 BPM 을 기본으로, 원하면 녹음에서 추정해 곡 BPM 에 맞춰 늘이고 줄임
    rec_bpm = bpm
    if tempo_from_recording and len(on) >= 4:
        t, _ = librosa.beat.beat_track(y=y, sr=sr, start_bpm=bpm)
        rec_bpm = float(np.atleast_1d(t)[0]) or bpm
    spb = 60.0 / rec_bpm
    f0, voiced, prob = librosa.pyin(y, fmin=70, fmax=1100, sr=sr, frame_length=1024)
    times = librosa.times_like(f0, sr=sr, hop_length=256)
    voiced_share = float(np.mean(voiced)) if len(voiced) else 0.0
    if mode == "auto":
        mode = "melody" if voiced_share > 0.35 else "drums"
    scale = _scale(key)
    notes = []

    def add(a, b, pitch, heard=None):
        near = on[np.abs(on - a) <= 0.12] if len(on) else []          # 음높이 변화 지점 → 근처 실제 소리 시작점으로
        if len(near):
            a = float(near[np.argmin(np.abs(near - a))])
        beat = a / spb
        q = round(beat / grid) * grid
        start = (1 - lock) * beat + lock * q
        length = max(grid, round(((b - a) / spb) / grid) * grid * 0.9)
        seg_rms = float(np.sqrt(np.mean(y[int(a * sr):int(min(b, a + 0.15) * sr)] ** 2)) + 1e-9)
        n = {"pitch": pitch, "start": round(start, 4), "length": round(length, 4), "velocity": int(np.clip(60 + 900 * seg_rms, 50, 120))}
        if heard is not None:
            n["heard_midi"] = round(heard, 2)
        notes.append(n)

    if mode == "melody":
        # 음높이가 실제로 바뀌는 곳에서 음을 나눈다(비브라토·꼬리 떨림을 새 음으로 듣지 않게)
        midi = np.where(voiced & ~np.isnan(f0), librosa.hz_to_midi(np.nan_to_num(f0, nan=1.0)), np.nan)
        hop = times[1] - times[0] if len(times) > 1 else 0.0116
        seg_start, cur = None, []
        for i, m in enumerate(midi):
            if np.isnan(m):
                if seg_start is not None and len(cur) * hop >= 0.07:
                    med = float(np.median(cur)); add(times[seg_start], times[i], _snap_pitch(med, scale), med)
                seg_start, cur = None, []
                continue
            if seg_start is None:
                seg_start, cur = i, [m]
                continue
            med = float(np.median(cur[-8:]))
            if abs(m - med) >= 0.75 and len(cur) * hop >= 0.07:          # 반음 가까이 움직이면 새 음
                full = float(np.median(cur)); add(times[seg_start], times[i], _snap_pitch(full, scale), full)
                seg_start, cur = i, [m]
            else:
                cur.append(m)
        if seg_start is not None and len(cur) * hop >= 0.07:
            med = float(np.median(cur)); add(times[seg_start], times[-1], _snap_pitch(med, scale), med)
        # 같은 음이 붙어서 반 박 안에 다시 시작하면 하나로(노트가 쪼개진 것)
        merged = []
        for n in notes:
            if merged and n["pitch"] == merged[-1]["pitch"] and n["start"] - (merged[-1]["start"] + merged[-1]["length"]) < 0.3:
                merged[-1]["length"] = round(n["start"] + n["length"] - merged[-1]["start"], 4)
            else:
                merged.append(n)
        notes = merged
    else:
        ends = list(on[1:]) + [len(y) / sr]
        for a, b in zip(on, ends):
            win = y[int(a * sr): int(a * sr) + int(0.08 * sr)]
            if len(win) < 256:
                continue
            pk = int(np.argmax(np.abs(win)))                              # 시작점이 소리보다 앞(무음)에 잡혀도 실제 봉우리에서 판단
            seg = y[int(a * sr) + max(0, pk - int(0.005 * sr)): int(a * sr) + max(0, pk - int(0.005 * sr)) + int(0.06 * sr)]
            if len(seg) < 256 or np.sqrt(np.mean(seg ** 2)) < 0.1 * np.sqrt(np.mean(y ** 2)):
                continue                                                  # 정말 소리 없는 가짜 시작점
            spec = np.abs(np.fft.rfft(seg * np.hanning(len(seg))))
            f = np.fft.rfftfreq(len(seg), 1 / sr)
            centroid = float((spec * f).sum() / (spec.sum() + 1e-9))       # 밝기 중심: 둥(킥) < 탁(스네어) < 츠(햇)
            low = spec[f < 200].sum() / (spec.sum() + 1e-9)
            add(a, b, 36 if (low > 0.35 or centroid < 400) else 42 if centroid > 3500 else 38)
            notes[-1]["length"] = 0.25
    if not notes:
        raise ValueError("음을 알아듣지 못했어요 — 조금 더 크게, 또렷하게 불러 주세요")
    t0 = notes[0]["start"]
    for n in notes:
        n["start"] = round(n["start"] - t0, 4)
    length_beats = max(n["start"] + n["length"] for n in notes)
    bars = max(1, int(np.ceil(length_beats / 4 - 1e-6)))
    conf = round(float(np.mean([abs(n["heard_midi"] - n["pitch"]) < 0.6 for n in notes])) if mode == "melody" else voiced_share, 2)
    return {"mode": mode, "notes": notes, "bars": bars, "recording_bpm": round(rec_bpm, 1), "key": key,
            "voiced_share": round(voiced_share, 2), "confidence": conf}


def _at_beats(at, bpm):
    """'1:20' / '80s' / 80.0(초) / 'bar 33' → 박."""
    if isinstance(at, (int, float)):
        return at * bpm / 60.0
    at = str(at).strip().lower()
    if at.startswith("bar"):
        return (int(at.split()[-1]) - 1) * 4
    if ":" in at:
        m, s = at.split(":")
        return (int(m) * 60 + float(s)) * bpm / 60.0
    return float(at.rstrip("s")) * bpm / 60.0


def place(song, heard, track="Hum", at=0.0, repeat=1, sound=None, snap_bar=True):
    """알아들은 노트를 곡에 넣는다(MIDI 클립 → 나중에 피아노롤로 고칠 수 있음)."""
    beat = _at_beats(at, song.bpm)
    if snap_bar:
        beat = round(beat / 4) * 4
    cycle = heard["bars"] * 4
    notes = [{**n, "start": round(n["start"] + k * cycle, 4)} for k in range(max(1, repeat)) for n in heard["notes"]]
    notes = [{k: v for k, v in n.items() if k != "heard_midi"} for n in notes]
    if sound is None:
        sound = "drums_acoustic_basic" if heard["mode"] == "drums" else "dexed:city_bell"
    t = song.track(track, sound, role="hummed " + heard["mode"])
    t.midi(notes, start=beat, length=cycle * max(1, repeat), name=f"hum@{beat:g}")
    song.log(f"흥얼거림 → {track}", {"at_beat": beat, "repeat": repeat, "mode": heard["mode"], "notes": len(heard["notes"])})
    return {"track": track, "start_beat": beat, "bars": heard["bars"] * max(1, repeat), "notes": len(notes)}
