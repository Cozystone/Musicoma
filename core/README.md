# Musicoma Core — 자체 오디오 엔진

`musicoma-engine.exe` (127.0.0.1:47800, 줄 단위 JSON). Tracktion Engine·JUCE·sfizz 없이 표준 C++ + Windows API + Steinberg VST3 SDK(MIT)만 쓴다.
코드는 전부 새로 썼다(클린룸) — 옛 엔진은 바깥에서 본 동작(명령 응답·소리)만 기록해 기준으로 삼았다(`tests/golden/`).

- 설계·측정·바뀐 점: [`docs/ENGINE.md`](../docs/ENGINE.md)
- 빌드: `core\build.bat` (MSVC x64 + Ninja) → `core\build\musicoma-engine.exe` · 모듈 시험 `test-fx` / `test-vst3` / `test-io`
- 소스: `src/` 공용(JSON · 오디오 파일 WAV/FLAC · 샘플 풀 · SFZ 파서 · 샘플러 · DSP) · `src/engine/` 엔진(모델 · 명령 · 그래프 · 실시간 · 이펙트 · VST3 · 입출력)

## 자체 SFZ 샘플러가 지원하는 것
헤더 `<control> <global> <master> <group> <region> <curve>`, `#include`, `#define`. 매핑(key·vel·라운드로빈·트리거·CC 범위·키스위치),
음량(velcurve·veltrack·keytrack·크로스페이드·rt_decay), 음높이(tune·transpose·bend), 재생(offset·end·delay·루프), DAHDSR 엔벨로프,
끄기(group·off_by·polyphony), 필터·EQ, CC 모듈레이션(`X_onccN`, 곡선). LFO·flex EG·내장 파형은 무시(세어서 보고).
Musicoma 라이브러리 160개 프로그램 전부 읽힘.
