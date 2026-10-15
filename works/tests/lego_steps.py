"""생성 스텝 수 실험(10-15): 50 / 30 / 20 스텝에서 같은 시드로 통과율·시간 비교. Coffee Rings 3구간 × 6테이크."""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import musicoma_008_coffee_rings as cr
from musicoma import lego, layout

guide = lego.render_guide(cr.spec)
secs = [s for s in cr.rap_sections() if s["name"] in ("verse_a", "verse_b", "hook1")]
caption = ("male rap vocals, english, upbeat jazz hip-hop, conversational storytelling flow, smooth and clear, "
           "slightly behind the beat, warm mid-range voice")
for steps in [int(x) for x in (sys.argv[1:] or ["50", "30", "20"])]:
    t = time.time()
    _, rep = lego.vocal_track(guide, secs, cr.BPM, cr.KEY, caption, layout.scratch("lego-steps", f"s{steps}.wav"), takes=6,
                              guide_wav=guide, pass_wer=0.3, min_key_fit=0.0, enough=0, steps=steps, log=lambda m: None)
    dt = time.time() - t
    for x in rep:
        ws = [r["wer"] for r in x["takes"]]
        sims = [r["voice_sim"] for r in x["takes"] if r["voice_sim"] is not None]
        print(f"steps {steps} {x['section']:8s} pass {sum(w <= 0.3 for w in ws)}/6 best {min(ws):.3f} "
              f"sim {max(sims) if sims else '-'}", flush=True)
    print(f"steps {steps}: {dt:.0f}s for {sum(len(x['takes']) for x in rep)} takes", flush=True)
