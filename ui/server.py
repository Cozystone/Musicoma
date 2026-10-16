"""Musicoma 화면용 중계 서버.

브라우저 ⇄ (WebSocket :47801) ⇄ 이 서버 ⇄ (TCP :47800) ⇄ 엔진
                                      └─ 'ask' 요청 → Claude Code(헤드리스, Musicoma MCP 도구만) → 진행 상황 스트림
정적 파일은 http://127.0.0.1:47802 에서.

실행: .venv/Scripts/python ui/server.py
"""
import asyncio
import functools
import http.server
import json
import shutil
import sys
import threading
import time
from pathlib import Path
from urllib.parse import unquote

import websockets

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from musicoma.engine import start as _start  # noqa: E402

start_engine = functools.partial(_start, breakaway=False)  # 화면 서버가 띄운 엔진은 앱과 함께 꺼진다

WS_PORT, HTTP_PORT, ENGINE_PORT = 47801, 47802, 47800
CLAUDE = shutil.which("claude") or str(Path.home() / ".local/bin/claude.exe")
CODEX = shutil.which("codex") or str(Path.home() / "AppData/Roaming/npm/codex.cmd")
ALLOWED = ["mcp__musicoma__*", "Read", "Glob", "Grep"]
# 화면의 사용자는 한국어로 본다 — 끝 보고만이 아니라 중간 진행 문장까지(10-16: 중간 문장이 영어로 나오던 것)
LANG_RULE = ("Musicoma 화면 사용자는 한국어 사용자다. 진행 중 짧은 문장과 최종 보고를 포함해 화면에 보이는 모든 글을 "
             "한국어로 쓴다. 코드·파일 이름·도구 이름·음악 용어(BPM, LUFS 등)만 원문 그대로 둔다.")
PY = str(ROOT / ".venv/Scripts/python.exe") if (ROOT / ".venv/Scripts/python.exe").exists() else sys.executable  # 설치판: 번들 런타임
CODEX_MCP = [  # 사용자 Codex 설정을 바꾸지 않고, 실행할 때만 Musicoma 도구를 붙인다
    "-c", f'mcp_servers.musicoma.command="{Path(PY).as_posix()}"',
    "-c", 'mcp_servers.musicoma.args=["-m","musicoma.mcp_server"]',
    "-c", f'mcp_servers.musicoma.cwd="{ROOT.as_posix()}"',
    "-c", 'mcp_servers.musicoma.env={PYTHONIOENCODING="utf-8",PYTHONUTF8="1"}',
    "-c", 'mcp_servers.musicoma.default_tools_approval_mode="approve"',
    "-c", 'approval_policy="never"',
]


def ai_status():
    import subprocess
    out = {}
    try:
        r = subprocess.run([CLAUDE, "auth", "status"], capture_output=True, text=True, timeout=20, encoding="utf-8")
        out["claude"] = {"installed": True, "logged_in": bool(json.loads(r.stdout or "{}").get("loggedIn"))}
    except Exception:
        out["claude"] = {"installed": False, "logged_in": False}
    try:
        r = subprocess.run([CODEX, "login", "status"], capture_output=True, text=True, timeout=20, encoding="utf-8")
        txt = (r.stdout + r.stderr)
        out["codex"] = {"installed": True, "logged_in": "Logged in" in txt, "detail": txt.strip()[:80]}
    except Exception:
        out["codex"] = {"installed": False, "logged_in": False}
    return out


def open_login(provider):
    """로그인은 본인이 브라우저에서 한다 — 여기선 로그인 창(터미널)만 띄운다."""
    import subprocess
    cmd = f'"{CLAUDE}" auth login' if provider == "claude" else f'"{CODEX}" login'
    subprocess.Popen(f'start "Musicoma 로그인" cmd /k {cmd}', shell=True)


