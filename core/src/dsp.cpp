#include "dsp.h"

namespace mc {

namespace {

double besselI0 (double x)
{
    double sum = 1, term = 1;
    for (int k = 1; k < 40; ++k)
    {
        term *= (x / (2 * k)) * (x / (2 * k));
        sum += term;
        if (term < 1e-12 * sum) break;
    }
    return sum;
}

} // namespace

SincTable::SincTable()
{
    t.resize ((size_t) (kPhases + 1) * kTaps);
    const double cutoff = 0.97;      // 나이퀴스트 대비
    const double beta = 8.0;         // 카이저 창
    const double i0b = besselI0 (beta);

    for (int ph = 0; ph <= kPhases; ++ph)
    {
        double frac = (double) ph / kPhases;
        double sum = 0;
        float* row = &t[(size_t) ph * kTaps];
        for (int k = 0; k < kTaps; ++k)
        {
            // 탭 k 는 샘플 (floor(pos) - kHalf + 1 + k)
            double x = (double) (k - kHalf + 1) - frac;
            double s = std::fabs (x) < 1e-12 ? cutoff : std::sin (kPi * cutoff * x) / (kPi * x);
            double r = x / (kHalf + 0.0);
            double w = std::fabs (r) >= 1.0 ? 0.0 : besselI0 (beta * std::sqrt (1 - r * r)) / i0b;
            row[k] = (float) (s * w);
            sum += s * w;
        }
        for (int k = 0; k < kTaps; ++k) row[k] = (float) (row[k] / sum);   // DC 이득 1
    }
}

const SincTable& SincTable::get()
{
    static SincTable table;
    return table;
}

void Compressor::process (float* L, float* R, int64_t n, double sr)
{
    const double att = std::exp (-1.0 / (std::max (0.05, attackMs) * 0.001 * sr));
    const double rel = std::exp (-1.0 / (std::max (1.0, releaseMs) * 0.001 * sr));
    const double slope = 1.0 - 1.0 / std::max (1.0, ratio);
    const float out = dbToGain (outputDb);

    for (int64_t i = 0; i < n; ++i)
    {
        double x = std::max (std::fabs ((double) L[i]), std::fabs ((double) R[i]));
        double over = gainToDb (x) - thresholdDb;
        double want = over > 0 ? over * slope : 0.0;
        env = want > env ? att * env + (1 - att) * want : rel * env + (1 - rel) * want;
        float g = dbToGain (-env) * out;
        L[i] *= g;
        R[i] *= g;
    }
}

} // namespace mc
