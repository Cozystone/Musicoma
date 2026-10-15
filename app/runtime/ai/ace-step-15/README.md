ACE-Step 1.5 (MIT) — Musicoma 의 주 보컬 엔진. 반주(가이드)를 '듣고' 그 위에 보컬 트랙을 생성한다(Lego 작업).
Musicoma 쪽 다리: musicoma/bridges/ace_lego.py (이 폴더의 .venv python 으로 실행, ACESTEP_HOME 또는 third_party/ace-step-15).
필요한 모델: checkpoints/{acestep-v15-xl-base, vae, Qwen3-Embedding-0.6B} — setup_assets --ai 가 ACE 자체 다운로더로 받는다.
16GB GPU: int8 양자화 + CPU 오프로드로 동작(테이크 3개 묶음, 테이크당 ~8초).
