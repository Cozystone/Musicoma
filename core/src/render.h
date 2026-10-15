// Musicoma Core — 렌더 계획(JSON) → 곡 그래프(트랙·클립·센드·마스터) → 스테레오 버퍼
#pragma once
#include <map>
#include <string>
#include <vector>
#include "json.h"
#include "sampler.h"

namespace mc {

struct RenderOptions
{
    int sampleRate = 48000;
    int threads = 0;            // 0 = 하드웨어 스레드 수
    Tuning tuning;
    int mixPanLaw = -1;         // -1 = 계획/기본값
};

struct RenderResult
{
    std::vector<std::vector<float>> out;    // L, R
    int64_t frames = 0;
    double audioSeconds = 0;
    std::vector<std::string> warnings;
    Json stats = Json::object();
};

/** 계획 JSON 을 렌더한다. 실패하면 예외. */
RenderResult renderPlan (const Json& plan, const RenderOptions& opt);

/** 계획의 "core_tuning" 객체/명령행 key=value 로 Tuning 을 고친다. */
bool applyTuning (Tuning& t, const std::string& key, double value);

} // namespace mc
