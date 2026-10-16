"""지식 — 장르 카드, 소리 카탈로그, 미세조정 어휘집을 읽고 찾는다."""
import difflib
import glob
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent


def _load(p):
    return yaml.safe_load(Path(p).read_text(encoding="utf-8"))


def styles():
    return {Path(p).stem: _load(p) for p in sorted(glob.glob(str(HERE / "styles/*.yaml")))}


def find_style(text):
    """'올드칸예 스타일에 시티팝 샘플링' → 관련 장르 카드들(점수순)."""
    t = text.lower().replace(" ", "")
    hits = []
    for sid, s in styles().items():
        score = 0
        for a in [sid, s.get("name", "")] + s.get("aliases", []):
            a2 = str(a).lower().replace(" ", "")
            if a2 and a2 in t:
                score += 3 + len(a2) / 10
        if score:
            hits.append((score, sid))
    if not hits:
        names = {str(a).lower(): sid for sid, s in styles().items() for a in s.get("aliases", []) + [sid]}
        for w in text.lower().split():
            for m in difflib.get_close_matches(w, names.keys(), n=1, cutoff=0.75):
                hits.append((1, names[m]))
    best = {}
    for sc, sid in hits:
        best[sid] = max(best.get(sid, 0), sc)
    return [sid for sid, _ in sorted(best.items(), key=lambda x: -x[1])]


def style(sid):
    return _load(HERE / f"styles/{sid}.yaml")


def sounds():
    cat = _load(HERE / "sounds.yaml")
    user = HERE / "sounds_user.yaml"            # AI 가 즉석에서 받은 팩(packs.add_from_url) — 역할 이름으로 합친다
    if user.exists():
        u = _load(user) or {}
        cat.setdefault("sfz", {}).update(u.get("sfz") or {})
    return cat


def tweaks():
    return _load(HERE / "tweaks.yaml")


def find_tweak(text):
    """사람 말 → 어휘집에서 맞는 조작들."""
    t = text.lower()
    out = []
    for group, items in tweaks().items():
        for it in items:
            for s in it["say"]:
                words = str(s).lower().split()
                # 구절의 단어가 모두 들어 있으면(사이에 '좀 더' 같은 말이 끼어도) 맞은 것으로
                if all(w in t for w in words):
                    out.append({"group": group, "matched": s, "do": it["do"]})
                    break
    return out


def resolve_sound(name):
    """역할 이름(piano_grand, rhodes, bass_sub, strings_violins...) → 엔진에 넣을 방법.

    돌려주는 것: {"device": "sfz", "sfz": path} | {"device": "Surge XT", "patch": fxp} | {"device": <vst3 이름>}
    """
    if name.startswith("dexed:"):                 # 우리가 잡은 FM 패치(musicoma/fm_patches.py)
        return {"device": "Dexed", "preset": str(ROOT / "sounds" / "presets" / "Dexed" / (name.split(":", 1)[1] + ".xml"))}
    cat = sounds()
    if name in cat["sfz"]:
        e = cat["sfz"][name]
        p = ROOT / e["path"]
        if not p.exists() and "musicoma-phonk" in e["path"]:     # 자체 합성 소리 — 받을 필요 없이 처음 쓸 때 만든다(설치판 첫 사용)
            from .. import kits
            kits.make_phonk(ROOT / "sounds" / "sfz" / "musicoma-phonk")
        return {"device": "sfz", "sfz": str(p), "map": e.get("map")}
    sx = cat["surge_xt"]
    if name in sx and name != "root":
        return {"device": "Surge XT", "patch": str(ROOT / sx["root"] / sx[name][0]), "alternatives": sx[name][1:]}
    # 'Keys/EP 2' 처럼 패치 직접 지정
    patch = ROOT / sx["root"] / (name if name.endswith(".fxp") else name + ".fxp")
    if patch.exists():
        return {"device": "Surge XT", "patch": str(patch)}
    # sfz 경로 직접 지정
    if name.endswith(".sfz"):
        p = Path(name) if Path(name).is_absolute() else ROOT / name
        return {"device": "sfz", "sfz": str(p)}
    # VSCO 파일 이름
    v = ROOT / "sounds/sfz/vsco2-ce" / (name + ".sfz")
    if v.exists():
        return {"device": "sfz", "sfz": str(v)}
    return {"device": name}


def presets():
    return _load(HERE / "presets.yaml")
