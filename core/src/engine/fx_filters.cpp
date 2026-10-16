// Musicoma Engine — 4밴드 EQ, LPF(저역 통과).
// 측정(scratch/golden/fx eq_*, lowpass_*)으로 확인한 것:
//   · EQ = RBJ 쿡북 바이쿼드 4개 직렬 — 로우 셸프 → 피크 → 피크 → 하이 셸프. Q 는 쿡북의 Q 그대로
//     (셸프도 S 가 아니라 Q 공식). 아이디가 "Low-pass …/High-pass …" 이지만 실제로는 셸프다.
//   · LPF = RBJ 2차 저역 통과, Q = 1/√2 (버터워스, 12 dB/oct). 임펄스 널 -75 dB 이하.
// 값을 바꾸면 계수가 튀지 않게 32샘플 조각마다 로그 주파수·게인·Q 를 목표로 평활한다(첫 처리 전에는 바로 적용).
#include "fx_common.h"
#include <algorithm>

namespace mc::fx {

namespace {

constexpr int kSub = 32;   // 평활 조각 길이

/** 평활 대상 파라미터 묶음: 주파수(로그 영역)·게인·Q */
struct SmoothParams
{
    double cur[12] {}, tgt[12] {};
    bool isFreq[12] {};
    int n = 0;
    double k = 0.05;
    bool moving = false;

    void setRate (double sr) { k = 1.0 - std::exp (-(double) kSub / (0.02 * sr)); }
    void snap() { for (int i = 0; i < n; ++i) cur[i] = tgt[i]; moving = false; }
    /** 한 조각 진행. 아직 움직이면 true */
    bool step()
    {
        bool any = false;
        for (int i = 0; i < n; ++i)
        {
            double t = tgt[i], c = cur[i];
            if (c == t) continue;
            if (isFreq[i]) c = std::exp (std::log (c) + (std::log (t) - std::log (c)) * k);
            else c += (t - c) * k;
            if (std::fabs (c - t) <= (isFreq[i] ? t * 1e-4 : 1e-4)) c = t;
            cur[i] = c;
            any = any || c != t;
        }
        moving = any;
        return true;
    }
};

// ───────────────────────── 4-Band Equaliser ─────────────────────────
class Eq final : public FxBase
{
public:
    Eq()
    {
        const double qMin = (double) 0.1f;   // 예전 엔진이 float 로 보고(0.100000001490116)
        defineParams ({
            { "Low-pass freq",  "Low-shelf freq",  20, 20000, 80,    fmtHz },
            { "Low-pass gain",  "Low-shelf gain",  -20, 20, 0,       fmtDb },
            { "Low-pass Q",     "Low-shelf Q",     qMin, 4, 0.5,     fmtQ },
            { "Mid freq 1",     "Mid freq 1",      20, 20000, 3000,  fmtHz },
            { "Mid gain 1",     "Mid gain 1",      -20, 20, 0,       fmtDb },
            { "Mid Q 1",        "Mid Q 1",         qMin, 4, 0.5,     fmtQ },
            { "Mid freq 2",     "Mid freq 2",      20, 20000, 5000,  fmtHz },
            { "Mid gain 2",     "Mid gain 2",      -20, 20, 0,       fmtDb },
            { "Mid Q 2",        "Mid Q 2",         qMin, 4, 0.5,     fmtQ },
            { "High-pass freq", "High-shelf freq", 20, 20000, 17000, fmtHz },
            { "High-pass gain", "High-shelf gain", -20, 20, 0,       fmtDb },
            { "High-pass Q",    "High-shelf Q",    qMin, 4, 0.5,     fmtQ },
        });
        sp.n = 12;
        for (int i = 0; i < 12; ++i) { sp.isFreq[i] = (i % 3) == 0; sp.tgt[i] = sp.cur[i] = values[(size_t) i]; }
    }

    std::string type() const override { return "4bandEq"; }
    std::string name() const override { return "4-Band Equaliser"; }

    void prepare (double sampleRate, int) override
    {
        sr = sampleRate;
        sp.setRate (sr);
        fresh = true;
        reset();
    }
    void reset() override { for (auto& b : band) b.reset(); fresh = true; }

    void process (float* L, float* R, int n, const std::vector<MidiEv>&, const ProcessInfo&) override
    {
        FtzGuard ftz;
        if (fresh) { sp.snap(); updateCoeffs(); fresh = false; }
        int pos = 0;
        while (pos < n)
        {
            int m = std::min (kSub, n - pos);
            if (sp.moving) { sp.step(); updateCoeffs(); }
            for (int i = pos; i < pos + m; ++i)
            {
                double l = L[i], r = R[i];
                for (auto& b : band) { l = b.process (l, 0); r = b.process (r, 1); }
                L[i] = (float) l; R[i] = (float) r;
            }
            pos += m;
        }
        for (auto& b : band) b.flush();
    }

    double tailSeconds() const override { return 0.05; }

protected:
    void paramChanged (int i) override
    {
        sp.tgt[i] = values[(size_t) i];
        sp.moving = true;
    }

private:
    void updateCoeffs()
    {
        const double* c = sp.cur;
        band[0].lowShelf (sr, c[0], c[2], c[1]);
        band[1].peak (sr, c[3], c[5], c[4]);
        band[2].peak (sr, c[6], c[8], c[7]);
        band[3].highShelf (sr, c[9], c[11], c[10]);
    }

    double sr = 48000;
    Biquad2 band[4];
    SmoothParams sp;
    bool fresh = true;
};

// ───────────────────────── LPF/HPF (저역 통과만) ─────────────────────────
class Lowpass final : public FxBase
{
public:
    Lowpass()
    {
        defineParams ({ { "frequency", "Frequency", 10, 22000, 4000, fmtHz } });
        sp.n = 1; sp.isFreq[0] = true; sp.tgt[0] = sp.cur[0] = values[0];
    }

    std::string type() const override { return "lowpass"; }
    std::string name() const override { return "LPF/HPF"; }

    void prepare (double sampleRate, int) override { sr = sampleRate; sp.setRate (sr); reset(); }
    void reset() override { bq.reset(); fresh = true; }

    void process (float* L, float* R, int n, const std::vector<MidiEv>&, const ProcessInfo&) override
    {
        FtzGuard ftz;
        if (fresh) { sp.snap(); bq.lowpass (sr, sp.cur[0], kQ); fresh = false; }
        int pos = 0;
        while (pos < n)
        {
            int m = std::min (kSub, n - pos);
            if (sp.moving) { sp.step(); bq.lowpass (sr, sp.cur[0], kQ); }
            for (int i = pos; i < pos + m; ++i)
            {
                L[i] = (float) bq.process (L[i], 0);
                R[i] = (float) bq.process (R[i], 1);
            }
            pos += m;
        }
        bq.flush();
    }

    double tailSeconds() const override { return 0.05; }

protected:
    void paramChanged (int) override { sp.tgt[0] = values[0]; sp.moving = true; }

private:
    static constexpr double kQ = 0.70710678118654752;
    double sr = 48000;
    Biquad2 bq;
    SmoothParams sp;
    bool fresh = true;
};

} // namespace

std::unique_ptr<Device> makeEq()      { return std::make_unique<Eq>(); }
std::unique_ptr<Device> makeLowpass() { return std::make_unique<Lowpass>(); }

} // namespace mc::fx
