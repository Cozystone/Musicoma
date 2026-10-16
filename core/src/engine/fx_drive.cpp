// Musicoma Engine — Drive(기타 앰프풍 오버드라이브/디스토션). 10-17: 밴드 곡에 드라이브 걸린 기타가 없어 '포크송' 소리가 나던 것.
//   신호 흐름: 로우컷(HPF) → 프레즌스(피크 EQ, 드라이브 앞) → 입력 게인 → 2배 오버샘플 파형 정형(tanh ↔ 하드 클립 섞기)
//              → 톤(LPF, 캐비닛 느낌) → 캐비닛 저역 살짝(피크 +2 dB @ 110 Hz) → 출력 게인 → 원음과 섞기
//   측정 기준 없음(새 장치) — 널 테스트 대상이 아니라 '소리'로 판정. 알리아싱은 2배 오버샘플 + 20 kHz 저역통과로 줄인다.
#include "fx_common.h"
#include <algorithm>
#include <cmath>

namespace mc::fx {

namespace {

class Drive final : public FxBase
{
public:
    Drive()
    {
        defineParams ({
            { "drive",     "Drive",      0, 40, 18,    fmtDb },        // 입력 게인(dB)
            { "character", "Character",  0, 1, 0.35,   fmtPercent },   // 0 = 부드러운 오버드라이브(tanh), 1 = 딱딱한 클립(디스토션)
            { "low cut",   "Low cut",    30, 400, 90,  fmtHz },        // 드라이브 앞 HPF — 뭉개짐 방지
            { "presence",  "Presence",   -6, 6, 1.5,   fmtDb },        // 2.5 kHz 피크(드라이브 앞) — 피크의 '긁힘'
            { "tone",      "Tone",       800, 10000, 3800, fmtHz },    // 드라이브 뒤 LPF(캐비닛)
            { "output",    "Output",     -24, 12, -8,  fmtDb },
            { "mix",       "Mix",        0, 1, 1,      fmtPercent },
        });
        gIn.setTime (48000, 0.02); gOut.setTime (48000, 0.02); mix.setTime (48000, 0.02);
    }

    std::string type() const override { return "drive"; }
    std::string name() const override { return "Drive (Amp)"; }

    void prepare (double sampleRate, int) override
    {
        sr = sampleRate;
        gIn.setTime (sr, 0.02); gOut.setTime (sr, 0.02); mix.setTime (sr, 0.02);
        recalc();
        gIn.snap(); gOut.snap(); mix.snap();
        reset();
    }
    void reset() override
    {
        hpf.reset(); pres.reset(); lpf.reset(); cab.reset(); up.reset(); down.reset();
        for (int c = 0; c < 2; ++c) last[c] = 0;
    }

    void process (float* L, float* R, int n, const std::vector<MidiEv>&, const ProcessInfo&) override
    {
        FtzGuard ftz;
        if (dirty) { recalc(); dirty = false; }
        float* ch[2] = { L, R };
        const double chr = values[1];
        for (int i = 0; i < n; ++i)
        {
            const double gi = gIn.next(), go = gOut.next(), mx = mix.next();
            for (int c = 0; c < 2; ++c)
            {
                const double dry = ch[c][i];
                double x = hpf.process (dry, c);
                x = pres.process (x, c);
                x *= gi;
                // 2배 오버샘플: [x_prev, x] 사이를 보간해 두 샘플로 → 정형 → 20 kHz LPF(96k 기준) → 둘째 샘플만 취함
                const double a = 0.5 * (last[c] + x);
                last[c] = x;
                double y0 = shape (up.process (a, c), chr);
                double y1 = shape (up.process (x, c), chr);
                down.process (y0, c);
                double y = down.process (y1, c);
                y = lpf.process (y, c);
                y = cab.process (y, c);
                ch[c][i] = (float) (dry * (1.0 - mx) + y * go * mx);
            }
        }
        hpf.flush(); pres.flush(); lpf.flush(); cab.flush(); up.flush(); down.flush();
    }

    double tailSeconds() const override { return 0.05; }

protected:
    void paramChanged (int) override { dirty = true; }

private:
    static inline double shape (double x, double chr)
    {
        // 부드러움(tanh) 과 딱딱함(소프트 니 클립)을 섞는다. 둘 다 |x|<=1 로 나온다
        const double soft = std::tanh (x);
        double hard = x;
        if (hard > 0.6) hard = 0.6 + (hard - 0.6) / (1.0 + ((hard - 0.6) / 0.4) * ((hard - 0.6) / 0.4));
        else if (hard < -0.6) hard = -0.6 + (hard + 0.6) / (1.0 + ((hard + 0.6) / 0.4) * ((hard + 0.6) / 0.4));
        hard = std::max (-1.0, std::min (1.0, hard));
        return soft * (1.0 - chr) + hard * chr;
    }
    void recalc()
    {
        gIn.target = std::pow (10.0, values[0] / 20.0);
        gOut.target = std::pow (10.0, values[5] / 20.0);
        mix.target = values[6];
        hpf.highpass (sr, values[2], 0.7071);
        pres.peak (sr, 2500.0, 0.9, values[3]);
        lpf.lowpass (sr, values[4], 0.8);
        cab.peak (sr, 110.0, 0.8, 2.0);
        // 오버샘플 경로의 20 kHz 저역통과(실제 처리 레이트 2·sr 기준)
        up.lowpass (2.0 * sr, std::min (20000.0, 0.45 * sr), 0.7071);
        down.lowpass (2.0 * sr, std::min (20000.0, 0.45 * sr), 0.7071);
    }

    double sr = 48000;
    bool dirty = true;
    Biquad2 hpf, pres, lpf, cab, up, down;
    Smoothed gIn, gOut, mix;
    double last[2] { 0, 0 };
};

} // namespace

std::unique_ptr<Device> makeDrive() { return std::make_unique<Drive>(); }

} // namespace mc::fx
