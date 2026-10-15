"""009 NG 구간만 다시 녹음(10-16): chorus1·chorus2 오류율 0.83·0.57 → 그 구간만 retake, 나머지 보컬은 그대로."""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from musicoma import lego, arrange

state = Path(arrange.ROOT) / "projects" / "musicoma-009-half-past-three" / "vocals" / "vox.json"
t0 = time.time()
for sec in sys.argv[1:] or ["chorus1", "chorus2"]:
    r = lego.retake(state, sec, takes=12, enough=2, log=lambda m: print(f"{time.time() - t0:5.0f}s {m}", flush=True))
    print(f"{time.time() - t0:5.0f}s RESULT {sec} seed {r['chosen']} wer {r['wer']} sim {r['voice_sim']}", flush=True)
