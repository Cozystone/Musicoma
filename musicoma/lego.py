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


# 보컬 생성용 '가이드 전용 악기'(10-15 검증): 곡의 실제 악기가 아니라 AI 가 반응하는 것이 확인된 소리로 박자·화성만 알려 준다.
# 시티팝 곡에서 SM Drums·핑거 베이스·FM 피아노 가이드는 같은 멜로디에서도 8/8 실패, 이 조합은 4/8 성공(오류율 ≤ 0.16).
GUIDE_PALETTE = {"drums": "drums/live_room", "bass": "bass/picked", "keys": "keys/cp80"}


def guide_spec(spec, roles=None, name_suffix="-guide"):
    """곡 설계서 → 보컬 생성용 가이드 설계서(드럼·베이스·건반 파트만, 가이드 전용 악기, 이펙트·센드 없음)."""
    import copy
    roles = roles or {}
    g = copy.deepcopy(spec)
    g["name"] = spec["name"] + name_suffix
    keep = {}
    for tname, t in spec["tracks"].items():
        role = (roles.get(tname) or t.get("perform_role") or t.get("role") or "").lower()
        kind = "drums" if "drum" in role else "bass" if "bass" in role else "keys" if role in ("keys", "piano") else None
        if kind and kind not in keep.values():
            keep[tname] = kind
    g["tracks"] = {n: {"preset": GUIDE_PALETTE[k], "role": k} for n, k in keep.items()}
    g["parts"] = [p for p in spec["parts"] if p["track"] in keep and not any(x in p for x in ("audio", "vocal", "rap"))]
    g["buses"], g["events"], g["automation"] = [], [], []
    g["mix"] = {"balance": False}
    return g


def render_guide(spec, roles=None):
    """가이드 wav — 가이드 설계서를 짓고 **트랙별로 렌더해 그냥 더한다(마스터 체인 없음)**.
    10-15 측정: 같은 가이드를 곡 전체 렌더(마스터·리미터 통과)로 주면 8/8 실패, 트랙 합으로 주면 4/8 성공(오류율 ≤ 0.23)."""
    import glob
    import hashlib
    from . import arrange
    g = guide_spec(spec, roles)
    digest = hashlib.sha1(json.dumps(g, sort_keys=True, default=str).encode()).hexdigest()
    out = ROOT / "projects" / g["name"] / "guide_stems.wav"
    stamp = out.with_suffix(".sha1")
    if out.exists() and stamp.exists() and stamp.read_text() == digest:
        return out                                   # 드럼·베이스·건반 파트가 그대로면 다시 짓지 않는다(믹스·가사만 고친 재생성 — 10-15 속도)
    s, _ = arrange.build(g, render=False, log=lambda m: None)
    s.render_stems()
    mix, sr = None, 48000
    for p in glob.glob(str(Path(s.dir) / ".work" / "stems" / "*.wav")):
        y, sr = sf.read(p, dtype="float32")
        mix = y if mix is None else mix[:len(y)] + y[:len(mix)]
    mix = mix / (np.abs(mix).max() + 1e-9) * 0.8
    out = Path(s.dir) / "guide_stems.wav"
    sf.write(str(out), mix, sr, subtype="PCM_24")
    out.with_suffix(".sha1").write_text(digest)
    return out


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


_NAMES = {"C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3, "E": 4, "F": 5, "F#": 6, "Gb": 6, "G": 7, "G#": 8, "Ab": 8,
          "A": 9, "A#": 10, "Bb": 10, "B": 11}


