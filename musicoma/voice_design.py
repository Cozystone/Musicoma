"""목소리 생성 — 고르지 않고 '매번 새로 만든다'. (VoxCPM2 Voice Design · Apache-2.0 코드·가중치)

    v = design("허스키한 40대 남성 래퍼, 낮고 거친 목소리, 자신감", seed=None)   # 새 목소리(시드 = 그 목소리의 신분)
    rap(v, lines, bpm=86, start_beat=16, out=...)                               # 박자 격자에 맞춘 랩
    speak(v, "문장", out=...)                                                   # 그냥 말하기

목소리 = (설명 + 시드). 같은 설명 + 같은 시드 = 같은 목소리, 시드만 바꾸면 같은 '느낌'의 다른 사람.
처음 만든 샘플(design.wav)을 기준 음색으로 삼아 이후 모든 줄을 같은 사람이 말하게 한다(Controllable Cloning).
Claude 가 느낌을 조정 = 설명을 고쳐 쓰거나(새 목소리) voice_character 손잡이로 미세 조정(같은 목소리).
실존 인물 이름·흉내 설명은 쓰지 않는다.
"""
import json
import os
import random
import subprocess
from pathlib import Path

import numpy as np
import soundfile as sf
import librosa

ROOT = Path(__file__).resolve().parent.parent
VOX = ROOT / "third_party/voxcpm"
PY = VOX / ".venv/Scripts/python.exe"
VOICES = ROOT / "sounds/voices"
SR = 48000

# 설명 안의 한국어도 그대로 통한다. 영어 가사를 말할 때는 영어 설명이 더 안정적이라 둘 다 받는다.
SAMPLE_TEXT = {"en": "Yeah, this one goes out to everybody chasing something bigger than the city lights.",
               "ko": "오늘 밤 도시의 불빛 아래에서 나는 다시 꿈을 꾼다."}


