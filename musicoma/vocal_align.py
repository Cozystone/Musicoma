"""생성 보컬을 쓴 멜로디(줄 시작)에 맞춰 당기기 — 프로듀서가 클립을 밀고 당기는 것.

10-17 Four O'Clock: ACE lego 는 가이드 멜로디를 줘도 '언제 부를지'는 자기 마음대로라 1절이 7초, 후렴2가 13초 늦게 들어왔다(본인: "보컬 싱크가 안 맞아").
방법: 받아쓰기 단어 시각 → 가사 줄의 첫 두 단어가 들리는 시각을 찾고, 그 단어가 든 '소리 덩어리'(무음으로 나뉜 구간) 전체를
줄 시작으로 옮긴다. 늘이거나 줄이지 않는다(목소리 질감 보존). 못 찾은 덩어리는 바로 앞 덩어리와 같은 양만큼 옮긴다.
"""
import re

import numpy as np
import soundfile as sf
import librosa


def _norm(w):
    return re.sub(r"[^a-z0-9']", "", w.lower())


def _chunks(mono, sr, gap=0.3, min_len=0.2, floor_db=-38):
    """무음으로 나뉜 소리 덩어리 [(시작초, 끝초)]"""
    hop = 512
    rms = librosa.feature.rms(y=mono, frame_length=2048, hop_length=hop)[0]
    db = 20 * np.log10(rms + 1e-9)
    on = db > db.max() + floor_db
    t = librosa.frames_to_time(np.arange(len(on)), sr=sr, hop_length=hop)
    out, start = [], None
    for i, v in enumerate(on):
        if v and start is None:
            start = t[i]
        elif not v and start is not None:
            if out and t[i - 1] - out[-1][1] < 0 and False:
                pass
            out.append([start, t[i]])
            start = None
    if start is not None:
        out.append([start, t[-1]])
    merged = []
    for a, b in out:
        if merged and a - merged[-1][1] < gap:
            merged[-1][1] = b
        else:
            merged.append([a, b])
    return [(a, b) for a, b in merged if b - a >= min_len]


def align_file(path, place_s, phrases, out, lang="en", log=print):
    """path: 구간 보컬 파일(place_s 초 자리에 놓이는 것). phrases: [{"start": 절대 초, "text": 가사 한 줄}].
    out: 맞춘 파일. 반환: [(줄 번호, 이동 초)]"""
    from . import voice_design as vd
    y, sr = sf.read(str(path), dtype="float32", always_2d=True)
    mono = y.mean(1)
    chunks = _chunks(mono, sr)
    if not chunks:
        sf.write(str(out), y, sr)
        return []
    words = vd.words(path, lang)
    # 줄마다 첫 두 단어가 들리는 시각(파일 기준 초)
    hits = []
    used = 0
    for i, ph in enumerate(phrases):
        toks = [_norm(w) for w in ph["text"].split() if _norm(w)]
        found = None
        for j in range(used, len(words)):
            if _norm(words[j]["w"]) == toks[0] and (len(toks) < 2 or j + 1 >= len(words) or _norm(words[j + 1]["w"]) == toks[1]
                                                     or (j + 1 < len(words) and _norm(words[j + 1]["w"])[:3] == toks[1][:3])):
                found = words[j]["s"]
                used = j + 1
                break
        hits.append(found)
    # 줄 단위로 자른다: 찾은 줄의 첫 단어 직전(0.08초 앞, 단 바로 앞 무음 안에서)부터 다음 찾은 줄 직전까지가 그 줄의 소리.
    # 노래는 줄 사이를 쉬지 않고 이어 부르기도 해서 '무음 덩어리'로는 너무 거칠다(10-17: 후렴 전체가 한 덩어리로 4초 밀림).
    total = len(mono) / sr
    found = [(i, h) for i, h in enumerate(hits) if h is not None]
    segs = []                                   # (파일 안 시작, 끝, 이동량)
    if not found:
        sf.write(str(out), y, sr)
        return []
    first_delta = (phrases[found[0][0]]["start"] - place_s) - found[0][1]
    if found[0][1] > 0.1:                      # 첫 줄 앞에 들리는 소리(흥얼거림·숨)는 첫 줄과 같이 움직인다
        segs.append((0.0, found[0][1] - 0.08, first_delta))
    for k, (i, h) in enumerate(found):
        nxt = found[k + 1][1] - 0.08 if k + 1 < len(found) else total
        segs.append((max(0.0, h - 0.08), nxt, (phrases[i]["start"] - place_s) - h))
    end = max(b + d for a, b, d in segs)
    res = np.zeros((int(max(end, total) * sr) + sr, y.shape[1]), np.float32)
    fade = int(0.012 * sr)
    squeezed = []
    for k, (a, b, d) in enumerate(segs):
        seg = y[int(a * sr):int(b * sr)].copy()
        # 넘침: 길게 부른 줄이 다음 줄 시작을 넘으면 음높이 그대로 최대 17% 줄이고(WSOLA), 그래도 남으면 다음 줄 0.06초 앞에서 페이드아웃
        if k + 1 < len(segs):
            slot = (segs[k + 1][0] + segs[k + 1][2]) - (a + d) - 0.06
            if slot > 0.3 and len(seg) / sr > slot:
                ratio = max(slot * sr / len(seg), 1 / 1.17)
                if ratio < 0.995:
                    from .voice_design import wsola
                    seg = np.stack([wsola(seg[:, c], ratio) for c in range(seg.shape[1])], 1)
                    squeezed.append((k, round(1 / ratio, 2)))
                if len(seg) / sr > slot:
                    n_keep = int(slot * sr)
                    f2 = min(int(0.08 * sr), n_keep)
                    seg = seg[:n_keep]
                    seg[-f2:] *= np.linspace(1, 0, f2)[:, None]
        if len(seg) > 2 * fade:
            seg[:fade] *= np.linspace(0, 1, fade)[:, None]
            seg[-fade:] *= np.linspace(1, 0, fade)[:, None]
        j0 = int((a + d) * sr)
        if j0 < 0:
            seg, j0 = seg[-j0:], 0
        res[j0:j0 + len(seg)] += seg[:max(0, len(res) - j0)]
    sf.write(str(out), res, sr)
    moved = [(i, round((phrases[i]["start"] - place_s) - h, 2)) for i, h in found]
    log(f"[align] {out.name if hasattr(out, 'name') else out}: 줄 {len(found)}/{len(phrases)} 찾음 · 줄 이동(초) {moved} · 줄임 {squeezed}")
    return moved


def align_state(state_json, lang="en", log=print):
    """vocals/<이름>.json 의 구간마다(phrases 가 있는 것만) 파일을 맞추고 원본은 *_raw.wav 로 남긴다."""
    import json
    from pathlib import Path
    p = Path(state_json)
    st = json.loads(p.read_text(encoding="utf-8"))
    for sec in st["sections"]:
        if not sec.get("phrases") or not sec.get("file"):
            continue
        f = Path(sec["file"])
        raw = f.with_name(f.stem + "_raw.wav")
        if not raw.exists():
            raw.write_bytes(f.read_bytes())
        align_file(raw, float(sec["place_s"]), sec["phrases"], f, lang=lang, log=log)
    p.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")
    return st
