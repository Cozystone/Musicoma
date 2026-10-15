"""musicoma-010 「Acelera」 — 브라질리언 퐁크, 포르투갈어 구호, 처음부터 끝까지. (10-16 본인: "새로운 장르인 브라질리언 퐁크로, 완성까지")

0 레퍼런스(knowledge/references/brazilian-phonk.yaml) + 새 장르 카드(styles/brazilian-phonk.yaml)
· 소리: 카우벨·808·킷은 무료 샘플이 없어 직접 합성(musicoma/kits.py, CC0)
→ 1 콘셉트 → 동기(카우벨 리프) → 비평 → 가이드 → [구호 구간별 녹음 ∥ 반주] → 구호를 잘라 찹(되풀이·디스토션) → 렌더.

    python works/musicoma_010_acelera.py dry | all v1 | final v2
"""
import json
import sys
import time
from pathlib import Path

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from musicoma import arrange, concept as concept_mod, critic, lego, motif

NAME = "musicoma-010-acelera"
BPM, KEY = 130, "A minor"
SPB = 60 / BPM

# 구호(새로 씀 — 원곡 구호 인용 없음). 짧게, 되풀이, 외치듯
LYR = {
    "drop": "Acelera, acelera, ninguém segura\nBate forte no baile, a noite é pura\n"
            "Acelera, acelera, sobe o som\nTodo mundo pulando nesse tom",
    "drop2": "Vai, vai, vai, não para não\nO grave bate forte no coração\n"
             "Vai, vai, vai, até o sol nascer\nAcelera que eu quero ver",
}

RIFF = "A5:.75@118 A5:.75@96 C6:.5@110 A5:.75@118 A5:.75@96 Bb5:.5@112"          # 3+3+2 강세 — 동기
RIFF_B = "A5:.75@118 A5:.75@96 C6:.5@110 E6:.75@120 D6:.75@100 Bb5:.5@112"       # 2마디째: 끝을 비튼다
RIFF_BII = "Bb5:.75@118 Bb5:.75@96 D6:.5@110 Bb5:.75@118 Bb5:.75@96 A5:.5@112"   # bII(Bb) 마디는 Bb 위에서 — 화음과 맞게
RIFF_END = "A5:.75@118 A5:.75@96 C6:.5@110 E6:.5@124 r:.25 E6:.5@110 G5:.5@100 r:.25"   # 4마디 끝맺음


def dev(text, ops):
    return motif.to_text(motif.develop(motif.parse(text), ops, KEY))


# 4마디 구절(화음 i i bII i 에 맞춤) — 섹션마다 동기를 변형(같은 4마디 복사 금지)
P_A = " ".join([RIFF, RIFF_B, RIFF_BII, RIFF_END])
P_B = " ".join([dev(RIFF, ["invert"]), dev(RIFF, ["up:2"]), RIFF_BII, dev(RIFF, ["retro"])])           # 대답: 뒤집고 올리고 거꾸로
P_BUILD = " ".join([dev(RIFF, ["fragment:2"]) + " r:2", dev(RIFF, ["up:1"]), dev(RIFF, ["up:2"])])     # 조각 → 한 칸씩 오름
P_OUT = P_A                                                                # 아웃트로 4마디 꽉(v1 은 2마디뿐이라 끝에 6.5초 빈 공기)

