// Musicoma Engine — 딜레이.
// 측정(delay_default, delay_long — 널 -124 dB):
//   · 지연 150 ms 고정(48 kHz 에서 7200 샘플). 길이 파라미터 없음, 템포와 무관(120 BPM 하나로만 측정됨).
//   · 되먹임: w[n] = x[n-D] + fb·w[n-D], fb = 10^(feedback dB/20) — 반복마다 정확히 feedback dB 씩 준다.
//   · 믹스는 등전력 크로스페이드: y = cos(m·π/2)·x + sin(m·π/2)·w  (m = mix proportion)
//   · 채널은 따로(같은 설정), 교차 되먹임 없음.
#include "fx_common.h"
#include <algorithm>

namespace mc::fx {

namespace {

class Delay final : public FxBase
{
public:
    Delay()
    {
        defineParams ({
            { "feedback",       "Feedback",       -30, 0, -6,                   fmtDb },
            { "mix proportion", "Mix proportion", 0, 1, (double) 0.3f,
              [] (double v) { char b[32]; std::snprintf (b, sizeof (b), "%lld%% wet", (long long) std::llround (v * 100)); return std::string (b); } },
        });
    }

    std::string type() const override { return "delay"; }
    std::string name() const override { return "Delay"; }

    void prepare (double sampleRate, int) override
    {
        sr = sampleRate;
        D = std::max (1, (int) std::lround (kDelaySec * sr));
        for (auto& b : buf) b.assign ((size_t) D, 0.0f);
        dryG.setTime (sr, 0.02); wetG.setTime (sr, 0.02); fbG.setTime (sr, 0.02);
        update();
        reset();
    }
    void reset() override
    {
        for (auto& b : buf) std::fill (b.begin(), b.end(), 0.0f);
        pos = 0;
        fresh = true;
    }

    void process (float* L, float* R, int n, const std::vector<MidiEv>&, const ProcessInfo&) override
    {
        if (D <= 0 || buf[0].empty()) return;
        FtzGuard ftz;
        if (fresh) { dryG.snap(); wetG.snap(); fbG.snap(); fresh = false; }
        float* bl = buf[0].data();
        float* br = buf[1].data();
        for (int i = 0; i < n; ++i)
        {
            double dg = dryG.next(), wg = wetG.next(), fb = fbG.next();
            double wl = bl[pos], wr = br[pos];          // w[n] = u[n-D]
            bl[pos] = (float) (L[i] + fb * wl);         // u[n] = x[n] + fb·w[n]
            br[pos] = (float) (R[i] + fb * wr);
            if (++pos >= D) pos = 0;
            L[i] = (float) (dg * L[i] + wg * wl);
            R[i] = (float) (dg * R[i] + wg * wr);
        }
    }

    double tailSeconds() const override
    {
        double fbDb = values[0];
        if (fbDb > -0.1) return 30.0;
        return std::min (30.0, kDelaySec * (1.0 + 60.0 / -fbDb));
    }

protected:
    void paramChanged (int) override { update(); }

private:
    void update()
    {
        double m = values[1];
        dryG.target = std::cos (m * kPi * 0.5);
        wetG.target = std::sin (m * kPi * 0.5);
        fbG.target = std::pow (10.0, values[0] / 20.0);
    }

    static constexpr double kDelaySec = 0.150;
    double sr = 48000;
    int D = 0, pos = 0;
    std::vector<float> buf[2];
    Smoothed dryG, wetG, fbG;
    bool fresh = true;
};

} // namespace

std::unique_ptr<Device> makeDelay() { return std::make_unique<Delay>(); }

} // namespace mc::fx
