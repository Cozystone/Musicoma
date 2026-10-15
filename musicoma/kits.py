"""직접 합성한 소리 묶음(저작권 걱정 없는 자체 소스, CC0). 장르에 필요한데 무료 샘플이 없는 소리를 여기서 만든다.

    make_phonk()  → sounds/sfz/musicoma-phonk/  (10-16 브라질리언 퐁크)
      phonk_kit.sfz   GM 드럼 맵: 킥 36 · 림 37 · 클랩 38/39 · 닫힌햇 42 · 열린햇 46 · 탬버린 54 · 카우벨 56
      cowbell.sfz     TR-808 식 카우벨을 음높이로(퐁크의 선율 악기) — 사각파 두 개(540·800Hz 비율) + 대역 통과
      808.sfz         808 베이스, 디스토션을 샘플에 굽는다(엔진 내장 이펙트에 디스토션이 없어서): drive 1·2·3 = 세기층
"""
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfilt

ROOT = Path(__file__).resolve().parent.parent
SR = 48000


def _env(n, attack=0.001, decay=0.2, sr=SR):
    t = np.arange(n) / sr
    return np.minimum(1, t / max(attack, 1e-4)) * np.exp(-t / decay)


def _bp(x, lo, hi, order=2):
    return sosfilt(butter(order, [lo, hi], btype="band", fs=SR, output="sos"), x)


def _lp(x, f, order=4):
    return sosfilt(butter(order, f, btype="low", fs=SR, output="sos"), x)


def _hp(x, f, order=2):
    return sosfilt(butter(order, f, btype="high", fs=SR, output="sos"), x)


def _norm(x, peak=0.9):
    return x / (np.abs(x).max() + 1e-9) * peak


def _sq(f, n):
    t = np.arange(n) / SR
    return np.sign(np.sin(2 * np.pi * f * t))


def kick(n=int(0.45 * SR)):
    t = np.arange(n) / SR
    f = 45 + 110 * np.exp(-t * 28)                       # 150 → 45Hz 음높이 떨어짐
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 7)
    click = _hp(np.random.default_rng(1).normal(size=n), 2500) * np.exp(-t * 300) * 0.4
    return _norm(np.tanh(2.2 * (body + click)))


def clap(n=int(0.35 * SR)):
    rng = np.random.default_rng(2)
    x = np.zeros(n)
    for k, d in enumerate([0, 0.011, 0.022, 0.033]):        # 손뼉 여러 겹
        i = int(d * SR)
        m = n - i
        x[i:] += rng.normal(size=m) * np.exp(-np.arange(m) / SR / (0.012 if k < 3 else 0.12))
    return _norm(_bp(x, 900, 3200))


def rim(n=int(0.12 * SR)):
    t = np.arange(n) / SR
    x = (np.sin(2 * np.pi * 1750 * t) + 0.6 * np.sin(2 * np.pi * 520 * t)) * np.exp(-t * 60)
    return _norm(x + 0.2 * _bp(np.random.default_rng(3).normal(size=n), 2000, 6000) * np.exp(-t * 120))


def hat(open_=False):
    n = int((0.45 if open_ else 0.09) * SR)
    x = sum(_sq(f, n) for f in (205.3, 304.4, 369.6, 522.7, 540.0, 800.0))   # 808 식 금속성 6음
    x = _lp(_hp(_bp(x, 6000, 15000), 7000), 16000)
    return _norm(x * _env(n, 0.0005, 0.16 if open_ else 0.022), 0.7)


def tamb(n=int(0.2 * SR)):
    x = _hp(np.random.default_rng(4).normal(size=n), 6000) * _env(n, 0.002, 0.05)
    return _norm(x, 0.6)


def cowbell(n=int(0.6 * SR)):
    """TR-808 카우벨: 540·800Hz 사각파 + 대역 통과, 짧은 첫 감쇠 + 긴 꼬리."""
    t = np.arange(n) / SR
    x = _sq(540, n) + _sq(800, n)
    x = _bp(x, 700, 3500, 4)
    env = 0.5 * np.exp(-t * 30) + 0.5 * np.exp(-t * 4.5)     # 10-16: 꼬리를 길게(짧으면 음량이 안 잡혀 페이더 최대에서도 묻힘)
    return _norm(_lp(x * env * np.minimum(1, t / 0.0008), 9000))


def bass808(drive=2.0, n=int(3.0 * SR), f0=65.406):
    """808 베이스(C2 기준). 음 시작에 짧은 음높이 내림 + 긴 지속. drive 로 tanh 디스토션(배음이 생겨 작은 스피커에서도 들림)."""
    t = np.arange(n) / SR
    f = f0 * (1 + 0.35 * np.exp(-t * 40))
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 0.45) * np.minimum(1, t / 0.002)
    x = np.tanh(drive * x) / np.tanh(drive)
    return _norm(_lp(x, 5000), 0.85)                        # 디스토션 모서리를 깎아 트루피크(샘플 사이 피크) 줄이기 — 10-16 v1 TP 가 먼저 막혀 -10 LUFS


def make_phonk(out=None):
    out = Path(out or ROOT / "sounds" / "sfz" / "musicoma-phonk")
    (out / "samples").mkdir(parents=True, exist_ok=True)
    W = lambda name, x: sf.write(str(out / "samples" / f"{name}.wav"), np.stack([x, x], 1).astype(np.float32), SR, subtype="PCM_24")
    W("kick", kick()); W("clap", clap()); W("rim", rim()); W("hat_c", hat()); W("hat_o", hat(True))
    W("tamb", tamb()); W("cowbell", cowbell())
    for i, d in enumerate((1.5, 3.0, 6.0), 1):
        W(f"808_d{i}", bass808(d))
    kit = ["<control> default_path=samples/", "<global> loop_mode=one_shot",
           "<region> key=36 sample=kick.wav", "<region> key=35 sample=kick.wav volume=-3",
           "<region> key=37 sample=rim.wav", "<region> key=38 sample=clap.wav", "<region> key=39 sample=clap.wav",
           "<region> key=42 sample=hat_c.wav group=1", "<region> key=44 sample=hat_c.wav group=1 volume=-4",
           "<region> key=46 sample=hat_o.wav group=2 off_by=1",
           "<region> key=54 sample=tamb.wav", "<region> key=56 sample=cowbell.wav"]
    (out / "phonk_kit.sfz").write_text("\n".join(kit) + "\n", encoding="utf-8")
    # 카우벨 원음 540Hz ≈ C#5(554Hz) - 44센트 → 건반 음 높이에 맞춤
    cb = ["<control> default_path=samples/",
          "<region> lokey=36 hikey=108 pitch_keycenter=73 tune=44 sample=cowbell.wav loop_mode=one_shot ampeg_release=0.05 volume=6"]
    (out / "cowbell.sfz").write_text("\n".join(cb) + "\n", encoding="utf-8")
    b = ["<control> default_path=samples/", "<global> lokey=0 hikey=72 pitch_keycenter=36 ampeg_release=0.06",
         "<region> lovel=0 hivel=70 sample=808_d1.wav", "<region> lovel=71 hivel=105 sample=808_d2.wav",
         "<region> lovel=106 hivel=127 sample=808_d3.wav"]
    (out / "808.sfz").write_text("\n".join(b) + "\n", encoding="utf-8")
    (out / "README.md").write_text("Musicoma 가 직접 합성한 브라질리언 퐁크 소리(musicoma/kits.py). CC0 — 자유롭게 사용.\n", encoding="utf-8")
    return out


if __name__ == "__main__":
    print(make_phonk())
