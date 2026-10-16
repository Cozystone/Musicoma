// Musicoma Engine — 내장 이펙트 공통 부품(파라미터 표, 문자열 형식, 바이쿼드, 평활, 비정규 수 차단).
// 클린룸: 예전 엔진의 코드는 보지 않았고 scratch/golden/fx 의 입·출력 측정으로만 동작을 맞췄다.
#pragma once
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <algorithm>
#include <cstring>
#include <functional>
#include <memory>
#include <string>
#include <vector>
#include <xmmintrin.h>
#include "device.h"

namespace mc::fx {

constexpr double kPi = 3.14159265358979323846;

/** process() 동안만 FTZ·DAZ 를 켠다(비정규 수로 CPU 가 느려지는 것 방지). 레지스터만 만지므로 실시간 안전. */
struct FtzGuard
{
    unsigned int old;
    FtzGuard() : old (_mm_getcsr()) { _mm_setcsr (old | 0x8040); }
    ~FtzGuard() { _mm_setcsr (old); }
};

/** 상태값 비정규 수 정리(FTZ 가 꺼진 환경 대비) */
inline double flushDenorm (double v) { return std::fabs (v) < 1e-25 ? 0.0 : v; }

/** ASCII 대소문자 무시 비교 — 할당 없음(오디오 스레드의 자동화 setParam 에서도 불림) */
inline bool equalsNoCase (const std::string& a, const std::string& b)
{
    if (a.size() != b.size()) return false;
    for (size_t i = 0; i < a.size(); ++i)
    {
        char x = a[i], y = b[i];
        if (x >= 'A' && x <= 'Z') x = (char) (x - 'A' + 'a');
        if (y >= 'A' && y <= 'Z') y = (char) (y - 'A' + 'a');
        if (x != y) return false;
    }
    return true;
}

inline bool equalsNoCase (const char* a, const std::string& b)
{
    size_t n = std::strlen (a);
    if (n != b.size()) return false;
    for (size_t i = 0; i < n; ++i)
    {
        char x = a[i], y = b[i];
        if (x >= 'A' && x <= 'Z') x = (char) (x - 'A' + 'a');
        if (y >= 'A' && y <= 'Z') y = (char) (y - 'A' + 'a');
        if (x != y) return false;
    }
    return true;
}

// ── 표시 문자열 (예전 엔진 device.params 의 text 형식 그대로) ──
std::string fmtHz (double v);          // "110 Hz"
std::string fmtDb (double v);          // "+0.00 dB", "-6.00 dB"
std::string fmtQ (double v);           // "0.500"
std::string fmtMs (double v);          // "100.0 ms"
std::string fmtRatio (double v);       // "2.00 : 1"
std::string fmtPercent (double v);     // 0..1 → "50%"
/** "3.5 kHz", "-6 dB", "-inf", "120ms" 같은 문자열에서 숫자 하나 뽑기(k 접두는 ×1000). 실패하면 false. */
bool parseNumberText (const std::string& text, double& out);

/** 파라미터 정의 한 줄 */
struct ParamDef
{
    const char* id;
    const char* name;
    double min, max, def;
    std::function<std::string (double)> format;
};

/** 파라미터 표를 가진 내장 이펙트 바탕 클래스. 값은 사람 단위로 values 에 둔다. */
class FxBase : public Device
{
public:
    std::vector<ParamInfo> params() override;
    bool setParam (const std::string& idOrName, double value) override;
    bool setParamText (const std::string& idOrName, const std::string& text) override;
    Json getState() override;
    void setState (const Json& state) override;

protected:
    void defineParams (std::vector<ParamDef> defs);
    int findParam (const std::string& idOrName) const;
    /** 값이 바뀐 뒤(명령 스레드 또는 오디오 스레드). 할당 금지 — 계수 계산만. */
    virtual void paramChanged (int index) { (void) index; }
    /** setParamText 가 특별한 문자열을 처리하고 싶을 때(예: "Off"/"On") */
    virtual bool parseSpecialText (int index, const std::string& text, double& out) { (void) index; (void) text; (void) out; return false; }

    std::vector<ParamDef> defs;
    std::vector<double> values;
};

/** 바이쿼드(RBJ 쿡북), TDF-II, double 상태, 2채널 */
struct Biquad2
{
    double b0 = 1, b1 = 0, b2 = 0, a1 = 0, a2 = 0;
    double z1[2] = { 0, 0 }, z2[2] = { 0, 0 };

    void reset() { z1[0] = z1[1] = z2[0] = z2[1] = 0; }
    void setNorm (double nb0, double nb1, double nb2, double na0, double na1, double na2)
    {
        b0 = nb0 / na0; b1 = nb1 / na0; b2 = nb2 / na0; a1 = na1 / na0; a2 = na2 / na0;
    }
    bool isIdentity() const { return b0 == 1 && b1 == 0 && b2 == 0 && a1 == 0 && a2 == 0; }

    inline double process (double x, int c)
    {
        double y = b0 * x + z1[c];
        z1[c] = b1 * x - a1 * y + z2[c];
        z2[c] = b2 * x - a2 * y;
        return y;
    }
    void flush() { for (int c = 0; c < 2; ++c) { z1[c] = flushDenorm (z1[c]); z2[c] = flushDenorm (z2[c]); } }

    void lowpass (double sr, double f, double q);
    void peak (double sr, double f, double q, double gainDb);
    void lowShelf (double sr, double f, double q, double gainDb);
    void highShelf (double sr, double f, double q, double gainDb);
};

/** 1극 평활(게인 등). snap() 이면 바로 목표값. */
struct Smoothed
{
    double cur = 0, target = 0, k = 0.002;
    void setTime (double sr, double seconds) { k = 1.0 - std::exp (-1.0 / std::max (1.0, seconds * sr)); }
    void snap() { cur = target; }
    inline double next() { cur += (target - cur) * k; return cur; }
};

// 각 fx_*.cpp 의 공장 함수
std::unique_ptr<Device> makeEq();
std::unique_ptr<Device> makeLowpass();
std::unique_ptr<Device> makeCompressor();
std::unique_ptr<Device> makeDelay();
std::unique_ptr<Device> makeReverb();
std::unique_ptr<Device> makeChorus();
std::unique_ptr<Device> makePhaser();
std::unique_ptr<Device> makePitchShifter();

} // namespace mc::fx