class Api(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")   # 화면 파일을 고치면 바로 반영
        super().end_headers()

    def do_GET(self):
        q = self.path
        if q.startswith("/api/edit_path"):                   # 곡 이름 → 엔진 편집 파일 경로(설치 위치와 상관없이)
            from urllib.parse import parse_qs, urlparse
            from musicoma.layout import edit_file
            name = parse_qs(urlparse(q).query).get("song", [""])[0]
            return self._json({"path": str(edit_file(name))})
        if q.startswith("/api/projects"):
            return self._json(sorted(p.parent.name for p in (ROOT / "projects").glob("*/song.json")))
        if q.startswith("/api/sounds"):
            from musicoma.knowledge import sounds
            cat = sounds()
            items = [{"group": "SFZ", "name": k, "note": v.get("note", "")} for k, v in cat["sfz"].items()]
            items += [{"group": "Surge XT", "name": k, "note": ", ".join(Path(x).stem for x in v)}
                      for k, v in cat["surge_xt"].items() if k != "root"]
            for f in sorted((ROOT / cat["surge_xt"]["root"]).glob("*/*.fxp")):
                items.append({"group": "Surge: " + f.parent.name, "name": f"{f.parent.name}/{f.stem}", "note": ""})
            items += [{"group": "Effects", "name": n, "note": ""} for n in cat["effects"]["builtin"]]
            items += [{"group": "Effects", "name": e["name"], "note": e["use"]} for e in cat["effects"]["vst3"]]
            return self._json(items)
        if q.startswith("/api/ai-status"):
            return self._json(ai_status())
        if q.startswith("/api/ai-login"):
            open_login(q.split("provider=", 1)[-1])
            return self._json({"opened": True})
        if q.startswith("/api/presets"):
            from musicoma.knowledge import presets
            return self._json({r: [{"key": k, "name": v["name"]} for k, v in d.items()] for r, d in presets().items()})
        if q.startswith("/api/preset-apply"):
            from urllib.parse import parse_qs, urlparse
            a = {k: v[0] for k, v in parse_qs(urlparse(q).query).items()}
            try:
                from musicoma.mcp_server import _song
                return self._json(_song(a["song"])[a["track"]].preset(a["role"], a["key"]))
            except StopIteration:
                return self._json({"error": f"트랙 '{a.get('track')}' 을 찾지 못함"})
            except Exception as ex:
                return self._json({"error": f"{type(ex).__name__}: {ex}"})
        if q.startswith("/api/export"):
            # 화면의 '내보내기' — 렌더 + 측정(LUFS·대역·PNG). 결과는 renders 목록에 뜬다
            from urllib.parse import parse_qs, urlparse
            a = {k: v[0] for k, v in parse_qs(urlparse(q).query).items()}
            try:
                from musicoma.mcp_server import _song
                rep = _song(a["song"]).render(lufs=float(a["lufs"]) if a.get("lufs") else None, label="export")
                return self._json({"file": rep.get("file"), "loudness": rep.get("loudness"), "issues": rep.get("issues")})
            except Exception as ex:
                return self._json({"error": f"{type(ex).__name__}: {ex}"})
        if q.startswith("/api/resolve"):
            from musicoma.knowledge import resolve_sound
            return self._json(resolve_sound(unquote(q.split("name=", 1)[-1])))
        if q.startswith("/api/song"):
            f = ROOT / "projects" / unquote(q.split("name=", 1)[-1]) / "song.json"
            return self._json(json.loads(f.read_text(encoding="utf-8")) if f.exists() else {})
        if q.startswith("/api/renders"):
            d = ROOT / "projects" / unquote(q.split("name=", 1)[-1]) / "renders"
            out = []
            files = [p for p in d.glob("*") if p.suffix in (".mp3", ".wav")] if d.exists() else []
            for w in sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)[:12]:
                png = w.with_suffix(".png")
                out.append({"name": w.stem, "wav": str(w), "png": str(png) if png.exists() else None,
                            "mtime": w.stat().st_mtime})
            return self._json(out)
        if q.startswith("/api/styles"):
            from musicoma.knowledge import styles
            return self._json([{"id": k, "name": v.get("name"), "aliases": v.get("aliases", [])[:3]}
                               for k, v in styles().items()])
        if q.startswith("/api/file"):
            # 렌더 wav / png 를 화면에서 듣고 보기 (projects 아래만)
            f = Path(unquote(q.split("path=", 1)[-1])).resolve()
            if (ROOT / "projects").resolve() not in f.parents or not f.exists():
                self.send_error(404)
                return
            data = f.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", {".wav": "audio/wav", ".mp3": "audio/mpeg", ".png": "image/png"}.get(f.suffix, "application/octet-stream"))
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        return super().do_GET()

    def do_POST(self):
        """화면 마이크 흥얼거림 업로드 → sounds/inbox/hum_<시각>.wav → 알아듣기(hum.listen). 곡의 BPM·조성 기준."""
        if not self.path.startswith("/api/hum"):
            self.send_error(404)
            return
        from urllib.parse import parse_qs, urlparse
        a = {k: v[0] for k, v in parse_qs(urlparse(self.path).query).items()}
        n = int(self.headers.get("Content-Length", "0"))
        if n <= 0 or n > 50_000_000:
            return self._json({"error": "녹음이 비었거나 너무 큼"})
        raw = self.rfile.read(n)
        inbox = ROOT / "sounds" / "inbox"
        inbox.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        src = inbox / f"hum_{stamp}.webm"
        src.write_bytes(raw)
        try:
            from musicoma import hum, theory, importer
            wav = importer.to_wav(src, out_dir=inbox)
            song = {}
            f = ROOT / "projects" / a.get("song", "") / "song.json"
            if a.get("song") and f.exists():
                song = json.loads(f.read_text(encoding="utf-8"))
            # 말 + 흥얼거림을 한 번에(10-15): 지시 문장(said)과 음악 구간(music)을 나눠 듣는다
            u = hum.understand(wav, float(song.get("bpm") or a.get("bpm") or 90), song.get("key") or "C major")
            for r in u["music"]:
                r["heard"] = [theory.note_name(x["pitch"]) for x in r["notes"]] if r["mode"] == "melody" else \
                    [{36: "킥", 38: "스네어", 42: "햇"}.get(x["pitch"], "?") for x in r["notes"]]
            if not u["music"] and not u["said"]:
                return self._json({"error": "소리를 못 찾았어요 — 조금 더 크게 불러 주세요"})
            u["path"] = wav
            return self._json(u)
        except Exception as ex:
            return self._json({"error": f"{type(ex).__name__}: {ex}"})

    def _json(self, data):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def serve_http():
    handler = functools.partial(Api, directory=str(Path(__file__).parent / "web"))
    http.server.ThreadingHTTPServer(("127.0.0.1", HTTP_PORT), handler).serve_forever()


