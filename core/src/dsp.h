// Musicoma Core — DSP 부품: 바이쿼드(RBJ 공식), 1극 필터, 창 씌운 sinc 보간표, 컴프레서
#pragma once
#include <cmath>
#include <vector>
#include "util.h"

namespace mc {

constexpr double kPi = 3.14159265358979323846;

/** 2차 IIR (Direct Form I 대신 TDF-II, double 상태) */
struct Biquad
{
    double b0 = 1, b1 = 0, b2 = 0, a1 = 0, a2 = 0;
    double z1[2] = { 0, 0 }, z2[2] = { 0, 0 };

    void reset() { z1[0] = z1[1] = z2[0] = z2[1] = 0; }

    inline float process (float x, int c)
    {
        double y = b0 * x + z1[c];
        z1[c] = b1 * x - a1 * y + z2[c];
        z2[c] = b2 * x - a2 * y;
        return (float) y;
    }

    void set (double nb0, double nb1, double nb2, double na0, double na1, double na2)
    {
        b0 = nb0 / na0; b1 = nb1 / na0; b2 = nb2 / na0; a1 = na1 / na0; a2 = na2 / na0;
    }

    // RBJ Audio EQ Cookbook 공식
    void lowpass (double sr, double f, double q)
    {
        f = clampv (f, 5.0, sr * 0.49);
        double w = 2 * kPi * f / sr, c = std::cos (w), al = std::sin (w) / (2 * q);
        set ((1 - c) / 2, 1 - c, (1 - c) / 2, 1 + al, -2 * c, 1 - al);
    }
    void highpass (double sr, double f, double q)
    {
        f = clampv (f, 5.0, sr * 0.49);
        double w = 2 * kPi * f / sr, c = std::cos (w), al = std::sin (w) / (2 * q);
        set ((1 + c) / 2, -(1 + c), (1 + c) / 2, 1 + al, -2 * c, 1 - al);
    }
    void bandpass (double sr, double f, double q)
    {
        f = clampv (f, 5.0, sr * 0.49);
        double w = 2 * kPi * f / sr, c = std::cos (w), al = std::sin (w) / (2 * q);
        set (al, 0, -al, 1 + al, -2 * c, 1 - al);
    }
    void notch (double sr, double f, double q)
    {
        f = clampv (f, 5.0, sr * 0.49);
        double w = 2 * kPi * f / sr, c = std::cos (w), al = std::sin (w) / (2 * q);
        set (1, -2 * c, 1, 1 + al, -2 * c, 1 - al);
    }
    void peak (double sr, double f, double bwOct, double gainDb)
    {
        f = clampv (f, 5.0, sr * 0.49);
        double A = std::pow (10.0, gainDb / 40.0);
        double w = 2 * kPi * f / sr, s = std::sin (w), c = std::cos (w);
        double al = s * std::sinh (std::log (2.0) / 2 * std::max (0.01, bwOct) * w / s);
        set (1 + al * A, -2 * c, 1 - al * A, 1 + al / A, -2 * c, 1 - al / A);
    }
};

/** 1극 LP/HP */
struct OnePole
{
    double a = 0, z[2] = { 0, 0 };
    bool hp = false;
    void set (double sr, double f, bool highpass)
    {
        f = clampv (f, 1.0, sr * 0.49);
        a = std::exp (-2 * kPi * f / sr);
        hp = highpass;
    }
    inline float process (float x, int c)
    {
        z[c] = (1 - a) * x + a * z[c];
        return (float) (hp ? x - z[c] : z[c]);
    }
};

/** 창 씌운 sinc 보간: 16탭(앞뒤 8), 위상 표 + 위상 사이 선형 보간 */
struct SincTable
{
    static constexpr int kTaps = 16;
    static constexpr int kHalf = kTaps / 2;
    static constexpr int kPhases = 512;
    std::vector<float> t;   // (kPhases+1) * kTaps

    SincTable();
    static const SincTable& get();

    /** frac ∈ [0,1): 계수 kTaps 개를 out 에 */
    inline void coeffs (double frac, float* out) const
    {
        double p = frac * kPhases;
        int i = (int) p;
        float f = (float) (p - i);
        const float* a = &t[(size_t) i * kTaps];
        const float* b = a + kTaps;
        for (int k = 0; k < kTaps; ++k) out[k] = a[k] + (b[k] - a[k]) * f;
    }
};

/** 간단한 피드포워드 컴프레서 (피크 검출, dB 영역에서 어택/릴리스). 조각 사이 상태 유지. */
struct Compressor
{
    double thresholdDb = -12, ratio = 2, attackMs = 10, releaseMs = 100, outputDb = 0;
    double env = 0;   // 깎는 양 (dB)
    void process (float* L, float* R, int64_t n, double sr);
};

} // namespace mc
