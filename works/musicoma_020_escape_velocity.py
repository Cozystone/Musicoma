"""musicoma-020 「Escape Velocity」 — 새 장르 '라이징 테이프(rising tape)'의 첫 곡. 10-19 본인: "완전히 전례 없는 장르와 느낌으로. 새 장르 개척".

라이징 테이프 선언
  1. 밴드 전체가 '한 개의 테이프'다. 곡의 형식 = 테이프의 속도. 조바꿈은 코드가 아니라 가속으로만 한다(속도 ×2^(n/12) = +n 반음).
  2. 테이프가 빨라지면 드럼·베이스·건반·노래가 함께 높아지고 빨라진다 — 칸예의 칩멍크 샘플을 '곡 전체'로 확장한 것.
  3. 단 하나, 래퍼만 테이프 밖에 있다. 세상이 가속하는 동안 그 목소리는 사람 속도 그대로(lego 가 각 고원의 비트를 듣고 그 자리에서 랩).
  4. 가속 구간(램프)엔 말하지 않는다 — 가속 자체가 사건이다.
  5. 끝은 반드시 떨어진다: 테이프 스톱 → 느리게 다시 돌아 원래보다 낮은 조로 끝난다.

테이프 계획(원래 76 BPM F장조, 한 번 연주·녹음)
  intro·v1  ×1.000  76  BPM F   — 낮고 느린 1절 랩
  ramp1     ×1→1.189            — 4마디 가속
  v2        ×1.189  90  BPM A♭  — 2절 랩
  ramp2     ×→1.335
  hook      ×1.335  101 BPM B♭  — 원래 F 로 부른 노래가 +5 칩멍크 훅이 된다
  ramp3     ×→1.498
  climax    ×1.498  114 BPM C   — 훅 + 짧은 랩
  stop      ×1.498→0.06         — 테이프 스톱, 정적
  outro     ×0.75   57  BPM C(아래) — 같은 훅이 -5 로 느리고 낮게

    python works/musicoma_020_escape_velocity.py
"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from musicoma import arrange, concept as concept_mod, lego, master, dsp

NAME = "musicoma-020-escape-velocity"
BASE_BPM, KEY = 76, "F major"
SPB = 60 / BASE_BPM
R = {n: 2 ** (n / 12) for n in (0, 3, 5, 7, -5)}
FORM = [("intro", 4), ("verse1", 16), ("ramp1", 4), ("verse2", 16), ("ramp2", 4), ("hook", 8), ("ramp3", 4),
        ("climax", 8), ("stop", 1), ("outro", 8)]
# (구간, 시작 속도, 끝 속도)
SPEED = {"intro": (R[0], R[0]), "verse1": (R[0], R[0]), "ramp1": (R[0], R[3]), "verse2": (R[3], R[3]), "ramp2": (R[3], R[5]),
         "hook": (R[5], R[5]), "ramp3": (R[5], R[7]), "climax": (R[7], R[7]), "stop": (R[7], 0.06), "outro": (R[-5], R[-5])}
ROOT = Path(arrange.ROOT)
RAP_REF = Path(r"D:\0.MUSIC\Musicoma\02 칸예 시티팝 (첫 산출물)\보컬\rap_lego_full.wav")

# ───────── 노래 훅(원래 F 로 부름 → 훅에서 +5, 클라이맥스 +7, 아웃트로 -5) — 한 토큰 = 한 음표 ─────────
HOOK_MEL = ("r:1 C5:.5 A4:.5 C5:1 D5:1 | C5:2 A4:2 | r:1 F4:.5 G4:.5 A4:1 C5:1 | A4:3 r:1 | "
            "r:1 C5:.5 A4:.5 C5:1 D5:1 | D5:2 C5:1 A4:1 | r:1 C5:.5 A4:.5 G4:1 F4:1 | F4:3 r:1")
HOOK_LYR = "if I go fast e- nough the night can't hold me if I go fast e- nough I'm gone be- fore the dawn"   # 23

# ───────── 랩(사람 속도 — 테이프 밖) ─────────
VERSE1 = ["Engine on at one, the street's still wet", "Radio's playing something my mother liked",
          "I didn't pack a bag, I took the keys", "Left the porch light on so it looks like I'm home",
          "Exit signs keep coming, I keep not taking them", "Every mile marker counting what I owe",
          "The song on the radio's getting faster", "Or I am, I can't tell anymore"]
VERSE2 = ["Now the singer sounds younger every mile", "Like the tape's running back to when she meant it",
          "Toll booth's empty, I pay a man who isn't there", "Gas station glow, then nothing, then the next one",
          "Phone buzzing in the cupholder, I let it", "Your name on the screen, spinning like a coin",
          "I'm not running from you, I'm running from the room", "The one where we stood still too long"]
CLIMAX = ["Faster now", "Lines on the road turn into one line", "Lights turn into rain", "Rain turns into stars",
          "Everything's a blur but me", "I'm the only thing standing still", "In a car doing a hundred", "That's the whole trick"]

CONCEPT = {
    "thesis": "새벽 한 시 도망치는 차 안 — 라디오의 노래가 점점 빨라지고 높아진다. 세상이 가속하는 동안 운전하는 사람만 제 속도로 말한다",
    "genre": "rising tape — 곡의 형식이 테이프 속도. 조바꿈은 가속으로만, 래퍼만 테이프 밖",
    "arc": [{"section": "intro/verse1", "intent": "×1.0 76 BPM, 낮은 F — 지친 1절", "energy": 0.4},
            {"section": "ramp1", "intent": "4마디 동안 밴드 전체가 +3 반음까지 가속, 말 없음", "energy": 0.6},
            {"section": "verse2", "intent": "×1.19 90 BPM A♭ — 2절, 노래가 '젊어진다'", "energy": 0.65},
            {"section": "hook", "intent": "×1.33 B♭ — 원래 여자 목소리가 칩멍크 훅", "energy": 0.9},
            {"section": "climax", "intent": "×1.5 C 114 BPM — 훅 + 짧은 랩, 가장 빠름", "energy": 1.0},
            {"section": "stop", "intent": "테이프 스톱 — 정적", "energy": 0.0},
            {"section": "outro", "intent": "×0.75 57 BPM, 같은 훅이 낮고 느리게 — 도망은 끝났다", "energy": 0.25}],
    "motif": {"melody": "C5:.5 A4:.5 C5:1 D5:1", "why": "'if I go fast' — 곡 내내 같은 음형이 속도만 바뀌며 세 번 다른 사람이 된다(F·B♭·C·아래 C)"},
    "collision": ["칸예 칩멍크(샘플 배속)", "곡 전체 배속(형식)", "사람 속도의 랩"],
    "irregular": [{"what": "코드 전조 없음, 가속 전조만", "why": "장르 선언 1"}, {"what": "끝이 시작보다 낮다", "why": "장르 선언 5"}],
    "constraints": ["램프에선 말하지 않는다", "랩은 각 고원에서 lego 로 그 속도의 비트를 듣고", "랩 줄 ≤9음절, 줄마다 2마디"],
    "references": "old-kanye-citypop.yaml(칩멍크 배속) — 곡 전체에 적용한 선례 없음",
    "not": ["코드로 전조", "고른 채움", "램프 위 랩"],
}


def band_spec():
    sw = 0.56
    D = lambda pat, fill=None: {"pattern": pat, "swing": sw, "humanize_ms": 7, "humanize_vel": 9, **({"fill": fill} if fill else {})}
    MAIN = {"kick": "x.....x...x..x..", "snare": "....X.......X...", "hat": "x-x-x-x-x-x-x-x-"}
    MAIN2 = {"kick": "X.....x...X..x..", "snare": "....X..o....X..o", "hat": "x-x-x-x-x-x-x-x-", "open_hat": "..........x....."}
    HK = {"kick": "X..x..x...X..x..", "snare": "....X..o....X..o", "hat": "xxxxxxxxxxxxxxxx", "open_hat": "..............x."}
    RAMP = {"kick": "x...x...x...x...", "snare": "....x.......x.xx", "hat": "xxxxxxxxxxxxxxxx"}
    F1 = {"kick": "X.....x...X.....", "snare": "....X.......xoxo", "hat": "x.x.x.x.x.x....."}
    F2 = {"kick": "X.........X.....", "snare": "....X...XoXoXXXX", "hat": "x.x.x.x........."}
    V = "Imaj7 vi7 IVmaj7 V7sus4"
    H = "IVmaj7 V7 iii7 vi7 IVmaj7 V7 Imaj7 Imaj7"
    return {
        "name": NAME, "bpm": BASE_BPM, "key": KEY, "style": "chipmunk-soul", "feel": "laid_back", "intensity": 0.7,
        "brief": "「Escape Velocity」 라이징 테이프 — 원래 76 BPM F 로 한 번 연주한 밴드 전체를 테이프처럼 가속",
        "sections": [{"name": n, "bars": b} for n, b in FORM],
        "tracks": {
            "Drums": {"sound": "drums_acoustic_basic", "role": "drums", "sends": {"0": -22}, "fx": [
                {"device": "eq", "params": {"Low-pass freq": 62, "Low-pass gain": 3, "Mid freq 1": 350, "Mid gain 1": -3, "Mid Q 1": 1.0, "Mid freq 2": 4500, "Mid gain 2": 2.5}},
                {"device": "compressor", "params": {"threshold": -19, "ratio": 4, "attack": 18, "release": 80, "output gain": 3}}]},
            "Bass": {"preset": "bass/finger", "role": "bass"},
            "Keys": {"preset": "keys/rhodes_classic", "role": "keys", "pan": -0.2, "sends": {"0": -9}},
            "Guitar": {"preset": "guitar/jangle", "role": "guitar", "pan": 0.35, "sends": {"0": -10}},
            "Strings": {"preset": "strings/ensemble", "role": "strings", "pan": -0.3, "sends": {"0": -6}},
            "Hook": {"role": "hook vocal (ns-singer-cp, sung at base F — the tape pitches it)", "sends": {"0": -8},
                     "fx": [{"device": "compressor", "params": {"threshold": -18, "ratio": 3}}]},
        },
        "buses": [{"name": "Room", "bus": 0, "device": "Dragonfly Plate Reverb", "volume_db": -5}],
        "parts": [
            {"track": "Keys", "in": ["intro"], "chords": {"progression": V, "beats_per_chord": 4, "voicing": "rhodes", "rhythm": [[0, 1.5, .9], [2.5, 1.5, .8]], "velocity": 60}},
            {"track": "Guitar", "in": ["intro"], "offset": 8, "chords": {"progression": V, "beats_per_chord": 4, "voicing": "guitar", "rhythm": [[1, .5, .7], [3, .5, .7]], "velocity": 60}},
            {"track": "Drums", "in": ["verse1"], "drums": D(MAIN, F1)},
            {"track": "Drums", "in": ["verse2"], "drums": D(MAIN2, F1)},
            {"track": "Drums", "in": ["ramp1", "ramp2", "ramp3"], "drums": D(RAMP)},
            {"track": "Drums", "in": ["hook", "climax"], "drums": D(HK, F2)},
            {"track": "Bass", "in": ["verse1", "verse2"], "bass": {"progression": V, "beats_per_chord": 4, "pattern": [[0, .9, 0], [1.5, .5, 0], [2.5, .45, 0], [3.25, .5, 7]], "velocity": 96}},
            {"track": "Bass", "in": ["ramp1", "ramp2", "ramp3"], "bass": {"progression": "V7sus4", "beats_per_chord": 16, "pattern": [[i * .5, .45, 0] for i in range(8)], "velocity": 100}},
            {"track": "Bass", "in": ["hook", "climax"], "bass": {"progression": H, "beats_per_chord": 4, "pattern": [[0, .9, 0], [.75, .3, 0], [1.75, .5, 0], [2.5, .4, 12], [3.5, .4, 7]], "velocity": 104}},
            {"track": "Bass", "in": ["outro"], "bass": {"progression": H, "beats_per_chord": 4, "pattern": [[0, 3.5, 0]], "velocity": 78}},
            {"track": "Keys", "in": ["verse1", "verse2"], "chords": {"progression": V, "beats_per_chord": 4, "voicing": "rhodes", "rhythm": [[1, .5, .9], [3, .5, .8]], "velocity": 60}},
            {"track": "Keys", "in": ["ramp1", "ramp2", "ramp3"], "chords": {"progression": "V7sus4", "beats_per_chord": 16, "voicing": "rhodes", "rhythm": [[i * .5, .4, .6 + .4 * i / 32] for i in range(32)], "velocity": 70}},
            {"track": "Keys", "in": ["hook", "climax", "outro"], "chords": {"progression": H, "beats_per_chord": 4, "voicing": "rhodes", "rhythm": [[0, 1.5, 1], [2, 1.5, .85]], "velocity": 66}},
            {"track": "Guitar", "in": ["verse2", "hook", "climax"], "chords": {"progression": V, "beats_per_chord": 4, "voicing": "guitar", "rhythm": [[.5, .25, .8], [1.5, .25, .7], [2.5, .25, .8], [3.5, .25, .7]], "velocity": 66}},
            {"track": "Strings", "in": ["ramp1", "ramp2", "ramp3"], "chords": {"progression": "V7sus4", "beats_per_chord": 16, "voicing": "pad", "velocity": 70, "legato": 1.0}},
            {"track": "Strings", "in": ["hook", "climax", "stop", "outro"], "chords": {"progression": H, "beats_per_chord": 4, "voicing": "pad", "velocity": 62, "legato": 1.0}},
            {"track": "Hook", "in": ["hook", "climax", "outro"], "vocal": {"voice": "ns-singer-cp", "melody": HOOK_MEL, "lyrics": HOOK_LYR, "seed": 4}},
        ],
        "mix": {"balance": True, "target_lufs": -14, "balance_lu": {"drums": 0, "bass": -3, "keys": -6, "guitar": -8, "strings": -9, "hook": 0}},
    }


def section_times():
    out, b = {}, 0
    for n, k in FORM:
        out[n] = (b * 4 * SPB, (b + k) * 4 * SPB)
        b += k
    return out


def tape(src_wav, out_wav):
    """테이프 속도 곡선을 원래 녹음에 건다. 원본(원래 박자 시간) s 에서의 속도 r(s) → 출력 시간 t(s)=∫ds/r. 96 kHz 에서 보간."""
    import librosa
    y, sr = sf.read(str(src_wav), dtype="float32", always_2d=True)
    hi = 96000
    y = librosa.resample(y.T, orig_sr=sr, target_sr=hi, res_type="soxr_hq").T
    st = section_times()
    knots_t, knots_r = [], []
    for n, _ in FORM:
        a, b = st[n]; r0, r1 = SPEED[n]
        if n == "outro":                       # 다시 돌기 시작: 첫 박 동안 0.2 → 0.75
            knots_t += [a, a + SPB, b]; knots_r += [0.2, r0, r1]
        else:
            knots_t += [a, b - 1e-4]; knots_r += [r0, r1]
    s = np.arange(len(y)) / hi
    r = np.interp(s, knots_t, knots_r).astype(np.float64)
    stop_a, stop_b = st["stop"]; out_a = st["outro"][0]
    seg_main = s < stop_b
    seg_out = s >= out_a

    def render(mask):
        idx = np.nonzero(mask)[0]
        t_out = np.concatenate([[0.0], np.cumsum(1.0 / r[idx][:-1]) / hi])
        n_out = int(t_out[-1] * hi)
        pos = np.interp(np.arange(n_out) / hi, t_out, idx.astype(np.float64))
        i0 = np.floor(pos).astype(np.int64); fr = (pos - i0)[:, None]
        i1 = np.minimum(i0 + 1, len(y) - 1)
        return (y[i0] * (1 - fr) + y[i1] * fr).astype(np.float32), t_out, idx

    main, t_main, idx_main = render(seg_main)
    f = int(0.4 * hi); main[-f:] *= np.linspace(1, 0, f)[:, None] ** 2          # 스톱 끝은 꺼진다
    gap = np.zeros((int(0.9 * hi), y.shape[1]), np.float32)                     # 정적
    outro, t_outro, _ = render(seg_out)
    full = np.concatenate([main, gap, outro])
    full = librosa.resample(full.T, orig_sr=hi, target_sr=48000, res_type="soxr_hq").T
    sf.write(str(out_wav), full, 48000, subtype="FLOAT")

    def where(t_src):                           # 원래 시간 → 출력 시간(본편만)
        return float(np.interp(t_src * hi, idx_main, t_main))
    marks = {n: (where(st[n][0]), where(st[n][1])) for n, _ in FORM if n not in ("outro",)}
    marks["outro"] = (len(main) / hi + len(gap) / hi, len(full) / 48000)
    return marks


def rap_on_plateau(beat, guide, name, lines, beats_per_line, bpm, key, marks, log=print):
    a, _ = marks[name]
    spb = 60.0 / bpm
    sec = {"name": name, "start": round(a, 3), "end": round(a + len(lines) * beats_per_line * spb, 3), "tag": "Verse",
           "lyrics": "\n".join(lines), "key": key}
    out = ROOT / "projects" / NAME / "vocals" / f"rap_{name}"
    cap = ("old school hip hop, male rapper, calm and low, laid back conversational flow, clear words, on the beat, "
           "leaves space between lines, no singing, dry close mic")
    _, rep = lego.vocal_track(beat, [sec], bpm, key, cap, out, takes=10, guide_wav=guide, pass_wer=0.3, min_key_fit=0.0,
                              lang="en", reference=str(RAP_REF), log=log)
    st = json.loads(out.with_suffix(".json").read_text(encoding="utf-8"))
    log(f"[rap] {name} @{bpm:.1f} BPM {key}: seed {rep[0]['chosen']} · 오류율 {rep[0]['wer']}")
    return st["full"]


def mix(band_wav, vox_wavs, out_wav):
    import pyloudnorm as pyln
    from scipy.signal import butter, sosfilt
    b, sr = sf.read(str(band_wav), dtype="float32", always_2d=True)
    meter = pyln.Meter(sr)
    lb = meter.integrated_loudness(b)
    sos = butter(2, 110, "highpass", fs=sr, output="sos")
    tot = b.copy()
    for w in vox_wavs:
        v, s2 = sf.read(str(w), dtype="float32", always_2d=True)
        assert s2 == sr, (s2, sr)
        if v.shape[1] == 1:
            v = np.repeat(v, 2, 1)
        v = sosfilt(sos, v, axis=0).astype(np.float32)
        v = dsp.compressor(v, sr, threshold_db=-20, ratio=3.5, attack_ms=8, release_ms=90)
        lv = meter.integrated_loudness(v)
        v = v * 10 ** ((lb + 1.5 - lv) / 20)                                  # 랩은 반주보다 1.5 LU 앞
        n = min(len(v), len(tot)); tot[:n] += v[:n]
    sf.write(str(out_wav), tot, sr, subtype="FLOAT")


if __name__ == "__main__":
    log = lambda m: print(m, flush=True)
    concept_mod.save(NAME, CONCEPT)
    d = ROOT / "projects" / NAME; (d / "vocals").mkdir(parents=True, exist_ok=True)
    spec = band_spec()
    s, rep = arrange.build(spec, label="tape-src", fmt="wav", log=lambda m: log("[band] " + m) if "sang" in m or "balance" in m else None)
    log(f"[1] 원래 녹음(76 BPM F): {rep['file']}")
    guide_src = lego.render_guide({**spec, "parts": [p for p in spec["parts"] if "vocal" not in p]})
    band = d / "tape_band.wav"; guide = d / "tape_guide.wav"
    marks = tape(rep["file"], band); tape(guide_src, guide)
    log("[2] 테이프 " + json.dumps({k: [round(x, 1) for x in v] for k, v in marks.items()}))
    vox = [rap_on_plateau(band, guide, "verse1", VERSE1, 8, BASE_BPM * R[0], "F major", marks, log),
           rap_on_plateau(band, guide, "verse2", VERSE2, 8, BASE_BPM * R[3], "Ab major", marks, log),
           rap_on_plateau(band, guide, "climax", CLIMAX, 4, BASE_BPM * R[7], "C major", marks, log)]
    mixed = d / "mix.wav"; mix(band, vox, mixed)
    m = master.master(str(mixed), lufs=-11.0, ceiling=-1.0, glue=True, out=str(d / "renders" / f"{NAME}_v1.wav"))
    mp3 = Path(m["path"]).with_suffix(".mp3")
    subprocess.run(["ffmpeg", "-nostdin", "-y", "-v", "error", "-i", m["path"], "-b:a", "320k", str(mp3)], check=True)
    log(json.dumps({"file": str(mp3), "lufs": m["lufs"], "true_peak": m["true_peak"], "marks": marks}, ensure_ascii=False))