def key_fit(path, key):
    """노래가 그 구간 조성의 음계 안에 머무는 비율(0~1). 전조 구간에서 옛 조로 부르는 테이크를 거른다(10-15 '마지막에 길을 잃음')."""
    import pyworld as pw
    tonic, _, mode = key.partition(" ")
    t = _NAMES.get(tonic, 0)
    scale = np.array([0, 2, 3, 5, 7, 8, 10] if mode.lower().startswith("min") else [0, 2, 4, 5, 7, 9, 11])
    v, sr = sf.read(str(path), dtype="float64")
    v = v.mean(1) if v.ndim > 1 else v
    f0, _ = pw.harvest(v, sr, frame_period=10, f0_floor=80, f0_ceil=1000)
    f = f0[f0 > 0]
    if len(f) < 50:
        return 0.0
    pc = np.round(69 + 12 * np.log2(f / 440)).astype(int) % 12
    return float(np.isin(pc, (scale + t) % 12).mean())


def _sim(a, b):
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))


class _Server:
    """ACE-Step 상주 프로세스(10-15 속도 개선). 모델은 한 번만 올리고 구간·테이크마다 요청만 보낸다(구간마다 23초 로드 → 0)."""

    def __init__(self, cfg, work):
        import queue
        import threading
        cfg_path = work / "server.json"
        cfg_path.write_text(json.dumps(cfg), encoding="utf-8")
        env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8", "ACESTEP_GENERATION_TIMEOUT": "3600"}
        self.err = open(work / "server.log", "a", encoding="utf-8", errors="replace")
        self.p = subprocess.Popen([str(ACE / ".venv/Scripts/python.exe"), str(ROOT / "musicoma" / "bridges" / "ace_lego.py"), "--serve", str(cfg_path)],
                                  cwd=ACE, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.err,
                                  text=True, encoding="utf-8", errors="replace", bufsize=1)
        self.q = queue.Queue()

        def pump():
            for line in self.p.stdout:
                if line.startswith("{"):
                    try:
                        self.q.put(json.loads(line))
                    except ValueError:
                        pass
            self.q.put({"exit": self.p.poll()})
        threading.Thread(target=pump, daemon=True).start()
        msg = self._next(timeout=900)
        if msg.get("init") is False or "exit" in msg:
            raise RuntimeError(f"[lego] 모델 로드 실패: {msg} (로그 {work / 'server.log'})")
        while "ready" not in msg:
            msg = self._next(timeout=900)

    def _next(self, timeout=1800):
        import queue
        try:
            msg = self.q.get(timeout=timeout)
        except queue.Empty:
            raise RuntimeError("[lego] 응답 없음(시간 초과)")
        if "exit" in msg:
            raise RuntimeError(f"[lego] 상주 프로세스 종료({msg['exit']}) — {self.err.name}")
        return msg

    def submit(self, req):
        self.p.stdin.write(json.dumps(req, ensure_ascii=False) + "\n")
        self.p.stdin.flush()

    def result(self):
        while True:
            msg = self._next()
            if "files" in msg:
                return msg["files"]

    def alive(self):
        return self.p.poll() is None

    def close(self):
        if self.err.closed:                          # 이미 닫음(직접 close 후 atexit 가 다시 부를 때)
            return
        try:
            if self.alive():
                self.p.stdin.write("quit\n")
                self.p.stdin.flush()
                self.p.wait(timeout=30)
            self.p.stdin.close()
        except Exception:
            self.p.kill()
        self.err.close()


_SERVERS = {}


def server(cfg, work):
    key = json.dumps(cfg, sort_keys=True)
    s = _SERVERS.get(key)
    if s is None or not s.alive():
        import atexit
        s = _SERVERS[key] = _Server(cfg, work)
        atexit.register(s.close)
    return s


_DEMUCS = None


