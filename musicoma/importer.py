"""가져오기 — Claude(또는 사용자)가 가져온 무엇이든 Musicoma 로.

import_any(path)   : 오디오(wav/mp3/flac/aiff/ogg/m4a) · 영상(mp4/mov/mkv/webm) · MIDI · 스템 폴더 · Ableton .als
reverse(path, name): 완성된 곡(영상·음원)을 '편집 가능한 Musicoma 프로젝트'로 역설계
                     = 스템 분리 → 템포·키 → 드럼/베이스/코드/멜로디 채보(MIDI) → 원본 스템(참고용) + 다시 연주한 트랙
권리: 본인 것 또는 권리가 있는 소재에 쓴다(가져오기 자체가 권리를 만들지 않는다).
"""
import json
import shutil
import subprocess
from pathlib import Path

import numpy as np
import librosa
import soundfile as sf

from . import crate, theory, transcribe

ROOT = Path(__file__).resolve().parent.parent
INBOX = ROOT / "sounds/inbox"
AUDIO = {".wav", ".mp3", ".flac", ".aif", ".aiff", ".ogg", ".m4a", ".aac", ".opus", ".wma"}
VIDEO = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}
MIDI = {".mid", ".midi"}


def _ffmpeg():
    exe = shutil.which("ffmpeg")
    if not exe:
        raise RuntimeError("ffmpeg 가 PATH 에 없음")
    return exe


