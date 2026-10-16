// Musicoma Engine — 컴프레서.
// 측정(scratch/golden/fx comp_*: 스윕·노이즈 버스트·음악)으로 찾은 동작 — 널 -61 ~ -78 dB:
//   · 검출: 모노 합 |L+R|/2 (× 사이드체인 게인) → 800 Hz 1극 저역 평활 s
//   · 엔벨로프: s 가 문턱 위면 어택 계수, 아래면 릴리스 계수로 env 가 s 를 따라간다(방향이 아니라 문턱 기준).
//     계수 = 1 - exp(ln(0.01) / (시간·sr))  — 설정 시간에 99% 도달
//   · 정특성은 선형 진폭 영역: 출력 레벨 = T + (env - T)/r  →  게인 = (T + (env-T)/r) / env  (env > T 일 때)
//     무릎(knee) 없음, 룩어헤드 없음, 스테레오 링크(같은 게인)
// 파라미터는 사람 단위로 보고한다(예전 엔진은 threshold 를 선형 게인, ratio 를 1/r 로 보고했다).
#include "fx_common.h"
#include <algorithm>

namespace mc::fx {

namespace {

class Compressor final : public FxBase
{
public:
    Compressor()
    {
        defineParams ({
            { "threshold",   "Threshold",      -40, 0, -6,                         fmtDb },
            { "ratio",       "Ratio",          1, 20, 2,                           fmtRatio },
            { "attack",      "Attack",         (double) 0.3f, 200, 100,            fmtMs },
            { "release",     "Release",        10, 300, 100,                       fmtMs },
            { "output gain", "Output gain",    -10, 24, 0,                         fmtDb },
            { "input gain",  "Sidechain gain", -24, 24, 0,                         fmtDb },
        });
    }

    std::string type() const override { return "compressor"; }
    std::string name() const override { return "Compressor"; }

    void prepare (double sampleRate, int) override
    {
        sr = sampleRate;
        cDet = 1.0 - std::exp (-2.0 * kPi * 800.0 / sr);
        makeup.setTime (sr, 0.02);
        update();
        reset();
    }
    void reset() override { s = env = 0; fresh = true; }

    void process (float* L, float* R, int n, const std::vector<MidiEv>&, const ProcessInfo&) override
    {
        FtzGuard ftz;
        if (fresh) { makeup.snap(); fresh = false; }
        const double T = thr, invR = 1.0 / ratio;
        for (int i = 0; i < n; ++i)
        {
            double x = std::fabs ((double) L[i] + (double) R[i]) * 0.5 * scGain;
            s += (x - s) * cDet;
            env += (s - env) * (s > T ? cAtt : cRel);
            double g = env > T ? (T + (env - T) * invR) / env : 1.0;
            g *= makeup.next();
            L[i] = (float) (L[i] * g);
            R[i] = (float) (R[i] * g);
        }
        s = flushDenorm (s);
        env = flushDenorm (env);
    }

protected:
    void paramChanged (int) override { update(); }

private:
    void update()
    {
        thr = std::pow (10.0, values[0] / 20.0);
        ratio = std::max (1.0, values[1]);
        cAtt = 1.0 - std::exp (std::log (0.01) / (values[2] * 0.001 * sr));
        cRel = 1.0 - std::exp (std::log (0.01) / (values[3] * 0.001 * sr));
        makeup.target = std::pow (10.0, values[4] / 20.0);
        scGain = std::pow (10.0, values[5] / 20.0);
    }

    double sr = 48000, cDet = 0.1, cAtt = 0.03, cRel = 0.001;
    double thr = 0.5, ratio = 2, scGain = 1;
    double s = 0, env = 0;
    Smoothed makeup;
    bool fresh = true;
};

} // namespace

std::unique_ptr<Device> makeCompressor() { return std::make_unique<Compressor>(); }

} // namespace mc::fx
