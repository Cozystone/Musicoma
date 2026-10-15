// Musicoma Core — 자체 SFZ 파서 (sfzformat.com 규격을 보고 새로 작성)
#pragma once
#include <array>
#include <cstdint>
#include <map>
#include <memory>
#include <string>
#include <vector>
#include "util.h"

namespace mc {

/** 0..127 CC 값을 0..1 로 받는 곡선 (SFZ <curve>, 기본 곡선 0~6) */
struct Curve
{
    std::array<float, 128> v {};
    float eval (float cc01) const
    {
        float x = clampv (cc01, 0.0f, 1.0f) * 127.0f;
        int i = (int) x;
        if (i >= 127) return v[127];
        float f = x - (float) i;
        return v[(size_t) i] + (v[(size_t) i + 1] - v[(size_t) i]) * f;
    }
};

enum class ModTarget
{
    Amplitude, Volume, Pan, Pitch, Offset,
    EgDelay, EgAttack, EgHold, EgDecay, EgSustain, EgRelease,
    AmpVeltrack, Cutoff1, Cutoff2, Resonance1, Resonance2,
    Eq1Gain, Eq2Gain, Eq3Gain, Eq1Freq, Eq2Freq, Eq3Freq,
    Delay,
    Count
};

struct CcMod
{
    ModTarget target;
    int cc;
    float depth;
    int curve = -1;     // -1 = 아직 정하지 않음 (기본 0)
};

struct CcRange { int cc; float lo, hi; };           // 0..127 단위 (hdcc 는 소수)

enum class Trigger { Attack, Release, First, Legato, ReleaseKey };
enum class LoopMode { Unset, NoLoop, OneShot, Continuous, Sustain };
enum class OffMode { Fast, Normal, Time };
enum class FilterType { None, Lpf1p, Hpf1p, Lpf2p, Hpf2p, Bpf2p, Brf2p, Lpf4p, Hpf4p, Lpf6p, Hpf6p };

struct FilterSpec
{
    FilterType type = FilterType::None;
    float cutoff = -1.0f;       // Hz, <0 = 꺼짐
    float resonance = 0.0f;     // dB
    float keytrack = 0.0f;      // cents/key
    int keycenter = 60;
    float veltrack = 0.0f;      // cents (vel 127 일 때)
    bool typeSet = false;
};

struct EqSpec { float freq = 0, bw = 1, gain = 0; };

struct Region
{
    std::string sample;         // 해석된 절대 경로 (UTF-8)
    bool silence = false;       // *silence 등 내장 샘플
    int lokey = 0, hikey = 127, keycenter = 60;
    int lovel = 1, hivel = 127;
    float lorand = 0.0f, hirand = 1.0f;
    int seqLength = 1, seqPosition = 1;
    Trigger trigger = Trigger::Attack;
    int64_t group = 0;
    bool hasOffBy = false;
    int64_t offBy = 0;
    OffMode offMode = OffMode::Fast;
    float offTime = 0.006f;
    float delay = 0.0f;
    float volume = 0.0f, amplitude = 100.0f, pan = 0.0f, width = 100.0f;
    float groupVolume = 0.0f, masterVolume = 0.0f, globalVolume = 0.0f;   // SFZ v2 단계별 볼륨 (dB)
    float tune = 0.0f;
    int transpose = 0;
    float pitchKeytrack = 100.0f;
    float bendUp = 200.0f, bendDown = -200.0f;
    int64_t offset = 0, end = -1;
    LoopMode loopMode = LoopMode::Unset;
    int64_t loopStart = -1, loopEnd = -1;
    float egDelay = 0, egAttack = 0, egHold = 0, egDecay = 0, egSustain = 100.0f, egRelease = 0.001f;
    float ampVeltrack = 100.0f;
    std::vector<std::pair<int, float>> velPoints;     // amp_velcurve_N
    float ampKeytrack = 0.0f;
    int ampKeycenter = 60;
    int xfinLovel = 0, xfinHivel = 0, xfoutLovel = 127, xfoutHivel = 127;
    int xfinLokey = 0, xfinHikey = 0, xfoutLokey = 127, xfoutHikey = 127;
    bool xfVelPower = true, xfKeyPower = true, xfCcPower = true;
    std::vector<CcRange> xfinCc, xfoutCc;
    std::vector<CcRange> ccConditions;                // locc/hicc
    std::vector<CcRange> ccTriggers;                  // on_locc/on_hicc
    int swLast = -1, swDown = -1, swUp = -1;
    float rtDecay = 0.0f;
    int polyphony = -1, notePolyphony = -1;
    FilterSpec fil[2];
    EqSpec eq[3];
    std::vector<CcMod> mods;
    int index = 0;
};

struct Instrument
{
    std::string path;
    std::vector<Region> regions;
    std::map<int, Curve> curves;              // 0~6 기본 + 사용자 정의
    std::array<float, 128> defaultCc {};      // 0..1
    int swLokey = -1, swHikey = -1, swDefault = -1;
    int noteOffset = 0;                       // note_offset + 12*octave_offset
    std::map<std::string, int> unsupported;   // 무시한 opcode → 횟수
    std::vector<std::string> warnings;
    int missingSamples = 0;

    const Curve& curve (int index) const;
};

/** SFZ 를 읽는다. 실패하면 nullptr + err. */
std::shared_ptr<Instrument> loadSfz (const std::string& path, std::string& err);

/** 'c4' / 'C#3' / '60' → MIDI 번호 (c4 = 60). 실패하면 -1000 */
int parseNoteOrNumber (const std::string& s);

} // namespace mc
