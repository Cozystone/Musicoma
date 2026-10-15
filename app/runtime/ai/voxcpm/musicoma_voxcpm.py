"""Musicoma ↔ VoxCPM2 다리. 요청 JSON(작업 목록)을 받아 모델을 한 번만 올리고 전부 생성한다.

요청: {"jobs": [{"text": "(설명)문장", "out": "a.wav", "seed": 1, "reference": "ref.wav"|null,
                  "cfg": 2.0, "steps": 10}]}
출력: 마지막 줄 JSON {"done": [{"out", "seconds"}]}
"""
import json
import sys

import soundfile as sf
import torch
from voxcpm import VoxCPM


def main(req_path):
    req = json.load(open(req_path, encoding="utf-8"))
    m = VoxCPM.from_pretrained("openbmb/VoxCPM2", load_denoiser=False)
    sr = m.tts_model.sample_rate
    done = []
    for j in req["jobs"]:
        torch.manual_seed(int(j.get("seed", 0)))
        kw = {}
        if j.get("reference"):
            kw["reference_wav_path"] = j["reference"]
        wav = m.generate(text=j["text"], cfg_value=float(j.get("cfg", 2.0)),
                         inference_timesteps=int(j.get("steps", 10)), **kw)
        sf.write(j["out"], wav, sr, subtype="PCM_24")
        done.append({"out": j["out"], "seconds": round(len(wav) / sr, 3)})
        print(json.dumps({"progress": len(done), "of": len(req["jobs"])}), flush=True)
    print(json.dumps({"done": done, "sample_rate": sr}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main(sys.argv[1])
