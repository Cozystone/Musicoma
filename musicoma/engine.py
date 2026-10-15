"""엔진 클라이언트. 엔진이 안 떠 있으면 띄운다.

    from musicoma.engine import connect
    e = connect()
    e.call("edit.new", {"name": "song", "bpm": 90})
"""
import json
import socket
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENGINE_EXE = ROOT / "engine/build/musicoma_engine_artefacts/Release/musicoma-engine.exe"
PORT = 47800


class EngineError(RuntimeError):
    pass


class Engine:
    def __init__(self, host="127.0.0.1", port=PORT, client="claude"):
        self.sock = socket.create_connection((host, port), timeout=900)
        self.file = self.sock.makefile("rwb")
        self.client = client
        self.next_id = 1
        self.events = []

    def call(self, method, params=None):
        req = {"id": self.next_id, "method": method, "params": params or {}, "client": self.client}
        self.next_id += 1
        self.file.write((json.dumps(req, ensure_ascii=False) + "\n").encode("utf-8"))
        self.file.flush()
        while True:
            line = self.file.readline()
            if not line:
                raise EngineError("engine connection closed")
            reply = json.loads(line.decode("utf-8"))
            if "event" in reply:
                self.events.append(reply)
                continue
            if not reply.get("ok"):
                raise EngineError(f"{method}: {reply.get('error')}")
            return reply.get("result")

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass


def is_running(port=PORT):
    try:
        socket.create_connection(("127.0.0.1", port), timeout=0.5).close()
        return True
    except OSError:
        return False


def start(port=PORT, wait=20.0):
    if is_running(port):
        return
    if not ENGINE_EXE.exists():
        raise EngineError(f"engine not built: {ENGINE_EXE} (run engine/build.bat)")
    log = open(ROOT / "engine/engine.log", "ab")
    flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(subprocess, "DETACHED_PROCESS", 0)
    subprocess.Popen([str(ENGINE_EXE), "--port", str(port), "--root", str(ROOT)],
                     cwd=ENGINE_EXE.parent, stdout=log, stderr=log, creationflags=flags)
    t0 = time.time()
    while time.time() - t0 < wait:
        if is_running(port):
            return
        time.sleep(0.25)
    raise EngineError("engine did not start (see engine/engine.log)")


def connect(client="claude", port=PORT):
    start(port)
    return Engine(port=port, client=client)
