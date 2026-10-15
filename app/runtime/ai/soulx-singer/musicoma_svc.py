"""Musicoma ↔ SoulX-Singer-SVC (Apache-2.0). 또렷한 가이드(말소리를 음표 길이에 맞춘 것) + 목표 f0 → 노래.

python musicoma_svc.py request.json
request = {"prompt_wav", "target_wav", "target_f0": [Hz per 20ms], "save_dir", "n_steps"?, "cfg"?, "pitch_shift"?}
"""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def f0_of(wav_path, sr=24000):
    import librosa
    import pyworld as pw
    y, _ = librosa.load(wav_path, sr=sr, mono=True)
    f0, t = pw.harvest(y.astype(np.float64), sr, frame_period=20.0, f0_floor=60, f0_ceil=1100)
    return f0.astype(np.float32)


def main(req_path):
    req = json.load(open(req_path, encoding="utf-8"))
    os.makedirs(req["save_dir"], exist_ok=True)
    pf0 = os.path.join(req["save_dir"], "prompt_f0.npy")
    tf0 = os.path.join(req["save_dir"], "target_f0.npy")
    np.save(pf0, f0_of(req["prompt_wav"]))
    np.save(tf0, np.asarray(req["target_f0"], dtype=np.float32))
    import subprocess
    cmd = [sys.executable, "-m", "cli.inference_svc", "--device", "cuda",
           "--model_path", "pretrained_models/SoulX-Singer/model-svc.pt",
           "--config", "soulxsinger/config/soulxsinger.yaml",
           "--prompt_wav_path", req["prompt_wav"], "--target_wav_path", req["target_wav"],
           "--prompt_f0_path", pf0, "--target_f0_path", tf0, "--save_dir", req["save_dir"],
           "--pitch_shift", str(req.get("pitch_shift", 0)), "--n_steps", str(req.get("n_steps", 32)),
           "--cfg", str(req.get("cfg", 3.0)), "--fp16"]
    env = {**os.environ, "PYTHONPATH": HERE, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
    r = subprocess.run(cmd, cwd=HERE, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        sys.stderr.write(r.stdout[-3000:] + "\n" + r.stderr[-3000:])
        sys.exit(r.returncode)
    print(json.dumps({"wav": os.path.join(req["save_dir"], "generated.wav")}))


if __name__ == "__main__":
    main(sys.argv[1])