CONCEPT = {
    "thesis": "멈추지 않는 밤의 가속 — 3+3+2 북소리가 계속 앞으로 미는데, 카우벨 리프는 같은 자리를 맴돈다",
    "arc": [{"section": "intro", "intent": "카우벨 리프와 림만, 구호 찹으로 예고", "energy": 0.35},
            {"section": "drop", "intent": "탐보르장 + 찌그러진 808 + 구호 '아셀레라'", "energy": 0.9},
            {"section": "drop_b", "intent": "구호를 잘라 되풀이(몬타젱)", "energy": 0.85},
            {"section": "break", "intent": "808 빠짐 — 프리지안 드론, 반음 내린 찹", "energy": 0.35},
            {"section": "build", "intent": "클랩 롤 + 카우벨 조각이 한 칸씩 오름", "energy": 0.7},
            {"section": "gap", "intent": "다 빠지고 외침 하나(1마디)", "energy": 0.2},
            {"section": "drop2", "intent": "더 세게 — 카우벨 한 옥타브 위, 드롭 패턴, 새 구호", "energy": 1.0},
            {"section": "drop2_b", "intent": "찹 + 끝까지 밀기", "energy": 1.0},
            {"section": "outro", "intent": "카우벨 혼자 남았다가 뚝", "energy": 0.4}],
    "motif": {"melody": RIFF, "why": "3+3+2 — 바일리 펑크 북소리와 같은 강세의 카우벨"},
    "collision": ["리우 바일리 펑크 탐보르장", "멤피스 퐁크의 찌그러진 808", "프리지안 반음(bII)의 긴장"],
    "constraints": ["화음은 거의 없다 — 선율은 카우벨, 색은 bII(Bb) 하나", "구호는 2~4마디 단위로 되풀이",
                    "드롭2는 같은 리프를 한 옥타브 위로(전개)", "2분 안팎으로 짧게"],
    "events": [{"section": "outro", "at": 7, "length": 1, "type": "stop", "why": "끝을 말하지 않고 뚝"}],
    "irregular": [{"what": "브레이크에서 808 을 완전히 뺌", "why": "다시 들어올 때의 충격"},
                  {"what": "빌드 3마디 + 1마디 공백(구호 외침만)", "why": "드롭2 직전 숨 — 다 빼고 목소리 하나"}],
    "references": "knowledge/references/brazilian-phonk.yaml — SLAY!(Eternxlkz) · 몬타젱 계열 · Soundtrap/SampleFocus 제작 안내",
    "not": ["스윙", "라이브 킷", "긴 화음 패드 위주", "깨끗한 마스터", "원곡 구호 인용"],
}

SECTIONS = [{"name": "intro", "bars": 8}, {"name": "drop", "bars": 8}, {"name": "drop_b", "bars": 8},
            {"name": "break", "bars": 8}, {"name": "build", "bars": 3}, {"name": "gap", "bars": 1}, {"name": "drop2", "bars": 8},
            {"name": "drop2_b", "bars": 8}, {"name": "outro", "bars": 4}]
PROG = {"drop": "i i bII i", "break": "bVI bII bVI bVII"}
DR = {"intro": {"rim": "..x..x....x..x.x", "hat": "x.x.x.x.x.x.x.x.", "kick": "x...............|................"},
      "tamborzao": {"kick": "x..x..x...x..x..", "clap": "....x.......x...", "rim": "..x..x....x..x.x", "hat": "x.x.x.x.x.x.x.x."},
      "tamborzao_b": {"kick": "x..x..x...x..x..", "clap": "....x.......x...", "rim": "x.xx.x....x.xx.x", "hat": "x.x.x.x.x.x.x.x.", "tamb": "..x...x...x...x."},
      "drop_b2": {"kick": "x..x..x.x..x..x.", "clap": "....x..x....x...", "rim": "x.xx.x.xx.x.x.xx", "hat": "xxxxxxxxxxxxxxxx", "open_hat": "......x.......x.", "tamb": "..x...x...x...x."},
      "drop": {"kick": "x..x..x.x..x..x.", "clap": "....x.......x...", "rim": "x.xx.x.xx.x.x.xx", "hat": "xxxxxxxxxxxxxxxx", "tamb": "..x...x...x...x."},
      "break": {"kick": "x...............", "clap": "............x...", "hat": "x...x...x...x..."},
      "build": {"kick": "x...x...x...x...", "clap": "x.x.x.x.xxxxxxxx", "hat": "xxxxxxxxxxxxxxxx"},
      "fill": {"kick": "x..x..x.", "clap": "....x.xxxxxxXXXX"}}


def drums(p, fill=False):
    return {"pattern": DR[p], "swing": 0.5, "humanize_ms": 2, "humanize_vel": 6, **({"fill": DR["fill"]} if fill else {})}


