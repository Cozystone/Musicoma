"""Musicoma Core (C1) 점검 — 엔진(47800) 없이 돈다.

    .venv/Scripts/python tests/test_core.py

1. core/ 를 빌드한다(실행 파일이 없거나 소스가 더 새로우면).
2. 사인파 샘플로 만든 작은 SFZ + 오디오 클립 + 센드/리턴 + LPF/컴프 계획을 렌더 →
   길이·무음 아님·음높이(440Hz)·좌우 채널을 확인.
3. 쓰는 SFZ 라이브러리(피아노·드럼·베이스)를 자체 파서로 읽어 빠진 샘플이 없는지.
4. (참고) scratch/core/*/engine.wav 가 있으면 널 테스트 수치를 출력 — 실패로 치지 않음.
"""
import json
import math
import struct
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

CORE = ROOT / "core"
EXE = CORE / "build" / "musicoma-core.exe"
TMP = ROOT / "scratch" / "core" / "test"
RESULTS = []


def check(name):
    def deco(fn):
        t0 = time.time()
        try:
            detail = fn()
            RESULTS.append({"test": name, "ok": True, "sec": round(time.time() - t0, 2), "detail": detail})
            print(f"  ok   {name}  {detail if detail is not None else ''}", flush=True)
        except Exception as ex:  # noqa: BLE001
            RESULTS.append({"test": name, "ok": False, "error": f"{type(ex).__name__}: {ex}"})
            print(f"  FAIL {name}: {ex}", flush=True)
        return fn
    return deco


