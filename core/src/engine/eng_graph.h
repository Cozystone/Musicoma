// Musicoma Engine — 곡 그래프: 블록 단위로 트랙(클립 → 체인 → 볼륨·팬) → 버스(센드·리턴) → 마스터.
// 실시간 재생과 오프라인 렌더가 같은 코드를 쓴다(소리가 같게).
#pragma once
#include <functional>
#include <array>
#include <map>
#include <set>
#include <string>
#include <vector>
#include "eng_model.h"

namespace mc {

class Graph
{
public:
    explicit Graph (Engine& e) : eng (e) {}

    /** 버퍼 확보(명령 스레드, 잠금 아래) */
    void prepare (double sampleRate, int maxBlock);

    /** 곡 위치 startFrame(절대 샘플, 0 = 1박 시작)부터 n 프레임. out 에 더하지 않고 '쓴다'.
        only: 비어 있지 않으면 그 트랙만 소리 낸다(렌더 tracks 옵션). live: 실시간 MIDI 입력(liveTrack 트랙에). */
    void process (float* L, float* R, int n, int64_t startFrame, bool playing,
                  const std::set<std::string>* only, const std::vector<MidiEv>* live, int liveTrack);

    /** 모든 디바이스 소리 끊기(정지·탐색) */
    void resetAll();

    /** 미터(dB): 트랙 이름 → [L,R], 마스터 */
    std::map<std::string, std::array<float, 2>> meters;
    std::array<float, 2> masterMeter { -100.0f, -100.0f };

    double sampleRate() const { return sr; }

    /** 곡 전체의 처리 지연(샘플) = 트랙 체인 지연의 최댓값. 모든 트랙을 이만큼 맞춰 늦춘다(PDC). */
    int latency();

    /** 트랙별 출력 엿듣기(페이더·팬 뒤, 마스터 앞) — 한 번의 렌더로 모든 트랙 스템을 뽑는다(10-17 속도). */
    std::function<void (const std::string& track, const float* L, const float* R, int n)> tap;

private:
    Engine& eng;
    double sr = 48000;
    int maxBlock = 0;
    std::vector<float> tL, tR, mL, mR;
    std::map<int, std::pair<std::vector<float>, std::vector<float>>> buses;
    std::vector<MidiEv> ev;
    std::map<std::string, std::array<float, 2>> peak;
    struct EndCache { uint64_t sig = 0; std::vector<double> end; };   // 같은 음이 겹칠 때 앞 음의 실제 끝(박, 클립 기준)
    std::map<const Clip*, EndCache> ends;
    struct Delay { std::vector<float> L, R; size_t pos = 0; int len = 0; };   // 트랙 지연 보정용 링 버퍼
    std::map<std::string, Delay> pdc;
    int trackLatency (const Track& t) const;
    const std::vector<double>& noteEnds (const Clip& c);

    void renderTrack (Track& t, int n, int64_t f0, bool playing, const std::vector<MidiEv>* live);
    void collectEvents (Track& t, int64_t f0, int n);
    void applyAutomation (Slot& s, double beat);
    void renderAudioClip (const Clip& c, int64_t f0, int n, float* L, float* R);
    void metronomeClick (float* L, float* R, int n, int64_t f0);
};

/** 오토메이션 값(beat 에서). 점 사이: curve 0 = 직선, ±1 쪽으로 휨 */
double automationValue (const std::vector<AutoPoint>& pts, double beat);

/** 옛 엔진에서 잰 팬 법칙: L = 1-p, R = 1+p (가운데 0 dB, 끝 +6 dB) */
inline void panGains (double pan, float& gl, float& gr)
{
    float p = (float) std::max (-1.0, std::min (1.0, pan));
    gl = 1 - p; gr = 1 + p;
}

} // namespace mc
