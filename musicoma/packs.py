"""악기팩 — AI 가 필요할 때 즉석에서 받아 넣는다(10-17 본인 요청 "무료 악기팩을 즉석에서 받아와서 넣는 유연함").

    packs.catalog()                      설치 목록(설치됨/안 됨, 크기, 라이선스) — setup_manifest.json 의 팩
    packs.install("dexed")               목록의 팩 하나 받기(진행은 로그 리스트로)
    packs.add_from_url(url, id, name, license, author, homepage, kind="sfz")
                                         목록에 없는 무료 팩(zip, SFZ/wav) — 받아 풀고 sounds/sfz/<id>/ 에 두고
                                         knowledge/sounds_user.yaml 에 역할 이름으로 등록 → resolve_sound 로 바로 쓸 수 있다
원칙: 라이선스가 자유로운 것만(CC0 · CC-BY · Public Domain · MIT/GPL 샘플). 출처·라이선스·저작자는 ATTRIBUTION 에 남긴다.
      zip 만 받는다(실행 파일·설치 프로그램 금지). 크기 상한 3 GB. 압축 안의 경로 탈출 검사는 setup_assets.extract 가 한다.
"""
import io
import json
import re
import shutil
import time
import zipfile
from pathlib import Path

import yaml

from . import setup_assets as sa

ROOT = Path(__file__).resolve().parent.parent
USER_YAML = Path(__file__).resolve().parent / "knowledge" / "sounds_user.yaml"
USER_DIR = ROOT / "sounds" / "sfz"
MAX_BYTES = 3 * 2 ** 30
FREE_LICENSES = ("cc0", "cc-by", "cc by", "public domain", "pd", "mit", "gpl", "lgpl", "unlicense", "ofl", "apache")


def _manifest():
    return json.loads(sa.MANIFEST.read_text(encoding="utf-8"))


def _quiet(log):
    """setup_assets 는 진행을 표준출력에 JSON 으로 쓴다 — MCP 안에선 표준출력이 통신선이라 리스트로 받는다."""
    def emit(event, **kw):
        log.append({"event": event, **kw})
    return emit


def catalog():
    m = _manifest()
    out = []
    for it in m["sounds"]:
        arch = ROOT / "sounds" / "_downloads" / (re.sub(r"[^\w.-]", "_", it["id"]) + ".zip")
        out.append({"id": it["id"], "name": it["name"], "pack": it.get("pack"), "license": it.get("license"),
                    "size_mb": round(it["size"] / 2 ** 20), "unpacked_mb": it.get("unpacked_mb"),
                    "installed": sa.markers_ok(ROOT, it), "downloaded": arch.exists(),
                    "homepage": it.get("homepage"), "note": it.get("note")})
    user = _user_catalog()
    for k, v in user.get("packs", {}).items():
        out.append({"id": k, "name": v.get("name"), "pack": "user", "license": v.get("license"),
                    "installed": (ROOT / v["dest"]).exists(), "homepage": v.get("homepage"), "sounds": v.get("sounds", [])})
    return out


def install(pack_id, log=None):
    """목록의 팩 하나 — 이미 있으면 그대로. 반환: {id, installed, seconds, log}"""
    log = log if log is not None else []
    m = _manifest()
    it = next((x for x in m["sounds"] if x["id"] == pack_id), None)
    if not it:
        raise ValueError(f"목록에 없는 팩: {pack_id} (catalog() 참고, 없는 팩은 add_from_url)")
    t0 = time.time()
    if sa.markers_ok(ROOT, it):
        return {"id": pack_id, "installed": True, "already": True}
    old = sa.emit
    sa.emit = _quiet(log)
    try:
        free = shutil.disk_usage(ROOT).free
        need = it.get("unpacked_mb", 0) * 2 ** 20 + it["size"]
        if need > free:
            raise RuntimeError(f"디스크 부족: 약 {need / 2**30:.1f} GB 필요, {free / 2**30:.1f} GB 남음")
        arch = sa.download(it, ROOT / "sounds" / "_downloads")
        sa.extract(it, arch, ROOT)
        sa.apply_overlays(m, ROOT, it["id"])
        if not sa.markers_ok(ROOT, it):
            raise RuntimeError(f"{pack_id}: 풀었는데 기대한 파일이 없음 {it.get('markers')}")
        arch.unlink(missing_ok=True)
        sa.write_attribution(m, ROOT)
    finally:
        sa.emit = old
    return {"id": pack_id, "installed": True, "seconds": round(time.time() - t0, 1),
            "log": [x for x in log if x["event"] in ("log", "error")][-5:]}


def _user_catalog():
    if not USER_YAML.exists():
        return {"packs": {}, "sfz": {}}
    return yaml.safe_load(USER_YAML.read_text(encoding="utf-8")) or {"packs": {}, "sfz": {}}


