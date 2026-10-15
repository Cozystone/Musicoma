"""콘셉트 문서 — 노트를 쓰기 전에 '이 곡은 무엇인가'를 한 장으로. 모든 결정은 여기에 근거해야 한다.

projects/<곡>/concept.json
{
  "thesis":  "한 문장 — 이 곡이 무엇에 관한 것인가",
  "arc":     [{"section": "intro", "intent": "무엇을 느끼게", "energy": 0.2}, ...],   # 감정 곡선(0~1)
  "motif":   {"melody": "A4:.5 C5:.5 E5:1 D5:2", "why": "이 동기가 무엇을 상징하나"},
  "collision": ["80년대 시티팝", "교회 성가대", "지하철 안내음"],                   # 서로 먼 재료 2~3개
  "constraints": ["후렴에 코드 없음 — 베이스와 목소리만", "브리지만 7/8"],
  "events":  [{"at": "verse2:-1", "type": "stop", "why": "숨 멈추게"}],                 # 사람들이 이야기할 순간
  "references": [{"song": "Nujabes - Luv(sic)", "principle": "재즈 코드 + 붐뱁 = 새 장르(형식의 발명)"}],
  "taste": ["본인 취향 문서에서 이 곡에 해당하는 축"],
  "not":     ["피할 것 — 흔한 4코드 반복, 훅 없는 랩만 등"]
}
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TASTE = Path("D:/0.Creative/IDENTITY")          # 본인 취향 축적 공간(있으면 읽는다)

REQUIRED = ("thesis", "arc", "motif", "events")

# 본인이 꼽은 '전례 없는 곡'에서 뽑은 원리(10-15) — 흉내가 아니라 결정 방식
PRINCIPLES = [
    {"song": "Nujabes - Luv(sic)", "principle": "서로 다른 세계(재즈 화성·피아노 / 붐뱁 드럼·랩)를 붙여 새 장르를 만든다 — 형식의 발명"},
    {"song": "이찬혁 - 멸종위기사랑", "principle": "들어본 적 없는 진행 — 기대한 다음 화음을 비튼다(모달 차용·반음 이동·예상 밖 해결)"},
    {"song": "Kanye West - On Sight", "principle": "비트 체인지 — 곡 중간에 세계가 바뀐다(갑작스러운 정지·전혀 다른 샘플·템포/질감 전환)"},
]


def path(name):
    return ROOT / "projects" / name / "concept.json"


def load(name):
    p = path(name)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def save(name, concept):
    problems = validate(concept)
    p = path(name)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(concept, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"path": str(p), "problems": problems}


def validate(c):
    out = [f"'{k}' 없음" for k in REQUIRED if not c.get(k)]
    if c.get("collision") is not None and len(c["collision"]) < 2:
        out.append("collision 은 서로 먼 재료 2개 이상")
    if c.get("arc"):
        en = [a.get("energy", 0) for a in c["arc"]]
        if max(en) - min(en) < 0.3:
            out.append("arc: 에너지 폭이 좁다(최대-최소 < 0.3) — 곡에 굴곡이 없다")
    if not c.get("constraints"):
        out.append("constraints 가 없다 — 제약이 개성을 만든다(최소 1개 권장)")
    return out


def taste_context(max_chars=4000):
    """본인 취향 문서(TASTE.md + LOG.md 끝부분)를 읽어 비평 기준으로. 없으면 빈 문자열."""
    parts = []
    for f in ("TASTE.md", "LOG.md"):
        p = TASTE / f
        if p.exists():
            t = p.read_text(encoding="utf-8")
            parts.append(f"## {f}\n" + (t if f == "TASTE.md" else t[-max_chars:]))
    return "\n\n".join(parts)[: max_chars * 2]


def template(thesis="", genre_hint=""):
    """빈 콘셉트 + 원리 목록. Claude 가 채운다."""
    return {"thesis": thesis, "arc": [], "motif": {"melody": "", "why": ""}, "collision": [], "constraints": [],
            "events": [], "references": PRINCIPLES, "taste": [], "not": [], "genre_hint": genre_hint}
