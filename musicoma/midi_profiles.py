"""MIDI 컨트롤러 자동 연결 — 꽂힌 포트 이름으로 프로필을 찾아, Ableton 의 컨트롤 서피스처럼 한 번에 붙인다(10-17).

    detect(port_names)          → [(port, profile)]   (knowledge/midi_controllers.yaml)
    apply(engine, track, ...)   → 노브 = 고른 트랙의 장치 파라미터(의미 있는 것부터), 페이더 = 트랙 볼륨(왼쪽부터), 트랙 선택
표준 CC(1 모드휠·64 서스테인 등)는 악기로 그대로 간다. 트랜스포트 버튼은 엔진이 CC 로 재생을 바꾸지 않으므로 알려만 준다.
"""
from pathlib import Path

import yaml

YAML = Path(__file__).resolve().parent / "knowledge" / "midi_controllers.yaml"
# 노브에 먼저 붙일 파라미터 — 이름에 이 말이 들어가면 우선(순서대로). Ableton 'best-of bank' 의 축소판
PREFER = ["cutoff", "freq", "reson", "drive", "attack", "decay", "sustain", "release", "mix", "wet", "feedback",
          "rate", "depth", "width", "tone", "gain", "level"]


def load():
    return yaml.safe_load(YAML.read_text(encoding="utf-8"))


def detect(port_names):
    cfg = load()
    out = []
    for port in port_names or []:
        low = (port or "").lower()
        for pr in cfg.get("profiles", []):
            if any(m in low for m in pr["match"]):
                out.append((port, pr))
                break
    return out


def pick_params(params, n):
    """장치 파라미터 중 노브 n 개에 붙일 것 — 선호 이름 먼저, 나머지는 자동화 가능한 순서대로."""
    auto = [p for p in params if p.get("automatable", True)]
    chosen, used = [], set()
    for key in PREFER:
        for p in auto:
            nm = (p.get("name") or p.get("id") or "").lower()
            if key in nm and p["id"] not in used:
                chosen.append(p); used.add(p["id"])
                if len(chosen) >= n:
                    return chosen
    for p in auto:
        if p["id"] not in used:
            chosen.append(p); used.add(p["id"])
            if len(chosen) >= n:
                break
    return chosen


def apply(e, track, profile=None, port_names=None):
    """반환: {profile, knobs:[{cc, device, param}], faders:[{cc, track}], transport, note}"""
    if profile is None:
        hits = detect(port_names if port_names is not None else [d for d in e.call("inputs.list").get("midi", [])])
        profile = hits[0][1] if hits else None
    info = e.call("edit.info")
    tr = next((t for t in info["tracks"] if t["name"] == track), None)
    if not tr:
        raise ValueError(f"트랙 없음: {track}")
    out = {"profile": profile["name"] if profile else "generic(표준 CC 만)", "knobs": [], "faders": [], "transport": None}
    knob_ccs = list((profile or {}).get("knobs") or [])
    if not knob_ccs:                                     # 모르는 장치: 표준 의미 CC 를 장치 파라미터에
        knob_ccs = [74, 71, 1, 91, 7]
    # 노브 → 첫 번째 '파라미터 있는' 장치(악기 우선)의 파라미터
    for di, d in enumerate(tr.get("devices", [])):
        try:
            ps = e.call("device.params", {"track": track, "device": di})["params"]
        except Exception:
            continue
        if not ps:
            continue
        for cc, p in zip(knob_ccs, pick_params(ps, len(knob_ccs))):
            e.call("midi.map", {"cc": cc, "track": track, "device": di, "param": p["id"]})
            out["knobs"].append({"cc": cc, "device": di, "param": p.get("name") or p["id"]})
        break
    # 페이더 → 트랙 볼륨(왼쪽부터 트랙 순서; 마지막 페이더가 하나 남으면 마스터 대신 고른 트랙)
    faders = list((profile or {}).get("faders") or [])
    names = [t["name"] for t in info["tracks"]]
    for cc, name in zip(faders, names):
        e.call("midi.map", {"cc": cc, "track": name, "param": "volume", "min": -60, "max": 6})
        out["faders"].append({"cc": cc, "track": name})
    if profile and profile.get("transport"):
        out["transport"] = {**profile["transport"], "note": "버튼 CC 는 알아만 둔다 — 재생·정지는 대화나 화면에서"}
    e.call("track.select", {"track": track})
    out["note"] = f"'{track}' 선택됨 — 건반은 이 트랙을 연주, 노브 {len(out['knobs'])}개·페이더 {len(out['faders'])}개 연결"
    return out