def _session_file(song):
    return ROOT / "projects" / song / "claude_session.txt"


async def ask_claude(ws, msg):
    """화면의 요청 → Claude Code 헤드리스. 같은 곡은 대화를 이어간다."""
    song, track, text = msg.get("song", ""), msg.get("track", ""), msg["ask"]
    context = _prompt(song, track, text)
    args = [CLAUDE, "-p", context, "--output-format", "stream-json", "--verbose",
            "--mcp-config", str(ROOT / ".mcp.json"), "--append-system-prompt", LANG_RULE, "--allowedTools", *ALLOWED]
    sf = _session_file(song) if song else None
    if sf and sf.exists() and not msg.get("new"):
        args += ["--resume", sf.read_text().strip()]
    proc = await asyncio.create_subprocess_exec(*args, cwd=str(ROOT), stdout=asyncio.subprocess.PIPE,
                                                stderr=asyncio.subprocess.PIPE, limit=2 ** 24)
    await ws.send(json.dumps({"claude": "start"}))
    async for raw in proc.stdout:
        try:
            ev = json.loads(raw)
        except ValueError:
            continue
        if ev.get("session_id") and sf:
            sf.parent.mkdir(parents=True, exist_ok=True)
            sf.write_text(ev["session_id"])
        if ev.get("type") == "assistant":
            for c in ev["message"].get("content", []):
                if c.get("type") == "text" and c["text"].strip():
                    await ws.send(json.dumps({"claude": "text", "text": c["text"]}, ensure_ascii=False))
                elif c.get("type") == "tool_use":
                    name = c["name"].replace("mcp__musicoma__", "")
                    detail = c["input"].get("method") or c["input"].get("op") or ""
                    await ws.send(json.dumps({"claude": "tool", "name": name, "detail": detail}, ensure_ascii=False))
        elif ev.get("type") == "result":
            await ws.send(json.dumps({"claude": "done", "result": ev.get("result", ""),
                                      "cost": ev.get("total_cost_usd")}, ensure_ascii=False))
    err = (await proc.stderr.read()).decode("utf-8", "replace").strip()
    if await proc.wait() != 0:
        await ws.send(json.dumps({"claude": "error", "text": err[-800:]}, ensure_ascii=False))


