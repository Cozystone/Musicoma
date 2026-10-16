"""FM 패치 — Dexed(DX7 호환 신스, GPL)에 우리가 직접 잡은 음색. 공장 ROM 데이터는 쓰지 않는다(값은 이 파일이 원본).

    build("city_ep")          → Dexed 파라미터(정규화) dict
    install_all(engine)       → sounds/presets/Dexed/<이름>.xml 로 저장(설계서 sound: "dexed:city_ep")

DX7 단위로 적고 여기서 0..1 로 바꾼다: 알고리즘 1~32, 피드백 0~7, EG 0~99, 출력 0~99, 비율 0~31, 디튠 -7~+7, 벨로시티 0~7.
"""

def _op(n, rates, levels, out, coarse=1, fine=0, detune=0, vel=0, rate_scale=0):
    p = {}
    for i, r in enumerate(rates, 1):
        p[f"OP{n} EG RATE {i}"] = r / 99
    for i, l in enumerate(levels, 1):
        p[f"OP{n} EG LEVEL {i}"] = l / 99
    p.update({f"OP{n} OUTPUT LEVEL": out / 99, f"OP{n} MODE": 0.0, f"OP{n} F COARSE": coarse / 31,
              f"OP{n} F FINE": fine / 99, f"OP{n} OSC DETUNE": (detune + 7) / 14, f"OP{n} KEY VELOCITY": vel / 7,
              f"OP{n} RATE SCALING": rate_scale / 7, f"OP{n} SWITCH": 1.0})
    return p


PATCHES = {
    # 80년대 FM 일렉피아노(시티팝·AOR 발라드의 반짝이는 건반). 알고리즘 5 = 세 쌍(2→1, 4→3, 6→5).
    # 1·2 = 몸통(따뜻, 세게 치면 '짝' 하는 바크) · 3·4 = 높은 틴(14배, 아주 빨리 사라짐) · 5·6 = 살짝 어긋난 두께
    "city_ep": {
        "ALGORITHM": (5 - 1) / 31, "FEEDBACK": 5 / 7, "OSC KEY SYNC": 1.0, "TRANSPOSE": 24 / 48,
        "LFO SPEED": 0.35, "LFO PM DEPTH": 0.0, "LFO AM DEPTH": 0.0, "Cutoff": 1.0, "Resonance": 0.0, "Output": 0.9,
        **_op(1, (95, 29, 20, 50), (99, 95, 0, 0), 99, coarse=1, detune=-2, vel=2, rate_scale=3),
        **_op(2, (95, 50, 35, 78), (99, 75, 0, 0), 78, coarse=1, vel=4, rate_scale=3),
        **_op(3, (95, 20, 20, 50), (99, 95, 0, 0), 92, coarse=1, detune=2, vel=2, rate_scale=3),
        **_op(4, (95, 70, 60, 78), (99, 40, 0, 0), 82, coarse=14, vel=4, rate_scale=4),
        **_op(5, (95, 25, 25, 55), (99, 92, 0, 0), 80, coarse=1, detune=1, vel=2, rate_scale=3),
        **_op(6, (95, 40, 25, 60), (99, 70, 0, 0), 70, coarse=1, vel=4, rate_scale=3),
    },
    # 맑은 FM 벨 패드(후렴 반짝임) — 알고리즘 5, 높은 비율 모듈레이터
    "city_bell": {
        "ALGORITHM": (5 - 1) / 31, "FEEDBACK": 3 / 7, "OSC KEY SYNC": 1.0, "TRANSPOSE": 24 / 48, "Output": 0.8,
        "Cutoff": 1.0, "Resonance": 0.0,
        **_op(1, (99, 30, 25, 40), (99, 80, 50, 0), 95, coarse=1, vel=3),
        **_op(2, (99, 45, 30, 50), (99, 60, 30, 0), 60, coarse=3, vel=5),
        **_op(3, (99, 30, 25, 40), (99, 80, 50, 0), 85, coarse=1, detune=3, vel=3),
        **_op(4, (99, 60, 40, 50), (99, 40, 20, 0), 55, coarse=7, vel=6),
        **_op(5, (80, 30, 25, 35), (99, 85, 60, 0), 70, coarse=2, detune=-3, vel=2),
        **_op(6, (99, 50, 35, 50), (99, 50, 0, 0), 45, coarse=1, vel=5),
    },
}


def install(e, name, track="__fm", device_name="Dexed"):
    """엔진에 Dexed 하나 올려 값을 넣고 프리셋 파일로 저장. 반환: 파일 경로."""
    tracks = [t["name"] for t in e.call("edit.info")["tracks"]]
    if track not in tracks:
        e.call("track.add", {"name": track})
    d = e.call("device.add", {"track": track, "device": device_name})["device"]
    e.call("device.set", {"track": track, "device": d, "params": PATCHES[name]})
    r = e.call("device.preset_save", {"track": track, "device": d, "name": name})
    e.call("device.remove", {"track": track, "device": d})
    return r["path"]


def install_all(e):
    """작업용 빈 편집에서 모든 패치를 저장(현재 곡을 건드리지 않게 scratch 편집을 연다)."""
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    e.call("edit.new", {"path": str(root / "scratch" / "fm_install.edit.json")})
    return {n: install(e, n) for n in PATCHES}
