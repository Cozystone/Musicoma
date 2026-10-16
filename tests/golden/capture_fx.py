"""골든 기록 ② — 지금 엔진의 내장 이펙트·믹서가 '어떤 소리를 내는지' 시험 신호로 잰다(10-16, 클린룸 기준선).
새 엔진의 이펙트는 이 입·출력 쌍에 맞춘다(널 테스트·주파수 응답·엔벨로프 비교). 코드를 보지 않고 바깥 동작만.

    .venv/Scripts/python tests/golden/capture_fx.py   → scratch/golden/fx/{input.wav, <case>.wav, cases.json}
신호(48 kHz 스테레오, 마디 = 120 BPM 4/4 기준 2초):
  0.0s 임펄스(1샘플, -6 dBFS) · 1.0s 로그 스윕 20 Hz→20 kHz 4초(-12 dBFS) · 6.0s 음악(피아노 렌더 4초)
  10.5s 핑크 노이즈 0.6초씩 -36/-24/-12/-6 dBFS(컴프레서 정특성) · 끝 3초 무음(꼬리)
"""
import json
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from musicoma.engine import connect  # noqa: E402

SR = 48000
OUT = ROOT / "scratch" / "golden" / "fx"
OUT.mkdir(parents=True, exist_ok=True)


def signal():
    n = int(16 * SR)
    x = np.zeros((n, 2), np.float32)
    x[int(0.0 * SR) + 10] = 0.5
    t = np.arange(int(4 * SR)) / SR
    f0, f1, T = 20.0, 20000.0, 4.0
    k = np.log(f1 / f0)
    sw = 0.25 * np.sin(2 * np.pi * f0 * T / k * (np.exp(t / T * k) - 1))
    x[SR:SR + len(sw)] = sw[:, None]
    music = ROOT / "scratch" / "golden" / "render.wav"
    if music.exists():
        m, sr = sf.read(str(music), dtype="float32", always_2d=True)
        m = m[:4 * SR]
        x[6 * SR:6 * SR + len(m)] = m[:, :2] / (np.abs(m).max() + 1e-9) * 0.5
    rng = np.random.default_rng(7)
    w = rng.normal(size=(int(0.6 * SR), 2))
    f = np.fft.rfftfreq(len(w), 1 / SR)
    pink = np.fft.irfft(np.fft.rfft(w, axis=0) / np.maximum(1, np.sqrt(f))[:, None], n=len(w), axis=0)
    pink /= np.sqrt(np.mean(pink ** 2))
    for i, db in enumerate((-36, -24, -12, -6)):
        a = int((10.5 + i * 0.8) * SR)
        x[a:a + len(pink)] = (pink * 10 ** (db / 20)).astype(np.float32)
    return x


CASES = [
    ("dry", None, {}),
    ("eq_default", "eq", {}),
    ("eq_song", "eq", {"Low-pass freq": 110, "Low-pass gain": -6, "Mid freq 2": 3200, "Mid gain 2": 1.5}),
    ("eq_lowshelf_up", "eq", {"Low-pass freq": 200, "Low-pass gain": 6, "Low-pass Q": 1.0}),
    ("eq_highshelf_down", "eq", {"High-pass freq": 6000, "High-pass gain": -8}),
    ("eq_mid1_peak", "eq", {"Mid freq 1": 1000, "Mid gain 1": 9, "Mid Q 1": 2.0}),
    ("eq_mid2_cut_wide", "eq", {"Mid freq 2": 3000, "Mid gain 2": -6, "Mid Q 2": 0.3}),
    ("comp_default", "compressor", {}),
    ("comp_song", "compressor", {"threshold": -20, "ratio": 4, "attack": 8, "release": 100, "output gain": 3}),
    ("comp_hard", "compressor", {"threshold": -24, "ratio": 6, "attack": 3, "release": 60}),
    ("comp_slow", "compressor", {"threshold": -14, "ratio": 2, "attack": 30, "release": 150}),
    ("reverb_default", "reverb", {}),
    ("reverb_big", "reverb", {"room size": 0.85, "damping": 0.2, "wet level": 0.6, "dry level": 0.4}),
    ("reverb_narrow", "reverb", {"room size": 0.5, "width": 0.2}),
    ("delay_default", "delay", {}),
    ("delay_long", "delay", {"feedback": -3, "mix proportion": 0.5}),
    ("chorus_default", "chorus", {}),
    ("phaser_default", "phaser", {}),
    ("lowpass_1800", "lowpass", {"frequency": 1800}),
    ("lowpass_400", "lowpass", {"frequency": 400}),
    ("lowpass_9000", "lowpass", {"frequency": 9000}),
    ("pitch_up5", "pitchshift", {"semitones up": 5}),
    ("pitch_down7", "pitchshift", {"semitones up": -7}),
    ("pitch_up12", "pitchshift", {"semitones up": 12}),
]
MIX = [  # 믹서·라우팅(디바이스 없이)
    ("vol_m6", {"volume_db": -6}),
    ("pan_l05", {"pan": -0.5}),
    ("pan_r1", {"pan": 1.0}),
]

if __name__ == "__main__":
    x = signal()
    inp = OUT / "input.wav"
    sf.write(str(inp), x, SR, subtype="FLOAT")
    e = connect("golden-fx")
    e.call("edit.new", {"name": "zz-golden-fx", "bpm": 120})
    meta = {"sr": SR, "bpm": 120, "input": str(inp), "cases": []}
    names = []
    for name, dev, params in CASES:
        e.call("track.add", {"name": name})
        e.call("clip.add_audio", {"track": name, "path": str(inp), "start": 0})
        if dev:
            e.call("device.add", {"track": name, "device": dev})
            if params:
                e.call("device.set", {"track": name, "device": 0, "params": params})
            p = e.call("device.params", {"track": name, "device": 0})
        else:
            p = None
        meta["cases"].append({"name": name, "device": dev, "params": params, "params_after": p})
        names.append(name)
    for name, mix in MIX:
        e.call("track.add", {"name": name})
        e.call("clip.add_audio", {"track": name, "path": str(inp), "start": 0})
        e.call("track.set", {"track": name, **mix})
        meta["cases"].append({"name": name, "mixer": mix})
        names.append(name)
    # 센드 → 리턴 버스(리버브) : 드라이 트랙 + 버스
    e.call("track.add", {"name": "send_src"})
    e.call("clip.add_audio", {"track": "send_src", "path": str(inp), "start": 0})
    e.call("device.add", {"track": "send_src", "device": "send", "bus": 0, "level_db": -6})
    e.call("track.add", {"name": "bus"})
    e.call("device.add", {"track": "bus", "device": "return", "bus": 0})
    meta["cases"].append({"name": "send_bus", "routing": "send_src --send(bus 0, -6 dB)--> bus(return 0); render both tracks"})
    for name in names:
        r = e.call("render", {"path": str(OUT / f"{name}.wav"), "start": 0, "end": 32, "tail": 0, "tracks": [name]})
    e.call("render", {"path": str(OUT / "send_bus.wav"), "start": 0, "end": 32, "tail": 0, "tracks": ["send_src", "bus"]})
    e.call("render", {"path": str(OUT / "send_src_only.wav"), "start": 0, "end": 32, "tail": 0, "tracks": ["send_src"]})
    meta["render_note"] = "render {start:0, end:32 beats(=16 s), tail:0, tracks:[case]} — 마스터 볼륨 기본(-3 dB 로 측정됨, core/README) 포함"
    (OUT / "cases.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print("cases", len(meta["cases"]), "->", OUT)