def auto_version(song):
    """AI 요청 직전 상태를 projects/<곡>/versions/auto-<시각>/ 에 남긴다(되돌릴 수 있게)."""
    import time as _t
    if not song:
        return None
    d = ROOT / "projects" / song
    if not d.exists():
        return None
    dst = d / "versions" / ("auto-" + _t.strftime("%m%d-%H%M%S"))
    dst.mkdir(parents=True, exist_ok=True)
    for f in [d / f"{song}.edit.json", d / f"{song}.tracktionedit", d / "song.json", d / "spec.json"]:
        if f.exists():
            shutil.copy2(f, dst / f.name)
    olds = sorted((d / "versions").glob("auto-*"))
    for o in olds[:-20]:                      # 자동 버전은 최근 20개만
        shutil.rmtree(o, ignore_errors=True)
    return dst.name


def _prompt(song, track, text):
    return (f"{LANG_RULE} [Musicoma 화면에서 온 요청] 현재 곡: '{song or '(새 곡)'}' (projects/{song}), 선택 트랙: '{track}'. "
            f"새 곡이면 이름을 정해 build_spec 으로 짓고, 기존 곡이면 song_status 로 상태부터 본다. "
            f"Musicoma MCP 도구로만 작업하고, 끝나면 render 해서 바꾼 것과 숫자를 짧게 한국어로 보고해. "
            f"요청이 지금 곡과 다른 장르·다른 곡이면 기존 곡을 덮지 말고 새 곡 이름으로 만든다. "
            f"장르·느낌의 기준이 필요하면 listen_reference 로 대표곡 1~3곡을 직접 들어 숫자(템포·조성·그루브·대역)로 잡는다. "
            f"요청: {text}")


async def ask_codex(ws, msg):
    song, track, text = msg.get("song", ""), msg.get("track", ""), msg["ask"]
    args = [CODEX, "exec", "--json", "--skip-git-repo-check", "-C", str(ROOT), "-s", "read-only", *CODEX_MCP,
            _prompt(song, track, text)]
    proc = await asyncio.create_subprocess_exec(*args, cwd=str(ROOT), stdin=asyncio.subprocess.DEVNULL,
                                                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                                                limit=2 ** 24)
    await ws.send(json.dumps({"claude": "start"}))
    async for raw in proc.stdout:
        try:
            ev = json.loads(raw)
        except ValueError:
            continue
        item = ev.get("item") or {}
        if ev.get("type") == "item.started" and item.get("type") == "mcp_tool_call":
            detail = (item.get("arguments") or {}).get("method") or (item.get("arguments") or {}).get("op") or ""
            await ws.send(json.dumps({"claude": "tool", "name": item.get("tool"), "detail": detail}, ensure_ascii=False))
        elif ev.get("type") == "item.completed" and item.get("type") == "agent_message":
            await ws.send(json.dumps({"claude": "text", "text": item.get("text", "")}, ensure_ascii=False))
        elif ev.get("type") == "item.completed" and item.get("type") == "mcp_tool_call" and item.get("error"):
            await ws.send(json.dumps({"claude": "error", "text": item["error"].get("message", "")}, ensure_ascii=False))
        elif ev.get("type") == "turn.completed":
            await ws.send(json.dumps({"claude": "done"}))
    await proc.wait()


