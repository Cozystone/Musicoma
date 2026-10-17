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
import re
from pathlib import Path

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


def _syllables(y, sr, times, hop=256):
    """소리 크기 봉우리마다 한 음절. 봉우리 사이 골짜기(5dB 이상 꺼짐)가 경계. 가장 큰 소리보다 22dB 이상 작은 건 숨·잡음."""
    from scipy.signal import find_peaks
    rms = librosa.feature.rms(y=y, frame_length=1024, hop_length=hop)[0]
    db = 20 * np.log10(rms + 1e-9)
    db = np.convolve(db, np.ones(3) / 3, mode="same")
    n = min(len(db), len(times))
    db, t = db[:n], times[:n]
    top = np.percentile(db, 98)
    pad = np.concatenate([[db.min() - 40] * 3, db])                      # 녹음 맨 앞의 첫 타격도 봉우리로 잡히게
    pk, _ = find_peaks(pad, height=top - 22, prominence=5, distance=max(1, int(0.09 * sr / hop)))
    pk = np.maximum(pk - 3, 0)
    out = []
    for j, p in enumerate(pk):
        lo = pk[j - 1] if j else 0
        hi = pk[j + 1] if j + 1 < len(pk) else n - 1
        lo = lo if j else max(0, p - int(0.3 * sr / hop))
        v0 = lo + int(np.argmin(db[lo:p + 1]))
        v1 = p + int(np.argmin(db[p:hi + 1]))
        rise = np.where(db[v0:p + 1] >= db[p] - 10)[0]                  # 시작 = 봉우리 10dB 아래까지 올라온 곳
        start = v0 + (int(rise[0]) if len(rise) else 0)
        fall = np.where(db[p:v1 + 1] < db[p] - 15)[0]                   # 끝 = 15dB 꺼진 곳 또는 다음 골짜기
        end = p + (int(fall[0]) if len(fall) else v1 - p)
        out.append((float(t[start]), float(t[max(end, start + 1)])))
    return out


def _fit_tempo(starts, bpm, grid=0.5):
    """박자 없이 부른 걸 곡 템포에 '찰떡같이': 녹음 속 음절 간격이 곡의 8분 격자에 가장 잘 맞는 녹음 템포를 찾는다.
    곡 템포에서 멀어질수록 벌점(반·두 배 속도로 부른 것도 후보)."""
    if len(starts) < 3:
        return bpm
    d = np.asarray(starts) - starts[0]
    best, err_best = bpm, 9e9
    for b in np.arange(bpm * 0.55, bpm * 1.8, 0.5):
        beats = d * b / 60.0
        err = float(np.mean(np.abs(beats / grid - np.round(beats / grid)))) + 0.12 * abs(np.log(b / bpm))
        if err < err_best:
            best, err_best = float(b), err
    return best


