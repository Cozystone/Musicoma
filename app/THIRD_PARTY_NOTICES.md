# Musicoma — 제3자 구성요소와 라이선스

설치 파일(`Musicoma Setup <버전>.exe`)에 **들어 있는** 것과, 첫 실행 때 **공식 배포처에서 받는** 것을 나눠 적는다.
(2026-10-15 기준. 버전이 바뀌면 이 문서도 갱신한다.)

## ⚠ 배포 전에 반드시 읽을 것
Musicoma 엔진(`musicoma-engine.exe`)은 **Tracktion Engine (GPL-3.0)** 과 **JUCE (AGPL-3.0, 상용 라이선스 선택 가능)** 를
링크한다. 또 런타임의 **pedalboard** 는 GPL-3.0 이다.
- 본인 PC 에서 쓰는 것은 문제없다.
- **설치 파일을 다른 사람에게 주는 순간** "배포"가 된다. 그때는 ① 엔진·셸 전체의 대응 소스 코드를 같은 조건(GPL-3.0/AGPL-3.0)으로
  함께 제공하고 라이선스 고지를 유지하거나, ② Tracktion·JUCE 의 상용 라이선스를 사야 한다.
  AGPL 은 네트워크로 서비스하는 경우에도 소스 제공 의무가 생긴다.
- 이 고지 문서는 법률 자문이 아니다. 외부 배포 전에는 각 라이선스 원문을 확인할 것.

## 1. 설치 파일에 포함된 것