async def bridge(ws):
    """브라우저 연결 하나당 엔진 연결 하나. 줄 단위 JSON 을 양방향으로 넘긴다.
    엔진이 꺼지면 다시 띄우고 다시 붙는다(브라우저 연결·AI 작업 스트림은 그대로) — 브라우저에는 engine_restarted 를 알린다."""
    link = {"writer": None, "pending": set(), "ready": asyncio.Event()}

    async def fail_pending(why):
        for i in list(link["pending"]):
            await ws.send(json.dumps({"id": i, "ok": False, "error": why}, ensure_ascii=False))
        link["pending"].clear()

    async def engine_to_browser():
        first = True
        while True:
            try:
                await asyncio.to_thread(start_engine)
                reader, writer = await asyncio.open_connection("127.0.0.1", ENGINE_PORT, limit=2 ** 24)
            except Exception as ex:  # 엔진 실행 파일 문제 등 — 잠시 뒤 다시
                print(f"engine unavailable: {ex}", flush=True)
                await asyncio.sleep(2)
                continue
            link["writer"] = writer
            link["ready"].set()
            if not first:
                print("engine restarted — reattached", flush=True)
                await ws.send(json.dumps({"event": "engine_restarted"}))
            first = False
            try:
                while True:
                    line = await reader.readline()   # 엔진이 강제로 꺼지면 빈 줄 대신 연결 리셋 오류가 난다
                    if not line:
                        break
                    try:
                        i = json.loads(line).get("id")
                        link["pending"].discard(i)
                    except ValueError:
                        pass
                    await ws.send(line.decode("utf-8"))
            except (ConnectionError, OSError, asyncio.IncompleteReadError) as ex:
                print(f"engine connection lost: {ex!r}", flush=True)
            link["writer"] = None
            link["ready"].clear()
            writer.close()
            await fail_pending("엔진이 다시 시작되는 중입니다")
            await asyncio.sleep(0.5)

    task = asyncio.create_task(engine_to_browser())
    try:
        async for msg in ws:
            req = json.loads(msg)
            if "ask" in req:
                v = auto_version(req.get("song", ""))
                if v:
                    await ws.send(json.dumps({"claude": "tool", "name": "자동 버전 저장", "detail": v}, ensure_ascii=False))
                asyncio.create_task(ask_codex(ws, req) if req.get("ai") == "codex" else ask_claude(ws, req))
                continue
            req["client"] = "ui"
            w = link["writer"]
            if w is None:                       # 앱을 막 켰을 때: 엔진이 붙을 때까지 잠깐 기다린다(10-17: 첫 ping 이 실패해 화면이 비어 있던 것)
                try:
                    await asyncio.wait_for(link["ready"].wait(), 15)
                except asyncio.TimeoutError:
                    pass
                w = link["writer"]
            if w is None or w.is_closing():
                await ws.send(json.dumps({"id": req.get("id"), "ok": False, "error": "엔진이 다시 시작되는 중입니다"},
                                         ensure_ascii=False))
                continue
            link["pending"].add(req.get("id"))
            try:
                w.write((json.dumps(req, ensure_ascii=False) + "\n").encode("utf-8"))
                await w.drain()
            except (ConnectionError, OSError):
                pass   # 읽는 쪽이 끊김을 알아채고 대기 중 요청을 오류로 돌려준 뒤 다시 붙는다
    finally:
        task.cancel()
        if link["writer"]:
            link["writer"].close()


async def watch_engine():
    """화면이 안 붙어 있어도 엔진은 늘 살아 있게(AI 작업·MCP 가 바로 쓸 수 있도록)."""
    while True:
        await asyncio.sleep(3)
        try:
            await asyncio.to_thread(start_engine)
        except Exception as ex:
            print(f"engine watchdog: {ex}", flush=True)


async def main():
    start_engine()
    asyncio.create_task(watch_engine())
    threading.Thread(target=serve_http, daemon=True).start()
    async with websockets.serve(bridge, "127.0.0.1", WS_PORT, max_size=2 ** 24):
        print(f"Musicoma UI  http://127.0.0.1:{HTTP_PORT}", flush=True)
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
