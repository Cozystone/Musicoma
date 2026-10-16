"""크레이트 — 샘플(원곡) 다루기: 분석, 배속(칩멍크), 루프 자르기, 찹, 늙히기, SFZ 킷.

모든 함수는 새 WAV 를 만들고 경로를 돌려준다. 원본은 건드리지 않는다.
결과는 sounds/crate/<이름>/ 아래에 쌓이고, 각 파일 옆에 .json 메모(무엇을 어떻게)가 붙는다.
"""
import json
import math
from pathlib import Path

import numpy as np
import soundfile as sf
import librosa

ROOT = Path(__file__).resolve().parent.parent
CRATE = ROOT / "sounds/crate"
SR = 48000

KEYS = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]
_MAJ = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
_MIN = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])


def _load(path, sr=SR):
    y, s = sf.read(str(path), always_2d=True, dtype="float32")
    y = y.T
    if y.shape[0] == 1:
        y = np.vstack([y, y])
    y = y[:2]
    if s != sr:
        y = librosa.resample(y, orig_sr=s, target_sr=sr, res_type="soxr_hq")
    return y, sr


def _writable(out):
    """엔진이 쓰고 있는(잠긴) 파일이면 _2, _3 … 새 이름."""
    out = Path(out)
    k = 2
    while out.exists():
        try:
            out.unlink()
            break
        except PermissionError:
            out = out.with_name(f"{out.stem.rsplit('__', 1)[0]}__{k}{out.suffix}")
            k += 1
    return out


