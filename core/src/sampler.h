// Musicoma Core — 자체 SFZ 샘플러 (보이스 할당·엔벨로프·서스테인·라운드로빈·초크·릴리스 트리거)
#pragma once
#include <cstdint>
#include <array>
#include <memory>
#include <random>
#include <string>
#include <vector>
#include "dsp.h"
#include "samplepool.h"
#include "sfz.h"

namespace mc {

struct MidiEv
{
    enum Kind { CC = 0, Bend = 1, NoteOff = 2, NoteOn = 3 };
    int64_t frame;
    int kind;
    int a;        // 음 번호 / CC 번호
    float v;      // 벨로시티 0..1 / CC 0..1 / 벤드 -1..1
};

/** 지금 엔진(Tracktion+sfizz)과 맞추려고 측정으로 정한 값들. 계획 JSON 의 "core_tuning" 으로 덮어쓸 수 있다. */
struct Tuning
{
    double envExpK = 9.0;          // 감쇠/릴리스: 시간 T 동안 e^-k 로 (선형 dB). 9 → T 에서 -78 dB
    double fastOff = 0.006;        // off_mode=fast 시간(초)
    int velModel = 0;              // 0 = 선형 섞기 g = 1 - t + t*curve, 1 = dB 비례 g = curve^t
    bool ampModMultiply = true;    // amplitude_onccN 을 곱으로 (false = 더하기)
    int panLaw = 0;                // 0 = 가운데 1, 끝 +3dB (√2·cos/sin), 1 = 일정 전력(가운데 -3dB), 2 = 밸런스(가운데 1, 끝 0~1)
    int maxVoices = 256;
    bool ccTriggerEnter = true;    // on_loccN: 범위에 '들어올 때만' 울림
    bool ccTriggerVelFromValue = true;
    bool deferReleaseOnPedal = true;
    double rtDecayFromRelease = 1; // rt_decay 기준 시간: 1 = 노트온~릴리스 트리거 시점
    bool defaultCc7 = true;        // SFZ 가 CC7 을 안 쓰면 amplitude_oncc7=100 (x² 곡선) 을 기본으로 (sfizz 와 같게)
    int defaultCc11 = 4;           // SFZ 가 CC11 을 안 쓰면 amplitude_oncc11=100 (이 곡선 번호, -1 = 끔)
    bool defaultCc10 = true;       // SFZ 가 CC10 을 안 쓰면 pan_oncc10=100 (양극 곡선)
    bool offsetCurveLinear = true; // offset_curveccN 무시(선형) — sfizz 동작
    int eventDelay = 1;            // MIDI 이벤트를 몇 샘플 늦게 (엔진 측정: 1)
    double bendSmoothMs = 0.0;
    int bendOffset = -170;         // 벤드 이벤트를 몇 샘플 옮기나 (엔진 측정: 약 3.5 ms 일찍)
    int bendBlock = 0;             // >0: 벤드를 이 블록 격자에 맞춰 적용 (음수 = 다음 경계)     // 피치 벤드 변화 매끄럽게 (1극, ms)
    int seqMode = 1;               // 라운드로빈 카운터 규칙 (seqStep 참고) — 엔진 측정: 1 (건반 범위만 맞으면 센다)
    bool polyCountsReleased = false; // (note_)polyphony 에 놓인(릴리스 중) 보이스도 세나
    double filterQBase = 1.0;      // SFZ 필터 Q = base · 10^(resonance/20)
};

struct SynthStats
{
    int64_t voicesStarted = 0;
    int maxActive = 0;
    int64_t missingSampleHits = 0;
    int64_t stolen = 0;
};

class SfzSynth
{
public:
    SfzSynth (std::shared_ptr<const Instrument> inst, SamplePool& pool, double sampleRate, const Tuning& tuning);
    ~SfzSynth();

    /** events 는 frame 순으로 정렬돼 있어야 한다. L/R 에 더한다. */
    void render (const std::vector<MidiEv>& events, int64_t frames, float* L, float* R);

    /** 조각 렌더: 앞 조각에 이어서 n 프레임을 L/R 에 더한다 (메모리를 조각 크기만 쓰게). */
    void process (const std::vector<MidiEv>& events, int64_t n, float* L, float* R);

    float outputGain = 1.0f;   // SFZ 디바이스 볼륨
    SynthStats stats;

private:
    struct Voice;
    std::shared_ptr<const Instrument> inst;
    SamplePool& pool;
    double sr;
    Tuning tune;

    std::vector<Voice> voices;
    std::vector<int> seqCounter;           // 리전별 라운드로빈 카운터
    std::vector<char> def7, def10, def11;         // 리전별: 기본 CC7/CC10 모듈레이션을 붙이나
    std::array<float, 128> cc {};
    float bend = 0;
    double bendSmoothed = 0;
    std::vector<std::pair<int64_t, float>> pendingBends;
    int currentSw = -1;
    bool held[128] {};
    float noteVel[128] {};
    int64_t noteOnFrame[128] {};
    std::vector<int> deferredRelease;      // 페달 때문에 미룬 릴리스 트리거(음 번호)
    std::mt19937 rng;
    uint64_t order = 0;
    int64_t now = 0;
    int64_t renderPos = 0;
    size_t eventPos = 0;

    void noteOn (int key, float vel);
    void noteOff (int key);
    void controlChange (int num, float v);
    void triggerRelease (int key);

    bool regionOk (const Region& r, int key, int vel127) const;
    bool seqStep (const Region& r, int key, int vel127);
    void startVoices (std::vector<const Region*>& regs, int key, float vel, bool releaseTrig, double rtSeconds);
    void startVoice (const Region& r, int key, float vel, bool releaseTrig, double rtSeconds);
    void release (Voice& v, OffMode mode, float time);
    float ccMod (const Region& r, ModTarget t) const;
    float velocityGain (const Region& r, float vel) const;
    void updateDynamic (Voice& v, bool snap);
    void renderVoice (Voice& v, int64_t n, float* L, float* R);
    Voice* allocVoice();
};

} // namespace mc
