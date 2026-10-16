"""노래 경로 2 — 또렷한 말소리를 음표에 맞추고(가이드) 노래 음색으로 바꾼다. 한국어·빠른 음에 강하다.

    sing_svc("gen-singer-b", "오늘 밤 도시의 불빛이 나를 부르네", melody="...", bpm=86, out=..., lang="ko")

1 가이드 말소리 : 생성 목소리(VoxCPM2)가 가사를 또박또박 말한다(목소리 = voice_design 의 그 사람)
2 음절 나누기  : 단어 시각(faster-whisper) 안에서 에너지 골짜기로 음절 경계를 찾는다
3 음표에 맞추기: 음절마다 자음 앞부분은 그대로, 모음을 늘이거나 줄여 음표 길이에 정확히(자체 WSOLA)
4 목표 음높이 : 악보 → 사람 같은 f0(voice.human_f0), 자음(무성) 구간은 0
5 SVC         : SoulX-Singer-SVC(Apache-2.0)가 가이드의 발음 + 목표 f0 + 그 사람 음색으로 노래

가사 규칙: 한 음표 = 한 음절. 한국어는 글자 하나가 한 음절('사랑해' = 3음표). 영어는 'ev- ery ci- ty' 처럼 하이픈.
'+' = 앞 음절을 이어 부름(멜리스마). 쉼표(r)는 가사 없음.
"""
import json
import os
import re
import subprocess
from pathlib import Path

import numpy as np
import soundfile as sf
import librosa

from . import voice as voice_mod
from . import voice_design as vd

ROOT = Path(__file__).resolve().parent.parent
SOULX = ROOT / "third_party/soulx-singer"
SR = 24000           # SVC 가 쓰는 샘플레이트
FPS = 50

_HANGUL = re.compile(r"[가-힣]")


def syllable_tokens(lyrics, lang):
    """가사 → 음표당 토큰 목록 + 단어 묶음. 반환: tokens(['오','늘','+',...]), words([[토큰 인덱스...], ...])."""
    toks, words = [], []
    for w in lyrics.split():
        if w == "+":
            toks.append("+")
            continue
        if lang == "ko" and _HANGUL.search(w):
            idx = []
            for ch in w:
                if _HANGUL.match(ch):
                    idx.append(len(toks))
                    toks.append(ch)
            if idx:
                words.append(idx)
        else:
            if words and toks and toks[-1].endswith("-") and words[-1] and words[-1][-1] == len(toks) - 1:
                words[-1].append(len(toks))
            else:
                words.append([len(toks)])
            toks.append(w)
    return toks, words


def _word_text(toks, idx, lang):
    return "".join(toks[i].rstrip("-") for i in idx) if lang == "ko" else "".join(toks[i].rstrip("-") for i in idx)


def _split_word(y, sr, a, b, n):
    """단어 구간 [a,b](초)를 n 음절로 — 등분점 근처(±35%)의 에너지 골짜기."""
    if n <= 1:
        return [a, b]
    seg = y[int(a * sr): int(b * sr)]
    hop = int(0.005 * sr)
    rms = librosa.feature.rms(y=seg, frame_length=hop * 4, hop_length=hop)[0] if len(seg) > hop * 4 else np.ones(1)
    marks = [a]
    L = b - a
    for k in range(1, n):
        c = a + L * k / n
        lo, hi = c - 0.35 * L / n, c + 0.35 * L / n
        f0, f1 = int((lo - a) / 0.005), int((hi - a) / 0.005)
        f0, f1 = max(0, f0), min(len(rms) - 1, f1)
        if f1 > f0:
            m = f0 + int(np.argmin(rms[f0:f1]))
            c = a + m * 0.005
        marks.append(max(marks[-1] + 0.03, c))
    marks.append(b)
    return marks


