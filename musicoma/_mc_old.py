"""엔진에 명령 하나(또는 여러 개)를 보내는 작은 클라이언트.

python mc.py ping
python mc.py edit.new '{"name":"test","bpm":100}'
python mc.py --batch steps.json      # [{"method":..., "params":...}, ...]
"""
import json
import socket
import sys


class Engine:
    def __init__(self, host="127.0.0.1", port=47800, client="cli"):
        self.sock = socket.create_connection((host, port), timeout=600)
        self.file = self.sock.makefile("rwb")
        self.client = client
        self.next_id = 1

    def call(self, method, params=None):
        req = {"id": self.next_id, "method": method, "params": params or {}, "client": self.client}
        self.next_id += 1
        self.file.write((json.dumps(req, ensure_ascii=False) + "\n").encode("utf-8"))
        self.file.flush()
        while True:
            reply = json.loads(self.file.readline().decode("utf-8"))
            if "event" in reply:
                continue
            if not reply.get("ok"):
                raise RuntimeError(f"{method}: {reply.get('error')}")
            return reply.get("result")


def main():
    args = sys.argv[1:]
    eng = Engine()
    if args and args[0] == "--batch":
        steps = json.load(open(args[1], encoding="utf-8"))
        for s in steps:
            out = eng.call(s["method"], s.get("params"))
            print(s["method"], "->", json.dumps(out, ensure_ascii=False)[:400])
        return
    method = args[0] if args else "ping"
    params = json.loads(args[1]) if len(args) > 1 else {}
    print(json.dumps(eng.call(method, params), ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