def build_if_needed():
    srcs = list((CORE / "src").glob("*")) + [CORE / "CMakeLists.txt"]
    if EXE.exists() and EXE.stat().st_mtime >= max(p.stat().st_mtime for p in srcs):
        return "up to date"
    p = subprocess.run(["cmd", "/c", str(CORE / "build.bat")], capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    if "BUILD_OK" not in p.stdout:
        raise RuntimeError("core build failed:\n" + (p.stdout + p.stderr)[-3000:])
    return "built"


def write_sine_wav(path, freq=440.0, sr=44100, seconds=1.0):
    n = int(sr * seconds)
    data = b"".join(struct.pack("<h", int(12000 * math.sin(2 * math.pi * freq * i / sr))) for i in range(n))
    hdr = b"RIFF" + struct.pack("<I", 36 + len(data)) + b"WAVE"
    hdr += b"fmt " + struct.pack("<IHHIIHH", 16, 1, 1, sr, sr * 2, 2, 16)
    hdr += b"data" + struct.pack("<I", len(data))
    path.write_bytes(hdr + data)


def tiny_plan():
    TMP.mkdir(parents=True, exist_ok=True)
    write_sine_wav(TMP / "sine440.wav")
    (TMP / "tone.sfz").write_text(
        "// 테스트용 SFZ\n#define $S sine440\n<control> default_path=./\n"
        "<global> ampeg_release=0.05 amp_veltrack=0\n<region> sample=$S.wav pitch_keycenter=a4 lokey=0 hikey=127\n",
        encoding="utf-8")
    sfz = str(TMP / "tone.sfz")
    return {
        "format": "musicoma-render-plan", "version": 1, "bpm": 120.0, "time_sig": "4/4",
        "tempo": [{"beat": 0, "bpm": 120.0}], "length_beats": 4.0,
        "render": {"start_beat": 0, "end_beat": 4.0, "tail_sec": 1.0, "sample_rate": 48000},
        "master": {"volume_db": -3.0, "chain": []},
        "tracks": [
            {"index": 0, "name": "Tone", "volume_db": 0.0, "pan": -0.5, "mute": False, "solo": False,
             "chain": [{"kind": "sfz", "sfz": sfz, "volume_db": 0.0, "enabled": True},
                       {"kind": "send", "bus": 0, "level_db": -12.0, "enabled": True},
                       {"kind": "lowpass", "frequency": 8000.0, "mode": "lowpass", "enabled": True},
                       {"kind": "compressor", "threshold_db": -20, "ratio": 3, "attack_ms": 5, "release_ms": 80,
                        "output_db": 0, "enabled": True}],
             "midi_clips": [{"start_beat": 0, "end_beat": 4, "mute": False,
                             "notes": [{"pitch": 69, "start": 0.0, "length": 1.5, "velocity": 100},
                                       {"pitch": 81, "start": 2.0, "length": 1.0, "velocity": 80}],
                             "cc": [{"cc": 64, "beat": 0.0, "value": 0}], "bend": []}],
             "audio_clips": []},
            {"index": 1, "name": "Clip", "volume_db": -6.0, "pan": 0.5, "mute": False, "solo": False, "chain": [],
             "midi_clips": [],
             "audio_clips": [{"file": str(TMP / "sine440.wav"), "start_beat": 4.0, "start_sec": 2.0, "length_sec": 0.6,
                              "offset_sec": 0.1, "gain_db": -2.0, "pan": 0.0, "fade_in_sec": 0.05, "fade_out_sec": 0.1,
                              "reverse": False, "mute": False}]},
            {"index": 2, "name": "Return", "volume_db": 0.0, "pan": 0.0, "mute": False, "solo": False,
             "chain": [{"kind": "return", "bus": 0, "enabled": True},
                       {"kind": "reverb", "name": "Reverb", "enabled": True}],
             "midi_clips": [], "audio_clips": []},
        ],
    }


def render(plan_path, out, *extra):
    p = subprocess.run([str(EXE), "render", str(plan_path), str(out), *extra], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if p.returncode != 0 or "RENDER_OK" not in p.stdout:
        raise RuntimeError(f"render failed: {p.stderr[-2000:]}")
    return json.loads(p.stdout[: p.stdout.rindex("RENDER_OK")]), p.stderr


@check("core.build")
def _():
    return build_if_needed()


@check("core.render_tiny_plan")
def _():
    plan = tiny_plan()
    pp = TMP / "plan.json"
    pp.write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf-8")
    out = TMP / "out.wav"
    stats, err = render(pp, out)
    x, sr = sf.read(str(out), always_2d=True)
    assert sr == 48000, sr
    assert abs(len(x) - 3 * 48000) <= 1, len(x)                      # 4박@120 = 2초 + 꼬리 1초
    rms = 20 * np.log10(np.sqrt((x ** 2).mean()) + 1e-12)
    assert rms > -40, f"too quiet {rms:.1f} dBFS"
    assert np.abs(x[:, 0]).max() > 0.01 and np.abs(x[:, 1]).max() > 0.01, "a channel is silent"
    # 첫 음 = A4 (440Hz): 0.1~0.6초 스펙트럼 정점
    seg = x[int(0.1 * sr): int(0.6 * sr)].mean(axis=1)
    spec = np.abs(np.fft.rfft(seg * np.hanning(len(seg))))
    peak = np.fft.rfftfreq(len(seg), 1 / sr)[np.argmax(spec)]
    assert abs(peak - 440) < 5, f"pitch {peak:.1f} Hz"
    # 두 번째 음 = A5 (880Hz)
    seg = x[int(1.1 * sr): int(1.4 * sr)].mean(axis=1)
    spec = np.abs(np.fft.rfft(seg * np.hanning(len(seg))))
    peak2 = np.fft.rfftfreq(len(seg), 1 / sr)[np.argmax(spec)]
    assert abs(peak2 - 880) < 8, f"pitch {peak2:.1f} Hz"
    # 트랙 팬 -0.5 → 왼쪽이 크다 (곡 앞부분은 Tone 트랙만)
    l, r = (x[: sr, 0] ** 2).sum(), (x[: sr, 1] ** 2).sum()
    assert l > r * 2, (l, r)
    # 오디오 클립(2.0~2.6초)이 들려야 한다
    clip = x[int(2.1 * sr): int(2.5 * sr)]
    assert np.abs(clip).max() > 0.01, "audio clip silent"
    assert any("reverb" in w for w in stats["warnings"]), "expected pass-through warning for reverb"
    return {"rms_dbfs": round(float(rms), 1), "peak_hz": [round(float(peak), 1), round(float(peak2), 1)],
            "realtime_x": stats["realtime_x"], "peak_ram_mb": stats["peak_ram_mb"]}


@check("core.threads_deterministic")
def _():
    pp = TMP / "plan.json"
    a, b = TMP / "t1.wav", TMP / "tN.wav"
    render(pp, a, "--threads", "1")
    render(pp, b)
    xa, _ = sf.read(str(a))
    xb, _ = sf.read(str(b))
    d = float(np.abs(xa - xb).max())
    assert d < 1e-6, d
    return "1 thread == N threads"


@check("core.sfz_libraries")
def _():
    from musicoma.knowledge import resolve_sound
    out = {}
    for role in ("piano_grand", "drums_rusty", "bass_hollow_finger"):
        path = resolve_sound(role)["sfz"]
        if not Path(path).exists():
            out[role] = "not installed"
            continue
        p = subprocess.run([str(EXE), "sfzinfo", path], capture_output=True, text=True, encoding="utf-8-sig",
                           errors="replace")
        info = json.loads(p.stdout)
        assert info["regions"] > 0 and info["missing_files"] == 0, (role, info)
        out[role] = f"{info['regions']} regions, {len(info['ignored_opcodes'])} ignored opcode kinds"
    return out


def null_tests_info():
    """scratch/core/<곡>/engine.wav 가 있으면 비교(참고)."""
    from core_null_run import run
    rows = []
    for d in sorted((ROOT / "scratch" / "core").glob("*/engine.wav")):
        name = d.parent.name
        if not (d.parent / "plan.json").exists():
            continue
        try:
            c = run(name)
            rows.append((name, c["lufs_diff"], c["residual_db"], c["core_realtime_x"]))
        except Exception as ex:  # noqa: BLE001
            rows.append((name, "err", str(ex)[:60], ""))
    if rows:
        print("\n  null test vs current engine (informational):")
        print("  " + f"{'song':<12}{'LU diff':>9}{'residual dB':>13}{'core x RT':>11}")
        for r in rows:
            print("  " + f"{r[0]:<12}{r[1]!s:>9}{r[2]!s:>13}{r[3]!s:>11}")
    return rows


if __name__ == "__main__":
    info = null_tests_info() if EXE.exists() else []
    ok = all(r["ok"] for r in RESULTS)
    (ROOT / "tests" / "report_core.json").write_text(
        json.dumps({"results": RESULTS, "null": info}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n{sum(r['ok'] for r in RESULTS)}/{len(RESULTS)} passed")
    sys.exit(0 if ok else 1)
