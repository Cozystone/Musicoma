"""새 엔진이 골든(옛 엔진 응답)과 같은 '모양'으로 답하는지 — 골든의 명령을 같은 순서로 다시 보내고
응답의 키·자료형을 재귀 비교한다(값·경로·플러그인 개수 같은 차이는 무시).

    .venv/Scripts/python tests/golden/check_protocol.py [port=47811] [--skip vst,fx]
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from musicoma.engine import Engine, EngineError  # noqa: E402

GOLD = json.loads(Path(__file__).with_name("protocol.json").read_text(encoding="utf-8"))
port = int(next((a for a in sys.argv[1:] if a.isdigit()), 47811))
skip = set(next((a.split("=", 1)[1].split(",") for a in sys.argv[1:] if a.startswith("--skip=")), []))
VST = ("Surge", "Dexed", "Dragonfly")
FX = ("eq", "compressor", "reverb", "delay", "chorus", "phaser", "lowpass", "pitchshift")


def kind(v):
    if isinstance(v, bool):
        return "bool"
    if isinstance(v, (int, float)):
        return "num"
    if isinstance(v, str):
        return "str"
    if isinstance(v, list):
        return "list"
    if isinstance(v, dict):
        return "dict"
    return "null"


def diff(a, b, path="", out=None):
    out = [] if out is None else out
    if kind(a) != kind(b):
        out.append(f"{path}: {kind(a)} != {kind(b)}")
        return out
    if isinstance(a, dict):
        for k in a:
            if k not in b:
                out.append(f"{path}.{k}: missing")
            else:
                diff(a[k], b[k], f"{path}.{k}", out)
    elif isinstance(a, list) and a and b:
        diff(a[0], b[0], f"{path}[0]", out)
    return out


def involves(call, names):
    s = json.dumps(call["params"], ensure_ascii=False)
    return any(n in s for n in names)


e = Engine(port=port, client="check")
ok = bad = skipped = 0
for c in GOLD["calls"]:
    m, p = c["method"], c["params"]
    if ("vst" in skip and (involves(c, VST) or p.get("track") in ("Synth", "FM", "Hall"))) or \
       ("fx" in skip and (p.get("track") == "FX" or p.get("device") in FX or (p.get("track") == "master" and m == "device.add"))):
        skipped += 1
        continue
    if m == "edit.new":
        p = {**p, "name": p.get("name", "x") + "-new"}
    if m == "render" and "path" in p:                     # 골든 파일을 덮어쓰지 않게
        p = {**p, "path": str(Path(p["path"]).parent / "new" / Path(p["path"]).name)}
    try:
        r = e.call(m, p)
        good = True
    except EngineError as ex:
        r, good = str(ex), False
    if c["ok"] != good:
        bad += 1
        print(f"FAIL {m} {json.dumps(p, ensure_ascii=False)[:90]} → ok={good} (golden ok={c['ok']}): {str(r)[:160]}")
        continue
    d = diff(c.get("result"), r) if good else []
    if d:
        bad += 1
        print(f"SHAPE {m}: " + "; ".join(d[:6]))
    else:
        ok += 1
print(f"\n{ok} same shape · {bad} different · {skipped} skipped")
