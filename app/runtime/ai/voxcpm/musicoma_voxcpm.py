"""Musicoma ↔ VoxCPM2 다리. 요청 JSON(작업 목록)을 받아 모델을 한 번만 올리고 전부 생성한다.

요청: {"jobs": [{"text": "(설명)문장", "out": "a.wav", "seed": 1, "reference": "ref.wav"|null,
                  "cfg": 2.0, "steps": 10}]}
출력: 마지막 줄 JSON {"done": [{"out", "seconds"}]}

    python musicoma_voxcpm.py req.json      한 번 돌고 끝(옛 방식)
    python musicoma_voxcpm.py --serve       상주: 모델을 한 번 올린 뒤 표준입력 한 줄 = 요청 JSON, "quit" 이면 끝
                                            (10-17 속도 개선 — 호출마다 모델 로드 약 20초가 0 으로)
"""
import json
import sys

import soundfile as sf
import torch
from voxcpm import VoxCPM


def run(m, jobs):
    sr = m.tts_model.sample_rate
    done = []
    for j in jobs:
        torch.manual_seed(int(j.get("seed", 0)))
        kw = {}
        if j.get("reference"):
            kw["reference_wav_path"] = j["reference"]
        wav = m.generate(text=j["text"], cfg_value=float(j.get("cfg", 2.0)),
                         inference_timesteps=int(j.get("steps", 10)), **kw)
        sf.write(j["out"], wav, sr, subtype="PCM_24")
        done.append({"out": j["out"], "seconds": round(len(wav) / sr, 3)})
        print(json.dumps({"progress": len(done), "of": len(jobs)}), flush=True)
    print(json.dumps({"done": done, "sample_rate": sr}, ensure_ascii=False), flush=True)


def load():
    return VoxCPM.from_pretrained("openbmb/VoxCPM2", load_denoiser=False)


def serve():
    m = load()
    print(json.dumps({"ready": True}), flush=True)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        if line == "quit":
            break
        try:
            run(m, json.loads(line)["jobs"])
        except Exception as ex:                    # 한 요청이 실패해도 상주는 유지
            print(json.dumps({"error": f"{type(ex).__name__}: {ex}"}, ensure_ascii=False), flush=True)


def main(req_path):
    req = json.load(open(req_path, encoding="utf-8"))
    run(load(), req["jobs"])


if __name__ == "__main__":
    serve() if sys.argv[1] == "--serve" else main(sys.argv[1])
