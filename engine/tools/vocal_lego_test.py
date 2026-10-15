"""보컬 자연스러움 실험: 우리 비트(훅 8마디)를 들려주고 ACE-Step 이 보컬 트랙만 얹게 한다(lego).
영어/한국어, 남/여 두 가지씩. 결과: sounds/crate/vocal-test/"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from musicoma import gen, crate  # noqa: E402

BACK = "D:/0.Musicoma/sounds/crate/vocal-test/hook_backing.wav"
CASES = [
    ("en_male", "soulful male R&B lead vocal, warm natural chest voice, early 2000s soul, intimate, not autotuned",
     "[chorus]\nOh baby come back to me tonight\nI still hear you on the radio", "en"),
    ("ko_female", "natural Korean female R&B lead vocal, warm breathy mid register, intimate, not autotuned",
     "[chorus]\n돌아와 줘 오늘 밤만은\n아직도 라디오에서 네 목소리가 들려", "ko"),
]
out = {}
for tag, caption, lyrics, lang in CASES:
    paths = gen.generate(caption, lyrics=lyrics, bpm=88, key="A major", seconds=22, task="lego",
                         src_audio=BACK, instruction="Generate the vocals track based on the audio context:",
                         steps=50, slug=f"vocal-test-{tag}", seed=5, language=lang, n=1)
    out[tag] = paths
    print(tag, paths, flush=True)
    # 보컬만 분리(얹힌 결과가 믹스로 나올 수 있으므로)
    try:
        st = crate.separate(paths[0])
        out[tag + "_vocal_stem"] = st["vocals"]
        print(tag, "stem", st["vocals"], flush=True)
    except Exception as ex:
        print("separate failed", ex, flush=True)
Path("D:/0.Musicoma/sounds/crate/vocal-test/results.json").write_text(json.dumps(out, ensure_ascii=False, indent=1),
                                                                       encoding="utf-8")
print("DONE", flush=True)
