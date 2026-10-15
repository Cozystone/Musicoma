"""인간다움 지식 — 좋은 곡을 많이 '듣고' 숫자로 기억한다. 레퍼런스를 매번 줄 필요가 없게. (10-15 본인)

    python -m musicoma.corpus D:/0.MUSIC/0.Soundsource      # 새 곡만 분석해서 쌓기(이미 한 곡은 건너뜀)
    priors(genre="hiphop")                                  # 곡 만들 때 쓰는 기준값

원곡 소리·가사는 저장하지 않는다. scratch/refs/<곡>/report.json(분석 숫자)과
musicoma/knowledge/human_priors.json(장르별 요약)만 남긴다.

요약하는 것(장르별 중앙값·범위)
  vocal_offset_ms / vocal_std_ms / vocal_on_grid   보컬 음절이 16분 격자에서 벗어나는 정도(사람다움의 핵심)
  syllables_per_sec_verse / _hook                   구간별 말·노래 밀도
  section_bars                                      구간 길이 분포(4의 배수 비율 = 정형성)
  transition_bars                                   1~2마디 짧은 구간(전환) 비율
  hook_vs_verse_db                                  훅에서 드럼·보컬이 얼마나 바뀌나
  swing                                             드럼 스윙
"""
import json
import re
from pathlib import Path

import numpy as np

from . import analyze_ref

ROOT = Path(__file__).resolve().parent.parent
PRIORS = ROOT / "musicoma" / "knowledge" / "human_priors.json"
AUDIO = {".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg", ".mp4", ".webm"}

# 파일 이름으로 장르 추정(모르면 'unknown' — 나중에 본인이 고칠 수 있게 index 에 남김)
GENRE_HINTS = [("kanye|hip ?hop|rap|boom|trap|drill", "hiphop"), ("city ?pop|yasuha|tatsuro|mariya|anri", "citypop"),
               ("ballad|이문세|발라드", "kballad"), ("김완선|kim wan|disco|댄스", "kdance80s"),
               ("jazz|nujabes", "jazzhop"), ("house|techno|edm", "electronic"), ("orchestra|symphony|score", "orchestral")]


def slug(name):
    return re.sub(r"[^a-z0-9가-힣]+", "-", name.lower()).strip("-")[:60]


def guess_genre(name):
    low = name.lower()
    for pat, g in GENRE_HINTS:
        if re.search(pat, low):
            return g
    return "unknown"


def index_path():
    return ROOT / "scratch" / "refs" / "index.json"


def load_index():
    p = index_path()
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def ingest(folder, log=print, genres=None):
    """폴더의 새 곡을 분석해 쌓는다. genres = {파일이름: 장르} 로 직접 지정 가능."""
    idx = load_index()
    files = [f for f in sorted(Path(folder).iterdir()) if f.suffix.lower() in AUDIO]
    for f in files:
        key = slug(f.stem)
        if key in idx and (ROOT / "scratch" / "refs" / key / "report.json").exists():
            continue
        log(f"== {f.name}")
        try:
            analyze_ref.analyze(str(f), name=key, log=lambda m: log("   " + m))
            idx[key] = {"file": str(f), "genre": (genres or {}).get(f.name) or guess_genre(f.name)}
        except Exception as ex:
            log(f"   실패: {ex}")
            idx[key] = {"file": str(f), "error": str(ex)[:200]}
        index_path().parent.mkdir(parents=True, exist_ok=True)
        index_path().write_text(json.dumps(idx, ensure_ascii=False, indent=1), encoding="utf-8")
    summarize(log)
    return idx


def _features(rep):
    t = rep.get("vocal_timing") or {}
    secs = rep.get("sections") or []
    bars = [s["bars"] for s in secs]
    voices = {v["section"]: v for v in rep.get("voices") or []}
    per = t.get("per_section") or []
    rates = sorted(p["onsets_per_sec"] for p in per)
    tr = (rep.get("transitions") or {}).get("boundaries") or []
    return {
        "tempo": rep.get("tempo"),
        "vocal_offset_ms": t.get("mean_offset_ms"), "vocal_std_ms": t.get("std_ms"), "vocal_on_grid": t.get("within_20ms"),
        "syllables_per_sec_verse": rates[-1] if rates else None,          # 가장 빽빽한 구간 ≈ 벌스
        "syllables_per_sec_hook": rates[0] if rates else None,            # 가장 성긴 구간 ≈ 훅
        "section_bars": bars,
        "bars_multiple_of_4": round(float(np.mean([b % 4 == 0 for b in bars])), 2) if bars else None,
        "transition_share": round(float(np.mean([b <= 2 for b in bars[1:-1]])), 2) if len(bars) > 2 else None,
        "boundary_drum_change_db": [b.get("drums") for b in tr],
        "boundary_vocal_change_db": [b.get("vocals") for b in tr],
        "swing": (rep.get("drums") or {}).get("swing_8th_ratio"),
        "loop_bars": (rep.get("loop") or {}).get("loop_bars"),
    }


def summarize(log=print):
    idx = load_index()
    by = {}
    for key, meta in idx.items():
        p = ROOT / "scratch" / "refs" / key / "report.json"
        if "error" in meta or not p.exists():
            continue
        f = _features(json.loads(p.read_text(encoding="utf-8")))
        by.setdefault(meta.get("genre", "unknown"), []).append({"song": key, **f})
        by.setdefault("all", []).append({"song": key, **f})
    out = {}
    for g, rows in by.items():
        def med(k):
            v = [r[k] for r in rows if isinstance(r.get(k), (int, float))]
            return {"median": round(float(np.median(v)), 2), "min": round(float(min(v)), 2), "max": round(float(max(v)), 2),
                    "n": len(v)} if v else None
        trans = [x for r in rows for x in (r["boundary_vocal_change_db"] or []) if isinstance(x, (int, float))]
        out[g] = {"songs": [r["song"] for r in rows],
                  **{k: med(k) for k in ("tempo", "vocal_offset_ms", "vocal_std_ms", "vocal_on_grid",
                                         "syllables_per_sec_verse", "syllables_per_sec_hook", "bars_multiple_of_4",
                                         "transition_share", "swing")},
                  "section_bars_seen": sorted({b for r in rows for b in r["section_bars"]}),
                  "vocal_change_at_boundaries_db": {"p10": round(float(np.percentile(trans, 10)), 1),
                                                    "p90": round(float(np.percentile(trans, 90)), 1)} if trans else None}
    PRIORS.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    log(f"인간다움 지식 갱신: {', '.join(f'{g}({len(v)})' for g, v in by.items())} → {PRIORS.name}")
    return out


def priors(genre=None):
    """곡 만들 때 기준값. 장르가 없거나 모르면 전체('all')."""
    if not PRIORS.exists():
        return {}
    d = json.loads(PRIORS.read_text(encoding="utf-8"))
    return d.get(genre) or d.get("all") or {}


if __name__ == "__main__":
    import sys
    ingest(sys.argv[1] if len(sys.argv) > 1 else "D:/0.MUSIC/0.Soundsource")
