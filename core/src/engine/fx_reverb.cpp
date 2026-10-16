// Musicoma Engine — 리버브.
// 측정(reverb_default/big/narrow — 젖은 신호 널 약 -48 dB)으로 확인: 공개 도메인 Freeverb(Jezar, 2000) 구조와 같다.
//   · 입력은 모노 합 (L+R)·0.015 → 채널마다 병렬 콤 8개(저역 감쇠 되먹임) → 직렬 올패스 4개(되먹임 0.5)
//   · 콤 길이 1116 1188 1277 1356 1422 1491 1557 1617, 올패스 556 441 341 225 (44.1 kHz 기준),
//     오른쪽은 +23. 실제 길이 = int((길이 [+23]) · sr/44100)  (48 kHz: 1214, 1239 … — 임펄스 첫 도착으로 확인)
//   · room size r → 콤 되먹임 0.7 + 0.28·r, damping d → 0.4·d, wet ×3, dry ×2,
//     width w → wet1 = wet·(w/2+0.5), wet2 = wet·(1-w)/2  (L = combL·wet1 + combR·wet2 + 입력L·dry)
//   · Freeze: 되먹임 1, 감쇠 0, 입력 0
// 표시 문자열: room size "int(v·10)+1", wet/dry 는 기본값(1/3, 1/2) 대비 dB.
#include "fx_common.h"
#include <algorithm>

namespace mc::fx {

namespace {

constexpr int kCombTune[8] = { 1116, 1188, 1277, 1356, 1422, 1491, 1557, 1617 };
constexpr int kApTune[4] = { 556, 441, 341, 225 };
constexpr int kSpread = 23;
constexpr float kFixedGain = 0.015f;

std::string fmtGainRel (double v, double scale)
{
    double g = v * scale;
    if (g <= 1e-9) return "-inf dB";
    return fmtDb (20.0 * std::log10 (g));
}

struct Comb
{
    std::vector<float> buf;
    int idx = 0;
    float store = 0;
    inline float process (float in, float fb, float d1, float d2)
    {
        float out = buf[(size_t) idx];
        store = out * d2 + store * d1;
        if (std::fabs (store) < 1e-20f) store = 0;
        buf[(size_t) idx] = in + store * fb;
        if (++idx >= (int) buf.size()) idx = 0;
        return out;
    }
};

struct Allpass
{
    std::vector<float> buf;
    int idx = 0;
    inline float process (float in)
    {
        float bo = buf[(size_t) idx];
        buf[(size_t) idx] = in + bo * 0.5f;
        if (++idx >= (int) buf.size()) idx = 0;
        return bo - in;
    }
};

class Reverb final : public FxBase
{
public:
    Reverb()
    {
        defineParams ({
            { "room size",  "Room Size",  0, 1, (double) 0.3f,       [] (double v) { return std::to_string ((int) (v * 10.0) + 1); } },
            { "damping",    "Damping",    0, 1, 0.5,                 fmtPercent },
            { "wet level",  "Wet Level",  0, 1, (double) (1.0f / 3), [] (double v) { return fmtGainRel (v, 3.0); } },
            { "dry level",  "Dry Level",  0, 1, 0.5,                 [] (double v) { return fmtGainRel (v, 2.0); } },
            { "width",      "Width",      0, 1, 1,                   fmtPercent },
            { "mode",       "Freeze",     0, 1, 0,                   [] (double v) { return std::string (v >= 0.5 ? "On" : "Off"); } },
        });
    }

    std::string type() const override { return "reverb"; }
    std::string name() const override { return "Reverb"; }

    void prepare (double sampleRate, int) override
    {
        sr = sampleRate;
        const double sc = sr / 44100.0;
        for (int c = 0; c < 2; ++c)
        {
            for (int k = 0; k < 8; ++k) comb[c][k].buf.assign ((size_t) std::max (1, (int) ((kCombTune[k] + c * kSpread) * sc)), 0.0f);
            for (int k = 0; k < 4; ++k) ap[c][k].buf.assign ((size_t) std::max (1, (int) ((kApTune[k] + c * kSpread) * sc)), 0.0f);
        }
        for (auto* g : { &wet1, &wet2, &dry }) g->setTime (sr, 0.02);
        update();
        reset();
    }

    void reset() override
    {
        for (int c = 0; c < 2; ++c)
        {
            for (auto& cb : comb[c]) { std::fill (cb.buf.begin(), cb.buf.end(), 0.0f); cb.idx = 0; cb.store = 0; }
            for (auto& a : ap[c]) { std::fill (a.buf.begin(), a.buf.end(), 0.0f); a.idx = 0; }
        }
        fresh = true;
    }

    void process (float* L, float* R, int n, const std::vector<MidiEv>&, const ProcessInfo&) override
    {
        if (comb[0][0].buf.empty()) return;
        FtzGuard ftz;
        if (fresh) { wet1.snap(); wet2.snap(); dry.snap(); fresh = false; }
        for (int i = 0; i < n; ++i)
        {
            const float in = (L[i] + R[i]) * inGain;
            float o[2];
            for (int c = 0; c < 2; ++c)
            {
                float acc = 0;
                for (auto& cb : comb[c]) acc += cb.process (in, fb, d1, d2);
                for (auto& a : ap[c]) acc = a.process (acc);
                o[c] = acc;
            }
            const double w1 = wet1.next(), w2 = wet2.next(), dr = dry.next();
            const double l = o[0] * w1 + o[1] * w2 + L[i] * dr;
            const double r = o[1] * w1 + o[0] * w2 + R[i] * dr;
            L[i] = (float) l;
            R[i] = (float) r;
        }
    }

    double tailSeconds() const override
    {
        if (values[5] >= 0.5) return 30.0;
        const double feedback = 0.7 + 0.28 * values[0];
        const double loop = (kCombTune[7] + kSpread) / 44100.0;
        return std::min (30.0, loop * 3.0 / -std::log10 (feedback) + 0.1);
    }

protected:
    void paramChanged (int) override { update(); }
    bool parseSpecialText (int index, const std::string& text, double& out) override
    {
        if (index != 5) return false;
        if (equalsNoCase (text, "on"))  { out = 1; return true; }
        if (equalsNoCase (text, "off")) { out = 0; return true; }
        return false;
    }

private:
    void update()
    {
        const bool freeze = values[5] >= 0.5;
        fb = freeze ? 1.0f : (float) (0.7 + 0.28 * values[0]);
        d1 = freeze ? 0.0f : (float) (0.4 * values[1]);
        d2 = 1.0f - d1;
        inGain = freeze ? 0.0f : kFixedGain;
        const double w = values[2] * 3.0, width = values[4];
        wet1.target = w * (width * 0.5 + 0.5);
        wet2.target = w * ((1.0 - width) * 0.5);
        dry.target = values[3] * 2.0;
    }

    double sr = 48000;
    Comb comb[2][8];
    Allpass ap[2][4];
    float fb = 0.784f, d1 = 0.2f, d2 = 0.8f, inGain = kFixedGain;
    Smoothed wet1, wet2, dry;
    bool fresh = true;
};

} // namespace

std::unique_ptr<Device> makeReverb() { return std::make_unique<Reverb>(); }

} // namespace mc::fx
