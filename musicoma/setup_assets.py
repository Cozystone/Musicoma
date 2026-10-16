"""첫 실행 자산 설치 — 음원 팩(공식 배포처에서 받기)과 선택 AI 모듈.

    python -m musicoma.setup_assets --root <dir> [--sounds core|full] [--ai] [--dry-run]

- 음원: musicoma/setup_manifest.json 의 sounds 목록. <root>/sounds/_downloads 에 받아(이어받기 가능)
  크기·SHA256 을 확인하고 <root>/sounds/sfz/<dir> (플러그인은 sounds/plugins/vst3) 에 푼다.
  이미 설치된 항목(표식 파일이 다 있음)은 건너뛴다. 끝나면 sounds/ATTRIBUTION.md 를 쓴다.
- AI(--ai): 번들 uv.exe 로 ① <root>/python-ai (런타임 위 가상환경) 에 torch(cu128)·faster-whisper·demucs,
  ② third_party/ace-step-15/.venv (Py 3.11, 주 보컬 엔진 — 반주를 듣고 부름, 모델 ~28GB),
  ③ third_party/soulx-singer/.venv (Py 3.10), ④ third_party/voxcpm/.venv (Py 3.11) 를 만들고 모델을 받는다.
- 진행 상황은 표준출력에 한 줄 JSON 으로 낸다(셸이 읽어 화면에 표시). 표준 라이브러리만 쓴다.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
CODE_ROOT = HERE.parent
MANIFEST = HERE / "setup_manifest.json"
UA = "Musicoma-setup/1 (+https://github.com/)"
CHUNK = 1 << 20


# ───────────────────────── 출력 ─────────────────────────
def emit(event: str, **kw):
    sys.stdout.write(json.dumps({"event": event, **kw}, ensure_ascii=False) + "\n")
    sys.stdout.flush()


class Progress:
    """다운로드 진행률을 0.5초마다 한 줄씩."""

    def __init__(self, item_id, total, done=0):
        self.id, self.total, self.done = item_id, total, done
        self.t0 = self.last = time.time()
        self.start_bytes = done

    def add(self, n):
        self.done += n
        now = time.time()
        if now - self.last >= 0.5:
            self.last = now
            speed = (self.done - self.start_bytes) / max(now - self.t0, 1e-6)
            emit("progress", id=self.id, phase="download", bytes=self.done, total=self.total,
                 pct=round(100 * self.done / self.total, 1) if self.total else None,
                 speed_mbps=round(speed / 1e6, 2))


# ───────────────────────── 경로 ─────────────────────────
def default_root() -> Path:
    env = os.environ.get("MUSICOMA_ROOT")
    return Path(env) if env else CODE_ROOT


def bundle_dir(root: Path) -> Path | None:
    """AI 접착 스크립트·requirements 가 있는 곳 (개발: app/runtime, 설치판: resources/musicoma/setup)."""
    cands = [os.environ.get("MUSICOMA_BUNDLE"), root / "setup", CODE_ROOT / "setup", CODE_ROOT / "app" / "runtime"]
    for c in cands:
        if c and (Path(c) / "requirements-ai.txt").exists():
            return Path(c)
    return None


def find_uv(explicit: str | None) -> str | None:
    cands = [explicit, os.environ.get("MUSICOMA_UV"),
             Path(sys.executable).resolve().parent.parent / "uv.exe",       # resources/runtime/python/python.exe → runtime/uv.exe
             CODE_ROOT / "app" / "runtime" / "dist" / "uv.exe",
             shutil.which("uv")]
    for c in cands:
        if c and Path(c).exists():
            return str(c)
    return None


# ───────────────────────── 네트워크 ─────────────────────────
def _open(url, headers=None, method="GET"):
    req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})}, method=method)
    return urllib.request.urlopen(req, timeout=60)


def resolve_github_asset(spec):
    """롤링 릴리스(예: Airwindows DAWPlugin) — 고정 URL 이 사라지면 같은 릴리스의 최신 자산을 고른다."""
    api = f"https://api.github.com/repos/{spec['repo']}/releases/tags/{spec['tag']}"
    with _open(api, {"Accept": "application/vnd.github+json"}) as r:
        rel = json.load(r)
    rx = re.compile(spec["asset_regex"])
    for a in rel.get("assets", []):
        if rx.search(a["name"]):
            dig = a.get("digest") or ""
            return a["browser_download_url"], a["size"], dig[7:] if dig.startswith("sha256:") else None
    raise RuntimeError(f"no asset matching {spec['asset_regex']} in {spec['repo']}@{spec['tag']}")


def download(item, dl_dir: Path) -> Path:
    url, size, sha = item["url"], item.get("size"), item.get("sha256")
    exact = item.get("size_exact", False)
    name = re.sub(r"[^\w.-]", "_", item["id"]) + ".zip"
    final, part = dl_dir / name, dl_dir / (name + ".part")
    dl_dir.mkdir(parents=True, exist_ok=True)

    if final.exists() and (not exact or final.stat().st_size == size) and _sha_ok(final, sha, item["id"]):
        emit("skip", id=item["id"], phase="download", reason="archive already downloaded")
        return final

    for attempt in range(1, 6):
        have = part.stat().st_size if part.exists() else 0
        headers = {"Range": f"bytes={have}-"} if have else {}
        try:
            resp = _open(url, headers)
        except urllib.error.HTTPError as e:
            if e.code == 404 and item.get("github_release"):
                url, size, sha2 = resolve_github_asset(item["github_release"])
                sha = sha2 or None
                emit("log", id=item["id"], text=f"pinned asset gone; using {url}")
                part.unlink(missing_ok=True)
                continue
            if e.code == 416 and have:              # 이미 다 받음
                break
            raise
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            emit("log", id=item["id"], text=f"network error (try {attempt}/5): {e}")
            time.sleep(min(30, 2 ** attempt))
            continue
        with resp:
            if have and resp.status != 206:          # 서버가 이어받기를 안 함 → 처음부터
                emit("log", id=item["id"], text="server ignored Range; restarting download")
                have = 0
                mode = "wb"
            else:
                mode = "ab" if have else "wb"
            total = None
            cr = resp.headers.get("Content-Range")
            if cr and "/" in cr and cr.rsplit("/", 1)[1].isdigit():
                total = int(cr.rsplit("/", 1)[1])
            elif resp.headers.get("Content-Length"):
                total = have + int(resp.headers["Content-Length"])
            total = total or size
            prog = Progress(item["id"], total, have)
            try:
                with open(part, mode) as f:
                    while True:
                        b = resp.read(CHUNK)
                        if not b:
                            break
                        f.write(b)
                        prog.add(len(b))
            except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
                emit("log", id=item["id"], text=f"interrupted (try {attempt}/5): {e}")
                time.sleep(min(30, 2 ** attempt))
                continue
        break
    else:
        raise RuntimeError(f"{item['id']}: download failed after 5 attempts")

    got = part.stat().st_size
    if exact and size and got != size:
        part.unlink(missing_ok=True)                 # 크기가 다르면 깨진 것 — 다음 실행에서 처음부터
        raise RuntimeError(f"{item['id']}: size mismatch (got {got}, expected {size})")
    if not exact and size and abs(got - size) > 0.05 * size:
        emit("log", id=item["id"], text=f"size differs from estimate ({got} vs ~{size}); verifying by contents")
    if not _sha_ok(part, sha, item["id"]):
        part.unlink(missing_ok=True)
        raise RuntimeError(f"{item['id']}: sha256 mismatch")
    if not zipfile.is_zipfile(part):
        part.unlink(missing_ok=True)
        raise RuntimeError(f"{item['id']}: downloaded file is not a zip")
    part.replace(final)
    return final


def _sha_ok(path: Path, sha: str | None, item_id: str) -> bool:
    if not sha:
        return True
    emit("progress", id=item_id, phase="verify")
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(CHUNK), b""):
            h.update(b)
    return h.hexdigest().lower() == sha.lower()


# ───────────────────────── 풀기 ─────────────────────────
def markers_ok(root: Path, item) -> bool:
    dest = root / item["dest"]
    return all((dest / m).exists() for m in item.get("markers", []))


def extract(item, archive: Path, root: Path):
    dest = (root / item["dest"]).resolve()
    stage = dest.parent / f".{item['id']}.staging"
    shutil.rmtree(stage, ignore_errors=True)
    stage.mkdir(parents=True)
    strip, include = int(item.get("strip", 0)), item.get("include")
    with zipfile.ZipFile(archive) as z:
        infos = z.infolist()
        total = sum(i.file_size for i in infos) or 1
        done, last = 0, 0.0
        for i in infos:
            parts = i.filename.replace("\\", "/").split("/")
            if len(parts) <= strip:
                continue
            rel = "/".join(parts[strip:])
            if not rel or (include and not any(rel.startswith(p) or rel + "/" == p for p in include)):
                continue
            out = (stage / rel).resolve()
            if stage.resolve() not in out.parents and out != stage.resolve():
                raise RuntimeError(f"{item['id']}: unsafe path in archive: {i.filename}")
            if i.is_dir():
                out.mkdir(parents=True, exist_ok=True)
                continue
            out.parent.mkdir(parents=True, exist_ok=True)
            with z.open(i) as src, open(out, "wb") as dst:
                shutil.copyfileobj(src, dst, CHUNK)
            done += i.file_size
            if time.time() - last > 0.5:
                last = time.time()
                emit("progress", id=item["id"], phase="extract", pct=round(100 * done / total, 1))
    # 스테이징 → 목적지 (플러그인처럼 여러 항목이 같은 폴더를 쓰면 최상위 항목 단위로 교체)
    dest.mkdir(parents=True, exist_ok=True)
    for child in stage.iterdir():
        target = dest / child.name
        if target.is_dir():
            shutil.rmtree(target)
        elif target.exists():
            target.unlink()
        shutil.move(str(child), str(target))
    shutil.rmtree(stage, ignore_errors=True)


def apply_overlays(manifest, root: Path, only_after: str | None = None):
    for ov in manifest.get("overlays", []):
        if only_after and ov.get("after") != only_after:
            continue
        src = CODE_ROOT / ov["src"]
        if not src.exists():
            src = root / ov["src"]
        dst = root / ov["dest"]
        if not src.exists() or not dst.exists():
            continue
        for f in src.rglob("*"):
            if f.is_file():
                t = dst / f.relative_to(src)
                if not t.exists():
                    t.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(f, t)
                    emit("log", id=ov.get("after"), text=f"overlay {t.relative_to(root).as_posix()}")


def write_attribution(manifest, root: Path):
    lines = ["# Musicoma 음원·플러그인 출처 (자동 생성)", "",
             "setup_assets 가 공식 배포처에서 받은 항목. CC-BY 항목은 결과물 공개 시 출처 표기가 필요하다.", ""]
    for it in manifest["sounds"]:
        if markers_ok(root, it):
            lines += [f"## {it['name']}", f"- 라이선스: {it['license']}", f"- 제작: {it['author']}",
                      f"- 출처: {it['homepage']}", f"- 받은 곳: {it['url']}", f"- 표기: {it['attribution']}", ""]
    p = root / "sounds" / "ATTRIBUTION.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(lines), encoding="utf-8")
    return p


# ───────────────────────── 음원 ─────────────────────────
def select_sounds(manifest, pack, only):
    items = manifest["sounds"]
    if only:
        ids = set(only)
        return [i for i in items if i["id"] in ids]
    if pack == "core":
        return [i for i in items if i["pack"] == "core"]
    if pack == "full":
        return list(items)
    return []


def run_sounds(manifest, root: Path, items, dry, keep_archives):
    dl_dir = root / "sounds" / "_downloads"
    plan, need_dl, unpacked, biggest = [], 0, 0, 0
    for it in items:
        installed = markers_ok(root, it)
        arch = dl_dir / (re.sub(r"[^\w.-]", "_", it["id"]) + ".zip")
        partial = (arch.parent / (arch.name + ".part"))
        have = partial.stat().st_size if partial.exists() else (arch.stat().st_size if arch.exists() else 0)
        state = "installed" if installed else ("downloaded" if arch.exists() else ("partial" if have else "missing"))
        if not installed:
            need_dl += max(0, it["size"] - have) if state != "downloaded" else 0
            unpacked += it["unpacked_mb"] * 2 ** 20
            biggest = max(biggest, it["size"])        # 압축 파일은 하나씩 받고 풀면 지운다
        plan.append({"id": it["id"], "state": state, "size": it["size"], "unpacked_mb": it["unpacked_mb"],
                     "dest": it["dest"], "url": it["url"], "license": it["license"]})
    need_disk = unpacked + biggest
    free = shutil.disk_usage(_existing_parent(root)).free
    emit("plan", kind="sounds", items=plan, download_bytes=need_dl, disk_bytes=need_disk, free_bytes=free)
    if dry:
        return True
    if need_disk > free:
        emit("error", kind="sounds", message=f"디스크 공간 부족: 필요 약 {need_disk / 2**30:.1f} GB, 남음 {free / 2**30:.1f} GB")
        return False
    ok = True
    for n, it in enumerate(items, 1):
        emit("start", id=it["id"], name=it["name"], index=n, count=len(items))
        if markers_ok(root, it):
            apply_overlays(manifest, root, it["id"])
            emit("done", id=it["id"], skipped=True)
            continue
        try:
            arch = download(it, dl_dir)
            extract(it, arch, root)
            apply_overlays(manifest, root, it["id"])
            if not markers_ok(root, it):
                raise RuntimeError(f"{it['id']}: expected files missing after extraction: {it.get('markers')}")
            if not keep_archives:
                arch.unlink(missing_ok=True)
            emit("done", id=it["id"])
        except Exception as e:  # 한 항목이 실패해도 나머지는 계속
            ok = False
            emit("error", id=it["id"], message=f"{type(e).__name__}: {e}")
    p = write_attribution(manifest, root)
    emit("log", text=f"attribution written: {p}")
    return ok


def _existing_parent(p: Path) -> Path:
    p = p.resolve()
    while not p.exists():
        p = p.parent
    return p


# ───────────────────────── AI ─────────────────────────
def _run(cmd, dry, env=None, cwd=None, step=""):
    emit("cmd", step=step, cmd=[str(c) for c in cmd], cwd=str(cwd) if cwd else None)
    if dry:
        return
    proc = subprocess.Popen([str(c) for c in cmd], cwd=cwd, env={**os.environ, **(env or {})},
                            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                            encoding="utf-8", errors="replace",
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    for line in proc.stdout:
        line = line.rstrip()
        if line:
            emit("log", step=step, text=line[-400:])
    if proc.wait() != 0:
        raise RuntimeError(f"{step}: command failed ({proc.returncode})")


def run_ai(manifest, root: Path, python: str, uv: str | None, dry):
    try:                                                     # 이 PC 사양으로 어떤 모델·설정이 되는지 먼저 알린다
        from musicoma.hardware import ace_profile
        pr = ace_profile()
        emit("hardware", gpu=pr.get("hw", {}).get("gpu"), vram_mb=pr.get("hw", {}).get("vram_mb"),
             ram_gb=pr.get("hw", {}).get("ram_gb"), ace_tier=pr.get("tier"), ace_model=pr.get("model"), note=pr.get("note"))
    except Exception as ex:
        emit("log", text=f"hardware check skipped: {ex}")
    ai = manifest["ai"]
    bdir = bundle_dir(root)
    emit("plan", kind="ai", uv=uv, python=python, bundle=str(bdir) if bdir else None,
         runtime_disk_mb=ai["runtime"]["approx_disk_mb"],
         venvs=[{"id": v["id"], "dir": v["dir"], "python": v["python"], "disk_mb": v["approx_disk_mb"]}
                for v in ai["venvs"]])
    if not uv:
        emit("error", kind="ai", message="uv.exe 를 찾지 못했습니다 (resources/runtime/uv.exe)")
        return False
    if not bdir:
        emit("error", kind="ai", message="AI 설치 파일 묶음(setup/requirements-ai.txt)을 찾지 못했습니다")
        return False
    tp = root / "third_party"
    uv_env = {"UV_PYTHON_INSTALL_DIR": str(tp / "_python"), "UV_CACHE_DIR": str(tp / "_uv-cache"),
              "UV_LINK_MODE": "copy", "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
    torch_idx = ["--extra-index-url", ai["runtime"]["torch_index"], "--index-strategy", "unsafe-best-match"]
    ok = True

    # ① 런타임 위에 얹는 가상환경(<root>/python-ai, system-site-packages) 에 torch(cu128)·faster-whisper·demucs.
    #    설치 폴더의 런타임을 직접 바꾸지 않으므로 앱을 업데이트해도 AI 모듈이 남는다. 셸은 이 환경이 있으면 이걸 쓴다.
    try:
        emit("start", id="ai-runtime", name="AI 모듈 (torch · faster-whisper · demucs)")
        venv = root / ai["runtime"]["venv"]
        vpy = venv / "Scripts" / "python.exe"
        if not vpy.exists() or dry:
            _run([uv, "venv", venv, "--python", python, "--system-site-packages"], dry, uv_env, step="ai-runtime")
        _run([uv, "pip", "install", "--python", vpy, *torch_idx,
              *ai["runtime"]["torch"], "-r", bdir / ai["runtime"]["requirements"]],
             dry, uv_env, step="ai-runtime")
        emit("done", id="ai-runtime", dry_run=dry)
    except Exception as e:
        ok = False
        emit("error", id="ai-runtime", message=str(e))

    # ②③ 별도 가상환경
    for v in ai["venvs"]:
        vid, vdir = v["id"], root / v["dir"]
        try:
            emit("start", id=vid, name=v["name"])
            if v.get("source_zip") and not all((vdir / m).exists() for m in v.get("markers", [])):
                item = {"id": vid + "-source", "url": v["source_zip"], "size": 0, "strip": v.get("source_strip", 0),
                        "dest": v["dir"], "markers": v.get("markers", [])}
                emit("cmd", step=vid, cmd=["download+extract", v["source_zip"], str(vdir)])
                if not dry:
                    arch = download(item, tp / "_downloads")
                    extract(item, arch, root)
                    arch.unlink(missing_ok=True)
            glue = bdir / v["glue"]
            emit("cmd", step=vid, cmd=["copy-glue", str(glue), str(vdir)])
            if not dry:
                vdir.mkdir(parents=True, exist_ok=True)
                for f in glue.iterdir():
                    if f.is_file():
                        shutil.copy2(f, vdir / f.name)
            vpy = vdir / ".venv" / "Scripts" / "python.exe"
            if not vpy.exists() or dry:
                _run([uv, "venv", vdir / ".venv", "--python", v["python"]], dry, uv_env, step=vid)
            pkgs = list(v["torch"]) + list(v.get("packages", []))
            req = ["-r", bdir / v["requirements"]] if v.get("requirements") else []
            if v.get("source_requirements"):                     # 받은 소스 안의 requirements(ACE-Step 은 자기 torch·인덱스를 고정)
                req += ["-r", vdir / v["source_requirements"]]
            _run([uv, "pip", "install", "--python", vpy, *torch_idx, *pkgs, *req], dry, uv_env, step=vid)
            for m in v.get("models", []):
                env = dict(uv_env)
                if m.get("code"):                                 # 모듈 자체 다운로더(파일 배치·코드 동기화까지 그쪽 규칙대로)
                    _run([vpy, "-c", m["code"]], dry, env, cwd=vdir, step=f"{vid}:model:{m.get('name', 'code')}")
                    continue
                if m.get("hf_home"):
                    env["HF_HOME"] = str(vdir / m["hf_home"])
                    code = f"from huggingface_hub import snapshot_download as s; print(s({m['repo']!r}))"
                else:
                    code = (f"from huggingface_hub import snapshot_download as s; "
                            f"print(s({m['repo']!r}, revision={m.get('revision')!r}, local_dir={m['local_dir']!r}))")
                _run([vpy, "-c", code], dry, env, cwd=vdir, step=f"{vid}:model:{m['repo']}")
            emit("done", id=vid, dry_run=dry)
        except Exception as e:
            ok = False
            emit("error", id=vid, message=str(e))
    if not dry and ok:
        shutil.rmtree(tp / "_uv-cache", ignore_errors=True)      # 받은 휠 캐시는 지운다(용량)
    return ok


# ───────────────────────── 진입점 ─────────────────────────
def main(argv=None):
    ap = argparse.ArgumentParser(description="Musicoma first-run asset installer")
    ap.add_argument("--root", default=None, help="Musicoma root (default: MUSICOMA_ROOT or the code folder)")
    ap.add_argument("--sounds", choices=["none", "core", "full"], default="none")
    ap.add_argument("--only", default="", help="comma-separated sound ids (overrides --sounds)")
    ap.add_argument("--ai", action="store_true", help="install optional AI modules (NVIDIA GPU)")
    ap.add_argument("--python", default=sys.executable, help="runtime python to receive AI modules")
    ap.add_argument("--uv", default=None, help="path to uv.exe (default: bundled)")
    ap.add_argument("--manifest", default=str(MANIFEST))
    ap.add_argument("--keep-archives", action="store_true")
    ap.add_argument("--dry-run", action="store_true", help="print the plan only")
    a = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8")      # 셸은 UTF-8 JSON 줄로 읽는다
    except (AttributeError, ValueError):
        pass

    root = Path(a.root).resolve() if a.root else default_root().resolve()
    manifest = json.loads(Path(a.manifest).read_text(encoding="utf-8"))
    emit("begin", root=str(root), dry_run=a.dry_run, sounds=a.sounds, ai=a.ai)
    ok = True
    only = [s for s in a.only.split(",") if s]
    items = select_sounds(manifest, a.sounds, only)
    if items:
        ok &= run_sounds(manifest, root, items, a.dry_run, a.keep_archives)
    if a.ai:
        ok &= run_ai(manifest, root, a.python, find_uv(a.uv), a.dry_run)
    emit("finish", ok=bool(ok), dry_run=a.dry_run)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
