"""Musicoma: 말/노래 샘플의 단어 정렬(Musicoma 쪽 ASR) → SoulX 프롬프트 메타데이터. (NeMo 없이)
python musicoma_prompt.py req.json   req = {"out", "language", "time":[ms0,ms1], "tokens":[{word,pitch,seconds,type}], "f0":[...]}"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from preprocess.tools.g2p import g2p_transform
req = json.load(open(sys.argv[1], encoding="utf-8"))
words = [t["word"] for t in req["tokens"]]
meta = [{"index": f"vocal_{req['time'][0]}_{req['time'][1]}", "language": req["language"], "time": req["time"],
         "duration": " ".join(f"{t['seconds']:.2f}" for t in req["tokens"]), "text": " ".join(words),
         "phoneme": " ".join(g2p_transform(words, req["language"])),
         "note_pitch": " ".join(str(t["pitch"]) for t in req["tokens"]),
         "note_type": " ".join(str(t["type"]) for t in req["tokens"]),
         "f0": " ".join(f"{x:.1f}" for x in req["f0"])}]
json.dump(meta, open(req["out"], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps({"ok": req["out"]}))