def listen(path, bpm, key="C major", mode="auto", grid=0.25, lock=0.8, tempo_from_recording="fit", transpose="fit"):
    y, sr = librosa.load(str(path), sr=22050, mono=True)
    y, _ = librosa.effects.trim(y, top_db=35)
    if len(y) < sr * 0.2:
        raise ValueError("소리가 너무 짧거나 작아요")
    on = librosa.onset.onset_detect(y=y, sr=sr, units="time", backtrack=True, delta=0.05)
    head = y[:int(0.05 * sr)]
    if len(on) == 0 or (on[0] > 0.04 and np.sqrt(np.mean(head ** 2)) > 0.1 * np.sqrt(np.mean(y ** 2))):
        on = np.concatenate([[0.0], on])                                 # 첫 소리가 녹음 맨 앞이면 시작점으로 안 잡힌다
    if len(on) > 1:                                                      # 같은 자리에 두 번 잡힌 시작점(실녹음 10-15)
        on = on[np.concatenate([[True], np.diff(on) > 0.06])]
    # (on 은 절대 시간 그대로 — 음높이 시간과 같은 기준. 첫 음을 0 으로 옮기는 건 맨 끝에서)
    # 녹음 템포: 곡 BPM 을 기본으로, 원하면 녹음에서 추정해 곡 BPM 에 맞춰 늘이고 줄임
    f0, voiced, prob = librosa.pyin(y, fmin=70, fmax=1100, sr=sr, frame_length=1024)
    times = librosa.times_like(f0, sr=sr, hop_length=256)
    voiced_share = float(np.mean(voiced)) if len(voiced) else 0.0
    if mode == "auto":
        mode = "melody" if voiced_share > 0.35 else "drums"
    syl = _syllables(y, sr, times)                                         # 음절(멜로디) · 타격(비트박스) = 소리 크기 봉우리
    if mode == "melody":                                                  # 음높이가 안 잡히는 봉우리(숨·잡음)는 음절이 아님
        syl = [(a, b) for a, b in syl if np.sum(voiced[(times >= a) & (times < b)]) >= 4]
    if mode == "drums" and syl:
        on = np.array([a for a, _ in syl])                                 # 킥 꼬리의 음높이 변화를 두 번째 타격으로 잡던 문제(10-15)
    rec_bpm = bpm
    if tempo_from_recording == "fit":                                     # 기본: 음절(또는 타격) 간격을 곡의 8분 격자에 맞춤
        rec_bpm = _fit_tempo([a for a, _ in syl] if syl else on, bpm)
    elif tempo_from_recording and len(on) >= 4:
        t, _ = librosa.beat.beat_track(y=y, sr=sr, start_bpm=bpm)
        rec_bpm = float(np.atleast_1d(t)[0]) or bpm
    spb = 60.0 / rec_bpm
    scale = _scale(key)
    notes = []

    def add(a, b, pitch, heard=None, snap_onset=True):
        near = on[np.abs(on - a) <= 0.12] if (len(on) and snap_onset) else []   # 음높이 변화 지점 → 근처 실제 소리 시작점으로
        if len(near):
            a = float(near[np.argmin(np.abs(near - a))])
        beat = a / spb
        q = round(beat / grid) * grid
        start = (1 - lock) * beat + lock * q
        length = max(grid, round(((b - a) / spb) / grid) * grid * 0.9)
        w = y[int(a * sr):int(max(min(b, a + 0.15), a + 0.01) * sr)]
        seg_rms = float(np.sqrt(np.mean(w ** 2))) if len(w) else 0.0
        n = {"pitch": pitch, "start": round(start, 4), "length": round(length, 4), "velocity": int(np.clip(60 + 900 * seg_rms, 50, 120))}
        if heard is not None:
            n["heard_midi"] = round(heard, 2)
        notes.append(n)

    if mode == "melody":
        # 실녹음(10-15 본인 '투두투두'): 같은 음으로 여러 음절을 부르면 음높이만으로는 한 음이 된다 →
        # 소리 크기가 꺼지는 곳(음절 사이)으로 먼저 나누고, 음절 안에서 음이 확실히 바뀌면(1.5반음, 0.1초 이상) 한 번 더 나눈다
        midi = np.where(voiced & ~np.isnan(f0), librosa.hz_to_midi(np.nan_to_num(f0, nan=1.0)), np.nan)
        for s0, s1 in syl:
            k = np.where((times >= s0) & (times < s1))[0]
            seg = [(i, midi[i]) for i in k if not np.isnan(midi[i])]
            if len(seg) < 4:
                continue
            parts, cur = [], [seg[0]]
            for i, m in seg[1:]:
                if abs(m - np.median([x for _, x in cur[-6:]])) >= 1.5 and len(cur) >= 8:
                    parts.append(cur)
                    cur = []
                cur.append((i, m))
            parts.append(cur)
            parts = [q for q in parts if len(q) >= 6] or [max(parts, key=len)]
            for j, q in enumerate(parts):
                a_ = s0 if j == 0 else times[q[0][0]]
                b_ = s1 if j == len(parts) - 1 else times[parts[j + 1][0][0]]
                body = [x for _, x in q[: max(3, int(len(q) * 0.7))]]           # 음절 끝의 꺾임(글라이드)은 빼고 앞 70%
                med = float(np.median(body))
                add(a_, b_, _snap_pitch(med, scale), med, snap_onset=(j == 0))
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
    shift = 0.0
    if mode == "melody" and transpose == "fit":
        # 사람은 곡 조성과 상관없는 높이로 흥얼거린다 → 선율 모양(음정 간격)은 그대로 두고 곡 조성에 가장 잘 맞게 통째로 옮긴다
        heard = np.array([n["heard_midi"] for n in notes])
        tune = float(np.median(heard - np.round(heard)))                    # 전체 음정 치우침(반음 사이에서 부른 정도)
        # 음마다 '가장 가까운 조성 음까지의 거리'로 점수(반올림하면 반음 사이에서 부른 음이 엉뚱한 쪽으로 넘어가 +4 같은 이조가 이김 — 10-17)
        def fit(k):
            h = heard + k                                              # 전체 치우침(tune)은 빼지 않는다 — 음마다 가장 가까운 조성 음으로 붙이는 쪽이 사람 노래엔 맞다
            s = 0.0
            for x in h:
                d = min(abs(x - c) for c in range(int(x) - 2, int(x) + 3) if c % 12 in scale)
                s += 0.6 - min(d, 0.6)
            return s - 0.05 * abs(k)
        k = max(sorted(range(-6, 6), key=abs), key=fit)                  # 같은 점수면 안 옮기는 쪽
        shift = float(k)
        for n in notes:
            n["pitch"] = _snap_pitch(n["heard_midi"] + shift, scale)
    elif mode == "melody" and isinstance(transpose, (int, float)):
        shift = float(transpose)
        for n in notes:
            n["pitch"] = _snap_pitch(n["heard_midi"] + shift, scale)
    conf = round(float(np.mean([abs(n["heard_midi"] + shift - n["pitch"]) < 0.6 for n in notes])) if mode == "melody" else voiced_share, 2)
    return {"mode": mode, "notes": notes, "bars": bars, "recording_bpm": round(rec_bpm, 1), "key": key,
            "voiced_share": round(voiced_share, 2), "confidence": conf, "transposed": round(shift, 2)}


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