### 셸 · 엔진
| 구성요소 | 라이선스 | 비고 |
|---|---|---|
| Electron 44 (Chromium, Node.js 포함) | MIT (Chromium·Node 는 각자 BSD/MIT 등 — `LICENSES.chromium.html` 이 설치 폴더에 함께 들어감) | 데스크톱 셸 |
| electron-builder / NSIS | MIT / zlib | 설치 프로그램 |
| Musicoma engine | (본인 코드) + 아래 링크 라이브러리 | `musicoma-engine.exe` |
| Tracktion Engine | **GPL-3.0** (상용 라이선스 별도) | 엔진에 정적 링크 |
| JUCE | **AGPL-3.0** (상용 라이선스 별도) | 엔진에 정적 링크 |
| sfizz 1.2.3 | BSD-2-Clause | `sfizz.dll` (https://github.com/sfztools/sfizz) |

### Python 런타임 (`resources/runtime/python`)
| 구성요소 | 라이선스 |
|---|---|
| CPython 3.13.12 (python-build-standalone, Astral) | PSF-2.0 (+ OpenSSL Apache-2.0, libffi MIT, SQLite public domain, zlib, bzip2, xz 등 — `runtime/python/` 안의 각 라이선스 파일) |
| uv 0.13.1 (`resources/runtime/uv.exe`) | MIT OR Apache-2.0 |

### Python 패키지 (런타임에 설치된 것 전부)
| 패키지 | 버전 | 라이선스 |
|---|---|---|
| annotated-types | 0.8.0 | MIT |
| anyio | 4.15.1 | MIT |
| attrs | 26.1.0 | MIT |
| audioop-lts | 0.2.2 | PSF-2.0 |
| audioread | 3.1.0 | MIT |
| certifi | 2026.7.22 | MPL-2.0 |
| cffi | 2.1.1 | MIT-0 |
| charset-normalizer | 3.5.2 | MIT |
| click | 8.5.0 | BSD-3-Clause |
| cloudpickle | 3.1.2 | BSD-3-Clause |
| contourpy | 1.4.0 | BSD-3-Clause |
| cryptography | 50.0.2 | Apache-2.0 OR BSD-3-Clause |
| cycler | 0.12.1 | BSD-3-Clause |
| decorator | 5.3.1 | BSD-2-Clause |
| fonttools | 4.67.0 | MIT |
| h11 | 0.16.0 | MIT |
| httpcore | 1.0.9 | BSD-3-Clause |
| httpx | 0.28.1 | BSD-3-Clause |
| httpx-sse | 0.4.3 | MIT |
| idna | 3.20 | BSD-3-Clause |
| joblib | 1.6.0 | BSD-3-Clause |
| jsonschema | 4.26.0 | MIT |
| jsonschema-specifications | 2025.9.1 | MIT |
| kiwisolver | 1.5.1 | BSD-3-Clause |
| lazy-loader | 0.6 | BSD-3-Clause |
| librosa | 0.11.0 | ISC |
| llvmlite | 0.47.0 | BSD-2-Clause AND Apache-2.0 WITH LLVM-exception |
| matplotlib | 3.11.0 | PSF 기반 matplotlib License |
| mcp | 1.30.0 | MIT |
| msgpack | 1.2.3 | Apache-2.0 |
| narwhals | 2.27.1 | MIT |
| numba | 0.65.1 | BSD-2-Clause |
| numpy | 2.4.6 | BSD-3-Clause (+ 0BSD, MIT, Zlib, CC0 구성요소) |
| packaging | 26.3 | Apache-2.0 OR BSD-2-Clause |
| **pedalboard** | 0.9.26 | **GPL-3.0** (JUCE 포함) |
| pillow | 12.3.0 | MIT-CMU |
| pip | 26.0.1 | MIT |
| platformdirs | 4.13.0 | MIT |
| pooch | 1.9.0 | BSD-3-Clause |
| pycparser | 3.11 | BSD-3-Clause |
| pydantic / pydantic-core / pydantic-settings | 2.14.1 / 2.50.1 / 2.16.0 | MIT |
| PyJWT | 2.15.1 | MIT |
| pyloudnorm | 0.2.0 | MIT |
| pyparsing | 3.3.3 | MIT |
| python-dateutil | 2.9.0.post0 | Apache-2.0 / BSD-3-Clause |
| python-dotenv | 1.2.4 | BSD-3-Clause |
| python-multipart | 0.0.32 | Apache-2.0 |
| pywin32 | 312 | PSF-2.0 |
| pyworld | 0.3.5 | MIT (WORLD: modified BSD) |
| PyYAML | 6.0.3 | MIT |
| referencing | 0.37.0 | MIT |
| requests | 2.34.2 | Apache-2.0 |
| rpds-py | 2026.9.1 | MIT |
| scikit-learn | 1.9.1 | BSD-3-Clause |
| scipy | 1.17.1 | BSD-3-Clause |
| six | 1.17.0 | MIT |
| soundfile | 0.13.1 | BSD-3-Clause (libsndfile 는 LGPL-2.1 — 동적 로드 DLL) |
| soxr | 1.1.0 | LGPL-2.1-or-later |
| sse-starlette | 3.5.0 | BSD-3-Clause |
| standard-aifc / standard-chunk / standard-sunau | 3.13.0 | PSF-2.0 |
| starlette | 1.8.0 | BSD-3-Clause |
| threadpoolctl | 3.7.0 | BSD-3-Clause |
| typing-extensions / typing-inspection | 4.16.0 / 0.4.4 | PSF-2.0 / MIT |
| urllib3 | 2.8.0 | MIT |
| uvicorn | 0.54.0 | BSD-3-Clause |
| websockets | 14.1 | BSD-3-Clause |

목록 재생성: `app\runtime\dist\python\python.exe -c "import importlib.metadata as m; [print(d.metadata['Name'], d.version, d.metadata.get('License-Expression') or d.metadata.get('License')) for d in m.distributions()]"`

## 2. 첫 실행 때 받는 것 (설치 파일에 없음)
정확한 URL·크기·해시는 `musicoma/setup_manifest.json`. 설치 후 `<root>/sounds/ATTRIBUTION.md` 가 자동으로 생긴다.

### 음원 (기본 팩)
| 항목 | 라이선스 | 출처 표기 |
|---|---|---|
| Salamander Grand Piano V3 | **CC-BY-3.0** | **필요** — "Salamander Grand Piano V3 by Alexander Holm, CC BY 3.0" (SFZ 매핑 kinwie / sfzinstruments) |
| Greg Sullivan E-Pianos (CP80 · Pianet T · Wurlitzer EP200) | **CC-BY-3.0** | **필요** — "E-Pianos by Greg Sullivan (sullivang.net), CC BY 3.0" (SFZ 매핑 kinwie / sfzinstruments) |
| Virtuosity Drums 0.925 (sfzinstruments) | CC0-1.0 | 불필요 |
| VS Chamber Orchestra CE 1.1.0 (Versilian Studios) | CC0-1.0 | 불필요 |
| Karoryfer Big Rusty Drums · Black And Blue Basses · Meatbass · Shinyguitar · Weresax | CC0-1.0 | 불필요 |
| Musicoma 자체 합성 퐁크 킷(808 킷·카우벨·808 베이스, `musicoma/kits.py` 가 처음 쓸 때 생성) | CC0-1.0 | 불필요 |

CC-BY 음원으로 만든 곡을 공개할 때는 설명란 등에 위 표기를 넣는다.

### 플러그인 (VST3)
| 항목 | 라이선스 |
|---|---|
| Surge XT 1.3.4 | GPL-3.0-or-later |
| Dragonfly Reverb 3.2.10 | GPL-3.0-or-later |
| Airwindows Consolidated | GPL-3.0 (래퍼) / Airwindows DSP 코드 MIT |
| Dexed 1.0.1 (전체 팩만) | GPL-3.0 |

### AI 모듈 (선택, NVIDIA GPU)
| 항목 | 라이선스 |
|---|---|
| PyTorch / torchaudio (cu128) | BSD-3-Clause (CUDA 런타임 DLL 은 NVIDIA EULA) |
| faster-whisper (+ CTranslate2) | MIT |
| demucs | MIT |
| ACE-Step 1.5 (코드·가중치 — 주 보컬 엔진, xl-base·VAE·Qwen3-Embedding-0.6B) | MIT (Qwen3-Embedding: Apache-2.0) |
| htdemucs 가중치 | MIT |
| SoulX-Singer (코드·가중치) | Apache-2.0 |
| VoxCPM2 (코드·가중치) | Apache-2.0 |
| Whisper "small" 모델 (faster-whisper 가 처음 쓸 때 받음) | MIT |
