"""Musicoma ↔ SoulX-Singer 브리지 (SoulX 가상환경에서 실행).

python musicoma_bridge.py request.json
request = {
  "prompt_wav": ..., "prompt_json": ..., "save_dir": ..., "language": "English",
  "control": "melody" | "score", "pitch_shift": 0,
  "tokens": [{"word": "baby" | "<SP>", "pitch": 64, "seconds": 0.5, "type": 1|2|3}],
  "f0": [hz per 20ms frame] (melody 모드)
}
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


VOWELS = {"AA", "AE", "AH", "AO", "AW", "AY", "EH", "ER", "EY", "IH", "IY", "OW", "OY", "UH", "UW"}
FPS = 50


def _is_vowel(ph):
    return ph.rstrip("012") in VOWELS


def syllables(phones):
    """ARPAbet → 음절(모음 핵 기준, 최대 onset: 모음 사이 자음은 마지막 하나만 다음 음절로)."""
    nuc = [i for i, ph in enumerate(phones) if _is_vowel(ph)]
    if len(nuc) <= 1:
        return [phones]
    cuts = []
    for a, b in zip(nuc[:-1], nuc[1:]):
        cons = b - a - 1
        cuts.append(b - (1 if cons >= 1 else 0))
    out, prev = [], 0
    for c in cuts:
        out.append(phones[prev:c])
        prev = c
    out.append(phones[prev:])
    return out


def english_phonemes(tokens):
    """단어 → 음표별 음소. 'ci- ty' 처럼 하이픈으로 나눈 음절, '+'(멜리스마)를 지원.
    여러 음표에 걸친 단어는 g2p 한 번 → 음절로 나눠 음표마다 한 음절."""
    from g2p_en import G2p
    g2p = G2p()
    out = [None] * len(tokens)
    i = 0
    while i < len(tokens):
        w = tokens[i]["word"]
        if w == "<SP>":
            out[i] = "<SP>"
            i += 1
            continue
        if tokens[i].get("type") == 3:            # 멜리스마: 앞 음의 모음을 이어 부름
            out[i] = None
            i += 1
            continue
        # 하이픈 음절 묶기: "ci-" "ty" → city 2음절
        j, parts = i, [w.rstrip("-")]
        while tokens[j]["word"].endswith("-") and j + 1 < len(tokens) and tokens[j + 1]["word"] != "<SP>":
            j += 1
            parts.append(tokens[j]["word"].rstrip("-"))
        clean = "".join(ch for ch in "".join(parts).lower() if ch.isalpha() or ch == "'")
        phones = [p for p in g2p(clean) if p.strip() and p not in (" ", "'")] or ["AH0"]
        sy = syllables(phones)
        n = j - i + 1
        if n == 1:
            groups = [phones]
        else:                                       # 음절 수 ≠ 음표 수면 앞에서부터 고르게 합침
            k = len(sy)
            groups = [sum(sy[int(a * k / n): int((a + 1) * k / n)] or [[sy[min(a, k - 1)][-1]]], []) for a in range(n)]
        for a in range(n):
            out[i + a] = "en_" + "-".join(groups[a])
        i = j + 1
    for i, o in enumerate(out):                    # 멜리스마 = 앞 음표의 마지막 모음
        if o is None:
            prev = next((out[k] for k in range(i - 1, -1, -1) if out[k] and out[k] != "<SP>"), "en_AH0")
            vow = [p for p in prev[3:].split("-") if _is_vowel(p)] or ["AH0"]
            out[i] = "en_" + vow[-1]
    return out


def preroll(tokens, phonemes, ms_per_cons=35, min_frames=2):
    """음절 첫 자음들을 박보다 조금 앞에 — 모음이 박 위에 떨어지게. 앞 토큰에서 시간을 빌린다.
    짧은 음표(프레임 < 음소+3)는 앞 음표에서 더 빌려서 음소가 빠지지 않게."""
    secs = [t["seconds"] for t in tokens]
    for i in range(1, len(tokens)):
        ph = phonemes[i]
        if not ph.startswith("en_"):
            continue
        parts = ph[3:].split("-")
        onset = 0
        for x in parts:
            if _is_vowel(x):
                break
            onset += 1
        need = onset * ms_per_cons / 1000.0
        short = len(parts) + 3 - secs[i] * FPS
        if short > 0:
            need += short / FPS
        give = max(0.0, secs[i - 1] - min_frames / FPS - (len(phonemes[i - 1][3:].split("-")) + 1) / FPS
                   if phonemes[i - 1].startswith("en_") else secs[i - 1] - 0.04)
        d = min(need, give)
        if d > 0:
            secs[i - 1] -= d
            secs[i] += d
    for t, s_ in zip(tokens, secs):
        t["seconds"] = round(s_, 4)
    return tokens


def main(req_path):
    req = json.load(open(req_path, encoding="utf-8"))
    from preprocess.tools.g2p import g2p_transform

    words = [t["word"] for t in req["tokens"]]
    if req.get("language", "English") == "English" and req.get("syllabify", True):
        phonemes = english_phonemes(req["tokens"])
        if req.get("preroll", False):
            preroll(req["tokens"], phonemes)
        words = [w.rstrip("-") or w for w in words]
    else:
        phonemes = g2p_transform(words, req.get("language", "English"))
    total_ms = int(round(sum(t["seconds"] for t in req["tokens"]) * 1000))
    meta = [{
        "index": f"vocal_0_{total_ms}",
        "language": req.get("language", "English"),
        "time": [0, total_ms],
        "duration": " ".join(f"{t['seconds']:.3f}" for t in req["tokens"]),
        "text": " ".join(words),
        "phoneme": " ".join(phonemes),
        "note_pitch": " ".join(str(t["pitch"]) for t in req["tokens"]),
        "note_type": " ".join(str(t["type"]) for t in req["tokens"]),
        "f0": " ".join(f"{x:.1f}" for x in req.get("f0", [])),
    }]
    os.makedirs(req["save_dir"], exist_ok=True)
    target = os.path.join(req["save_dir"], "target.json")
    json.dump(meta, open(target, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    cmd = [sys.executable, "-m", "cli.inference", "--device", "cuda",
           "--model_path", "pretrained_models/SoulX-Singer/model.pt",
           "--config", "soulxsinger/config/soulxsinger.yaml",
           "--prompt_wav_path", req["prompt_wav"], "--prompt_metadata_path", req["prompt_json"],
           "--target_metadata_path", target, "--phoneset_path", "soulxsinger/utils/phoneme/phone_set.json",
           "--save_dir", req["save_dir"], "--pitch_shift", str(req.get("pitch_shift", 0)),
           "--control", req.get("control", "melody"), "--fp16"]
    env = {**os.environ, "PYTHONPATH": HERE, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
    r = subprocess.run(cmd, cwd=HERE, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        sys.stderr.write(r.stdout[-3000:] + "\n" + r.stderr[-3000:])
        sys.exit(r.returncode)
    print(json.dumps({"wav": os.path.join(req["save_dir"], "generated.wav"), "target": target}))


if __name__ == "__main__":
    main(sys.argv[1])
