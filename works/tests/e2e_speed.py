"""곡 전체 속도(10-15): 가이드 → [보컬 생성 ∥ 반주 빌드+밸런스] → 보컬 트랙만 재서 맞춤 → 렌더.
Coffee Rings 설계서를 다른 이름으로 지어 원래 곡은 건드리지 않는다(끝나면 scratch/ 로 옮김)."""
import copy
import shutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import musicoma_008_coffee_rings as cr
from musicoma import arrange, lego, layout

t0 = time.time()
stamp = lambda: f"{time.time() - t0:6.0f}s"
spec = copy.deepcopy(cr.spec)
spec["name"] = "speedtest-coffee-rings"
root = Path(arrange.ROOT) / "projects" / spec["name"]
guide = lego.render_guide(spec)
print(stamp(), "guide", flush=True)
caption = ("male rap vocals, english, upbeat jazz hip-hop, conversational storytelling flow, smooth and clear, "
           "slightly behind the beat, warm mid-range voice")
out = root / "vocals" / "rap.wav"
pool = ThreadPoolExecutor(1)
fut = pool.submit(lego.vocal_track, guide, cr.rap_sections(), cr.BPM, cr.KEY, caption, out, takes=9, guide_wav=guide,
                  pass_wer=0.3, min_key_fit=0.0, log=lambda m: print(stamp(), m, flush=True))
spec["tracks"]["Rap"] = {"role": "rap vocal (generated over the arrangement)", "sends": {"0": -20},
                         "fx": [{"device": "eq", "params": {"Low-pass freq": 110, "Low-pass gain": -6, "Mid freq 2": 3200, "Mid gain 2": 1.5}},
                                {"device": "compressor", "params": {"threshold": -20, "ratio": 3, "attack": 8, "release": 100}}]}


def vocals():
    fut.result()
    print(stamp(), "vocals ready", flush=True)
    return {"track": "Rap", "vocal_sections": str(out.with_suffix(".json"))}


s, rep = arrange.build(spec, label="v1", later={"Rap": vocals}, log=lambda m: print(stamp(), m, flush=True))
print(stamp(), "DONE", rep["file"], rep["loudness"]["lufs_integrated"], flush=True)
_, report = fut.result()
print("takes", sum(len(x["takes"]) for x in report), [(x["section"], x["chosen"], x["wer"], x["voice_sim"]) for x in report])
