"""파일 정리 규칙 — 사람이 열어 봐도 바로 알아보게.

곡 폴더 projects/<곡>/
    README.md          이 곡 안내(자동 생성): 최신 렌더, 버전, 보컬, 설계서
    spec.json          설계서(곡의 원본)        song.json   메타·요청 기록·버전
    <곡>.edit.json     엔진 편집 파일(자체 엔진 형식, 10-16)
    renders/           렌더 결과(wav + 측정 png)만
    vocals/            최종 보컬 wav + 그 설정(json)만
    versions/          스냅숏
    .work/             중간 파일 전부(줄별 랩 원본, 가이드, 테이크, SoulX 작업, 트랙별 측정 스템, 로그)
루트 scratch/          테스트·실험 조각(곡이 아닌 것). 저장소에 넣지 않음.

생성 코드는 work_dir() 로 중간 파일 위치를 받는다. 이미 섞인 폴더는 tidy() 로 정리.
"""
import json
import shutil
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROJECTS = ROOT / "projects"
SCRATCH = ROOT / "scratch"
WORK = ".work"
_INTERMEDIATE_SUFFIX = ("_lines", "_soulx", "_svc")


def work_dir(out, kind):
    """결과 파일 out 의 중간 파일 폴더: <out 폴더>/.work/<out 이름>_<kind>/ (곡 폴더 밖이면 그 옆의 .work)."""
    out = Path(out).resolve()
    d = out.parent / WORK / f"{out.stem}_{kind}"
    d.mkdir(parents=True, exist_ok=True)
    return d


def scratch(*parts):
    """실험·테스트용 경로(scratch/...). 폴더를 만들어 준다."""
    p = SCRATCH.joinpath(*parts)
    (p if not p.suffix else p.parent).mkdir(parents=True, exist_ok=True)
    return p


def _move(src, dst_dir, log):
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / src.name
    if dst.exists():
        dst = dst_dir / f"{src.stem}_{time.strftime('%H%M%S')}{src.suffix}"
    shutil.move(str(src), str(dst))
    log.append(f"{src.relative_to(ROOT)} → {dst.relative_to(ROOT)}")


def tidy(project, dry_run=False):
    """곡 폴더를 규칙대로: 중간 파일 → .work/. 지우지 않고 옮기기만 한다. 반환: 옮긴 목록."""
    d = PROJECTS / project if not Path(project).is_absolute() else Path(project)
    moves = []
    if not d.exists():
        raise FileNotFoundError(d)
    plan = []
    for sub in ("vocals", "renders"):
        sd = d / sub
        if not sd.exists():
            continue
        for p in sd.iterdir():
            if p.name.startswith("."):
                continue
            if p.is_dir() and (p.name.endswith(_INTERMEDIATE_SUFFIX) or p.name == "stems"):
                plan.append((p, sd / WORK))
            elif p.suffix in (".log", ".txt"):
                plan.append((p, sd / WORK))
    for p in d.glob("*.log"):
        plan.append((p, d / WORK))
    if dry_run:
        return [f"{a.relative_to(ROOT)} → {b.relative_to(ROOT)}/" for a, b in plan]
    for src, dst in plan:
        _move(src, dst, moves)
    write_readme(d.name)
    return moves


def tidy_root(dry_run=False):
    """루트 renders/ 의 테스트 조각 → scratch/renders/."""
    src = ROOT / "renders"
    if not src.exists():
        return []
    items = [p for p in src.iterdir()]
    if dry_run:
        return [str(p.relative_to(ROOT)) for p in items]
    moves = []
    for p in items:
        _move(p, SCRATCH / "renders", moves)
    return moves


def write_readme(project):
    """곡 안내 README.md — 무엇을 들으면 되는지, 어떻게 만들어졌는지 한 장에."""
    d = PROJECTS / project
    song = json.loads((d / "song.json").read_text(encoding="utf-8")) if (d / "song.json").exists() else {}
    spec = json.loads((d / "spec.json").read_text(encoding="utf-8")) if (d / "spec.json").exists() else {}
    renders = sorted((d / "renders").glob("*.wav"), key=lambda p: p.stat().st_mtime, reverse=True) if (d / "renders").exists() else []
    vocals = sorted((d / "vocals").glob("*.wav")) if (d / "vocals").exists() else []
    versions = sorted((d / "versions").iterdir()) if (d / "versions").exists() else []
    L = [f"# {project}", ""]
    if song.get("brief") or spec.get("brief"):
        L += [song.get("brief") or spec.get("brief"), ""]
    L += [f"- 템포 {song.get('bpm', spec.get('bpm', '?'))} BPM · 키 {song.get('key', spec.get('key', '?'))} · 스타일 {song.get('style', spec.get('style', '-'))}"]
    secs = spec.get("sections") or song.get("sections") or []
    if secs:
        L.append("- 구성: " + " → ".join(f"{s['name']}({s['bars']})" for s in secs))
    L += ["", "## 들어볼 것"]
    if renders:
        L.append(f"- **최신**: `renders/{renders[0].name}`")
        for r in renders[1:8]:
            L.append(f"- `renders/{r.name}`")
    else:
        L.append("- (아직 렌더 없음)")
    if vocals:
        L += ["", "## 보컬"] + [f"- `vocals/{v.name}`" for v in vocals]
    if versions:
        L += ["", "## 버전"] + [f"- `versions/{v.name}`" for v in versions[-10:]]
    L += ["", "## 파일", "- `spec.json` 설계서(이걸 고쳐 다시 지으면 곡이 바뀜) · `song.json` 요청·조치 기록",
          "- `.work/` 중간 파일(줄별 랩 원본·가이드·테이크·측정 스템) — 지워도 곡은 다시 지을 수 있음", ""]
    (d / "README.md").write_text("\n".join(L), encoding="utf-8")
    return str(d / "README.md")


if __name__ == "__main__":
    import sys
    dry = "--dry-run" in sys.argv
    names = [a for a in sys.argv[1:] if not a.startswith("--")] or [p.name for p in PROJECTS.iterdir() if p.is_dir()]
    for n in names:
        r = tidy(n, dry_run=dry)
        print(n, len(r), "moved" if not dry else "to move")
    if "--root" in sys.argv:
        print("root renders →", len(tidy_root(dry)))


def edit_file(name):
    """곡의 엔진 편집 파일 경로(projects/<곡>/<곡>.edit.json). 옛 .tracktionedit 만 있으면 그 경로(엔진이 변환 안내)."""
    d = ROOT / "projects" / name
    new = d / f"{name}.edit.json"
    old = d / f"{name}.tracktionedit"
    return new if new.exists() or not old.exists() else old