def vocals_only(path, out_path):
    """demucs 보컬 분리를 이 프로세스 안에서(모델 상주). 예전엔 테이크마다 demucs 를 새로 띄워 2.8초 → 0.3초대."""
    global _DEMUCS
    import torch
    from demucs.apply import apply_model
    if _DEMUCS is None:
        from demucs.pretrained import get_model
        _DEMUCS = get_model("htdemucs").cuda().eval()
    m = _DEMUCS
    y, sr = sf.read(str(path), dtype="float32", always_2d=True)
    if y.shape[1] == 1:
        y = np.concatenate([y, y], 1)
    if sr != m.samplerate:
        y = librosa.resample(y.T, orig_sr=sr, target_sr=m.samplerate).T
    wav = torch.from_numpy(np.ascontiguousarray(y[:, :2].T)).cuda()
    ref = wav.mean(0)
    mu, sd = ref.mean(), ref.std() + 1e-8
    with torch.no_grad():
        src = apply_model(m, ((wav - mu) / sd)[None], device="cuda", shifts=1, split=True, overlap=0.25, progress=False)[0]
    v = (src[m.sources.index("vocals")] * sd + mu).cpu().numpy().T
    sf.write(str(out_path), v, m.samplerate)
    return str(Path(out_path).resolve())


