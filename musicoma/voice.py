"""보컬 — Musicoma 가 쓴 멜로디+가사를 '가수'에게 부르게 한다 (SoulX-Singer, 로컬).

곡을 생성하는 게 아니라 노래만 부른다. 목소리는 voices/<이름>/ 의 짧은 노래 샘플(10~30초)로 정한다.
복제는 본인 목소리 또는 허락받은 목소리만.

    add_voice("me", "sounds/inbox/my_singing.wav", language="English")   # 한 번 (전처리)
    sing("me", melody="E4:1 G4:.5 A4:1.5 r:1 ...", lyrics="I keep your let-+ ters by the win-+ dow",
         bpm=88, out="projects/x/vocal.wav")

가사 규칙: 공백으로 나눈 토큰 하나가 음표 하나. '+' = 앞 단어를 늘여 부르기(멜리스마).
쉼표(r)는 가사를 쓰지 않는다. 한 단어 = 한 토큰(음절로 쪼개지 않는다).
"""
import json
import math

import shutil
import subprocess
from pathlib import Path

import numpy as np
import soundfile as sf
import librosa

ROOT = Path(__file__).resolve().parent.parent
SOULX = ROOT / "third_party/soulx-singer"
PY = SOULX / ".venv/Scripts/python.exe"
VOICES = ROOT / "sounds/voices"
FPS = 50