# ── 말 + 흥얼거림이 섞인 녹음(10-15 본인: "최종 목표는 음성만으로 AI 와 실시간 대화하며 만들기 — 흥얼거림만 추려 내는 방식으론 힘들다")
# 한 번 말할 때 지시("이거 1분 20초에 네 번 넣어 줘")와 소리("투두투두")가 섞여 나온다 → 받아쓰기로 말을 찾고, 의성어·말 아닌 구간은 음악으로.
_ONO = set("투두둥딩띵땅따빠빰붐쿵쿠탁틱칙츠치키카파퍼푸뚜뚱뚝또도다디라랄라나난너누루룰룽음흠흐후하아오우에이야예와빱밥바부비삐뿌뽀둠담덤동똥칭짠짜찌쯔슈쉬스크텅통팡펑퐁뿜뽕뚱땡뎅딴단둡답닥덕둑쾅콩캉칫팟탓")
_ONO_EN = {"la", "da", "na", "do", "du", "doo", "dum", "dun", "ding", "dong", "boom", "bap", "ba", "pa", "tss", "ts", "ch", "shh", "sh",
           "tu", "tutu", "dudu", "hmm", "mm", "hm", "oh", "ooh", "ah", "uh", "bum", "dee", "di", "ta", "ti", "ka", "ki", "pum"}


