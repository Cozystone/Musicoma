"""레퍼런스 실시간 듣기 — 앱(Electron)이 숨은 창에서 곡을 재생하며 받은 소리를 메모리에서 바로 잰다.

오디오는 디스크에 쓰지 않는다. 남는 건 숫자(레퍼런스 카드)뿐 — 사람이 듣고 메모하는 것과 같은 자리.
    card = analyze_clips([clip1, clip2, clip3], sr, meta={"title": ..., "url": ..., "at": [12.0, 70.0, 130.0]})

재는 것(구간마다 → 모아서)
  tempo / key       템포(박 추적), 조성(화성 스템 크로마)
  loudness/bands    음량·6대역·스테레오(ears 와 같은 눈금 → 우리 렌더와 바로 비교)
  drums             16칸 킥/스네어/햇 패턴(가장 흔한 것)과 스윙(8분 엇박 위치, 0.5 = 곧음)
  stems_db          보컬·드럼·베이스·그 밖의 비중(믹스 대비 dB)
  vocal             있음/없음, 음높이 중앙값·범위, 초당 음절
  density           초당 어택 수(바쁨), 다이내믹(단기 LUFS 폭)
유튜브는 음량을 평준화하므로 loudness 는 '재생된 소리' 기준 — 절대 마스터 음량이 아니다.
"""
import json
import re
import time
from pathlib import Path

import librosa
import numpy as np

from . import ears
from .analyze_ref import drum_pattern_y

ROOT = Path(__file__).resolve().parent.parent
REFS = ROOT / "scratch" / "refs"
_DEMUCS = None


def _slug(t):
    return re.sub(r"[^a-z0-9]+", "-", str(t).lower()).strip("-")[:60] or "ref"


def _separate(y, sr):
    """demucs(htdemucs) 를 이 프로세스 안에서 — GPU 가 없으면 None(스템 없이 잰다)."""
    global _DEMUCS
    try:
        import torch
        from demucs.apply import apply_model
        if not torch.cuda.is_available():
            return None, None
        if _DEMUCS is None:
            from demucs.pretrained import get_model
            _DEMUCS = get_model("htdemucs").cuda().eval()
    except Exception:
        return None, None
    m = _DEMUCS
    if sr != m.samplerate:
        y = librosa.resample(y.T, orig_sr=sr, target_sr=m.samplerate).T
    wav = torch.from_numpy(np.ascontiguousarray(y[:, :2].T, dtype=np.float32)).cuda()
    ref = wav.mean(0)
    mu, sd = ref.mean(), ref.std() + 1e-8
    with torch.no_grad():
        src = apply_model(m, ((wav - mu) / sd)[None], device="cuda", shifts=1, split=True, overlap=0.25,
                          progress=False)[0]
    out = {name: (src[i] * sd + mu).mean(0).cpu().numpy() for i, name in enumerate(m.sources)}
    return out, m.samplerate


def _rms_db(x):
    return ears.db(np.sqrt(np.mean(np.square(x))) + 1e-12)


def _clip(y, sr):
    """구간 하나(스테레오 배열) → 템포·드럼·스템·보컬."""
    mono = y.mean(1)
    y22 = librosa.resample(mono, orig_sr=sr, target_sr=22050)
    tempo, beats = librosa.beat.beat_track(y=y22, sr=22050, units="time", start_bpm=90, tightness=200)
    tempo = float(np.atleast_1d(tempo)[0])
    onsets = librosa.onset.onset_detect(y=y22, sr=22050, units="time")
    out = {"seconds": round(len(mono) / sr, 1), "tempo": round(tempo, 2),
           "attacks_per_sec": round(len(onsets) / max(1e-3, len(mono) / sr), 2)}
    stems, ssr = _separate(y, sr)
    if stems:
        mix_db = _rms_db(sum(stems.values()))
        out["stems_db"] = {k: round(_rms_db(v) - mix_db, 1) for k, v in stems.items()}
        drums22 = librosa.resample(stems["drums"], orig_sr=ssr, target_sr=22050)
        if len(beats) > 8:
            out["drums"] = drum_pattern_y(drums22, beats, 22050)
        voc = stems["vocals"]
        present = out["stems_db"]["vocals"] > -18
        v = {"present": bool(present)}
        if present:
            v16 = librosa.resample(voc, orig_sr=ssr, target_sr=16000)
            f0, voiced, _ = librosa.pyin(v16, fmin=65, fmax=1000, sr=16000, frame_length=1024)
            f0 = f0[voiced & np.isfinite(f0)] if f0 is not None else np.array([])
            if len(f0) > 20:
                midi = librosa.hz_to_midi(f0)
                v.update({"pitch_median": librosa.midi_to_note(float(np.median(midi))),
                          "pitch_range": [librosa.midi_to_note(float(np.percentile(midi, 5))),
                                          librosa.midi_to_note(float(np.percentile(midi, 95)))],
                          "voiced_ratio": round(float(voiced.mean()), 2)})
            # 음절 = 보컬 스템 어택. 나누는 시간 = 목소리가 실제로 나는 구간(최대 대비 -30 dB 위) — 쉼은 빼고
            syl = librosa.onset.onset_detect(y=v16, sr=16000, units="time", delta=0.08)
            rms = librosa.feature.rms(y=v16, frame_length=1024, hop_length=512)[0]
            active = float((20 * np.log10(rms + 1e-9) > 20 * np.log10(rms.max() + 1e-9) - 30).mean())
            v["syllables_per_sec"] = round(len(syl) / max(1.0, active * len(v16) / 16000), 2)
        out["vocal"] = v
    # 조성: 구간마다 전체 믹스(화성 성분)로 재고 나중에 투표 — 스템을 섞거나 구간을 이어 붙이면 틀렸다
    # (10-17 시험: Back On My Feet 구간별 C maj/E min/E min → 투표 E minor 정답, 이어 붙이면 C major)
    k, kc = ears.estimate_key(librosa.effects.harmonic(y22), 22050)
    out["key"], out["key_confidence"] = k, kc
    return out