def _run(args, cwd=SOULX):
    env = {"PYTHONPATH": str(SOULX), "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
    import os
    r = subprocess.run([str(PY)] + args, cwd=cwd, env={**os.environ, **env}, capture_output=True, stdin=subprocess.DEVNULL, text=True,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError((r.stdout[-1500:] + "\n" + r.stderr[-2500:]).strip())
    return r.stdout


def voices():
    return sorted(p.name for p in VOICES.glob("*") if (p / "prompt.json").exists())


def add_voice(name, wav, language="English", vocal_sep=False):
    """노래 샘플 → 음색 프롬프트(가사·음표 자동 전사). vocal_sep=True 면 반주 섞인 파일에서 보컬만."""
    d = VOICES / name
    d.mkdir(parents=True, exist_ok=True)
    src = d / ("source" + Path(wav).suffix)
    shutil.copy2(wav, src)
    tmp = d / "_pre"
    _run(["-m", "preprocess.pipeline", "--audio_path", str(src), "--save_dir", str(tmp), "--language", language,
          "--device", "cuda", "--vocal_sep", str(vocal_sep), "--max_merge_duration", "30000",
          "--midi_transcribe", "True"])
    jsons = sorted(tmp.rglob("*.json"), key=lambda p: p.stat().st_size, reverse=True)
    wavs = [p for p in tmp.rglob("*.wav")]
    meta = next((j for j in jsons if isinstance(json.loads(j.read_text(encoding="utf-8")), list)), None)
    if meta is None:
        raise RuntimeError(f"preprocess produced no metadata in {tmp}")
    shutil.copy2(meta, d / "prompt.json")
    vocal = next((w for w in wavs if "vocal" in w.name.lower()), None) or src
    shutil.copy2(vocal, d / ("prompt" + Path(vocal).suffix))
    (d / "voice.json").write_text(json.dumps({"name": name, "language": language, "source": str(wav)},
                                             ensure_ascii=False, indent=1), encoding="utf-8")
    return {"voice": name, "dir": str(d)}


def add_voice_aligned(name, wav, language="English", max_seconds=9.0):
    """NeMo 없이 목소리 등록 — Musicoma 의 단어 정렬(faster-whisper) + 음높이(WORLD)로 프롬프트를 만든다.
    생성된 목소리(voice_design)나 말소리 샘플도 그대로 노래하는 목소리가 된다."""
    import pyworld as pw
    from .voice_design import words as asr_words
    d = VOICES / name
    d.mkdir(parents=True, exist_ok=True)
    y, sr = sf.read(str(wav), dtype="float64")
    y = y.mean(1) if y.ndim > 1 else y
    ws = asr_words(wav, "en" if language == "English" else "zh")
    ws = [w for w in ws if w["e"] <= max_seconds] or ws[:8]
    t0, t1 = max(0.0, ws[0]["s"] - 0.2), min(len(y) / sr, ws[-1]["e"] + 0.2)
    seg = y[int(t0 * sr): int(t1 * sr)]
    sf.write(str(d / "prompt.wav"), seg.astype(np.float32), sr, subtype="PCM_16")
    f0, _ = pw.harvest(seg, sr, frame_period=1000 / FPS, f0_floor=60, f0_ceil=900)
    toks, cur = [], 0.0
    for w in ws:
        s, e = w["s"] - t0, w["e"] - t0
        word = "".join(ch for ch in w["w"] if ch.isalpha() or ch == "'")
        if not word:
            continue
        if s > cur + 0.03:
            toks.append({"word": "<SP>", "pitch": 0, "seconds": round(s - cur, 2), "type": 1})
        fz = f0[int(s * FPS): max(int(s * FPS) + 1, int(e * FPS))]
        fz = fz[fz > 0]
        pitch = int(round(69 + 12 * math.log2(np.median(fz) / 440))) if len(fz) else 0
        toks.append({"word": word, "pitch": pitch, "seconds": round(max(0.05, e - max(s, cur)), 2), "type": 2})
        cur = e
    total = len(seg) / sr
    if total > cur + 0.03:
        toks.append({"word": "<SP>", "pitch": 0, "seconds": round(total - cur, 2), "type": 1})
    n = int(round(sum(t["seconds"] for t in toks) * FPS))
    f0l = list(np.pad(f0, (0, max(0, n - len(f0))))[:n])
    req = d / "_prompt_req.json"
    req.write_text(json.dumps({"out": str(d / "prompt.json"), "language": language,
                               "time": [int(t0 * 1000), int(t1 * 1000)], "tokens": toks, "f0": f0l},
                              ensure_ascii=False), encoding="utf-8")
    _run([str(SOULX / "musicoma_prompt.py"), str(req)])
    vj = d / "voice.json"
    meta = json.loads(vj.read_text(encoding="utf-8")) if vj.exists() else {"name": name}
    meta.update({"language": language, "singing_prompt": "aligned", "source": str(wav)})
    vj.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"voice": name, "tokens": len(toks), "seconds": round(total, 2)}


def _prompt_files(name):
    d = VOICES / name
    wav = next((p for p in d.glob("prompt.*") if p.suffix in (".wav", ".mp3", ".flac")), None)
    if wav is None or not (d / "prompt.json").exists():
        raise FileNotFoundError(f"voice '{name}' not prepared (add_voice). available: {voices()}")
    return wav, d / "prompt.json"


# --------------------------------------------------------------------------- 사람처럼 부르는 음높이 곡선
def human_f0(tokens, vibrato_cents=35, vibrato_hz=5.4, vibrato_delay=0.28, glide_ms=70, drift_cents=8,
             scoop_cents=40, fall_cents=60, seed=0):
    """음표 → 자연스러운 f0 (20ms 프레임):
    - 앞 음에서 미끄러져 들어오기(포르타멘토), 짧은 아래에서 올려 잡기(스쿱)
    - 긴 음에만 늦게 시작해서 점점 깊어지는 비브라토
    - 느린 미세 흔들림(drift), 프레이즈 끝 살짝 떨어뜨리기"""
    rnd = np.random.default_rng(seed)
    f0 = []
    prev_hz = None
    for i, t in enumerate(tokens):
        n = max(1, int(round(t["seconds"] * FPS)))
        if t["pitch"] <= 0 or t["word"] == "<SP>":
            f0 += [0.0] * n
            prev_hz = None
            continue
        hz = 440.0 * 2 ** ((t["pitch"] - 69) / 12)
        cents = np.zeros(n)
        tt = np.arange(n) / FPS
        g = min(n, int(glide_ms / 1000 * FPS))
        if prev_hz and g > 1 and t["type"] != 3:
            start_c = 1200 * math.log2(prev_hz / hz)
            cents[:g] = start_c * (1 - np.sin(np.linspace(0, np.pi / 2, g)))
        elif g > 1:
            cents[:g] = -scoop_cents * (1 - np.linspace(0, 1, g)) ** 2
        if t["seconds"] > vibrato_delay + 0.15:
            ramp = np.clip((tt - vibrato_delay) / 0.3, 0, 1)
            rate = vibrato_hz * (1 + 0.05 * rnd.standard_normal())
            cents += vibrato_cents * ramp * np.sin(2 * np.pi * rate * tt + rnd.random() * 6)
        drift = np.cumsum(rnd.standard_normal(n)) * 0.6
        cents += np.clip(drift, -drift_cents, drift_cents)
        nxt = tokens[i + 1] if i + 1 < len(tokens) else None
        if (nxt is None or nxt["word"] == "<SP>") and n > 10:
            k = min(n, 8)
            cents[-k:] -= fall_cents * np.linspace(0, 1, k) ** 2
        f0 += list(hz * 2 ** (cents / 1200))
        prev_hz = hz
    return f0


def tokens_from(melody_notes, lyrics, bpm):
    """노트(박) + 가사 → 토큰(초). 노트 사이 빈틈은 <SP>."""
    words = lyrics.split()
    spb = 60.0 / bpm
    toks, t, wi, last_word = [], 0.0, 0, None
    for n in sorted(melody_notes, key=lambda n: n["start"]):
        if n["start"] > t + 1e-4:
            toks.append({"word": "<SP>", "pitch": 0, "seconds": (n["start"] - t) * spb, "type": 1})
        if wi >= len(words):
            raise ValueError(f"lyrics ran out at note {len(toks)} (notes need {len(melody_notes)} tokens)")
        w = words[wi].strip(",.!?") or words[wi]
        wi += 1
        if w in ("+", "~", "-"):
            if last_word is None:
                raise ValueError("'+' cannot start the lyrics")
            toks.append({"word": last_word, "pitch": n["pitch"], "seconds": n["length"] * spb, "type": 3})
        else:
            toks.append({"word": w, "pitch": n["pitch"], "seconds": n["length"] * spb, "type": 2})
            last_word = w
        t = n["start"] + n["length"]
    if wi < len(words):
        raise ValueError(f"{len(words) - wi} lyric tokens left over (more words than notes)")
    toks.insert(0, {"word": "<SP>", "pitch": 0, "seconds": 0.2, "type": 1})
    toks.append({"word": "<SP>", "pitch": 0, "seconds": 0.3, "type": 1})
    return toks


def sing(voice, lyrics, bpm, melody=None, notes=None, out=None, language="English", control="score",
         humanize=None, seed=0, sample_rate=48000, syllabify=True, preroll=False):
    """멜로디(표기 또는 노트) + 가사 → 보컬 WAV.
    control='score'(기본): 악보로 부름 — 가사가 또렷(SoulX 메인테이너 권장, 이슈 #33).
    control='melody': 사람같은 f0 곡선을 강제 — 긴 음 위주 발라드에서만.
    가사: 한 토큰 = 한 음표. 여러 음표에 걸친 단어는 'beau- ti- ful' 처럼 하이픈으로 음절을 나눈다.
    syllabify: 음절별 음소 배치(기본). preroll: 자음을 박 앞에 — 10-15 A/B 에서 오히려 나빠서 기본 끔.
    측정(100BPM 16분음, 3시드 평균 WER): 옛 방식 0.63 · score+단어 0.10 · score+음절 0.00 · +preroll 0.17."""
    from .arrange import melody as parse_melody
    if notes is None:
        notes, _ = parse_melody(melody, legato=1.0)
    toks = tokens_from(notes, lyrics, bpm)
    prompt_wav, prompt_json = _prompt_files(voice)
    out = (Path(out) if out else ROOT / "sounds/vocals" / f"{voice}_{abs(hash(lyrics)) % 10**6}.wav").resolve()
    from .layout import work_dir
    work = work_dir(out, "soulx")
    req = {"prompt_wav": str(prompt_wav), "prompt_json": str(prompt_json), "save_dir": str(work),
           "language": language, "control": control, "tokens": toks, "syllabify": syllabify, "preroll": preroll}
    if control == "melody":
        req["f0"] = human_f0(toks, seed=seed, **(humanize or {}))
    work.mkdir(parents=True, exist_ok=True)
    (work / "request.json").write_text(json.dumps(req, ensure_ascii=False), encoding="utf-8")
    res = json.loads(_run([str(SOULX / "musicoma_bridge.py"), str(work / "request.json")]).strip().splitlines()[-1])
    y, sr = sf.read(res["wav"], always_2d=True, dtype="float32")
    y = librosa.resample(y.T, orig_sr=sr, target_sr=sample_rate, res_type="soxr_vhq")
    # 앞에 넣은 0.2초 쉼을 잘라 박자에 맞춘다
    y = y[:, int(0.2 * sample_rate):]
    out.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(out), y.T, sample_rate, subtype="PCM_24")
    out.with_suffix(".json").write_text(json.dumps({"voice": voice, "lyrics": lyrics, "bpm": bpm, "melody": melody,
                                                    "control": control, "humanize": humanize, "seed": seed},
                                                   ensure_ascii=False, indent=1), encoding="utf-8")
    return str(out)


