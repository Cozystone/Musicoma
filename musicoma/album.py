"""앨범 공통 — 랩을 '한 번에' 만든다: 줄마다 TTS 로 뱉어 격자에 붙이는 대신, ACE-Step lego 가 비트를 듣고 절 전체를 랩으로 부른다.
10-18 본인: "속사포로 읊어, 랩이 아니라 뱉는 느낌. 보컬을 쪼개서 만들어서 그런가? 하나로 만들어 봐." — 본인이 가장 좋아한 칸예 시티팝 02 의 랩이 이 방식(rap_lego_full, seed 5/4).

rap_with_lego(spec, label, caption, reference):
  1) 설계서에서 'rap' 파트(Rap·RapC 트랙)를 빼고 반주를 wav 로 짓는다
  2) 빠진 절마다 lego.vocal_track — 가사는 줄을 이어 붙인 것, 비트·가이드를 듣고 랩, 받아쓰기로 테이크 고름, reference 로 같은 래퍼
  3) 반주 설계서 + vocal_sections 로 최종 빌드(mp3)
"""
import json
from pathlib import Path

from . import arrange, lego

ROOT = arrange.ROOT
RAP_REF = Path(r"D:\0.MUSIC\Musicoma\02 칸예 시티팝 (첫 산출물)\보컬\rap_lego_full.wav")        # 앨범 공통 래퍼(칸예 시티팝 02 의 목소리)


def rap_with_lego(spec, label, caption, reference=None, takes=10, pass_wer=0.3, tracks=("Rap", "RapC"), log=print, steps=50):
    name = spec["name"]
    rap_parts = [p for p in spec["parts"] if "rap" in p and p["track"] in tracks]
    band = {**spec, "parts": [p for p in spec["parts"] if not ("rap" in p and p["track"] in tracks)]}
    s, rep = arrange.build(band, label=f"{label}-band", fmt="wav", log=lambda m: None)
    beat = Path(rep["file"])
    guide = lego.render_guide(band)
    sections_all, _ = arrange._sections(spec)
    spb = 60.0 / spec["bpm"]
    secs = []
    for p in rap_parts:
        names = p["in"] if isinstance(p["in"], list) else [p["in"]]
        sec = next(x for x in sections_all if x["name"] == names[0])
        lines = p["rap"]["lines"]
        texts = [l["text"] if isinstance(l, dict) else l for l in lines]
        beats = sum((l.get("beats", p["rap"].get("beats_per_line", 4)) if isinstance(l, dict) else p["rap"].get("beats_per_line", 4)) for l in lines)
        start_b = sec["start_bar"] * 4 + p.get("offset", 0)
        tag = "Bridge" if "bridge" in names[0] else "Verse"
        secs.append({"name": f"{names[0]}{'' if p.get('offset', 0) == 0 else '_b' + str(p.get('offset'))}", "start": round(start_b * spb, 3),
                     "end": round((start_b + beats) * spb, 3), "tag": tag, "lyrics": "\n".join(texts), "key": spec["key"]})
    out = ROOT / "projects" / name / "vocals" / f"rap_lego_{label}"
    _, report = lego.vocal_track(beat, secs, spec["bpm"], spec["key"], caption, out, takes=takes, guide_wav=guide,
                                 pass_wer=pass_wer, min_key_fit=0.0, lang="en", reference=str(reference or RAP_REF), log=log, steps=steps)
    for r in report:
        log(f"[lego rap] {r['section']}: seed {r['chosen']} · 오류율 {r['wer']}")
    final = {**band, "parts": band["parts"] + [{"track": tracks[0], "vocal_sections": str(out.with_suffix(".json"))}]}
    s2, rep2 = arrange.build(final, label=label, log=lambda m: None)
    rep2["rap_report"] = report
    return s2, rep2
