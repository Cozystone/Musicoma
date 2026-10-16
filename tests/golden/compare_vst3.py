"""VST3 호스팅 비교 — 새 엔진(core test-vst3)의 플러그인 렌더를 옛 엔진(Tracktion) 렌더와 잰다(클린룸: 바깥 소리만).

    .venv/Scripts/python tests/golden/compare_vst3.py ref       → 옛 엔진(127.0.0.1:47800)으로 기준 렌더(zz-vst3-* 프로젝트)
    .venv/Scripts/python tests/golden/compare_vst3.py compare   → core/build-vst3/out/*.wav 와 ref_*.wav 비교

같은 음표 목록을 core/tests/test_vst3.cpp 가 쓴다(바꾸면 둘 다).
옛 렌더에는 마스터 볼륨 -3 dB 가 들어 있으므로 비교 전에 +3 dB 보정한다.
기준: 통합 라우드니스 차 ≤ 1 dB, 멜 스펙트럼 엔벨로프 상관 > 0.95. 널 잔차는 참고(LFO·랜덤 위상이 있으면 못 맞춤).
"""
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "core" / "build-vst3" / "out"
SR = 48000
BPM = 120
PLUG = ROOT / "sounds" / "plugins" / "vst3"
EP1 = PLUG / "Surge Synth Team" / "SurgeXTData" / "patches_factory" / "Keys" / "EP 1.fxp"

# (음, 시작 박, 길이 박, 벨로시티 0-127) — test_vst3.cpp 의 kNotes 와 같다
NOTES = [
    (60, 0, 2, 100), (64, 0, 2, 100), (67, 0, 2, 100),
    (72, 2, 0.5, 96), (74, 2.5, 0.5, 96), (76, 3, 0.5, 96), (79, 3.5, 0.5, 96),
    (65, 4, 2, 90), (69, 4, 2, 90), (72, 4, 2, 90),
    (77, 6, 0.5, 100), (76, 6.5, 0.5, 100), (74, 7, 1, 100),
]
END_BEATS = 8
TAIL_SEC = 1.0


def hit_signal():
    """짧은 북 소리(결정적): 80 Hz 사인 + 노이즈 버스트 0.25초, 피크 -6 dBFS. test_vst3.cpp 의 makeHit() 와 같은 식."""
    n = int(0.25 * SR)
    t = np.arange(n) / SR
    env = np.exp(-t * 30.0)
    # 결정적 노이즈: LCG (C++ 와 같은 수열)
    state = 12345
    noise = np.empty(n)
    for i in range(n):
        state = (state * 1103515245 + 12345) & 0x7FFFFFFF
        noise[i] = state / 0x7FFFFFFF * 2.0 - 1.0
    x = (0.6 * np.sin(2 * np.pi * 80 * t) + 0.4 * noise * np.exp(-t * 60.0)) * env * 0.5
    return x.astype(np.float32)


def make_ref():
    from musicoma.engine import connect
    OUT.mkdir(parents=True, exist_ok=True)
    e = connect("vst3-ref")
    notes = [{"pitch": p, "start": s, "length": l, "velocity": v} for p, s, l, v in NOTES]

    # Surge XT + EP 1.fxp
    e.call("edit.new", {"name": "zz-vst3-ref-surge", "bpm": BPM})
    e.call("track.add", {"name": "S"})
    e.call("device.add", {"track": "S", "device": "Surge XT"})
    r = e.call("device.load_file", {"track": "S", "device": 0, "path": str(EP1)})
    print("load_file:", r)
    e.call("clip.add_midi", {"track": "S", "start": 0, "length": END_BEATS, "notes": notes})
    print(e.call("render", {"path": str(OUT / "ref_surge_ep1.wav"), "start": 0, "end": END_BEATS,
                            "tail": TAIL_SEC, "tracks": ["S"]}))

    # Dexed 기본 패치
    e.call("edit.new", {"name": "zz-vst3-ref-dexed", "bpm": BPM})
    e.call("track.add", {"name": "D"})
    e.call("device.add", {"track": "D", "device": "Dexed"})
    e.call("clip.add_midi", {"track": "D", "start": 0, "length": END_BEATS, "notes": notes})
    print(e.call("render", {"path": str(OUT / "ref_dexed.wav"), "start": 0, "end": END_BEATS,
                            "tail": TAIL_SEC, "tracks": ["D"]}))

    # Dragonfly Hall Reverb — 북 소리 한 번
    hit = hit_signal()
    hitwav = OUT / "hit.wav"
    sf.write(str(hitwav), np.stack([hit, hit], 1), SR, subtype="FLOAT")
    e.call("edit.new", {"name": "zz-vst3-ref-hall", "bpm": BPM})
    e.call("track.add", {"name": "H"})
    e.call("clip.add_audio", {"track": "H", "path": str(hitwav), "start": 0})
    e.call("device.add", {"track": "H", "device": "Dragonfly Hall Reverb"})
    print(e.call("render", {"path": str(OUT / "ref_dragonfly_hall.wav"), "start": 0, "end": END_BEATS,
                            "tail": TAIL_SEC, "tracks": ["H"]}))
    e.close()


