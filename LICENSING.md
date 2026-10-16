# Musicoma 라이선스 (이중 라이선스)

Copyright (C) 2026 Cozystone

Musicoma 의 코드(이 저장소의 Musicoma 가 직접 쓴 부분 — 엔진 `core/`, `musicoma/`, `ui/`, `app/`, `works/`, `tests/`, 문서)는
두 가지 라이선스 중 하나로 쓸 수 있다.

## 1. GNU Affero General Public License v3.0 (AGPL-3.0-only) — 무료
전문은 [`LICENSE`](LICENSE). 요약(법적 효력은 전문에 있음):
- 누구나 무료로 쓰고, 고치고, 다시 배포할 수 있다(상업적 사용 포함).
- 대신 **고친 Musicoma 를 배포하거나 네트워크 서비스로 제공하면, 그 전체 소스 코드를 같은 AGPL-3.0 으로 공개**해야 한다.
- 저작권·라이선스 고지를 지워서는 안 된다.

## 2. 상용 라이선스 — 유료/별도 계약
AGPL-3.0 의 소스 공개 의무 없이 Musicoma 를 제품·서비스에 넣고 싶다면 저작권자와 별도 상용 라이선스를 맺는다.
문의: GitHub [@Cozystone](https://github.com/Cozystone) (이 저장소 Issues).

## 기여
외부 기여(풀 리퀘스트)는 이중 라이선스를 유지할 수 있도록, 기여자가 저작권자에게 그 기여를 두 라이선스 모두로 배포할 권리를 준다는
데 동의한 경우에만 받는다.

## 제3자 구성요소
Musicoma 가 함께 쓰는 남의 코드·음원·모델은 각자의 라이선스를 따른다 — [`app/THIRD_PARTY_NOTICES.md`](app/THIRD_PARTY_NOTICES.md).
엔진에 들어간 외부 코드는 Steinberg VST3 SDK(MIT)뿐이고, 모두 AGPL-3.0 및 상용 배포와 함께 쓸 수 있는 허용 라이선스다.
첫 실행 때 받는 플러그인(Surge XT·Dexed·Dragonfly 등, GPL-3.0)은 따로 배포되는 별개 프로그램이다.

생성된 음악(사용자가 Musicoma 로 만든 곡)에 대해서는 Musicoma 가 어떤 권리도 주장하지 않는다.
