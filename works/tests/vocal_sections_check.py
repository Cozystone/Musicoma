"""구간별 보컬(10-15) 검사: 기존 Coffee Rings 보컬 기록을 새 형식으로 옮기고, 구간 클립의 합 = 예전 전체 보컬인지(널 테스트)."""
import json
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import musicoma_008_coffee_rings as cr
from musicoma import lego, layout

root = Path(lego.ROOT) / "projects" / cr.NAME
old = json.loads((root / "vocals" / "rap_lego.json").read_text(encoding="utf-8"))
guide = Path(lego.ROOT) / "projects" / (cr.NAME + "-guide") / "guide_stems.wav"
info = sf.info(str(guide))
secs = {s["name"]: s for s in cr.rap_sections()}
out = layout.scratch("vocal-sections", "rap_lego.json")
st = {"engine": old["engine"], "caption": old["caption"], "bpm": cr.BPM, "key": cr.KEY, "lang": "en", "track": "vocals",
      "guide": str(guide), "work": str(out.parent / ".work"), "pass_wer": 0.3, "min_key_fit": 0.0, "steps": 50,
      "sr": info.samplerate, "length": info.frames, "sections": []}
for x in old["sections"]:
    best = next(r for r in x["takes"] if r["seed"] == x["chosen"])
    for r in x["takes"]:
        r["pass"] = r["wer"] <= 0.3
    st["sections"].append({**secs[x["section"]], "chosen": x["chosen"], "wer": x["wer"], "key_fit": x["key_fit"],
                           "voice_sim": x["voice_sim"], "vox": best["vox"], "takes": x["takes"]})
st["ref_vox"] = st["sections"][0]["vox"]
st = lego._write(st, out)
a, sr = sf.read(st["full"], dtype="float32")
b, _ = sf.read(str(root / "vocals" / "rap_lego.wav"), dtype="float32")
n = min(len(a), len(b))
diff = 20 * np.log10(np.sqrt(np.mean((a[:n] - b[:n]) ** 2)) / (np.sqrt(np.mean(b[:n] ** 2)) + 1e-12) + 1e-12)
print("sections", [(s["name"], Path(s["file"]).name, s["place_s"]) for s in st["sections"]])
print("takes kept", sum(len([r for r in s["takes"] if r.get("file")]) for s in st["sections"]))
print(f"null vs old full vocal: {diff:.1f} dB", "OK" if diff < -60 else "FAIL")
# 다른 테이크로 바꾸기
alt = next(r for r in st["sections"][2]["takes"] if r.get("pass") and r["seed"] != st["sections"][2]["chosen"])
r = lego.use_take(out, st["sections"][2]["name"], alt["seed"])
print("use_take", r["section"], r["chosen"], "OK" if lego.takes_list(out)[2]["chosen"] == alt["seed"] else "FAIL")
