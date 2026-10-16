// Musicoma Engine — VST3 플러그인 호스팅(Steinberg VST3 SDK 3.8.1, MIT — third_party/vst3sdk).
// 구현: core/src/engine/vst3_*.cpp
#pragma once
#include <memory>
#include <string>
#include <vector>
#include "device.h"

namespace mc {

struct Vst3Desc
{
    std::string name;        // "Surge XT"
    std::string vendor;      // "Surge Synth Team"
    std::string category;    // "Instrument|Synth", "Fx|Reverb" …
    std::string path;        // .vst3 번들/파일 경로
    std::string cid;         // 클래스 ID(16진 32자)
    bool instrument = false;
};

/** dirs 아래 .vst3 를 찾아 오디오 클래스 목록을 만든다(번들 폴더·단일 파일 둘 다). 결과는 캐시 파일에 둘 수 있다. */
std::vector<Vst3Desc> scanVst3 (const std::vector<std::string>& dirs, std::vector<std::string>* warnings = nullptr);

/** 플러그인 인스턴스 만들기(초기화·버스 활성화·처리 준비 전까지). 실패하면 nullptr + error. */
std::unique_ptr<Device> createVst3 (const Vst3Desc& desc, std::string& error);

/** 창 스레드: 플러그인 편집 창 메시지 루프를 돌린다(엔진 main 이 별도 스레드로 부름). 프로세스 종료까지 반환 안 함. */
void runVst3WindowThread();

} // namespace mc
