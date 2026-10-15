"""반주를 '듣고' 부르는 보컬 — ACE-Step 1.5 XL-base Lego(vocals). 10-15 본인: "비트를 주면 AI 가 그 위에 보이스를 올려야".

    vocal_track(beat_wav, sections, bpm, key, caption, out, takes=8)
      sections = [{"name": "verse", "start": 10.9, "end": 32.7, "lyrics": "줄\\n줄..."}, ...]   (초)
      → 곡 길이 전체 보컬 wav(보컬만) + 구간별 테이크 점수 json

구간마다
  1 앞뒤 문맥을 포함해 비트를 자른다(최대 ~44초 — 16GB 에서 빠름)
  2 Lego 로 takes 개 생성(시드만 다름). 결과는 그 구간을 비트까지 새로 그린 믹스 → demucs 로 보컬만
  3 점수: 받아쓰기 정확도(가사 대비) + 목소리 일관성(첫 구간에서 고른 목소리와의 MFCC 유사도)
  4 가장 좋은 테이크를 원래 비트 위치에 놓는다. 첫 구간의 고른 보컬을 다음 구간의 '참조 음성'으로 넣어 같은 사람으로 이어 간다
측정 기준(10-15): 가사 오류율 ≤ 0.2 를 통과선으로, 목소리 유사도는 첫 구간 대비 ≥ 0.95 권장.
"""
import difflib
import json
import os
import re
import subprocess
from pathlib import Path

import numpy as np
import soundfile as sf
import librosa

from . import crate
from .layout import work_dir

ROOT = Path(__file__).resolve().parent.parent
ACE = ROOT / "third_party" / "ace-step-15"
CONTEXT = 10.0          # 구간 앞뒤로 비트 문맥(초)
MAX_CROP = 44.0


def _wer(ref, hyp):
    r = re.findall(r"[a-z']+", ref.lower())
    h = re.findall(r"[a-z']+", hyp.lower())
    if not r:
        return 1.0
    return 1 - difflib.SequenceMatcher(None, r, h).ratio()


def _voiceprint(path):
    y, sr = librosa.load(path, sr=16000, mono=True)
    m = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=20)
    e = librosa.feature.rms(y=y)[0][: m.shape[1]]
    keep = e > np.percentile(e, 50)
    m = m[:, keep] if keep.any() else m
    return np.concatenate([m.mean(1), m.std(1)])


def _sim(a, b):
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))


