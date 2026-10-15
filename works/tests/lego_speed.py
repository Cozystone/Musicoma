"""보컬 생성 속도 측정(10-15). Coffee Rings 랩을 새 방식(상주 모델 · 조기 멈춤 · 생성/채점 겹치기)으로 다시 만들어 시간을 잰다.
이전: 7구간 × 10테이크, 21:06:35 → 21:29:22 = 22분 47초."""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import musicoma_008_coffee_rings as cr
from musicoma import lego, layout

t0 = time.time()
guide = lego.render_guide(cr.spec)
t1 = time.time()
caption = ("male rap vocals, english, upbeat jazz hip-hop, conversational storytelling flow, smooth and clear, "
           "slightly behind the beat, warm mid-range voice")
out = layout.scratch("lego-speed", "rap_fast.wav")
vox, rep = lego.vocal_track(guide, cr.rap_sections(), cr.BPM, cr.KEY, caption, out, takes=10, guide_wav=guide,
                            pass_wer=0.3, min_key_fit=0.0,
                            log=lambda m: print(f"{time.time() - t0:7.1f}s {m}", flush=True))
t2 = time.time()
for x in rep:
    print(x["section"], "seed", x["chosen"], "takes", len(x["takes"]), "wer", x["wer"], "sim", x["voice_sim"])
print(f"guide {t1 - t0:.0f}s · vocals {t2 - t1:.0f}s · total {t2 - t0:.0f}s · takes {sum(len(x['takes']) for x in rep)}")
