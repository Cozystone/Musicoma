# Musicoma 데스크톱 앱 (설치판)

`dist/Musicoma Setup <버전>.exe` 를 실행하면 Electron 셸 "Musicoma" 를 설치한다
(사용자별 설치, 기본 위치 `%LOCALAPPDATA%\Programs\musicoma`, 위치 변경 가능, 시작 메뉴 + 바탕화면 바로가기).
**개발용 Python 환경이 없는 PC 에서도 돈다** — Python 런타임·엔진·코드가 설치 파일에 들어 있다.
음원(수 GB)은 넣지 않고, 첫 실행 때 공식 배포처에서 받는다.

## 설치 폴더 구조
```
<설치 폴더>\
  Musicoma.exe, resources\app.asar          Electron 셸 (main.js · splash · 첫 실행 창)
  resources\runtime\python\                 독립 실행 CPython 3.13.12 + 핵심 패키지 (≈430 MB, venv 아님)
  resources\runtime\uv.exe                  AI 모듈 설치용
  resources\musicoma\                       ← 설치판의 "루트"
    musicoma\  (+ knowledge\*.yaml, setup_manifest.json, setup_assets.py, sfz_overlays\)
    ui\        (server.py, web\)
    engine\build\musicoma_engine_artefacts\Release\musicoma-engine.exe, sfizz.dll
    setup\     (requirements-*.txt, ai\ — AI 접착 스크립트)
    THIRD_PARTY_NOTICES.md
    ── 실행하면서 생기는 것 ──
    sounds\sfz\…, sounds\plugins\vst3\…     첫 실행 때 받은 음원·플러그인 (+ sounds\ATTRIBUTION.md)
    projects\, renders\                     작업
    python-ai\                              AI 모듈(선택) — 런타임 위에 얹은 가상환경
    third_party\soulx-singer\, voxcpm\      AI 보컬 모듈(선택)
    .mcp.json                               셸이 번들 Python 경로로 자동 작성
```
설치 파일에 **넣지 않는 것**: `sounds/`, `projects/`, `renders/`, `third_party/`, `.venv/`.

## 실행하면 하는 일
1. **루트 결정**: ① 환경변수 `MUSICOMA_ROOT` → ② `%APPDATA%\Musicoma\config.json` 의 `root`
   → ③ 설치 폴더의 `resources\musicoma` → ④ `D:\0.Musicoma`.
2. **Python 결정**: 루트가 설치 폴더면 `python-ai`(AI 를 깔았으면) → 번들 런타임.
   외부 루트(개발 체크아웃)면 그 루트의 `.venv` → 번들 런타임. (개발 venv 에는 AI 패키지까지 다 있으므로 그쪽을 먼저 쓴다.)
3. **첫 실행**: `<root>\sounds\sfz` 가 없거나 비었거나 기본 팩 일부가 빠져 있으면 "처음 설정" 창이 뜬다.
   - **기본 음원 받기 (약 7.1 GB 다운로드 · 설치 후 8.2 GB)** — 기본 체크
   - **AI 모듈 설치 (선택, 약 32 GB, NVIDIA GPU 필요)** — `nvidia-smi` 로 GPU 를 확인해 안내
   - 진행 상황(항목 n/12, 받은 양·속도, 푸는 중)이 창에 나온다. 창을 닫거나 "중단하고 건너뛰기"를 누르면 멈추고,
     다음 실행 때 **이어받는다**(받다 만 파일은 `sounds\_downloads\*.part`).
   - "건너뛰기" + "다시 묻지 않기" → `%APPDATA%\Musicoma\state.json` 에 `skipSetup: true`.
   - 엔진·화면 서버가 이미 떠 있으면(쓰는 중) 묻지 않는다.