def _fit(seg, sr, want, onset=0.06):
    """음절 하나를 want 초로: 앞 onset(자음)은 그대로, 나머지(모음)만 늘이고 줄인다."""
    n_want = int(round(want * sr))
    if n_want <= 0:
        return np.zeros(0, np.float32)
    if len(seg) < 64:
        return np.zeros(n_want, np.float32)
    head = min(int(onset * sr), int(0.35 * len(seg)), int(0.5 * n_want))
    body = seg[head:]
    rest = n_want - head
    if rest <= 0:
        out = vd.wsola(seg, n_want / len(seg))
    else:
        out = np.concatenate([seg[:head], vd.wsola(body, rest / max(1, len(body)))])
    out = librosa.util.fix_length(out.astype(np.float32), size=n_want)
    f = min(len(out) // 4, int(0.004 * sr))
    if f > 1:
        out[:f] *= np.linspace(0, 1, f)
        out[-f:] *= np.linspace(1, 0, f)
    return out


def guide(voice, lyrics, notes, bpm, work, lang="ko", style="speaking slowly and very clearly, every syllable distinct", seed=0):
    """가이드 보컬(말소리를 음표 길이에 맞춘 것) + 음표별 토큰(초) 반환."""
    toks, words = syllable_tokens(lyrics, lang)
    notes = sorted(notes, key=lambda n: n["start"])
    if len(toks) != len(notes):
        raise ValueError(f"음절 {len(toks)}개 ≠ 음표 {len(notes)}개 — 한 음표 = 한 음절(+ 는 이어 부르기)")
    text = " ".join(_word_text(toks, w, lang) for w in words)
    raw = work / "guide_raw.wav"
    vd.speak(voice, text, raw, style=style, seed=seed)
    y, sr = sf.read(str(raw), dtype="float32")
    y = y.mean(1) if y.ndim > 1 else y
    y = librosa.resample(y, orig_sr=sr, target_sr=SR)
    y, off = vd._trim(y, SR)
    sf.write(str(work / "guide_trim.wav"), y, SR)
    ws = vd.words(work / "guide_trim.wav", lang)
    # 단어 시각: ASR 단어 수가 우리 단어 수와 같으면 그대로, 아니면 전체를 글자 수 비례로
    if len(ws) == len(words):
        spans = [(w["s"], w["e"]) for w in ws]
    else:
        total = len(y) / SR
        counts = [len(w) for w in words]
        acc, spans = 0.0, []
        for c in counts:
            d = total * c / sum(counts)
            spans.append((acc, acc + d))
            acc += d
    syl = {}                                            # 토큰 인덱스 → (a, b) 초
    for (a, b), idx in zip(spans, words):
        m = _split_word(y, SR, a, b, len(idx))
        for k, ti in enumerate(idx):
            syl[ti] = (m[k], m[k + 1])
    spb = 60.0 / bpm
    out = np.zeros(int((notes[-1]["start"] + notes[-1]["length"]) * spb * SR) + SR, np.float32)
    tokens, t_prev = [], 0.0
    for i, (tok, n) in enumerate(zip(toks, notes)):
        st, ln = n["start"] * spb, n["length"] * spb
        if st > t_prev + 1e-4:
            tokens.append({"word": "<SP>", "pitch": 0, "seconds": st - t_prev, "type": 1})
        if tok == "+":                                  # 이어 부르기: 앞 음절의 끝(모음)을 늘여 이어 붙임
            j = i - 1
            while j >= 0 and toks[j] == "+":
                j -= 1
            a, b = syl.get(j, (0, 0.1))
            seg = y[int((a + (b - a) * 0.6) * SR): int(b * SR)]
            tokens.append({"word": "+", "pitch": n["pitch"], "seconds": ln, "type": 3})
        else:
            a, b = syl[i]
            seg = y[int(a * SR): int(b * SR)]
            tokens.append({"word": tok, "pitch": n["pitch"], "seconds": ln, "type": 2})
        z = _fit(seg, SR, ln, onset=0.0 if tok == "+" else 0.06)
        s0 = int(st * SR)
        out[s0: s0 + len(z)] += z[: max(0, len(out) - s0)]
        t_prev = st + ln
    out = out[: int(t_prev * SR) + int(0.2 * SR)]
    gpath = work / "guide.wav"
    sf.write(str(gpath), out / (np.abs(out).max() + 1e-9) * 0.9, SR, subtype="PCM_16")
    return gpath, tokens


def _fill_short_gaps(f0, max_frames=8):
    """짧은 무성 구간(자음)은 앞뒤 음높이로 이어 준다 — SVC 는 끊긴 f0 보다 이어진 곡선에서 발음이 또렷했다(10-15 A/B)."""
    f0 = f0.copy()
    z = np.where(f0 <= 0)[0]
    if not len(z):
        return f0
    for r in np.split(z, np.where(np.diff(z) != 1)[0] + 1):
        if len(r) and len(r) <= max_frames and r[0] > 0 and r[-1] < len(f0) - 1:
            f0[r] = np.linspace(f0[r[0] - 1], f0[r[-1] + 1], len(r))
    return f0


def score_take(path, lyrics, lang):
    """테이크 점수 = 받아쓰기 오류율(낮을수록 또렷). 한국어는 글자, 영어는 단어 단위."""
    import difflib
    hyp = " ".join(w["w"] for w in vd.words(path, lang))
    if lang == "ko":
        ref = "".join(ch for ch in lyrics if _HANGUL.match(ch))
        h = "".join(ch for ch in hyp if _HANGUL.match(ch))
        return 1 - difflib.SequenceMatcher(None, ref, h).ratio(), hyp
    r = re.findall(r"[a-z']+", lyrics.replace("- ", "").replace("+", "").lower())
    h = re.findall(r"[a-z']+", hyp.lower())
    return 1 - difflib.SequenceMatcher(None, r, h).ratio(), hyp


def sing_svc(voice, lyrics, bpm, melody=None, notes=None, out=None, lang="ko", seed=0, humanize=None,
             n_steps=32, cfg=5.0, sample_rate=48000, takes=3, prosody=0.0):
    """takes 개를 불러 받아쓰기로 가장 또렷한 것을 고른다(녹음실의 테이크 고르기). 점수는 .json 에 남긴다."""
    import pyworld as pw
    from .arrange import melody as parse_melody
    if notes is None:
        notes, _ = parse_melody(melody, legato=1.0)
    out = Path(out).resolve()
    from .layout import work_dir
    work = work_dir(out, "svc")
    work.mkdir(parents=True, exist_ok=True)
    gpath, tokens = guide(voice, lyrics, notes, bpm, work, lang=lang, seed=seed)
    # 목표 f0: 악보 → 사람 같은 곡선. 자음(가이드가 무성인 곳)은 0 으로 두어 발음을 지킨다
    f0 = np.array(voice_mod.human_f0(tokens, seed=seed, **(humanize or {})), dtype=np.float64)
    g, _ = sf.read(str(gpath), dtype="float64")
    gf0, _ = pw.harvest(g, SR, frame_period=1000 / FPS, f0_floor=60, f0_ceil=900)
    n = int(np.ceil(len(g) / (SR / FPS)))
    f0 = np.pad(f0, (0, max(0, n - len(f0))))[:n]
    gf0 = np.pad(gf0, (0, max(0, n - len(gf0))))[:n]
    if prosody > 0:
        # 말소리의 잔 억양(0.3초 이동 중앙값 대비 굴곡)을 악보 음높이에 섞는다 — 악보만 따르면 오토튠처럼 들림
        from scipy.ndimage import median_filter
        lg = np.where(gf0 > 0, np.log(np.maximum(gf0, 1e-3)), np.nan)
        base = np.copy(lg)
        idx = np.where(~np.isnan(lg))[0]
        if len(idx) > 5:
            base[np.isnan(base)] = np.interp(np.where(np.isnan(base))[0], idx, lg[idx])
            dev = lg - median_filter(base, size=15)
            dev = np.nan_to_num(dev)
            ok = (f0 > 0) & (gf0 > 0)
            f0[ok] = f0[ok] * np.exp(prosody * np.clip(dev[ok], -0.35, 0.35))
    f0[gf0 <= 0] = 0.0
    f0 = _fill_short_gaps(f0)
    prompt = vd.VOICES / voice / "design.wav"
    env = {**os.environ, "PYTHONPATH": str(SOULX), "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
    results = []
    for k in range(max(1, takes)):
        d = work / f"take{k + 1}"
        d.mkdir(exist_ok=True)
        req = {"prompt_wav": str(prompt), "target_wav": str(gpath), "target_f0": [float(x) for x in f0],
               "save_dir": str(d), "n_steps": n_steps, "cfg": cfg}
        (d / "svc_request.json").write_text(json.dumps(req), encoding="utf-8")
        r = subprocess.run([str(SOULX / ".venv/Scripts/python.exe"), str(SOULX / "musicoma_svc.py"), str(d / "svc_request.json")],
                           cwd=SOULX, env=env, capture_output=True, stdin=subprocess.DEVNULL, text=True, encoding="utf-8", errors="replace")
        if r.returncode != 0:
            raise RuntimeError((r.stdout[-1500:] + "\n" + r.stderr[-2500:]).strip())
        wav = json.loads(r.stdout.strip().splitlines()[-1])["wav"]
        err, hyp = score_take(wav, lyrics, lang) if takes > 1 else (None, "")
        results.append({"take": k + 1, "wav": wav, "error": None if err is None else round(err, 3), "heard": hyp})
    best = min(results, key=lambda r: r["error"] if r["error"] is not None else 0)
    y, sr = sf.read(best["wav"], dtype="float32", always_2d=True)
    y = librosa.resample(y.T, orig_sr=sr, target_sr=sample_rate, res_type="soxr_vhq")
    sf.write(str(out), y.T if y.ndim > 1 else y, sample_rate, subtype="PCM_24")
    out.with_suffix(".json").write_text(json.dumps({"engine": "svc", "voice": voice, "lyrics": lyrics, "bpm": bpm,
                                                    "melody": melody, "lang": lang, "seed": seed, "cfg": cfg,
                                                    "takes": results, "chosen": best["take"]}, ensure_ascii=False,
                                                   indent=1), encoding="utf-8")
    return str(out)