def _run_lego(req, work):
    req_path = work / f"req_{req['tag']}.json"
    req_path.write_text(json.dumps(req, ensure_ascii=False), encoding="utf-8")
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8", "ACESTEP_GENERATION_TIMEOUT": "3600"}
    r = subprocess.run([str(ACE / ".venv/Scripts/python.exe"), str(ACE / "musicoma_lego.py"), str(req_path)], cwd=ACE,
                       env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    line = [l for l in r.stdout.splitlines() if l.startswith('{"files"')]
    if r.returncode != 0 or not line:
        raise RuntimeError((r.stdout[-1500:] + "\n" + r.stderr[-1500:]).strip())
    return json.loads(line[-1])["files"]


def vocal_track(beat_wav, sections, bpm, key, caption, out, takes=8, lang="en", reference=None, log=print,
                pass_wer=0.2, track="vocals", guide_wav=None):
    """guide_wav: 보컬 생성에만 쓰는 '가벼운 반주'(드럼·베이스·건반만). 10-15 측정: 꽉 찬 편곡(브라스·스트링·기타)을 주면
    Lego 가 '이미 완성된 곡'으로 보고 보컬을 거의 안 얹는다(보컬 -45~-60dB) — 덜어 낸 반주에서는 노래가 나온다.
    결과 보컬은 원래 반주(beat_wav) 위치에 놓인다. 노래는 랩보다 성공률이 낮아 takes 16~20 권장."""
    out = Path(out).resolve()
    work = work_dir(out, "lego")
    from . import voice_design as vd
    beat, sr = sf.read(str(guide_wav or beat_wav), dtype="float32")
    if beat.ndim == 1:
        beat = np.stack([beat, beat], 1)
    full = np.zeros_like(beat)
    ref_print = _voiceprint(reference) if reference else None
    report = []
    for si, sec in enumerate(sections):
        a, b = float(sec["start"]), float(sec["end"])
        c0 = max(0.0, a - CONTEXT)
        c1 = min(len(beat) / sr, max(b + CONTEXT, c0 + 20.0), c0 + MAX_CROP)
        if b > c1:                                   # 구간이 길면 문맥을 줄인다
            c0, c1 = max(0.0, a - 2.0), min(len(beat) / sr, b + 2.0)
        crop = work / f"{si:02d}_{sec['name']}_beat.wav"
        sf.write(str(crop), beat[int(c0 * sr):int(c1 * sr)], sr, subtype="PCM_24")
        req = {"tag": f"{si:02d}_{sec['name']}", "beat": str(crop), "lyrics": f"[{sec.get('tag', 'Verse')}]\n{sec['lyrics']}",
               "caption": caption, "bpm": int(round(bpm)), "key": key, "start": round(a - c0, 3), "end": round(b - c0, 3),
               "seeds": list(range(1 + si * 100, 1 + si * 100 + takes)), "out_dir": str(work / f"{si:02d}_{sec['name']}"),
               "track": track, "steps": 50, "model": "acestep-v15-xl-base", "offload": True,
               "quantization": "int8_weight_only", "vocal_language": lang}
        if ref_print is not None and (reference or report):
            req["reference"] = str(Path(reference or report[0]["vox"]).resolve())
        log(f"[lego] {sec['name']} {a:.1f}~{b:.1f}s · 테이크 {takes}")
        files = _run_lego(req, work)
        rows = []
        for f in files:
            y, s2 = sf.read(f["path"], dtype="float32")
            cut = Path(f["path"]).with_name("section.wav")
            sf.write(str(cut), y[int(max(0, a - c0 - 0.3) * s2):int((b - c0 + 0.3) * s2)], s2)
            st = crate.separate(str(cut), folder=str(Path(f["path"]).parent / "sep"))
            st = {k: str(Path(v).resolve()) for k, v in st.items()}
            hyp = " ".join(w["w"] for w in vd.words(st["vocals"], lang))
            vp = _voiceprint(st["vocals"])
            rows.append({"seed": f["seed"], "wer": round(_wer(sec["lyrics"], hyp), 3),
                         "voice_sim": round(_sim(vp, ref_print), 3) if ref_print is not None else None,
                         "vox": st["vocals"], "heard": hyp[:160]})
        if not rows:
            raise RuntimeError(f"[lego] {sec['name']}: 생성된 테이크가 없음(요청 {work / ('req_' + req['tag'] + '.json')} 확인)")
        ok = [r for r in rows if r["wer"] <= pass_wer] or sorted(rows, key=lambda r: r["wer"])[:2]
        best = max(ok, key=lambda r: (r["voice_sim"] or 0) - 0.5 * r["wer"]) if ref_print is not None else min(ok, key=lambda r: r["wer"])
        if ref_print is None:                        # 첫 구간에서 고른 목소리가 이후 구간의 기준
            ref_print = _voiceprint(best["vox"])
        v, s3 = sf.read(best["vox"], dtype="float32")
        if v.ndim == 1:
            v = np.stack([v, v], 1)
        if s3 != sr:
            v = librosa.resample(v.T, orig_sr=s3, target_sr=sr).T
        f_ = int(0.03 * sr)
        v[:f_] *= np.linspace(0, 1, f_)[:, None]
        v[-f_:] *= np.linspace(1, 0, f_)[:, None]
        i = int(max(0, a - 0.3) * sr)
        full[i:i + len(v)] += v[:len(full) - i]
        report.append({"section": sec["name"], "start": a, "end": b, "chosen": best["seed"], "wer": best["wer"],
                       "voice_sim": best["voice_sim"], "vox": best["vox"], "takes": rows})
        log(f"[lego] {sec['name']}: seed {best['seed']} · 오류율 {best['wer']} · 유사도 {best['voice_sim']}")
    try:
        sf.write(str(out), full, sr, subtype="PCM_24")
    except Exception:                                # 엔진이 이전 파일을 열고 있으면 새 이름으로(10-15 잠금 사고)
        import time
        out = out.with_name(f"{out.stem}_{time.strftime('%H%M%S')}{out.suffix}")
        sf.write(str(out), full, sr, subtype="PCM_24")
    out.with_suffix(".json").write_text(json.dumps({"engine": "ACE-Step 1.5 xl-base lego + demucs", "caption": caption,
                                                    "bpm": bpm, "key": key, "sections": report}, ensure_ascii=False,
                                                   indent=1), encoding="utf-8")
    return str(out), report