def _save(y, sr, out, note=None):
    out = _writable(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    peak = np.abs(y).max()
    if peak > 0.999:
        y = y * (0.999 / peak)
    sf.write(str(out), y.T, sr, subtype="PCM_24")
    if note is not None:
        out.with_suffix(".json").write_text(json.dumps(note, ensure_ascii=False, indent=1), encoding="utf-8")
    return str(out)


def source_name(path):
    """crate 폴더 이름: 생성물은 '<slug>_<stamp>', 그 밖은 파일 이름."""
    p = Path(path)
    if CRATE in p.parents:
        return p.relative_to(CRATE).parts[0]
    return f"{p.parent.name}_{p.stem}" if p.parent.name and "generated" in p.parts else p.stem


def _out(path, suffix, folder=None):
    p = Path(path)
    d = Path(folder) if folder else (p.parent if CRATE in p.parents else CRATE / source_name(p))
    return d / f"{p.stem}{suffix}.wav"


def _fade(y, sr, fin=0.003, fout=0.008):
    n_in, n_out = int(fin * sr), int(fout * sr)
    if n_in:
        y[:, :n_in] *= np.linspace(0, 1, n_in)
    if n_out:
        y[:, -n_out:] *= np.linspace(1, 0, n_out)
    return y


# ---------------------------------------------------------------------------
def analyze(path):
    """템포·키·길이·박 위치·추천 루프 지점."""
    y, sr = _load(path, 22050)
    mono = y.mean(axis=0)
    tempo, beats = librosa.beat.beat_track(y=mono, sr=sr, units="time")
    tempo = float(np.atleast_1d(tempo)[0])
    chroma = librosa.feature.chroma_cqt(y=mono, sr=sr).mean(axis=1)
    best = max(((np.corrcoef(chroma, np.roll(p, i))[0, 1], f"{KEYS[i]} {m}")
                for i in range(12) for m, p in (("major", _MAJ), ("minor", _MIN))))
    rms = librosa.feature.rms(y=mono)[0]
    # 4박 단위로 에너지가 안정된 구간 = 루프 후보
    bars = []
    for i in range(0, max(0, len(beats) - 4), 4):
        a, b = beats[i], beats[i + 4] if i + 4 < len(beats) else beats[-1]
        fa, fb = librosa.time_to_frames([a, b], sr=sr)
        bars.append({"bar": i // 4, "start": round(float(a), 3), "end": round(float(b), 3),
                     "energy": round(float(rms[fa:fb].mean()) if fb > fa else 0.0, 4)})
    return {
        "path": str(path), "seconds": round(len(mono) / sr, 2), "bpm": round(tempo, 2),
        "key": best[1], "key_confidence": round(float(best[0]), 2),
        "beats": [round(float(b), 3) for b in beats[:64]], "bars": bars[:48],
        "beats_all": [round(float(b), 3) for b in beats], "downbeat_phase": _downbeat_phase(mono, sr, beats),
    }


def _downbeat_phase(mono, sr, beats):
    """박 4개 중 어느 것이 마디 첫 박인지 — 저역(킥) 타격이 가장 센 위상."""
    if len(beats) < 8:
        return 0
    low = librosa.onset.onset_strength(y=mono, sr=sr, fmax=200, n_mels=32)
    fr = librosa.time_to_frames(beats, sr=sr)
    fr = np.clip(fr, 0, len(low) - 1)
    return int(np.argmax([low[fr[p::4]].mean() for p in range(4)]))


def varispeed(path, semitones=None, ratio=None, out=None):
    """테이프식 배속: 빨라지면 음도 올라간다(칩멍크 소울의 핵심). 반음 또는 배율."""
    if ratio is None:
        ratio = 2 ** ((semitones or 0) / 12)
    y, sr = _load(path)
    # sr*ratio 로 재생한 것과 같다 = sr/ratio 로 리샘플 후 sr 로 재생
    z = librosa.resample(y, orig_sr=sr, target_sr=sr / ratio, res_type="soxr_vhq")
    out = out or _out(path, f"_vari{12 * math.log2(ratio):+.2f}st")
    return _save(z, sr, out, {"op": "varispeed", "source": str(path), "ratio": ratio,
                              "semitones": round(12 * math.log2(ratio), 3)})


def stretch(path, rate=None, target_bpm=None, source_bpm=None, semitones=0.0, out=None):
    """음정 유지하고 템포만(또는 템포 유지하고 음정만) — 위상 보코더(musicoma.dsp, pedalboard 없이 10-16)."""
    from . import dsp
    if rate is None:
        rate = (target_bpm / source_bpm) if target_bpm and source_bpm else 1.0
    y, sr = _load(path)
    z = dsp.time_stretch(y.T, sr, rate=rate, semitones=semitones).T
    out = out or _out(path, f"_x{rate:.3f}_{semitones:+.1f}st")
    return _save(z, sr, out, {"op": "stretch", "source": str(path), "rate": rate, "semitones": semitones})


def cut(path, start, end, out=None, fade=True):
    """초 단위 구간 잘라내기."""
    y, sr = _load(path)
    seg = y[:, int(start * sr): int(end * sr)].copy()
    if fade:
        seg = _fade(seg, sr)
    out = out or _out(path, f"_cut{start:.2f}-{end:.2f}")
    return _save(seg, sr, out, {"op": "cut", "source": str(path), "start": start, "end": end})


def loop(path, bars=2, start=None, bar_index=None, target_bpm=None, beats_per_bar=4, out=None):
    """박 검출로 마디 경계에 맞춰 루프를 잘라 target_bpm 에 딱 맞는 길이로 만든다.

    target_bpm 을 주면 '배속'(음정 같이 변함)으로 맞춘다 — 칩멍크 소울 방식.
    음정을 지키고 싶으면 stretch() 를 따로 쓴다.
    """
    info = analyze(path)
    beats = info["beats"]
    if start is None:
        bi = (bar_index or 0) * beats_per_bar
        if bi + bars * beats_per_bar >= len(beats):
            raise ValueError(f"not enough detected beats for {bars} bars from bar {bar_index}")
        start, end = beats[bi], beats[bi + bars * beats_per_bar]
    else:
        end = start + bars * beats_per_bar * 60 / info["bpm"]
    y, sr = _load(path)
    seg = y[:, int(start * sr): int(end * sr)].copy()
    src_len = seg.shape[1] / sr
    note = {"op": "loop", "source": str(path), "start": start, "end": end, "bars": bars,
            "source_bpm_est": info["bpm"]}
    if target_bpm:
        want = bars * beats_per_bar * 60 / target_bpm
        ratio = src_len / want
        seg = librosa.resample(seg, orig_sr=sr, target_sr=sr / ratio, res_type="soxr_vhq")
        seg = seg[:, : int(round(want * sr))]
        note.update({"target_bpm": target_bpm, "varispeed_ratio": round(ratio, 4),
                     "semitones": round(12 * math.log2(ratio), 2)})
    seg = _fade(seg, sr, 0.002, 0.004)
    out = _save(seg, sr, out or _out(path, f"_loop{bars}bar" + (f"_{target_bpm}bpm" if target_bpm else "")), note)
    return {"path": out, **note}


def loop_region(path, start, end, bars, target_bpm, beats_per_bar=4, out=None, tag="loop"):
    """정해진 구간(초)을 target_bpm 의 bars 마디 길이에 맞춰 배속. 여러 스템에 같은 구간을 쓸 때."""
    y, sr = _load(path)
    seg = y[:, int(start * sr): int(end * sr)].copy()
    want = bars * beats_per_bar * 60 / target_bpm
    ratio = (seg.shape[1] / sr) / want
    seg = librosa.resample(seg, orig_sr=sr, target_sr=sr / ratio, res_type="soxr_vhq")[:, : int(round(want * sr))]
    seg = _fade(seg, sr, 0.002, 0.004)
    note = {"op": "loop_region", "source": str(path), "start": start, "end": end, "bars": bars,
            "target_bpm": target_bpm, "varispeed_ratio": round(ratio, 4), "semitones": round(12 * math.log2(ratio), 2)}
    out = _save(seg, sr, out or _out(path, f"_{tag}{bars}bar_{target_bpm}bpm"), note)
    return {"path": out, **note}


def mix_files(paths, out, gains_db=None):
    """여러 WAV 를 하나로 (스템 재조합: 예 vocals+other = 드럼·베이스 뺀 샘플)."""
    ys = [_load(p)[0] for p in paths]
    n = max(y.shape[1] for y in ys)
    acc = np.zeros((2, n), dtype=np.float32)
    for i, y in enumerate(ys):
        g = 10 ** ((gains_db[i] if gains_db else 0) / 20)
        acc[:, : y.shape[1]] += y * g
    return _save(acc, SR, out, {"op": "mix", "sources": [str(p) for p in paths], "gains_db": gains_db})


def best_bars(path, bars=4, bpm=None, beats=None, phase=0):
    """보컬 에너지가 가장 크고 고른 bars 마디 구간(초) — 루프 후보 1순위. phase = 마디 첫 박 위상."""
    info = analyze(path) if beats is None else None
    beats = beats if beats is not None else info["beats_all"]
    y, sr = _load(path, 22050)
    rms = librosa.feature.rms(y=y.mean(axis=0))[0]
    span = bars * 4
    best = None
    for i in range(phase, len(beats) - span, 4):
        a, b = beats[i], beats[i + span]
        fa, fb = librosa.time_to_frames([a, b], sr=sr)
        seg = rms[fa:fb]
        if len(seg) == 0:
            continue
        score = seg.mean() - 0.5 * seg.std()          # 크고 고른 구간
        if best is None or score > best[0]:
            best = (float(score), float(a), float(b), i // 4)
    if best is None:
        raise ValueError("not enough beats")
    return {"start": best[1], "end": best[2], "bar": best[3], "score": round(best[0], 4)}


def chop(path, mode="onsets", n=16, min_len=0.12, max_len=2.0, folder=None, start=0.0, end=None):
    """찹: onsets(타격 지점) / beats(박) / even(n등분). 각 조각 WAV + 목록."""
    y, sr = _load(path)
    y = y[:, int(start * sr): int(end * sr) if end else None]
    mono = y.mean(axis=0)
    length = len(mono) / sr
    if mode == "even":
        points = list(np.linspace(0, length, n + 1)[:-1])
    elif mode == "beats":
        _, b = librosa.beat.beat_track(y=mono, sr=sr, units="time")
        points = [0.0] + [float(t) for t in b]
    else:
        o = librosa.onset.onset_detect(y=mono, sr=sr, units="time", backtrack=True, delta=0.08)
        points = [0.0] + [float(t) for t in o]
    points = sorted(set(round(p, 4) for p in points if p < length - min_len))
    # 너무 가까운 지점 합치기
    merged = []
    for p in points:
        if not merged or p - merged[-1] >= min_len:
            merged.append(p)
    # 에너지 큰 순으로 n개 고르되 시간순 정렬
    slices = []
    for i, s in enumerate(merged):
        e = min(merged[i + 1] if i + 1 < len(merged) else length, s + max_len)
        seg = y[:, int(s * sr): int(e * sr)]
        if seg.shape[1] < int(min_len * sr):
            continue
        slices.append((float(np.sqrt((seg ** 2).mean())), s, e))
    slices = sorted(sorted(slices, reverse=True)[:n], key=lambda x: x[1])
    folder = Path(folder) if folder else CRATE / source_name(path) / f"chops_{Path(path).stem}_{mode}"
    out = []
    for k, (energy, s, e) in enumerate(slices):
        seg = _fade(y[:, int(s * sr): int(e * sr)].copy(), sr, 0.002, 0.01)
        f = _save(seg, sr, folder / f"{k:02d}.wav")
        out.append({"slot": k, "path": f, "start": round(start + s, 3), "end": round(start + e, 3),
                    "seconds": round(e - s, 3), "rms": round(energy, 4)})
    (folder / "chops.json").write_text(json.dumps({"source": str(path), "mode": mode, "chops": out},
                                                  ensure_ascii=False, indent=1), encoding="utf-8")
    return out


def make_kit(chops, out_sfz, base_note=36, one_shot=True, names=None, choke=False):
    """찹 → SFZ 킷 (패드처럼 노트 하나에 조각 하나). SfzPlugin 에 바로 로드."""
    out_sfz = Path(out_sfz)
    out_sfz.parent.mkdir(parents=True, exist_ok=True)
    lines = ["// Musicoma chop kit", "<control>", f"default_path={out_sfz.parent.as_posix()}/", "", "<global>",
             "ampeg_attack=0.001", "ampeg_release=0.03" if one_shot else "ampeg_release=0.25"]
    if one_shot:
        lines.append("loop_mode=one_shot")
    if choke:
        lines += ["group=1", "off_by=1", "off_mode=fast"]
    mapping = {}
    for i, c in enumerate(chops):
        p = Path(c["path"] if isinstance(c, dict) else c)
        key = base_note + i
        rel = Path(p).resolve().relative_to(out_sfz.parent.resolve()).as_posix() if out_sfz.parent.resolve() in Path(p).resolve().parents else Path(p).resolve().as_posix()
        lines += ["", "<region>", f"sample={rel}", f"key={key}", "pitch_keycenter=" + str(key)]
        mapping[(names[i] if names and i < len(names) else f"chop{i:02d}")] = key
    out_sfz.write_text("\n".join(lines) + "\n", encoding="utf-8")
    (out_sfz.with_suffix(".json")).write_text(json.dumps({"kit": mapping}, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"sfz": str(out_sfz), "kit": mapping}


def make_instrument(path, out_sfz, root_note=60, low=24, high=108, loop=False):
    """한 음(조각)을 건반 전체에 펼친 SFZ (음정 따라 배속 = 칩멍크식 연주)."""
    out_sfz = Path(out_sfz)
    out_sfz.parent.mkdir(parents=True, exist_ok=True)
    p = Path(path).resolve().as_posix()
    body = ["<global>", "ampeg_attack=0.002", "ampeg_release=0.2", "<region>", f"sample={p}",
            f"lokey={low}", f"hikey={high}", f"pitch_keycenter={root_note}"]
    if loop:
        body.append("loop_mode=loop_continuous")
    out_sfz.write_text("\n".join(body) + "\n", encoding="utf-8")
    return {"sfz": str(out_sfz)}


# ---------------------------------------------------------------------------
AGE_PRESETS = {
    # 이름: (저역컷, 고역컷, 비트, 샘플레이트, 드라이브dB, 노이즈dB, 와우깊이)
    "vinyl": (35, 11000, None, None, 4, -42, 0.0012),
    "dusty": (60, 7500, 12, 26040, 6, -38, 0.0018),     # SP-1200 / MPC60 느낌
    "tape": (30, 14000, None, None, 5, -50, 0.0025),
    "radio": (300, 3800, None, None, 8, -46, 0.0),
    "clean": (20, 20000, None, None, 0, -120, 0.0),
}


def age(path, preset="vinyl", out=None, seed=1):
    """늙히기: 대역 제한·비트 감소·포화·잡음·와우/플러터."""
    from . import dsp
    hp, lp, bits, rate, drive, noise_db, wow = AGE_PRESETS[preset]
    y, sr = _load(path)
    if wow:
        t = np.arange(y.shape[1]) / sr
        rnd = np.random.default_rng(seed)
        mod = wow * (np.sin(2 * np.pi * 0.55 * t + rnd.random() * 6) + 0.3 * np.sin(2 * np.pi * 6.1 * t))
        idx = np.clip(np.arange(y.shape[1]) + mod * sr, 0, y.shape[1] - 1)
        y = np.vstack([np.interp(idx, np.arange(y.shape[1]), ch) for ch in y]).astype(np.float32)
    z = y.T                                            # (프레임, 채널)
    z = dsp.lowpass(dsp.highpass(z, sr, hp, order=1), sr, lp, order=1) if hp > 20 or lp < 20000 else z
    if rate:
        z = dsp.lofi_resample(z, sr, rate)
    if bits:
        z = dsp.bitcrush(z, bits)
    if drive:
        z = dsp.gain(dsp.distortion(z, drive), -drive * 0.8)
    z = np.ascontiguousarray(np.asarray(z, dtype=np.float32).T)
    if noise_db > -100:
        rnd = np.random.default_rng(seed)
        hiss = rnd.normal(0, 1, z.shape) * 10 ** (noise_db / 20) * 0.3
        crackle = np.zeros_like(z)
        pops = rnd.random(z.shape[1]) < 1.6 / sr * 8
        crackle[:, pops] = rnd.normal(0, 1, (2, pops.sum())) * 10 ** ((noise_db + 18) / 20)
        z = z + hiss.astype(np.float32) + crackle.astype(np.float32)
    out = out or _out(path, f"_{preset}")
    return _save(z, sr, out, {"op": "age", "source": str(path), "preset": preset})


def separate(path, folder=None, model="htdemucs"):
    """스템 분리(vocals/drums/bass/other) — demucs 가 있으면 쓴다."""
    import subprocess
    import sys
    folder = Path(folder) if folder else CRATE / source_name(path) / "stems"
    folder.mkdir(parents=True, exist_ok=True)
    r = subprocess.run([sys.executable, "-m", "demucs", "-n", model, "-o", str(folder), str(path)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError("demucs failed: " + r.stderr[-800:])
    stems = {p.stem: str(p) for p in (folder / model / Path(path).stem).glob("*.wav")}
    return stems