4. 엔진(127.0.0.1:47800)과 화면 서버(:47802)가 이미 떠 있으면 그대로 쓰고, 없으면 직접 띄운다(창 없이).
   로그는 `%LOCALAPPDATA%\Musicoma\logs\` (`shell.log`, `engine.log`, `ui-server.log`, `setup.log`).
5. http://127.0.0.1:47802 를 1600×1000 창으로 연다.
6. 닫으면 **이 앱이 띄운 프로세스만** 끈다. 원래 떠 있던 엔진·서버는 건드리지 않는다.

## 음원·AI 설치 도구 (명령줄)
```
<python> -m musicoma.setup_assets --root <루트> --sounds core|full [--ai] [--dry-run] [--only id,id] [--keep-archives]
```
- 목록·URL·크기·해시·라이선스: `musicoma/setup_manifest.json` (2026-10-15 에 `gh api`/HEAD 로 확인).
  `core` = `knowledge/sounds.yaml` 이 쓰는 모든 악기·이펙트, `full` = core + Dexed.
- GitHub 릴리스 자산은 크기(+있으면 SHA256)를 정확히 검사, 저장소 압축(codeload)은 크기를 알 수 없어 표식 파일로 검사.
  이미 설치된 항목(표식 파일이 다 있음)은 건너뛴다. `Range` 이어받기, 실패 시 5회 재시도.
- `musicoma/sfz_overlays/` — Musicoma 가 직접 쓴 sfz 래퍼(예: Shinyguitar `musicoma_*.sfz`). 풀고 나서 복사한다.
  `sounds/` 쪽 래퍼를 고치면 여기도 같이 고칠 것.
- `--ai`: 번들 `uv.exe` 로 ① `<root>\python-ai` (번들 런타임 위 `--system-site-packages` 가상환경) 에
  torch/torchaudio 2.11 (cu128) + faster-whisper + demucs, ② `third_party\soulx-singer` (코드: GitHub 고정 커밋 zip,
  Py 3.10, torch 2.7.1, `setup\ai\soulx-singer\req-portable.txt` — webrtcvad 를 미리 빌드된 `webrtcvad-wheels` 로 바꿔
  MSVC 없이 설치) + HF 모델 2개, ③ `third_party\voxcpm` (Py 3.11, torch 2.11, voxcpm 2.0.3) + `openbmb/VoxCPM2`.
  Python 자체도 uv 가 `third_party\_python` 에 받는다. 출력은 한 줄 JSON(`event`: begin/plan/start/progress/log/cmd/done/error/finish).

## 다시 빌드
```
cd app
npm install
npm run build:runtime   # runtime\build_runtime.ps1 → runtime\dist\python (+ uv.exe), 복사본으로 import 시험까지
npm run dist            # → dist\Musicoma Setup 0.2.0.exe
npm run dist:full       # 위 둘을 한 번에
npm start               # 설치 없이 바로 실행 (번들 런타임은 runtime\dist 를 씀)
```
- `build_runtime.ps1` 은 uv 로 python-build-standalone CPython 3.13.12 를 `runtime\.cache` 에 받고,
  `runtime\dist\python` 에 복사한 뒤 `requirements-core.txt` 를 그 안에 직접 설치한다(가상환경이 아니라 어디로 옮겨도 동작).
  tkinter·테스트·콘솔 실행 파일은 뺀다. 마지막에 `third_party` 의 AI 접착 스크립트를 `runtime\ai\` 로 동기화한다.
- 엔진은 미리 빌드돼 있어야 한다(`engine\build\…\Release\musicoma-engine.exe` + `sfizz.dll`).
- 아이콘: `python scripts/make-icon.py` (Pillow) → `build/icon.ico`.
- 서명 인증서가 없으면 서명은 건너뛴다(첫 실행 때 SmartScreen 경고가 뜰 수 있다).

## 업데이트 · 제거
`build/installer.nsh` 의 `customRemoveFiles` 가 업데이트 때 **코드만** 지우고 `resources\musicoma` 아래
`sounds`, `projects`, `renders`, `python-ai`, `third_party` 등은 남긴다(다시 받지 않게).
진짜 제거 때는 "음원·AI 모듈과 프로젝트도 지울까요?" 를 묻는다(기본 아니오, 조용한 제거는 남김).

## 개발 PC 에서 (D:\0.Musicoma)
설치판은 루트 순서상 `resources\musicoma` 를 `D:\0.Musicoma` 보다 먼저 고른다.
개발 폴더를 계속 쓰려면 `%APPDATA%\Musicoma\config.json` 을 만든다:
```json
{ "root": "D:\\0.Musicoma" }
```
(또는 환경변수 `MUSICOMA_ROOT`). 이때 Python 은 `D:\0.Musicoma\.venv` 를 쓴다.

## 라이선스 · 출처 표기
자세한 목록은 [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).
- **배포 주의**: 엔진이 Tracktion Engine(GPL-3.0)과 JUCE(AGPL-3.0)를, 런타임의 pedalboard 가 GPL-3.0 을 쓴다.
  본인 PC 사용은 괜찮지만 **설치 파일을 남에게 주면** GPL/AGPL 조건(대응 소스 제공 등)을 지키거나 상용 라이선스를 사야 한다.
- Electron MIT · CPython PSF-2.0 · uv MIT/Apache-2.0 · sfizz BSD-2-Clause · 각 Python 패키지는 NOTICES 표 참고.
- 음원: **Salamander Grand Piano V3 — CC BY 3.0, Alexander Holm** / **Greg Sullivan E-Pianos — CC BY 3.0, Greg Sullivan**
  (이 둘은 곡 공개 시 출처 표기 필요). Virtuosity Drums · VSCO2 CE · Karoryfer 5종은 CC0.
  플러그인 Surge XT · Dragonfly · Airwindows Consolidated · Dexed 는 GPL-3.0 (Airwindows DSP 는 MIT).
- 설치된 항목의 표기 문구는 `<root>\sounds\ATTRIBUTION.md` 에 자동으로 모인다.
