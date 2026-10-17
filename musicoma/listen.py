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
    if stems:
        # 코드 진행(이 구간): 화성 스템(other+bass) → 박 정렬 삼화음·7th 채보(조성 안 코드 가산, 변화 억제).
        # 전엔 transcribe.chords(9th 템플릿·2박 고정 창)를 썼는데 밀집한 밴드 믹스에서 Cm9 Fmaj9 Emaj9… 처럼 엉뚱했다(10-17 LUCY 선잠)
        try:
            out["chords"] = chords_simple(stems["other"] + stems["bass"], ssr, tempo if 60 < tempo < 200 else 120, key=k)
        except Exception as ex:
            out["chords_error"] = str(ex)[:100]
    return out


_TRIADS = {"": [0, 4, 7], "m": [0, 3, 7], "7": [0, 4, 7, 10], "maj7": [0, 4, 7, 11], "m7": [0, 3, 7, 10], "sus4": [0, 5, 7]}
_DEGREE = ["I", "bII", "II", "bIII", "III", "IV", "#IV", "V", "bVI", "VI", "bVII", "VII"]


def _parse_key(key):
    """'D major' / 'C# minor' / 'G♯ major' → (으뜸음 0~11, 'major'|'minor')"""
    from .theory import NAMES_FLAT, NAMES_SHARP
    name, _, mode = (key or "C major").partition(" ")
    name = name.replace("♯", "#").replace("♭", "b")
    tonic = NAMES_SHARP.index(name) if name in NAMES_SHARP else NAMES_FLAT.index(name) if name in NAMES_FLAT else 0
    return tonic, ("minor" if mode.strip().lower().startswith("min") else "major")


def _roman(root, q, key):
    tonic, _ = _parse_key(key)
    d = _DEGREE[(root - tonic) % 12]
    if q in ("m", "m7"):
        d = d.lower()
    return d + {"": "", "m": "", "m7": "7", "7": "7", "maj7": "maj7", "sus4": "sus4"}[q]


def chords_simple(harm, sr, bpm, key=None, beats_per_chord=2):
    """화성 스템 → [{chord, roman, beats}] 박 정렬. 코사인 유사도(삼화음·7th·sus4) + 조성 안 코드 +0.08 + 바뀔 때 -0.12(비터비)."""
    from .theory import NAMES_FLAT
    y = librosa.resample(np.asarray(harm, dtype=np.float32), orig_sr=sr, target_sr=22050) if sr != 22050 else np.asarray(harm, dtype=np.float32)
    y = librosa.effects.harmonic(y)
    _, beats = librosa.beat.beat_track(y=y, sr=22050, start_bpm=bpm, tightness=100, units="frames", hop_length=512)
    if len(beats) < 4:
        return []
    chroma = librosa.feature.chroma_cqt(y=y, sr=22050, hop_length=512)
    segs = []
    for i in range(0, len(beats) - 1, beats_per_chord):
        a, b = int(beats[i]), int(beats[min(i + beats_per_chord, len(beats) - 1)])
        if b > a:
            segs.append(chroma[:, a:b].mean(1))
    names, tpls = [], []
    for root in range(12):
        for q, ivs in _TRIADS.items():
            v = np.zeros(12)
            for iv in ivs:
                v[(root + iv) % 12] = 1.0
            names.append((root, q)); tpls.append(v / np.linalg.norm(v))
    T = np.array(tpls)
    bonus = np.zeros(len(names))
    if key:
        tonic, mode = _parse_key(key)
        pcs = {(tonic + s) % 12 for s in ([0, 2, 4, 5, 7, 9, 11] if mode == "major" else [0, 2, 3, 5, 7, 8, 10])}
        for j, (root, q) in enumerate(names):
            if all(((root + iv) % 12) in pcs for iv in _TRIADS[q]):
                bonus[j] = 0.08
    S = np.array([T @ (c / (np.linalg.norm(c) + 1e-9)) + bonus for c in segs])
    n, m = S.shape
    dp, back = S[0].copy(), np.zeros((n, m), dtype=int)
    for i in range(1, n):
        b = int(np.argmax(dp))
        change = np.full(m, dp[b] - 0.12)
        stay = dp >= change
        back[i] = np.where(stay, np.arange(m), b)
        dp = np.where(stay, dp, change) + S[i]
    path = [int(np.argmax(dp))]
    for i in range(n - 1, 0, -1):
        path.append(int(back[i][path[-1]]))
    out = []
    for j in path[::-1]:
        root, q = names[j]
        name = NAMES_FLAT[root] + q
        if out and out[-1]["chord"] == name:
            out[-1]["beats"] += beats_per_chord
        else:
            out.append({"chord": name, "roman": _roman(root, q, key), "beats": beats_per_chord})
    return out[:64]


