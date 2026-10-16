// Musicoma Engine — 코러스, 페이저 (파라미터 없음 — 예전 엔진과 같이 고정 설정).
//
// 코러스 — 측정(chorus_default: 음악 구간 널 -48/-53 dB, 전체 약 -25 dB):
//   · y = 0.7071·x + 0.7071·x(n - d(n))   (등전력 50 % 믹스)
//   · d(n) = 20 ms + 1.5 ms·(1 + sin φ)  → 20 ~ 23 ms (48 kHz 에서 960 ~ 1104 샘플)
//   · LFO 1 Hz 사인(실측 주기 1.00062 Hz — 예전 엔진의 float 위상 누적 오차로 보임), 왼쪽 φ0 = π, 오른쪽 = 왼쪽 + π/2
//   · 소수 지연 읽기: k = round(d), f = d - k (−0.5..0.5), w = x[n-k]·(1-f) + x[n-k-1]·f
//     — f < 0 이면 외삽이 된다(예전 엔진 그대로; 임펄스 탭 1.28/-0.29 로 확인). 고역이 선형 보간보다 덜 깎인다.
//
// 페이저 — 측정(phaser_default: 왼쪽 널 -69 dB, 오른쪽 -41 dB):
//   · 1차 올패스 4단 직렬, 되먹임 0.7(한 샘플 지연), 출력 = x + 올패스열 출력(드라이·웻 1:1)
//     v = x + 0.7·y[n-1];  각 단: y = -a·v + z;  z = a·y + v
//   · 계수 a = (1 - d)/(1 + d),  d = f/(sr/2),  f 는 161.8 Hz ~ 4999 Hz 를 로그 영역 삼각파로 오간다
//   · LFO 주기 2.4747 s(0.4041 Hz), 시작 위상 0.1983(주기 비율, 0 = 가장 낮은 f 에서 올라가기 시작)
//   · 두 채널이 같은 LFO.
#include "fx_common.h"
#include <algorithm>

namespace mc::fx {

namespace {

// ───────────────────────── Chorus ─────────────────────────
class Chorus final : public FxBase
{
public:
    std::string type() const override { return "chorus"; }
    std::string name() const override { return "Chorus"; }

    void prepare (double sampleRate, int) override
    {
        sr = sampleRate;
        base = kBaseSec * sr;
        depth = kDepthSec * sr;
        size = (int) std::ceil (base + depth) + 4;
        for (auto& b : buf) b.assign ((size_t) size, 0.0f);
        reset();
    }
    void reset() override
    {
        for (auto& b : buf) std::fill (b.begin(), b.end(), 0.0f);
        wpos = 0;
        phase = 0;
    }

    void process (float* L, float* R, int n, const std::vector<MidiEv>&, const ProcessInfo&) override
    {
        if (size <= 0 || buf[0].empty()) return;
        FtzGuard ftz;
        const double inc = 2.0 * kPi * kRateHz / sr;
        float* ch[2] = { L, R };
        for (int i = 0; i < n; ++i)
        {
            buf[0][(size_t) wpos] = L[i];
            buf[1][(size_t) wpos] = R[i];
            for (int c = 0; c < 2; ++c)
            {
                const double d = base + depth * 0.5 * (1.0 + std::sin (phase + kPhase0[c]));
                const int k = (int) (d + 0.5);
                const double f = d - k;
                int i0 = wpos - k;      if (i0 < 0) i0 += size;
                int i1 = i0 - 1;        if (i1 < 0) i1 += size;
                const double w = buf[c][(size_t) i0] * (1.0 - f) + buf[c][(size_t) i1] * f;
                ch[c][i] = (float) (kMix * ch[c][i] + kMix * w);
            }
            if (++wpos >= size) wpos = 0;
            phase += inc;
            if (phase >= 2.0 * kPi) phase -= 2.0 * kPi;
        }
    }

    double tailSeconds() const override { return kBaseSec + kDepthSec; }
    std::vector<ParamInfo> params() override { return {}; }

private:
    static constexpr double kBaseSec = 0.020, kDepthSec = 0.003;
    static constexpr double kRateHz = 1.00062;
    static constexpr double kMix = 0.70710678118654752;
    static constexpr double kPhase0[2] = { 3.1497, 4.7215 };   // ≈ π, 3π/2
    double sr = 48000, base = 960, depth = 144, phase = 0;
    int size = 0, wpos = 0;
    std::vector<float> buf[2];
};

// ───────────────────────── Phaser ─────────────────────────
class Phaser final : public FxBase
{
public:
    std::string type() const override { return "phaser"; }
    std::string name() const override { return "Phaser"; }

    void prepare (double sampleRate, int) override { sr = sampleRate; reset(); }
    void reset() override
    {
        for (auto& c : st) { for (double& z : c.z) z = 0; c.prev = 0; }
        lfo = kLfoPhase0;
    }

    void process (float* L, float* R, int n, const std::vector<MidiEv>&, const ProcessInfo&) override
    {
        FtzGuard ftz;
        const double inc = 1.0 / (kPeriodSec * sr);
        const double lmin = std::log (kFminHz / (sr * 0.5)), lmax = std::log (kFmaxHz / (sr * 0.5));
        float* ch[2] = { L, R };
        for (int i = 0; i < n; ++i)
        {
            const double tri = lfo < 0.5 ? 2.0 * lfo : 2.0 - 2.0 * lfo;
            const double d = std::exp (lmin + (lmax - lmin) * tri);
            const double a = (1.0 - d) / (1.0 + d);
            for (int c = 0; c < 2; ++c)
            {
                auto& s = st[c];
                const double x = ch[c][i];
                double v = x + kFeedback * s.prev;
                for (double& z : s.z)
                {
                    const double y = -a * v + z;
                    z = y * a + v;
                    v = y;
                }
                s.prev = v;
                ch[c][i] = (float) (x + v);
            }
            lfo += inc;
            if (lfo >= 1.0) lfo -= 1.0;
        }
        for (auto& c : st) { for (double& z : c.z) z = flushDenorm (z); c.prev = flushDenorm (c.prev); }
    }

    double tailSeconds() const override { return 0.1; }
    std::vector<ParamInfo> params() override { return {}; }

private:
    static constexpr double kFminHz = 161.78, kFmaxHz = 4998.8;
    static constexpr double kPeriodSec = 2.47467;
    static constexpr double kLfoPhase0 = 0.19828;
    static constexpr double kFeedback = 0.7;
    struct Ch { double z[4] {}; double prev = 0; };
    Ch st[2];
    double sr = 48000, lfo = kLfoPhase0;
};

} // namespace

std::unique_ptr<Device> makeChorus() { return std::make_unique<Chorus>(); }
std::unique_ptr<Device> makePhaser() { return std::make_unique<Phaser>(); }

} // namespace mc::fx
