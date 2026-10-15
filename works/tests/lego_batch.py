"""배치 생성 실험(10-15): 같은 구간 6테이크를 batch 1 / 2 / 3 으로. 시간·VRAM."""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from musicoma import lego, layout

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import musicoma_008_coffee_rings as cr

work = layout.scratch("lego-batch", ".work")
sec = [x for x in cr.rap_sections() if x["name"] == "hook1"][0]
beat = Path(lego.ROOT) / "scratch/lego-steps/.work/s50_lego/02_hook1_beat.wav"
c0 = max(0.0, sec["start"] - lego.CONTEXT)
ref = sorted((Path(lego.ROOT) / "scratch/lego-steps/.work/s50_lego").glob("00_verse_a/seed*/vocals.wav"))[0]
base = {"beat": str(beat), "lyrics": f"[{sec.get('tag', 'Chorus')}]\n{sec['lyrics']}", "reference": str(ref),
        "caption": "male rap vocals, english, upbeat jazz hip-hop, conversational storytelling flow, smooth and clear",
        "bpm": cr.BPM, "key": cr.KEY, "start": round(sec["start"] - c0, 3), "end": round(sec["end"] - c0, 3), "track": "vocals",
        "steps": 50, "model": "acestep-v15-xl-base", "offload": True, "quantization": "int8_weight_only", "vocal_language": "en"}
srv = lego.server({k: base[k] for k in ("model", "offload", "quantization")}, work)
for n in (1, 2, 3):
    t = time.time()
    srv.submit({**base, "seeds": [9001, 9002, 9003, 9004, 9005, 9006], "batch": n, "out_dir": str(work / f"b{n}")})
    files = srv.result()
    print(f"batch {n}: {len(files)} takes in {time.time() - t:.1f}s", flush=True)
srv.close()
