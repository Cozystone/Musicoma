"""생성기 — ACE-Step 1.5(로컬, MIT)로 '샘플 원곡'을 만든다.

저작권 있는 녹음을 받아오는 대신, 원하는 시대·장르의 가짜 레코드를 직접 찍는다.
결과는 sounds/generated/<slug>/ 에 WAV + 프롬프트 원문 JSON 으로 남는다(재현용).

    from musicoma.gen import generate
    generate("1983 Japanese city pop, female vocal, Rhodes, slap bass, brass", bpm=104, key="F major",
             seconds=60, lyrics="[verse]\\n...", slug="citypop-01")
"""
import json
import os
import re
import subprocess
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ACE_DIR = ROOT / "third_party/ace-step"
OUT = ROOT / "sounds/generated"
API = "http://127.0.0.1:8001"


def _post(path, body, timeout=60):
    req = urllib.request.Request(API + path, data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.loads(r.read().decode("utf-8"))
    if data.get("code") != 200:
        raise RuntimeError(f"ACE-Step {path}: {data.get('error')}")
    return data["data"]


def is_running():
    try:
        urllib.request.urlopen(API + "/health", timeout=1)
        return True
    except Exception:
        try:
            urllib.request.urlopen(API + "/v1/models", timeout=1)
            return True
        except Exception:
            return False


def start(wait=120):
    if is_running():
        return
    uv = next(Path.home().glob("AppData/Local/Microsoft/WinGet/Packages/astral-sh.uv*/uv.exe"), None)
    if uv is None:
        raise RuntimeError("uv not found — ACE-Step not installed")
    log = open(ROOT / "third_party/ace-step.log", "ab")
    flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(subprocess, "DETACHED_PROCESS", 0)
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}   # cp949 콘솔에서 죽지 않게
    subprocess.Popen([str(uv), "run", "acestep-api", "--host", "127.0.0.1", "--port", "8001",
                      "--download-source", "huggingface"], cwd=ACE_DIR, stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                     creationflags=flags, env=env)
    t0 = time.time()
    while time.time() - t0 < wait:
        if is_running():
            return
        time.sleep(1)
    raise RuntimeError("ACE-Step API did not start (see third_party/ace-step.log)")


def _slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:48] or "gen"


def generate(prompt, lyrics="", bpm=None, key=None, seconds=60, instrumental=False, seed=None, n=1,
             slug=None, task="text2music", src_audio=None, reference_audio=None, cover_strength=None,
             repaint=None, steps=8, thinking=True, language="en", timeout=1800, **extra):
    """생성하고 WAV 경로 목록을 돌려준다. task: text2music | cover | repaint | extract ..."""
    start()
    body = {
        "prompt": prompt, "lyrics": "[Instrumental]" if instrumental and not lyrics else lyrics,
        "audio_duration": seconds, "audio_format": "wav", "batch_size": n, "inference_steps": steps,
        "thinking": thinking, "vocal_language": language, "task_type": task,
    }
    if bpm:
        body["bpm"] = int(round(bpm))
    if key:
        body["key_scale"] = key
    if seed is not None:
        body.update({"use_random_seed": False, "seed": int(seed)})
    files = {}
    if src_audio:
        files["src_audio"] = Path(src_audio)
    if reference_audio:
        files["reference_audio"] = Path(reference_audio)
    if cover_strength is not None:
        body["audio_cover_strength"] = cover_strength
    if repaint:
        body["repainting_start"], body["repainting_end"] = repaint

    body.update(extra)
    if files:
        # 서버가 절대 경로를 막으므로 파일은 업로드(multipart)로 보낸다
        import httpx
        form = {k: (json.dumps(v) if isinstance(v, (bool, dict, list)) else str(v)) for k, v in body.items()}
        with httpx.Client(timeout=300) as c:
            r = c.post(API + "/release_task", data=form,
                       files={k: (p.name, p.read_bytes(), "audio/wav") for k, p in files.items()})
        data = r.json()
        if data.get("code") != 200:
            raise RuntimeError(f"ACE-Step release_task: {data.get('error') or data}")
        task_id = data["data"]["task_id"]
    else:
        task_id = _post("/release_task", body)["task_id"]
    t0 = time.time()
    while True:
        res = _post("/query_result", {"task_id_list": [task_id]})[0]
        if res["status"] == 1:
            break
        if res["status"] == 2:
            raise RuntimeError(f"generation failed: {res.get('result')}")
        if time.time() - t0 > timeout:
            raise TimeoutError("generation timed out")
        time.sleep(2)

    items = json.loads(res["result"]) if isinstance(res["result"], str) else res["result"]
    folder = OUT / (slug or _slug(prompt))
    folder.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    paths = []
    for i, it in enumerate(items):
        dst = folder / f"{stamp}_{i}.wav"
        urllib.request.urlretrieve(API + it["file"], dst)
        meta = {"prompt": prompt, "lyrics": body["lyrics"], "request": body, "metas": it.get("metas"),
                "seed": it.get("seed_value"), "dit_model": it.get("dit_model"), "lm_model": it.get("lm_model"),
                "generation_info": it.get("generation_info"), "seconds_taken": round(time.time() - t0, 1)}
        dst.with_suffix(".json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
        paths.append(str(dst))
    return paths