def _is_music_word(w):
    w = re.sub(r"[^\w가-힣]", "", w.lower())
    if not w:
        return True
    if re.fullmatch(r"[가-힣]+", w):
        if len(w) == 1:                                                    # 한 글자는 말('이', '아', '음')일 때가 많다
            return w in "둥딩띵쿵탁칙츠붐빰땅뚱팍칫"
        return all(c in _ONO for c in w) and (len(set(w)) <= 3 or len(w) >= 4 and len(set(w)) <= len(w) // 2)
    if re.fullmatch(r"[a-z]+", w):
        return w in _ONO_EN or bool(re.fullmatch(r"(la|da|na|du|doo|tu|ba|pa|ta|ka|ts|ch|bum|dum|ding|dong)+", w))
    return False


def parse_place(text, bpm):
    """말 속의 배치 지시 → place() 인자. '1분 20초', '80초', '33마디', '네 번 반복' 정도만(나머지는 프로듀서 AI 가 해석)."""
    nums = {"한": 1, "두": 2, "세": 3, "네": 4, "다섯": 5, "여섯": 6, "일곱": 7, "여덟": 8, "아홉": 9, "열": 10}
    out = {}
    m = re.search(r"(\d+)\s*분\s*(\d+)?\s*초?", text)
    if m:
        out["at"] = f"{m.group(1)}:{m.group(2) or 0}"
    elif re.search(r"(\d+(?:\.\d+)?)\s*초", text):
        out["at"] = float(re.search(r"(\d+(?:\.\d+)?)\s*초", text).group(1))
    m = re.search(r"(\d+)\s*(?:번째\s*)?마디", text)
    if m and "at" not in out:
        out["at"] = f"bar {m.group(1)}"
    m = re.search(r"(\d+|한|두|세|네|다섯|여섯|일곱|여덟|아홉|열)\s*번", text)
    if m and re.search(r"반복|번\s*(넣|깔|돌|틀)", text):
        g = m.group(1)
        out["repeat"] = int(g) if g.isdigit() else nums[g]
    elif re.search(r"반복|계속|루프", text):
        out["repeat"] = 4
    return out


def understand(path, bpm, key="C major", lang="ko"):
    """한 녹음 → {"said": 지시 문장, "music": [listen 결과 + 녹음 속 위치], "place": 배치 추정}.
    말이 하나도 없으면 녹음 전체가 음악."""
    from . import voice_design as vd
    y, sr = librosa.load(str(path), sr=22050, mono=True)
    words = vd.words(path, lang)
    speech = [w for w in words if not _is_music_word(w["w"])]
    said = [w["w"] for w in speech]
    # 음악 구간 = 소리가 나는 곳 − 말한 단어 구간. 받아쓰기는 흥얼거림을 자주 빼먹거나 엉뚱한 말로 적는다(10-15) → 소리 크기로 찾는다
    hop = 256
    db = 20 * np.log10(librosa.feature.rms(y=y, frame_length=1024, hop_length=hop)[0] + 1e-9)
    t = librosa.frames_to_time(np.arange(len(db)), sr=sr, hop_length=hop)
    act = db > np.percentile(db, 98) - 30
    for w in speech:
        act[(t >= w["s"] - 0.12) & (t <= w["e"] + 0.12)] = False
    regions, i = [], 0
    while i < len(act):
        if not act[i]:
            i += 1
            continue
        j = i
        while j < len(act) and (act[j] or (j + 1 < len(act) and np.any(act[j:j + int(0.35 * sr / hop)]))):
            j += 1
        regions.append([float(t[i]), float(t[min(j, len(t) - 1)])])
        i = j
    regions = [r for r in regions if r[1] - r[0] >= 0.6]
    music = []
    for a, b in regions:
        a, b = max(0.0, a - 0.05), min(len(y) / sr, b + 0.15)
        clip = Path(path).with_name(f"{Path(path).stem}_m{len(music)}.wav")
        sf.write(str(clip), y[int(a * sr):int(b * sr)], sr)
        try:
            r = listen(clip, bpm, key)
        except ValueError:
            continue
        music.append({**r, "from_s": round(a, 2), "to_s": round(b, 2), "path": str(clip)})
    text = " ".join(said).strip()
    return {"said": text, "music": music, "place": parse_place(text, bpm)}
