"""기기 사양 → AI 모델 선택(10-17 본인 요청 "설치 때 사양 확인해서 적합한 걸로, 낮으면 대체").

    hardware.info()         {"gpu": "NVIDIA GeForce RTX 5080", "vram_mb": 16303, "ram_gb": 61, "cuda": True}
    hardware.ace_profile()  ACE-Step 1.5 설정: {"model", "offload", "quantization", "tier", "note"}
                            (config/ai.json 에 {"ace": {...}} 를 두면 그게 우선 — 사용자가 직접 고르는 길)
기준은 ACE-Step 1.5 XL 모델 카드의 단계(24 GB 풀 / 20 GB 오프로드 없이 / 16 GB 오프로드 / 12 GB 오프로드+INT8).
lego(반주를 듣고 부르기)는 XL base 만 되므로 12 GB 아래에선 노래 생성을 끄고(랩·TTS 는 VoxCPM 으로) 안내한다.
"""
import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OVERRIDE = ROOT / "config" / "ai.json"


def info():
    out = {"gpu": None, "vram_mb": 0, "ram_gb": 0, "cuda": False}
    try:
        import psutil
        out["ram_gb"] = round(psutil.virtual_memory().total / 2 ** 30)
    except Exception:
        pass
    smi = shutil.which("nvidia-smi")
    if smi:
        try:
            r = subprocess.run([smi, "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
                               capture_output=True, text=True, timeout=8, stdin=subprocess.DEVNULL)
            line = (r.stdout or "").strip().splitlines()
            if line:
                name, mem = [x.strip() for x in line[0].split(",")[:2]]
                out.update({"gpu": name, "vram_mb": int(float(mem)), "cuda": True})
        except Exception:
            pass
    return out


TIERS = [
    # (최소 VRAM MB, tier, 설정)
    (23000, "full",     {"model": "acestep-v15-xl-base", "offload": False, "quantization": None}),
    (19000, "no-offload", {"model": "acestep-v15-xl-base", "offload": False, "quantization": "int8_weight_only"}),
    (15000, "offload",  {"model": "acestep-v15-xl-base", "offload": True, "quantization": "int8_weight_only"}),
    (11000, "offload-int8", {"model": "acestep-v15-xl-base", "offload": True, "quantization": "int8_weight_only"}),
]


def ace_profile(hw=None):
    if OVERRIDE.exists():
        try:
            o = json.loads(OVERRIDE.read_text(encoding="utf-8")).get("ace")
            if o and o.get("model"):
                return {**o, "tier": "user", "note": f"사용자 설정({OVERRIDE.name})"}
        except Exception:
            pass
    hw = hw or info()
    v = hw["vram_mb"]
    if not hw["cuda"] or v < 11000:
        return {"model": None, "offload": True, "quantization": None, "tier": "none", "hw": hw,
                "note": ("NVIDIA GPU 없음" if not hw["cuda"] else f"VRAM {v // 1024} GB") +
                        " — ACE-Step(노래 생성)은 12 GB 이상 필요. 랩·말하기(VoxCPM)와 악기 연주는 그대로 되고, 노래는 SoulX-Singer 로"}
    for mn, tier, cfg in TIERS:
        if v >= mn:
            notes = {"full": "풀 품질(오프로드·양자화 없음)", "no-offload": "오프로드 없이, INT8",
                     "offload": "CPU 오프로드 + INT8(구간당 생성 약 25초)", "offload-int8": "CPU 오프로드 + INT8 — 느리지만 됨"}
            return {**cfg, "tier": tier, "hw": hw, "note": f"{hw['gpu']} {v // 1024} GB → ACE-Step XL, {notes[tier]}"}
    return {"model": None, "tier": "none", "hw": hw, "note": "분류 실패"}
