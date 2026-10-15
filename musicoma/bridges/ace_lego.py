"""Musicoma ↔ ACE-Step 1.5 Lego — 우리 비트를 '듣고' 그 위에 보컬 트랙을 생성한다(반주 조건부).
ACE-Step venv 의 python 으로 실행한다(musicoma 패키지는 import 하지 않음). ACE 위치 = ACESTEP_HOME 또는 third_party/ace-step-15.

python ace_lego.py request.json               한 번 실행(모델 로드 → seeds 전부 → 종료)
python ace_lego.py --serve config.json      상주(10-15 속도 개선): 모델은 한 번만 올리고, stdin 한 줄 = 요청 하나
request = {"beat": "beat.wav", "lyrics": "[Verse]\n...", "caption": "...", "bpm": 88, "key": "A major",
           "start": 10.9, "end": 32.7, "seeds": [1, 2, 3], "out_dir": "...", "track": "vocals", "steps": 50,
           "model": "acestep-v15-xl-base", "offload": true}
출력: 시드마다 {"seed": n, "ok": true, "path": ...} · 요청 끝에 {"files": [...]}
"""
import json
import os
import sys

# ACE-Step 1.5 체크아웃(별도 git·venv) — ACE 의 python 으로 실행하고 cwd 도 거기
HERE = os.environ.get("ACESTEP_HOME") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "third_party", "ace-step-15")
HERE = os.path.abspath(HERE)
sys.path.insert(0, HERE)


def load(cfg):
    from acestep.handler import AceStepHandler
    from acestep.llm_inference import LLMHandler
    dit = AceStepHandler()
    msg, ok = dit.initialize_service(project_root=HERE, config_path=cfg.get("model", "acestep-v15-xl-base"),
                                     device="cuda", offload_to_cpu=cfg.get("offload", True),
                                     offload_dit_to_cpu=cfg.get("offload_dit", False),
                                     quantization=cfg.get("quantization"))
    print(json.dumps({"init": ok, "msg": str(msg)[:300]}), flush=True)
    if not ok:
        sys.exit(2)
    _cache_vae_encode(dit)
    return dit, LLMHandler()                 # Lego 는 소스 오디오 직접 조건이라 LM 을 건너뛴다(inference.py)


def _cache_vae_encode(dit, keep=12):
    """같은 오디오(반주 구간·참조 목소리)를 테이크마다 다시 VAE 인코딩하던 것(테이크 9초 중 7.6초 — 10-15 실측)을 한 번만.
    입력 텐서 내용의 해시로 기억한다. 시드마다 달라지는 건 확산 노이즈라 결과는 같다."""
    import hashlib
    import torch
    orig = dit.tiled_encode
    cache = {}

    def cached(audio, *a, **k):
        t = audio.detach()
        key = hashlib.sha1(t.float().contiguous().cpu().numpy().tobytes()).hexdigest() + repr((tuple(t.shape), a, sorted(k.items())))
        if key not in cache:
            if len(cache) >= keep:
                cache.pop(next(iter(cache)))
            cache[key] = orig(audio, *a, **k)
        v = cache[key]
        return v.clone() if torch.is_tensor(v) else v
    dit.tiled_encode = cached

    # 참조 목소리는 ACE 가 매번 무작위 10초 ×3 조각을 뽑는다 → 인코딩 캐시가 안 맞고 목소리 조건도 테이크마다 흔들린다.
    # 같은 파일이면 처음 뽑은 조각을 계속 쓴다(같은 사람 유지가 목적 — 10-15)
    orig_ref = dit.process_reference_audio
    refs = {}

    def fixed_ref(audio_file):
        if audio_file is None:
            return orig_ref(audio_file)
        try:
            k = (os.path.abspath(audio_file), os.path.getmtime(audio_file))
        except OSError:
            return orig_ref(audio_file)
        if k not in refs:
            refs[k] = orig_ref(audio_file)
        v = refs[k]
        return v.clone() if torch.is_tensor(v) else v
    dit.process_reference_audio = fixed_ref


def run(dit, llm, req):
    from acestep.inference import GenerationParams, GenerationConfig, generate_music
    track = req.get("track", "vocals")
    files = []
    os.makedirs(req["out_dir"], exist_ok=True)
    seeds_all = [int(x) for x in req.get("seeds", [1])]
    n = max(1, int(req.get("batch", 1)))                   # 한 번에 여러 테이크(인코딩·텍스트 조건 공유, GPU 를 더 채움)
    for g in range(0, len(seeds_all), n):
        group = seeds_all[g:g + n]
        seed = group[0]
        task = req.get("task", "lego")
        extra = {}
        if task == "lego":
            extra["instruction"] = f"Generate the {track.upper()} track based on the audio context:"
        if task == "cover":
            extra["audio_cover_strength"] = float(req.get("cover_strength", 0.7))
        params = GenerationParams(
            task_type=task, src_audio=req["beat"], **extra,
            caption=req.get("caption", ""), lyrics=req.get("lyrics", ""),
            bpm=req.get("bpm"), keyscale=req.get("key", ""),
            repainting_start=float(req.get("start", 0.0)), repainting_end=float(req.get("end", -1)),
            thinking=False, use_cot_metas=False, use_cot_caption=False, use_cot_language=False,
            seed=int(seed), inference_steps=int(req.get("steps", 50)),
            **({"reference_audio": req["reference"]} if req.get("reference") else {}),
            **({"vocal_language": req["vocal_language"]} if req.get("vocal_language") else {}),
            **({"guidance_scale": float(req["guidance"])} if req.get("guidance") else {}),
        )
        config = GenerationConfig(batch_size=len(group), audio_format="wav", use_random_seed=False, seeds=group)
        res = generate_music(dit, llm, params, config, save_dir=os.path.join(req["out_dir"], f"seed{seed}"))
        if not res.success:
            print(json.dumps({"seed": seed, "error": str(res.error)[:500]}), flush=True)
            continue
        for i, a in enumerate(res.audios):
            sd = group[i] if i < len(group) else seed
            files.append({"seed": sd, "path": a["path"]})
            print(json.dumps({"seed": sd, "ok": True, "path": a["path"]}), flush=True)
    print(json.dumps({"files": files}), flush=True)


def main(argv):
    if argv[0] == "--serve":
        cfg = json.load(open(argv[1], encoding="utf-8")) if len(argv) > 1 else {}
        dit, llm = load(cfg)
        print(json.dumps({"ready": True}), flush=True)
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            if line == "quit":
                break
            try:
                run(dit, llm, json.loads(line))
            except Exception as e:                       # 요청 하나가 실패해도 상주는 계속
                print(json.dumps({"files": [], "error": repr(e)[:500]}), flush=True)
        return
    req = json.load(open(argv[0], encoding="utf-8"))
    dit, llm = load(req)
    run(dit, llm, req)


if __name__ == "__main__":
    main(sys.argv[1:])