def to_wav(path, out_dir=None, sr=48000):
    """어떤 오디오/영상이든 48k 스테레오 WAV 로."""
    p = Path(path)
    out_dir = Path(out_dir or INBOX / "imported")
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / (p.stem + ".wav")
    if p.suffix.lower() == ".wav":
        y, s = sf.read(str(p), always_2d=True)
        if s == sr:
            if p.resolve() != out.resolve():
                shutil.copy2(p, out)
            return str(out)
    r = subprocess.run([_ffmpeg(), "-y", "-v", "error", "-i", str(p), "-vn", "-ac", "2", "-ar", str(sr), "-c:a", "pcm_s24le", str(out)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError("ffmpeg: " + r.stderr[-400:])
    return str(out)


def import_any(path, song=None, track=None, start_beat=0.0):
    """파일/폴더를 받아 알맞게 처리. song(Song) 을 주면 그 곡에 트랙으로 넣는다."""
    p = Path(path)
    if p.is_dir():
        files = sorted(f for f in p.iterdir() if f.suffix.lower() in AUDIO | VIDEO)
        return {"kind": "stems", "items": [import_any(f, song, f.stem, start_beat) for f in files]}
    ext = p.suffix.lower()
    if ext == ".als":
        from . import als
        s, rep = als.import_als(p, log=lambda m: None)
        return {"kind": "ableton", "song": s.name, "tracks": len(rep["tracks"])}
    if ext in MIDI:
        if song is None:
            return {"kind": "midi", "path": str(p), "note": "곡을 지정하면 트랙으로 넣음"}
        name = track or p.stem
        song.track(name, "piano_grand", role="imported midi")
        r = song.e.call("clip.import_midi", {"track": name, "path": str(p), "start": start_beat})
        return {"kind": "midi", "track": name, **r}
    if ext in AUDIO | VIDEO:
        wav = to_wav(p)
        info = crate.analyze(wav)
        out = {"kind": "video" if ext in VIDEO else "audio", "wav": wav, "bpm": info["bpm"], "key": info["key"],
               "seconds": info["seconds"]}
        if song is not None:
            name = track or p.stem
            song.track(name, role="imported audio")
            song.e.call("clip.add_audio", {"track": name, "path": wav, "start": start_beat})
            out["track"] = name
        return out
    raise ValueError(f"모르는 형식: {ext}")


# --------------------------------------------------------------------------- 드럼 채보
def drum_notes(path, bpm, grid=0.25):
    """드럼 스템 → kick/snare/hat MIDI. 타격 지점마다 스펙트럼 무게중심으로 분류."""
    y, sr = librosa.load(str(path), sr=22050, mono=True)
    onsets = librosa.onset.onset_detect(y=y, sr=sr, units="samples", backtrack=False, delta=0.07)
    spb = 60.0 / bpm
    notes = []
    for o in onsets:
        seg = y[o: o + int(0.06 * sr)]
        if len(seg) < 256:
            continue
        spec = np.abs(np.fft.rfft(seg * np.hanning(len(seg))))
        f = np.fft.rfftfreq(len(seg), 1 / sr)
        low, mid, high = spec[f < 150].sum(), spec[(f >= 150) & (f < 2500)].sum(), spec[f >= 5000].sum()
        tot = low + mid + high + 1e-9
        pitch = 36 if low / tot > 0.45 else 42 if high / tot > 0.35 else 38
        vel = int(np.clip(50 + 400 * np.sqrt((seg ** 2).mean()), 40, 120))
        beat = round((o / sr) / spb / grid) * grid
        notes.append({"pitch": pitch, "start": round(beat, 4), "length": 0.25, "velocity": vel})
    # 같은 칸 중복 제거
    seen, out = set(), []
    for n in notes:
        k = (n["pitch"], n["start"])
        if k not in seen:
            seen.add(k)
            out.append(n)
    return out


def melody_notes(path, bpm, grid=0.25, fmin=80, fmax=1000):
    """보컬/리드 스템 → 멜로디 MIDI (pYIN)."""
    y, sr = librosa.load(str(path), sr=22050, mono=True)
    f0, voiced, prob = librosa.pyin(y, fmin=fmin, fmax=fmax, sr=sr, hop_length=256)
    t = librosa.times_like(f0, sr=sr, hop_length=256)
    spb, notes, cur = 60.0 / bpm, [], None
    for i in range(len(f0)):
        p = int(round(librosa.hz_to_midi(f0[i]))) if voiced[i] and prob[i] > 0.4 else None
        beat = round(t[i] / spb / grid) * grid
        if cur and (p != cur["pitch"]):
            cur["length"] = max(grid, round(beat - cur["start"], 4))
            notes.append(cur)
            cur = None
        if p is not None and cur is None:
            cur = {"pitch": p, "start": beat, "length": grid, "velocity": 90}
    if cur:
        notes.append(cur)
    return [n for n in notes if n["length"] >= grid]


def reverse(path, name, bars_limit=None, log=print):
    """완성된 곡 → 편집 가능한 Musicoma 프로젝트(뼈대 재구성)."""
    from .song import Song
    wav = to_wav(path)
    info = crate.analyze(wav)
    bpm = round(info["bpm"], 2)
    log(f"[1] {Path(path).name}: {bpm} BPM, {info['key']}, {info['seconds']}s")
    stems = crate.separate(wav)
    log(f"[2] 스템: {', '.join(stems)}")
    # 첫 박 위치를 0 박으로 맞춤
    offset = info["beats"][0] if info["beats"] else 0.0
    trimmed = {}
    for k, v in stems.items():
        y, sr = sf.read(v, always_2d=True)
        out = Path(v).with_name(f"{k}_aligned.wav")
        sf.write(str(out), y[int(offset * sr):], sr, subtype="PCM_24")
        trimmed[k] = str(out)
    drums = drum_notes(trimmed["drums"], bpm)
    bass = transcribe.bass_notes(trimmed["bass"], bpm, grid=0.25)
    chords = transcribe.simplify(transcribe.chords(trimmed["other"], bpm, beats_per_chord=2, bass_path=trimmed["bass"]))
    melody = melody_notes(trimmed["vocals"], bpm)
    log(f"[3] 채보: 드럼 {len(drums)} · 베이스 {len(bass)} · 코드 {len(chords)} · 멜로디 {len(melody)}")

    s = Song.new(name, bpm=bpm, key=info["key"], brief=f"역설계: {Path(path).name}")
    length = max([n["start"] + n["length"] for n in drums + bass + melody] + [16])
    for k, v in trimmed.items():                                        # 원본 스템(참고용, 기본 뮤트)
        t = s.track(f"ref_{k}", role=f"reference stem {k}", volume_db=-6)
        s.e.call("clip.add_audio", {"track": f"ref_{k}", "path": v, "start": 0})
        t.mix(mute=True)
    s.track("Drums", "drums_acoustic_basic", role="drums").midi(drums, length=length, name="drums")
    s.track("Bass", "bass_finger", role="bass").midi(bass, length=length, name="bass")
    vo = theory.voice([c[0] for c in chords], "piano") if chords else []
    keys = []
    for (name_, start, dur), v in zip(chords, vo):
        for p in v:
            keys.append({"pitch": p, "start": start, "length": (dur or 2) * 0.95, "velocity": 75})
    s.track("Keys", "rhodes", role="keys").midi(keys, length=length, name="chords")
    s.track("Melody", "flute", role="lead (vocal melody)").midi(melody, length=length, name="melody")
    s.meta["reverse"] = {"source": str(path), "stems": trimmed, "chords": chords}
    s.save()
    log("[4] 프로젝트 완성 — ref_* 트랙(원본 스템)은 뮤트, 다시 연주한 트랙은 바로 편집 가능")
    return s