BASS_PAT = [[0, 0.7, 0], [0.75, 0.7, 0], [1.5, 0.95, 12], [2.5, 0.7, 0], [3.25, 0.7, -2]]      # 킥 자리(3+3+2)를 따라
BASS_PAT_B = [[0, 0.7, 0], [0.75, 0.45, 12], [1.25, 0.25, 0], [1.5, 0.95, 12], [2.5, 0.7, 0], [3.25, 0.25, 7], [3.5, 0.5, 10]]
spec = {
    "name": NAME, "bpm": BPM, "key": KEY, "style": "brazilian-phonk", "feel": "tight", "intensity": 0.9,
    "brief": "「Acelera」 브라질리언 퐁크 · 포르투갈어 구호 · 자체 합성 카우벨·808",
    "sections": SECTIONS,
    "tracks": {
        "Drums": {"preset": "drums/phonk", "role": "drums"},
        "Bass808": {"preset": "bass/808_dist", "role": "bass"},
        "Cowbell": {"preset": "lead/cowbell", "role": "lead", "perform_role": "pluck", "sends": {"0": -18},
                    "fx": [{"device": "compressor", "params": {"threshold": -22, "ratio": 4, "attack": 1, "release": 80, "output gain": 6}}]},
        "Pad": {"preset": "pad/warm", "role": "pad", "fx": [{"device": "lowpass", "params": {"frequency": 1800}}], "sends": {"0": -8}},
    },
    "buses": [{"name": "Room", "bus": 0, "device": "Dragonfly Room Reverb", "volume_db": -8}],
    "parts": [
        {"track": "Drums", "in": ["intro"], "drums": drums("intro")},
        {"track": "Drums", "in": ["drop"], "drums": drums("tamborzao", fill=True)},
        {"track": "Drums", "in": ["drop_b"], "drums": drums("tamborzao_b", fill=True)},
        {"track": "Drums", "in": ["break"], "drums": drums("break")},
        {"track": "Drums", "in": ["build"], "drums": drums("build")},
        {"track": "Drums", "in": ["drop2"], "drums": drums("drop", fill=True)},
        {"track": "Drums", "in": ["drop2_b"], "drums": drums("drop_b2", fill=True)},
        {"track": "Cowbell", "in": ["intro", "drop"], "melody": {"text": P_A, "velocity": 100}},
        {"track": "Cowbell", "in": ["drop_b"], "melody": {"text": P_B, "velocity": 102}},
        {"track": "Cowbell", "in": ["build"], "melody": {"text": P_BUILD, "velocity": 92, "repeat": False}},
        {"track": "Cowbell", "in": ["drop2"], "transpose": 12, "melody": {"text": P_A, "velocity": 106}},
        {"track": "Cowbell", "in": ["drop2_b"], "transpose": 12, "melody": {"text": P_B, "velocity": 108}},
        {"track": "Cowbell", "in": ["outro"], "melody": {"text": P_OUT, "velocity": 96, "repeat": False}},
        {"track": "Bass808", "in": ["drop"], "bass": {"progression": PROG["drop"], "beats_per_chord": 4, "low": 33, "high": 48,
                                                    "pattern": BASS_PAT, "velocity": 100}},
        {"track": "Bass808", "in": ["drop_b"], "bass": {"progression": PROG["drop"], "beats_per_chord": 4, "low": 33, "high": 48,
                                                      "pattern": BASS_PAT_B, "velocity": 104}},
        {"track": "Bass808", "in": ["drop2"], "bass": {"progression": PROG["drop"], "beats_per_chord": 4, "low": 33, "high": 48,
                                                     "pattern": BASS_PAT, "velocity": 118}},
        {"track": "Bass808", "in": ["drop2_b"], "bass": {"progression": PROG["drop"], "beats_per_chord": 4, "low": 33, "high": 48,
                                                       "pattern": BASS_PAT_B, "velocity": 122}},
        {"track": "Bass808", "in": ["build"], "bass": {"progression": "i", "beats_per_chord": 4, "low": 33, "high": 48,
                                                      "pattern": [[0, 3.5, 0]], "velocity": 90}},
        {"track": "Pad", "in": ["intro"], "chords": {"progression": PROG["drop"], "beats_per_chord": 4, "voicing": "pad", "velocity": 56, "legato": 1.0}},
        {"track": "Pad", "in": ["break"], "chords": {"progression": PROG["break"], "beats_per_chord": 8, "voicing": "pad", "velocity": 64, "legato": 1.0}},
    ],
    "events": CONCEPT["events"],
    "mix": {"balance": True, "target_lufs": -8,
            "balance_lu": {"drums": 0, "bass808": 0, "cowbell": -2, "pad": -12, "vox": -1, "chop": -3}},
}