def _form(y, sr, bpm_hint=None):
    """전곡 → 구간 목록(A/B/…, 시작 초, 마디 수, 크기 dB) + 첫 '가장 큰 반복 구간'(후렴일 가능성)이 오는 시각."""
    from .analyze_ref import _beats, _sections
    mono = y.mean(1) if y.ndim > 1 else y
    y22 = librosa.resample(mono, orig_sr=sr, target_sr=22050)
    tempo, beats = _beats(y22, 22050, bpm_hint)
    secs = _sections(y22, 22050, beats)
    rms = librosa.feature.rms(y=y22, frame_length=2048, hop_length=512)[0]
    out = []
    for s in secs:
        a, b = librosa.time_to_frames([s["start"], s["end"]], sr=22050, hop_length=512)
        lvl = float(20 * np.log10(rms[a:max(a + 1, b)].mean() + 1e-9))
        out.append({"label": s["label"], "start_s": s["start"], "bars": s["bars"], "level_db": round(lvl, 1)})
    if not out:
        return {"sections": []}
    top = max(out, key=lambda x: x["level_db"])
    cnt = {}
    for s in out:
        cnt[s["label"]] = cnt.get(s["label"], 0) + 1
    chorus_like = [s for s in out if s["label"] == top["label"]] if cnt.get(top["label"], 0) >= 2 else [top]
    return {"tempo_est": round(float(tempo), 1), "sections": out,
            "first_loud_repeat_s": chorus_like[0]["start_s"], "loud_repeat_label": top["label"],
            "note": "후렴 추정 = 가장 크고 반복되는 구간. first_loud_repeat_s 가 곡에서 후렴이 처음 오는 시각(원칙: 서두르는가?)"}


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
    speeds0 = list(meta.get("speeds") or [1] * len(clips))
    keep = [i for i, c in enumerate(clips) if len(c) > sr * 3]
    clips = [np.asarray(clips[i], dtype=np.float32) for i in keep]
    speeds = [speeds0[i] if i < len(speeds0) else 1 for i in keep]    # 짧아서 버린 구간과 배속 표를 같이 버린다(10-17: 어긋나 1배속 구간을 4배속으로 봄)
    if not clips:
        raise ValueError("들은 소리가 없습니다(3초 미만)")
    full = np.concatenate(clips)
    rep, _, _ = ears.analyze_array(full, sr)
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
    longest = max(range(len(per)), key=lambda i: len(clips[i]))   # 전곡(clips=0)이면 긴 구간의 템포가 기준 — 24초 구간은 반박자(½·2배)로 자주 틀린다(10-17 조깅: 143 vs 70 → 중앙값 107 이라는 엉뚱한 값)
    tempo = tempos[longest] if len(clips[longest]) > sr * 75 else float(np.median(tempos))
    swings = [p["drums"]["swing_8th_ratio"] for p in per if p.get("drums", {}).get("swing_8th_ratio")]
    card = {
        "title": meta.get("title"), "url": meta.get("url"), "channel": meta.get("channel"),
        "duration": meta.get("duration"), "listened_at": meta.get("at"), "speeds": meta.get("speeds"),
        "listened_seconds": round(len(full) / sr, 1),
        "tempo": round(float(tempo), 1), "tempo_per_clip": tempos,
        "key": key, "key_confidence": conf,
        "loudness": rep["loudness"], "bands_db": rep["bands_db"], "stereo": rep["stereo"],
        "attacks_per_sec": round(float(np.mean([p["attacks_per_sec"] for p in per])), 2),
        "swing_8th_ratio": round(float(np.median(swings)), 3) if swings else None,
        "clips": per,
    }
    # 전곡(clips=0)으로 들었으면 구성까지: 마디 단위 자기유사도로 구간을 나누고 구간별 크기 → 절·후렴이 언제 오는지
    long = [c for c in clips if len(c) > sr * 75]
    if long:
        try:
            card["form"] = _form(long[0], sr, card["tempo"])
        except Exception as ex:
            card["form_error"] = str(ex)[:120]
    for p, s in zip(per, speeds):
        if (s or 1) == 1 and p.get("chords"):
            card["chords_1x"] = p["chords"]            # 1배속으로 들은 구간(가운데 = 대개 후렴 근처)의 코드 진행
    if not card.get("chords_1x") and per[longest].get("chords"):
        card["chords_full_head"] = per[longest]["chords"]   # 1배속 구간이 비었으면 전곡 앞부분(인트로·절)의 코드라도
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