def lufs(x):
    import pyloudnorm as pyln
    return pyln.Meter(SR).integrated_loudness(x)


def mel_env(x):
    import librosa
    m = librosa.feature.melspectrogram(y=x.mean(1), sr=SR, n_fft=2048, hop_length=512, n_mels=64)
    return np.log10(m + 1e-8)


def compare_pair(name, ref, new):
    a, sra = sf.read(str(ref), dtype="float64", always_2d=True)
    b, srb = sf.read(str(new), dtype="float64", always_2d=True)
    assert sra == srb == SR, (sra, srb)
    a = a * 10 ** (3 / 20)        # 옛 엔진 마스터 -3 dB 보정
    n = min(len(a), len(b))
    # 정렬: 앞 1초 안에서 교차상관 최대 지연(플러그인 지연 차이)
    seg = min(n, SR * 2)
    xa, xb = a[:seg].mean(1), b[:seg].mean(1)
    corr = np.correlate(xb[:seg], xa[:seg - 2048], mode="valid") if seg > 4096 else np.array([0])
    lag = int(np.argmax(np.abs(corr))) if len(corr) > 1 else 0
    lag = lag if lag < 2048 else 0
    b2 = b[lag:lag + n] if lag else b[:n]
    n = min(len(a), len(b2))
    a, b2 = a[:n], b2[:n]
    la, lb = lufs(a), lufs(b2)
    ma, mb = mel_env(a), mel_env(b2)
    k = min(ma.shape[1], mb.shape[1])
    ea, eb = ma[:, :k].ravel(), mb[:, :k].ravel()
    mc = float(np.corrcoef(ea, eb)[0, 1])
    # 시간 엔벨로프(프레임별 에너지) 상관도 따로
    ta, tb = ma[:, :k].mean(0), mb[:, :k].mean(0)
    tc = float(np.corrcoef(ta, tb)[0, 1])
    res = b2 - a
    pa = np.sqrt(np.mean(a ** 2)) + 1e-12
    null_db = 20 * np.log10(np.sqrt(np.mean(res ** 2)) / pa + 1e-12)
    ok = abs(la - lb) <= 1.0 and mc > 0.95
    print(f"{name:16s} LUFS old {la:7.2f} new {lb:7.2f} diff {lb - la:+5.2f} dB | mel corr {mc:.4f} "
          f"| env corr {tc:.4f} | null {null_db:+7.2f} dB (lag {lag}) | peak old {np.abs(a).max():.3f} "
          f"new {np.abs(b2).max():.3f} | {'PASS' if ok else 'FAIL'}")
    return ok


def compare():
    # 주의(10-16 확인): 옛 엔진은 device.load_file 뒤에도 Surge 파라미터가 그대로다(A Osc 1 Type 'Classic' 유지) —
    # 즉 ref_surge_ep1.wav 는 사실 Surge 기본(Init Saw) 소리. 그래서 새 엔진의 '패치 없는' 렌더(surge_default)와 맞춘다.
    # surge_ep1(새 엔진, EP 1 실제 적용)은 참고로만 보여 준다.
    pairs = [("surge_default", "ref_surge_ep1.wav", "surge_default.wav"),
             ("dexed", "ref_dexed.wav", "dexed.wav"),
             ("dragonfly_hall", "ref_dragonfly_hall.wav", "dragonfly_hall.wav")]
    if (OUT / "surge_ep1.wav").exists():
        print("(참고) 옛 엔진은 EP 1 을 실제로 적용하지 못함 — 아래 줄은 다른 소리끼리 비교:")
        compare_pair("surge_ep1 (info)", OUT / "ref_surge_ep1.wav", OUT / "surge_ep1.wav")
    allok = True
    for name, r, n in pairs:
        if not (OUT / r).exists() or not (OUT / n).exists():
            print(f"{name}: 파일 없음 ({r} / {n})")
            allok = False
            continue
        allok &= compare_pair(name, OUT / r, OUT / n)
    print("ALL PASS" if allok else "SOME FAIL")
    return 0 if allok else 1


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "compare"
    if cmd == "ref":
        make_ref()
    elif cmd == "hit":
        h = hit_signal()
        print(h[:4], h.max())
    else:
        sys.exit(compare())