def _run(jobs, tag="job"):
    work = VOX / "_jobs"
    work.mkdir(exist_ok=True)
    req = work / f"{tag}_{random.randrange(10**8)}.json"
    req.write_text(json.dumps({"jobs": jobs}, ensure_ascii=False), encoding="utf-8")
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8", "HF_HOME": str(VOX / "hf"),
           "HF_HUB_OFFLINE": "1"}
    r = subprocess.run([str(PY), str(VOX / "musicoma_voxcpm.py"), str(req)], cwd=VOX, env=env,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError(r.stderr[-2500:])
    return json.loads([l for l in r.stdout.splitlines() if l.startswith('{"done"')][-1])


def design(description, seed=None, name=None, lang="en", sample_text=None):
    """설명 → 새 목소리. 반환: 목소리 이름(sounds/voices/<이름>/)."""
    seed = random.randrange(10**6) if seed is None else int(seed)
    name = name or f"gen-{seed:06d}"
    d = VOICES / name
    d.mkdir(parents=True, exist_ok=True)
    text = f"({description}){sample_text or SAMPLE_TEXT[lang]}"
    _run([{"text": text, "out": str(d / "design.wav"), "seed": seed}], "design")
    (d / "voice.json").write_text(json.dumps({"name": name, "kind": "designed", "engine": "VoxCPM2",
                                              "description": description, "seed": seed, "lang": lang,
                                              "sample_text": sample_text or SAMPLE_TEXT[lang]},
                                             ensure_ascii=False, indent=1), encoding="utf-8")
    return name


def info(voice):
    return json.loads((VOICES / voice / "voice.json").read_text(encoding="utf-8"))


def speak_many(voice, texts, outs, style="", seed=0):
    """같은 목소리로 여러 문장. style = 말투 지시(예: 'rhythmic hip-hop rap delivery, punchy')."""
    ref = str(VOICES / voice / "design.wav")
    jobs = [{"text": (f"({style})" if style else "") + t, "out": str(Path(o).resolve()), "seed": seed + i, "reference": ref}
            for i, (t, o) in enumerate(zip(texts, outs))]
    return _run(jobs, "speak")


def speak(voice, text, out, style="", seed=0):
    speak_many(voice, [text], [out], style, seed)
    return str(out)


# --------------------------------------------------------------------------- 시간 늘이기(WSOLA, 자체 구현)
def wsola(x, ratio, frame=1024, hop=256, tol=256):
    """음높이를 바꾸지 않고 길이만 ratio 배(출력/입력). 말소리용 파형 유사도 중첩."""
    if abs(ratio - 1) < 1e-3 or len(x) < frame * 2:
        return librosa.util.fix_length(x, size=max(1, int(round(len(x) * ratio))))
    win = np.hanning(frame).astype(np.float32)
    n_out = int(round(len(x) * ratio))
    y = np.zeros(n_out + frame * 2, np.float32)
    norm = np.zeros_like(y)
    xp = np.pad(x.astype(np.float32), (tol, frame + tol + hop))
    prev = 0                     # 직전 프레임이 실제로 쓴 입력 위치
    k = 0
    while k * hop < n_out:
        nominal = int(k * hop / ratio)
        if k == 0:
            pos = nominal
        else:
            natural = xp[tol + prev + hop: tol + prev + hop + frame]          # 이어졌을 자연스러운 다음 조각
            lo, hi = tol + nominal - tol, tol + nominal + tol
            seg = xp[lo: hi + frame]
            if len(natural) == frame and len(seg) >= frame:
                c = np.correlate(seg, natural, mode="valid")
                pos = nominal - tol + int(np.argmax(c))
            else:
                pos = nominal
        pos = max(0, pos)
        chunk = xp[tol + pos: tol + pos + frame]
        if len(chunk) < frame:
            break
        y[k * hop: k * hop + frame] += chunk * win
        norm[k * hop: k * hop + frame] += win
        prev = pos
        k += 1
    y = y[:n_out] / np.maximum(norm[:n_out], 1e-3)
    return y


def warp(x, sr, src_marks, dst_marks):
    """구간별 늘이기: src_marks(초) → dst_marks(초). 양 끝 포함, 단조 증가."""
    out = []
    for (a, b), (c, d) in zip(zip(src_marks[:-1], src_marks[1:]), zip(dst_marks[:-1], dst_marks[1:])):
        seg = x[int(a * sr): int(b * sr)]
        want = int(round((d - c) * sr))
        if want <= 0:
            continue
        if len(seg) < 64:
            out.append(np.zeros(want, np.float32))
            continue
        y = wsola(seg, want / len(seg))
        out.append(librosa.util.fix_length(y, size=want))
    return np.concatenate(out) if out else np.zeros(1, np.float32)


# --------------------------------------------------------------------------- 랩: 줄 → 박자 격자
_ASR = None


def words(path, lang="en"):
    """단어별 시작·끝(초) — 정렬의 기준점."""
    global _ASR
    if _ASR is None:
        from faster_whisper import WhisperModel
        _ASR = WhisperModel("small", device="cuda", compute_type="float16")
    segs, _ = _ASR.transcribe(str(path), language=lang, word_timestamps=True, vad_filter=False)
    return [{"w": w.word.strip(), "s": w.start, "e": w.end} for s in segs for w in s.words]


def _trim(y, sr, db=40):
    _, (a, b) = librosa.effects.trim(y, top_db=db)
    return y[a:b], a / sr


def flow(line_words, src, bpm, beats, grid=0.25, lock=0.75, pickup=0.0, squeeze=(0.85, 1.12)):
    """단어 시작점 → 격자. 말 빠르기는 자연스러운 범위(squeeze)에서만 바꾸고, 남는 박은 숨(쉼)으로 둔다.
    각 단어 시작을 grid(16분)로 lock 만큼 당긴다. lock=1 이면 기계처럼 딱, 0.6~0.8 이 사람 래퍼에 가깝다."""
    spb = 60.0 / bpm
    total = src
    fit = (beats * spb) / max(total, 1e-3)
    scale = min(max(fit, squeeze[0]), squeeze[1])
    if total * scale > beats * spb:          # 너무 긴 줄은 다음 줄을 침범하지 않게 마디에 맞춰 줄인다
        scale = fit
    marks_src, marks_dst = [0.0], [0.0]
    last = 0.0
    for w in line_words:
        t = w["s"] * scale
        q = round((t / spb - pickup) / grid) * grid * spb + pickup * spb
        tgt = (1 - lock) * t + lock * q
        if w["s"] <= marks_src[-1] + 0.03 or tgt <= last + 0.05:
            continue
        marks_src.append(w["s"])
        marks_dst.append(tgt)
        last = tgt
    marks_src.append(total)
    marks_dst.append(max(total * scale, last + 0.1))
    return marks_src, marks_dst


def rap(voice, lines, bpm, out, start_beat=0.0, beats_per_line=4, style="confident rhythmic hip-hop rap delivery",
        lock=0.75, seed=0, lang="en", gap_beats=0.0, lead_in=0.0):
    """가사 줄들 → 한 개의 보컬 WAV(곡 박 0 기준으로 start_beat 에 놓임). 각 줄 = beats_per_line 박.
    lines 원소는 문자열 또는 {"text", "beats"}."""
    out = Path(out).resolve()
    from .layout import work_dir
    work = work_dir(out, "lines")
    work.mkdir(parents=True, exist_ok=True)
    items = [l if isinstance(l, dict) else {"text": l} for l in lines]
    raws = [work / f"raw_{i:02d}.wav" for i in range(len(items))]
    speak_many(voice, [it["text"] for it in items], raws, style=style, seed=seed)
    spb = 60.0 / bpm
    cursor = start_beat
    placed = []
    report = []
    for i, (it, rp) in enumerate(zip(items, raws)):
        y, sr = sf.read(str(rp), dtype="float32")
        if y.ndim > 1:
            y = y.mean(1)
        if sr != SR:
            y = librosa.resample(y, orig_sr=sr, target_sr=SR)
        y, _ = _trim(y, SR)
        tmp = work / f"trim_{i:02d}.wav"
        sf.write(str(tmp), y, SR)
        ws = words(tmp, lang)
        beats = it.get("beats", beats_per_line)
        ms, md = flow(ws, len(y) / SR, bpm, beats - gap_beats, lock=lock)
        z = warp(y, SR, ms, md)
        fade = int(0.006 * SR)
        z[:fade] *= np.linspace(0, 1, fade)
        z[-fade:] *= np.linspace(1, 0, fade)
        placed.append((cursor + lead_in, z))
        report.append({"line": it["text"], "start_beat": round(cursor, 3), "beats": beats,
                       "stretch": round((ms and md and md[-1] / max(ms[-1], 1e-3)) or 1, 3), "words": len(ws)})
        cursor += beats
    end = max(int((b * spb) * SR) + len(z) for b, z in placed)
    mix = np.zeros(end + SR, np.float32)
    for b, z in placed:
        s = int(b * spb * SR)
        mix[s: s + len(z)] += z
    mix = mix / (np.abs(mix).max() + 1e-9) * 0.89
    out.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(out), np.stack([mix, mix], 1), SR, subtype="PCM_24")
    meta = {"voice": voice, "voice_info": info(voice), "bpm": bpm, "start_beat": 0, "style": style, "lock": lock,
            "seed": seed, "lines": report}
    out.with_suffix(".json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    return str(out), report