def _feel(card):
    """숫자 → 짧은 말(프로듀서가 바로 잡는 느낌). 판단 기준은 우리 렌더 측정과 같은 눈금."""
    b, words = card.get("bands_db", {}), []
    t = card.get("tempo")
    if t:
        words.append(f"{t:.0f} BPM" + (" (하프타임 느낌 가능)" if t >= 130 else ""))
    sw = card.get("swing_8th_ratio")
    if sw:
        words.append("곧은 그루브" if sw < 0.54 else "약한 스윙" if sw < 0.6 else "강한 스윙(셔플)")
    if b:
        if b.get("sub", -99) > -12:
            words.append("서브가 큼")
        if b.get("air", -99) < -28:
            words.append("고역이 어두움(로파이·빈티지 쪽)")
        elif b.get("air", -99) > -20:
            words.append("고역이 밝음")
    d = card.get("attacks_per_sec")
    if d:
        words.append("빽빽함" if d > 6 else "여백 많음" if d < 3 else "중간 밀도")
    st = card.get("stereo", {}).get("width_side_to_mid_db")
    if st is not None:
        words.append("넓은 스테레오" if st > -8 else "좁은(모노에 가까운) 스테레오" if st < -16 else "보통 폭")
    v = card.get("vocal") or {}
    if v.get("present"):
        rate = v.get("syllables_per_sec")
        words.append(f"보컬 있음({v.get('pitch_median', '?')}, " + ("랩/빠른 말" if rate and rate > 4.5 else "노래") + ")")
    elif "vocal" in card:
        words.append("보컬 거의 없음(인스트)")
    return words


def analyze_clips(clips, sr, meta=None, name=None, save=True):
    """clips: [(n, 2) float32 배열, ...] 같은 곡의 여러 구간. 반환: 레퍼런스 카드(숫자). 파일은 카드 JSON 만."""
    meta = meta or {}
    t0 = time.time()
    clips = [np.asarray(c, dtype=np.float32) for c in clips if len(c) > sr * 3]
    if not clips:
        raise ValueError("들은 소리가 없습니다(3초 미만)")
    full = np.concatenate(clips)
    rep, _, _ = ears.analyze_array(full, sr)
    speeds = meta.get("speeds") or [1] * len(clips)
    normal = [c for c, s in zip(clips, speeds) if (s or 1) == 1]
    if normal and len(normal) < len(clips):   # 빨리 들은 구간은 10 kHz 위가 깎이므로 소리 색(대역)은 1배속 구간으로
        rep["bands_db"] = ears.band_energy(np.concatenate(normal).mean(1), sr)
    per = [_clip(c, sr) for c in clips]
    votes = {}
    for p in per:
        votes[p["key"]] = votes.get(p["key"], 0) + p["key_confidence"]
    key = max(votes, key=votes.get)
    conf = round(votes[key] / max(1e-9, sum(votes.values())), 2)       # 구간 투표에서 이 조성의 몫
    tempos = [p["tempo"] for p in per]
    swings = [p["drums"]["swing_8th_ratio"] for p in per if p.get("drums", {}).get("swing_8th_ratio")]
    card = {
        "title": meta.get("title"), "url": meta.get("url"), "channel": meta.get("channel"),
        "duration": meta.get("duration"), "listened_at": meta.get("at"), "speeds": meta.get("speeds"),
        "listened_seconds": round(len(full) / sr, 1),
        "tempo": round(float(np.median(tempos)), 1), "tempo_per_clip": tempos,
        "key": key, "key_confidence": conf,
        "loudness": rep["loudness"], "bands_db": rep["bands_db"], "stereo": rep["stereo"],
        "attacks_per_sec": round(float(np.mean([p["attacks_per_sec"] for p in per])), 2),
        "swing_8th_ratio": round(float(np.median(swings)), 3) if swings else None,
        "clips": per,
    }
    vs = [p["vocal"] for p in per if "vocal" in p]
    if vs:
        card["vocal"] = next((v for v in vs if v.get("present")), vs[0])
    sd = [p["stems_db"] for p in per if "stems_db" in p]
    if sd:
        card["stems_db"] = {k: round(float(np.mean([s[k] for s in sd])), 1) for k in sd[0]}
    card["feel"] = _feel(card)
    card["note"] = "loudness 는 유튜브 등에서 평준화된 재생음 기준. 소리는 저장하지 않았고 숫자만 남김."
    card["analyze_sec"] = round(time.time() - t0, 1)
    if save:
        d = REFS / _slug(name or meta.get("title") or "ref")
        d.mkdir(parents=True, exist_ok=True)
        (d / "listen.json").write_text(json.dumps(card, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
        card["saved"] = str(d / "listen.json")
    return card