VDIR = Path(arrange.ROOT) / "projects" / NAME / "vocals"
VOX = VDIR / "chant.wav"
CAPTION = ("male brazilian funk MC, portuguese, shouted rhythmic chant, aggressive and hype, baile funk phonk, "
           "solo vocal, no singing, no backing vocals")
spec["tracks"]["Vox"] = {"role": "vocal chant (generated over the beat)", "sends": {"0": -16},
                         "fx": [{"device": "eq", "params": {"Low-pass freq": 160, "Low-pass gain": -8, "Mid freq 2": 2500, "Mid gain 2": 3}},
                                {"device": "compressor", "params": {"threshold": -24, "ratio": 6, "attack": 3, "release": 60, "output gain": 3}}]}
spec["tracks"]["Chop"] = {"role": "vocal chops (montagem)", "fx": [{"device": "compressor", "params": {"threshold": -20, "ratio": 4, "attack": 2, "release": 50}}]}
VOX_PART = {"track": "Vox", "vocal_sections": str(VOX.with_suffix(".json"))}
CHOP = VDIR / "chops.wav"
CHOP_PART = {"track": "Chop", "in": ["intro"], "audio": {"path": str(CHOP), "length": sum(s["bars"] for s in SECTIONS) * 4}}


def bar_s(name, occurrence=1):
    b, k = 0, 0
    for s in SECTIONS:
        if s["name"] == name:
            k += 1
            if k == occurrence:
                return b * 4 * SPB, (b + s["bars"]) * 4 * SPB
        b += s["bars"]
    raise KeyError(name)


def vocal_sections():
    out = []
    for name in ("drop", "drop2"):
        a, b = bar_s(name)
        out.append({"name": name, "start": round(a, 3), "end": round(b, 3), "tag": "Chorus", "lyrics": LYR[name], "key": KEY})
    return out