def _save_user(cat):
    USER_YAML.write_text(yaml.safe_dump(cat, allow_unicode=True, sort_keys=False), encoding="utf-8")


def _slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:48]


def add_from_url(url, pack_id, name, license, author="", homepage="", roles=None, log=None):
    """목록에 없는 무료 SFZ 팩(zip). roles = {역할이름: "팩 안 .sfz 상대경로"} — 비우면 .sfz 파일을 찾아 파일 이름으로 등록."""
    log = log if log is not None else []
    pack_id = _slug(pack_id)
    lic = (license or "").strip()
    if not any(k in lic.lower() for k in FREE_LICENSES):
        raise ValueError(f"자유 라이선스만 받습니다(CC0·CC-BY·Public Domain·MIT…). 받은 값: '{license}'")
    if not url.lower().startswith("https://"):
        raise ValueError("https 주소만")
    dest = USER_DIR / pack_id
    dl = ROOT / "sounds" / "_downloads"
    dl.mkdir(parents=True, exist_ok=True)
    arch = dl / f"user_{pack_id}.zip"
    t0 = time.time()
    # 받기(크기 상한·zip 확인)
    with sa._open(url) as r:
        total = int(r.headers.get("Content-Length") or 0)
        if total > MAX_BYTES:
            raise RuntimeError(f"너무 큼: {total / 2**30:.1f} GB (상한 3 GB)")
        ctype = (r.headers.get("Content-Type") or "").lower()
        with open(arch, "wb") as f:
            got = 0
            while True:
                chunk = r.read(sa.CHUNK)
                if not chunk:
                    break
                got += len(chunk)
                if got > MAX_BYTES:
                    raise RuntimeError("너무 큼(상한 3 GB)")
                f.write(chunk)
    if not zipfile.is_zipfile(arch):
        arch.unlink(missing_ok=True)
        raise RuntimeError(f"zip 파일이 아님(Content-Type {ctype}) — 직접 받을 수 있는 zip 링크여야 합니다")
    with zipfile.ZipFile(arch) as z:
        names = [i.filename for i in z.infolist() if not i.is_dir()]
    bad = [n for n in names if n.lower().endswith((".exe", ".msi", ".dll", ".bat", ".cmd", ".ps1", ".vbs", ".scr"))]
    if bad:
        arch.unlink(missing_ok=True)
        raise RuntimeError(f"실행 파일이 들어 있어 거부: {bad[:3]}")
    sfz = [n for n in names if n.lower().endswith(".sfz")]
    if not sfz:
        arch.unlink(missing_ok=True)
        raise RuntimeError("SFZ 파일이 없는 압축 — 지금은 SFZ 팩만 받습니다")
    # 최상위 폴더 하나로 감싸져 있으면 벗긴다
    tops = {n.split("/")[0] for n in names}
    strip = 1 if len(tops) == 1 and all("/" in n for n in names) else 0
    item = {"id": f"user-{pack_id}", "dest": str(dest.relative_to(ROOT)).replace("\\", "/"), "strip": strip}
    old = sa.emit
    sa.emit = _quiet(log)
    try:
        sa.extract(item, arch, ROOT)
    finally:
        sa.emit = old
    arch.unlink(missing_ok=True)
    # 역할 등록
    cat = _user_catalog()
    found = {}
    for n in sorted(sfz):
        rel = "/".join(n.split("/")[strip:])
        key = roles and next((k for k, v in roles.items() if v == rel), None)
        key = key or _slug(Path(rel).stem).replace("-", "_") or "sound"
        if key in cat.get("sfz", {}) or key in found:
            key = f"{pack_id.replace('-', '_')}_{key}"
        found[key] = {"path": f"{item['dest']}/{rel}", "pack": pack_id, "note": f"{name} ({lic})"}
    cat.setdefault("sfz", {}).update(found)
    cat.setdefault("packs", {})[pack_id] = {"name": name, "license": lic, "author": author, "homepage": homepage,
                                            "url": url, "dest": item["dest"], "sounds": list(found),
                                            "added": time.strftime("%Y-%m-%d")}
    _save_user(cat)
    # 출처 기록
    attr = ROOT / "sounds" / "ATTRIBUTION_user.md"
    with open(attr, "a", encoding="utf-8") as f:
        f.write(f"- **{name}** — {lic}" + (f", {author}" if author else "") + f" — {homepage or url}\n")
    return {"id": pack_id, "installed": True, "seconds": round(time.time() - t0, 1), "sfz_files": len(sfz),
            "sounds": {k: v["path"] for k, v in found.items()},
            "note": "이 역할 이름을 song_track(sound=…) 이나 build_spec 의 sound 에 바로 쓸 수 있다"}
