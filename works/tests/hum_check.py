"""흥얼거림 인식 회귀 검사(10-15). 합성 멜로디(음정 25~40센트 틀림)·합성 비트박스 + 본인 실녹음(있으면)."""
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
import librosa

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from musicoma import hum

ROOT = Path(__file__).resolve().parents[2]
sr = 22050
spb = 60 / 92
# 1) 멜로디 D4 F4 A4 G4 F4 D4, 8분음, 음 사이 짧은 숨, 센트 틀림
mel, cents = [62, 65, 69, 67, 65, 62], [30, -25, 40, -35, 25, -30]
y = []
for m, c in zip(mel, cents):
    t = np.arange(int(spb / 2 * sr * 0.85)) / sr
    f = 440 * 2 ** ((m + c / 100 - 69) / 12) * (1 + 0.006 * np.sin(2 * np.pi * 5.5 * t))
    env = np.minimum(1, t / 0.02) * np.minimum(1, (t[-1] - t) / 0.03)
    y += [0.4 * np.sin(2 * np.pi * np.cumsum(f) / sr) * env, np.zeros(int(spb / 2 * sr * 0.15))]
p = ROOT / "scratch/hum/syn_melody.wav"
sf.write(p, np.concatenate(y), sr)
r = hum.listen(p, 92, "D minor", tempo_from_recording=False, transpose=0)
got = [n["pitch"] for n in r["notes"]]
print("melody", r["mode"], got, "OK" if got == mel else "FAIL")
# 2) 비트박스: 킥(저역)·스네어(잡음)·햇(고역)
rng = np.random.default_rng(0)
def hit(kind):
    t = np.arange(int(0.12 * sr)) / sr
    if kind == 36:
        return 0.8 * np.sin(2 * np.pi * (60 + 80 * np.exp(-t * 30)) * t) * np.exp(-t * 25)
    if kind == 38:
        from scipy.signal import butter, lfilter                      # 입 스네어 '푸ㅅ/카' = 1~3kHz 대역 잡음
        b, a = butter(2, [800, 3000], btype="band", fs=sr)
        return 0.6 * lfilter(b, a, rng.normal(size=len(t))) * np.exp(-t * 30)
    n = rng.normal(size=len(t)); n = np.diff(np.concatenate([[0], n]))
    return 0.4 * n * np.exp(-t * 60)
pat = [36, 42, 38, 42, 36, 36, 38, 42]
y = np.zeros(int(len(pat) * spb / 2 * sr) + sr)
for i, k in enumerate(pat):
    h = hit(k); a = int(i * spb / 2 * sr); y[a:a + len(h)] += h
p = ROOT / "scratch/hum/syn_beatbox.wav"
sf.write(p, y, sr)
r = hum.listen(p, 92, "D minor", tempo_from_recording=False)
got = [n["pitch"] for n in r["notes"]]
print("beatbox", r["mode"], got, "OK" if got == pat else "FAIL")
# 3) 본인 실녹음(10-15, '투두투두' 8음절)
p = ROOT / "sounds/inbox/hum_user_01.mp3"
if p.exists():
    r = hum.listen(p, 92, "D minor")
    print("user01", r["mode"], len(r["notes"]), "notes", "OK" if len(r["notes"]) == 8 else "FAIL", "bpm", r["recording_bpm"], "conf", r["confidence"])
# 4) 말 + 흥얼거림 섞인 녹음(합성 말소리 + 본인 '투두투두'): 지시와 소리를 나눠 듣는가
if p.exists():
    import librosa as _l
    a, _ = _l.load(str(ROOT / "scratch/hum/say_a.wav"), sr=22050)
    h, _ = _l.load(str(p), sr=22050)
    mixp = ROOT / "scratch/hum/mixed_say_hum.wav"
    sf.write(mixp, np.concatenate([a, np.zeros(int(0.4 * 22050)), h]), 22050)
    u = hum.understand(mixp, 92, "D minor")
    print("mixed said:", u["said"], "| place", u["place"], "| music",
          [(m["from_s"], m["to_s"], m["mode"], len(m["notes"])) for m in u["music"]],
          "OK" if u["place"].get("at") == "1:20" and u["place"].get("repeat") == 4 and len(u["music"]) == 1 and len(u["music"][0]["notes"]) == 8 else "CHECK")