def make_chops():
    """구호에서 가장 센 짧은 외침 두 개를 잘라 3+3+2 자리에 되풀이(몬타젱 찹), tanh 디스토션.
    브레이크엔 5반음 내린 찹. 결과 = 곡 길이 전체 오디오 한 줄."""
    import librosa
    st = json.loads(VOX.with_suffix(".json").read_text(encoding="utf-8"))
    v, sr = sf.read(st["sections"][0]["file"], dtype="float32")
    mono = v.mean(1)
    on = librosa.onset.onset_detect(y=mono, sr=sr, units="samples", backtrack=True)
    L = int(SPB * 0.5 * sr)                                  # 8분음표 길이 조각
    cands = sorted(((float(np.sqrt(np.mean(mono[o:o + L] ** 2))), int(o)) for o in on if o + L < len(mono)), reverse=True)
    picks = [o for _, o in cands[:2]] or [0]
    chops = []
    for o in picks:
        c = v[o:o + L].copy()
        c *= np.minimum(1, np.arange(L) / (0.004 * sr))[:, None] * np.minimum(1, (L - np.arange(L)) / (0.01 * sr))[:, None]
        chops.append(np.tanh(3.0 * c / (np.abs(c).max() + 1e-9)) * 0.8)
    low = [librosa.effects.pitch_shift(c.T, sr=sr, n_steps=-5).T for c in chops]
    total = int(sum(s["bars"] for s in SECTIONS) * 4 * SPB * sr) + sr
    out = np.zeros((total, 2), np.float32)

    def put(t_beats, c, gain=1.0):
        i = int(t_beats * SPB * sr)
        out[i:i + len(c)] += c[:max(0, total - i)] * gain

    bars_start, b = {}, 0
    for s in SECTIONS:
        bars_start.setdefault(s["name"], []).append((b, s["bars"]))
        b += s["bars"]
    for name, src, gain, beats in (("intro", chops, 0.6, [0, 0.75, 1.5]), ("drop_b", chops, 1.0, [0, 0.75, 1.5, 2.5, 3.25]),
                                   ("break", low, 0.8, [0, 1.5]), ("drop2_b", chops, 1.0, [0, 0.75, 1.5, 2.5, 3.0, 3.5])):
        for b0, n in bars_start.get(name, []):
            for bar in range(n):
                if name == "intro" and bar % 2 == 0:          # 인트로는 예고만(두 마디에 한 번)
                    continue
                for k, t in enumerate(beats):
                    put((b0 + bar) * 4 + t, src[k % len(src)], gain)
    # 공백 1마디: 드롭2 구호의 첫 외침("Vai, vai, vai")을 한 마디 길이로 그대로 — 다 빠진 자리에 목소리 하나
    v2, _ = sf.read(st["sections"][-1]["file"], dtype="float32")
    m2 = v2.mean(1)
    on2 = librosa.onset.onset_detect(y=m2, sr=sr, units="samples", backtrack=True)
    o2 = int(on2[0]) if len(on2) else 0
    shout = v2[o2:o2 + int(4 * SPB * sr)].copy()
    shout *= np.minimum(1, (len(shout) - np.arange(len(shout))) / (0.08 * sr))[:, None]
    shout = np.tanh(2.0 * shout / (np.abs(shout).max() + 1e-9)) * 0.85
    for b0, n in bars_start.get("gap", []):
        put(b0 * 4, shout, 1.0)
    path = lego._safe_write(CHOP, out, sr)                   # 엔진이 이전 찹 파일을 열고 있으면 새 이름으로
    return {**CHOP_PART, "audio": {**CHOP_PART["audio"], "path": str(path)}}


def make_vocals(log=print):
    guide = lego.render_guide(spec)
    _, rep = lego.vocal_track(guide, vocal_sections(), BPM, KEY, CAPTION, VOX, takes=12, guide_wav=guide, lang="pt",
                              pass_wer=0.4, min_key_fit=0.0, log=log)
    for x in rep:
        log(f"{x['section']}: seed {x['chosen']} · 오류율 {x['wer']} · 유사도 {x['voice_sim']}")
    return VOX_PART


if __name__ == "__main__":
    step = sys.argv[1] if len(sys.argv) > 1 else "all"
    label = sys.argv[2] if len(sys.argv) > 2 else "v1"
    concept_mod.save(NAME, CONCEPT)
    r = critic.critique({**spec, "tracks": {k: v for k, v in spec["tracks"].items() if k not in ("Vox", "Chop")}}, CONCEPT)
    print(critic.format_report(r).split("Claude 가")[0])
    if step == "dry":
        sys.exit(0)
    t0 = time.time()
    stamp = lambda m: print(f"{time.time() - t0:6.0f}s {m}", flush=True)
    if step == "all":
        from concurrent.futures import ThreadPoolExecutor
        lego.render_guide(spec)
        stamp("가이드")
        fut = ThreadPoolExecutor(1).submit(make_vocals, stamp)
        s, rep = arrange.build(spec, label=label, later={"Vox": fut.result, "Chop": lambda: (fut.result(), make_chops())[1]}, log=stamp)
    elif step == "final":
        spec["parts"] += [VOX_PART, make_chops()]
        s, rep = arrange.build(spec, label=label, log=stamp)
    else:
        raise SystemExit(f"unknown step {step}")
    stamp("완성")
    print(json.dumps({k: rep[k] for k in ("file", "loudness", "bands_db", "issues")}, ensure_ascii=False, default=str))