def vocal_track(beat_wav, sections, bpm, key, caption, out, takes=8, lang="en", reference=None, log=print,
                pass_wer=0.2, track="vocals", guide_wav=None, min_key_fit=0.8, enough=3):
    """guide_wav: 보컬 생성에만 쓰는 '가벼운 반주'(드럼·베이스·건반만). 10-15 측정: 꽉 찬 편곡(브라스·스트링·기타)을 주면
    Lego 가 '이미 완성된 곡'으로 보고 보컬을 거의 안 얹는다(보컬 -45~-60dB) — 덜어 낸 반주에서는 노래가 나온다.
    결과 보컬은 원래 반주(beat_wav) 위치에 놓인다. 노래는 랩보다 성공률이 낮아 takes 16~20 권장.
    takes 는 '최대'다 — 통과(오류율·조성·목소리) 테이크가 enough 개 모이면 그 구간은 멈춘다. enough=0 이면 끝까지."""
    out = Path(out).resolve()
    work = work_dir(out, "lego")
    from . import voice_design as vd
    beat, sr = sf.read(str(guide_wav or beat_wav), dtype="float32")
    if beat.ndim == 1:
        beat = np.stack([beat, beat], 1)
    from .vocal_melody import synth
    beat = beat / (np.abs(beat).max() + 1e-9) * 0.8
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
        seg = beat[int(c0 * sr):int(c1 * sr)].copy()
        if sec.get("melody_notes"):
            # 가이드 멜로디는 '이 구간 안에만'. 문맥(앞뒤)에 멜로디 악기가 들리면 모델이 '악기가 노래하는 곡'으로 보고 보컬을 안 얹는다(10-15: 8/8 실패 → 5/8 성공)
            m = synth(sec["melody_notes"], bpm, sr, len(beat))[int(c0 * sr):int(c1 * sr)] * 0.35
            seg = seg + m[:, None]
            seg = seg / (np.abs(seg).max() + 1e-9) * 0.85
        sf.write(str(crop), seg, sr, subtype="PCM_24")
        req = {"tag": f"{si:02d}_{sec['name']}", "beat": str(crop), "lyrics": f"[{sec.get('tag', 'Verse')}]\n{sec['lyrics']}",
               "caption": caption, "bpm": int(round(bpm)), "key": sec.get("key", key), "start": round(a - c0, 3), "end": round(b - c0, 3),
               "seeds": list(range(1 + si * 100, 1 + si * 100 + takes)), "out_dir": str(work / f"{si:02d}_{sec['name']}"),
               "track": track, "steps": 50, "model": "acestep-v15-xl-base", "offload": True,
               "quantization": "int8_weight_only", "vocal_language": lang}
        good = [r for r in report if r["wer"] <= pass_wer]                 # 통과한 테이크만 목소리 기준으로(실패작이 참조가 되면 뒤가 전부 무음 — 10-15)
        if reference or good:
            req["reference"] = str(Path(reference or good[0]["vox"]).resolve())
        log(f"[lego] {sec['name']} {a:.1f}~{b:.1f}s · 최대 {takes} 테이크(통과 {enough}개면 멈춤)")
        srv = server({k: req[k] for k in ("model", "offload", "quantization")}, work)

        def score(f):
            y, s2 = sf.read(f["path"], dtype="float32")
            cut = Path(f["path"]).with_name("section.wav")
            sf.write(str(cut), y[int(max(0, a - c0 - 0.3) * s2):int((b - c0 + 0.3) * s2)], s2)
            vox = vocals_only(cut, cut.with_name("vocals.wav"))
            hyp = " ".join(w["w"] for w in vd.words(vox, lang))
            return {"seed": f["seed"], "wer": round(_wer(sec["lyrics"], hyp), 3),
                    "key_fit": round(key_fit(vox, sec.get("key", key)), 3),
                    "voice_sim": round(_sim(_voiceprint(vox), ref_print), 3) if ref_print is not None else None,
                    "vox": vox, "heard": hyp[:160]}

        def passes(r):
            return r["wer"] <= pass_wer and r["key_fit"] >= min_key_fit and (r["voice_sim"] is None or r["voice_sim"] >= 0.95)

        # 생성(ACE 프로세스)과 채점(이 프로세스)을 겹친다: 테이크 n 을 채점하는 동안 n+1 을 만든다. 통과가 enough 개면 멈춤
        # (10-15 Coffee Rings 기록으로 모의: 70 → 37 테이크, 고른 테이크는 같거나 동급)
        seeds = req["seeds"]
        srv.submit({**req, "seeds": [seeds[0]]})
        sent, in_flight, rows = 1, 1, []
        while in_flight:
            files = srv.result()
            in_flight -= 1
            if (not enough or sum(map(passes, rows)) < enough) and sent < len(seeds):
                srv.submit({**req, "seeds": [seeds[sent]]})
                sent += 1
                in_flight += 1
            rows += [score(f) for f in files]
        if not rows:
            raise RuntimeError(f"[lego] {sec['name']}: 생성된 테이크가 없음(요청 {work / ('req_' + req['tag'] + '.json')} 확인)")
        ok = [r for r in rows if r["wer"] <= pass_wer] or sorted(rows, key=lambda r: r["wer"])[:2]
        in_key = [r for r in ok if r["key_fit"] >= min_key_fit]
        ok = in_key or ok                                    # 조성 적합도 통과 테이크 우선
        best = max(ok, key=lambda r: (r["voice_sim"] or 0) - 0.5 * r["wer"] + 0.5 * r["key_fit"]) if ref_print is not None             else max(ok, key=lambda r: r["key_fit"] - r["wer"])
        if ref_print is None and best["wer"] <= pass_wer:     # 처음 통과한 구간의 목소리가 이후 구간의 기준
            ref_print = _voiceprint(best["vox"])
        v, s3 = sf.read(best["vox"], dtype="float32")
        if v.ndim == 1:
            v = np.stack([v, v], 1)
        if s3 != sr:
            v = librosa.resample(v.T, orig_sr=s3, target_sr=sr).T
        # 분리할 때 앞뒤 0.3초를 붙여 잘랐다 → 구간 [a-0.15, b] 만 쓰고 짧게 페이드(이음새에서 두 테이크가 겹쳐 '여러 목소리'로 들리던 문제)
        v = v[int(0.15 * sr):int((b - a + 0.3) * sr)]                    # 끝 = 구간 끝(다음 구간과 겹치지 않게)
        f_ = min(int(0.15 * sr), len(v) // 4)
        v[:f_] *= np.linspace(0, 1, f_)[:, None]
        v[-int(0.02 * sr):] *= np.linspace(1, 0, int(0.02 * sr))[:, None]
        i = int(max(0, a - 0.15) * sr)
        full[i:i + len(v)] += v[:len(full) - i]
        report.append({"section": sec["name"], "start": a, "end": b, "chosen": best["seed"], "wer": best["wer"],
                       "key_fit": best["key_fit"],
                       "voice_sim": best["voice_sim"], "vox": best["vox"], "takes": rows})
        log(f"[lego] {sec['name']}: seed {best['seed']} · 오류율 {best['wer']} · 유사도 {best['voice_sim']} · 조성 {best['key_fit']}")
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
