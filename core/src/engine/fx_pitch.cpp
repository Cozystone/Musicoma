// Musicoma Engine — 피치 시프터(반음 단위, -24 ~ +24).
// 방식: 위상 보코더의 '피크 이동' 피치 시프트(Laroche & Dolson 1999, 공개 문헌).
//   · STFT: Hann 창 N(48 kHz 에서 2048, 96 kHz 에서 4096), 홉 N/4, 합성 창도 Hann(겹침 합 1.5 로 나눔)
//   · 프레임마다 크기 피크를 찾고, 피크 사이 골을 경계로 '영역'을 나눈다.
//     피크 p 의 영역 전체를 bin q = round(p·비율) 로 통째로 옮긴다(창 모양·주변 위상 관계 보존 = 위상 고정).
//     피크의 합성 위상 = 지난 프레임 q 의 합성 위상 + 순간 주파수·비율·홉,  영역의 다른 bin 은 피크와의 분석 위상 차를 그대로.
//   · 포먼트 보존 없음(포먼트도 같이 움직인다). 비율 1 이면 분석 스펙트럼을 그대로 되돌려(지연만) 원음과 같다.
//   · 지연(latency) = N - N/4 샘플(48 kHz 1536 = 32 ms). 엔진이 latency() 로 보정.
//   · 블록 크기와 무관(샘플 단위 FIFO), 처리 안에서 할당 없음.
#include "fx_common.h"
#include <algorithm>
#include <complex>

namespace mc::fx {

namespace {

using cplx = std::complex<double>;

/** 반복형 radix-2 FFT (크기 2^k). 표는 prepare 에서 만든다. */
struct Fft
{
    int n = 0;
    std::vector<int> rev;
    std::vector<cplx> tw;

    void init (int size)
    {
        n = size;
        rev.assign ((size_t) n, 0);
        int bits = 0;
        while ((1 << bits) < n) ++bits;
        for (int i = 0; i < n; ++i)
        {
            int r = 0;
            for (int b = 0; b < bits; ++b) if (i & (1 << b)) r |= 1 << (bits - 1 - b);
            rev[(size_t) i] = r;
        }
        tw.resize ((size_t) n / 2);
        for (int i = 0; i < n / 2; ++i) tw[(size_t) i] = std::polar (1.0, -2.0 * kPi * i / n);
    }

    /** inverse 면 켤레 회전(정규화 없음) */
    void run (cplx* a, bool inverse) const
    {
        for (int i = 0; i < n; ++i) if (i < rev[(size_t) i]) std::swap (a[i], a[rev[(size_t) i]]);
        for (int len = 2; len <= n; len <<= 1)
        {
            const int half = len >> 1, step = n / len;
            for (int i = 0; i < n; i += len)
                for (int j = 0; j < half; ++j)
                {
                    cplx w = tw[(size_t) (j * step)];
                    if (inverse) w = std::conj (w);
                    const cplx u = a[i + j], v = a[i + j + half] * w;
                    a[i + j] = u + v;
                    a[i + j + half] = u - v;
                }
        }
    }
};

inline double princArg (double p)
{
    p = std::fmod (p + kPi, 2.0 * kPi);
    if (p < 0) p += 2.0 * kPi;
    return p - kPi;
}

std::string fmtSemis (double v)
{
    if (std::fabs (v) < 1e-9) return "(Original pitch)";
    char b[48];
    if (std::fabs (v - std::round (v)) < 1e-6) std::snprintf (b, sizeof (b), "%+d semitones", (int) std::lround (v));
    else std::snprintf (b, sizeof (b), "%+.2f semitones", v);
    return b;
}

class PitchShifter final : public FxBase
{
public:
    PitchShifter()
    {
        defineParams ({ { "semitones up", "Semitones", -24, 24, 0, fmtSemis } });
    }

    std::string type() const override { return "pitchShifter"; }
    std::string name() const override { return "Pitch Shifter"; }

    void prepare (double sampleRate, int) override
    {
        sr = sampleRate;
        N = sr > 70000 ? 4096 : 2048;
        H = N / 4;
        Lat = N - H;
        const int nb = N / 2 + 1;
        fft.init (N);
        win.resize ((size_t) N);
        for (int k = 0; k < N; ++k) win[(size_t) k] = 0.5 - 0.5 * std::cos (2.0 * kPi * k / N);   // 주기형 Hann
        for (auto& c : ch)
        {
            c.inFifo.assign ((size_t) N, 0.0f);
            c.outFifo.assign ((size_t) N, 0.0f);
            c.accum.assign ((size_t) N * 2, 0.0);
            c.lastPhase.assign ((size_t) nb, 0.0);
            c.synPhase.assign ((size_t) nb, 0.0);
        }
        spec.assign ((size_t) N, cplx());
        outSpec.assign ((size_t) nb, cplx());
        mag.assign ((size_t) nb, 0.0);
        pha.assign ((size_t) nb, 0.0);
        omega.assign ((size_t) nb, 0.0);
        peaks.assign ((size_t) nb, 0);
        reset();
    }

    void reset() override
    {
        for (auto& c : ch)
        {
            std::fill (c.inFifo.begin(), c.inFifo.end(), 0.0f);
            std::fill (c.outFifo.begin(), c.outFifo.end(), 0.0f);
            std::fill (c.accum.begin(), c.accum.end(), 0.0);
            std::fill (c.lastPhase.begin(), c.lastPhase.end(), 0.0);
            std::fill (c.synPhase.begin(), c.synPhase.end(), 0.0);
        }
        rover = Lat;
    }

    void process (float* L, float* R, int n, const std::vector<MidiEv>&, const ProcessInfo&) override
    {
        if (N == 0) return;
        FtzGuard ftz;
        float* io[2] = { L, R };
        for (int i = 0; i < n; ++i)
        {
            for (int c = 0; c < 2; ++c)
            {
                ch[c].inFifo[(size_t) rover] = io[c][i];
                io[c][i] = ch[c].outFifo[(size_t) (rover - Lat)];
            }
            if (++rover >= N)
            {
                rover = Lat;
                const double ratio = std::pow (2.0, values[0] / 12.0);
                for (auto& c : ch) frame (c, ratio);
            }
        }
    }

    int latency() const override { return Lat; }

protected:
    bool parseSpecialText (int, const std::string& text, double& out) override
    {
        if (text.find ("riginal") == std::string::npos) return false;   // "(Original pitch)"
        out = 0;
        return true;
    }

public:
    double tailSeconds() const override { return sr > 0 ? (double) (Lat + N) / sr : 0.1; }

private:
    struct Chan
    {
        std::vector<float> inFifo, outFifo;
        std::vector<double> accum, lastPhase, synPhase;
    };

    void frame (Chan& c, double ratio)
    {
        const int nb = N / 2 + 1;
        for (int k = 0; k < N; ++k) spec[(size_t) k] = cplx (c.inFifo[(size_t) k] * win[(size_t) k], 0.0);
        fft.run (spec.data(), false);

        const bool unity = std::fabs (ratio - 1.0) < 1e-9;
        const double expct = 2.0 * kPi * H / N;   // bin 당 홉 위상 진행
        double maxMag = 0;
        for (int k = 0; k < nb; ++k)
        {
            mag[(size_t) k] = std::abs (spec[(size_t) k]);
            pha[(size_t) k] = std::arg (spec[(size_t) k]);
            const double dp = princArg (pha[(size_t) k] - c.lastPhase[(size_t) k] - k * expct);
            omega[(size_t) k] = k * expct + dp;                  // 홉 동안의 실제 위상 진행
            c.lastPhase[(size_t) k] = pha[(size_t) k];
            maxMag = std::max (maxMag, mag[(size_t) k]);
        }

        if (unity)
        {
            for (int k = 0; k < nb; ++k) c.synPhase[(size_t) k] = pha[(size_t) k];
        }
        else
        {
            // 피크 찾기(-100 dB 아래는 버림)
            int np = 0;
            const double floorMag = maxMag * 1e-5;
            for (int k = 1; k < nb - 1; ++k)
                if (mag[(size_t) k] > floorMag && mag[(size_t) k] > mag[(size_t) k - 1] && mag[(size_t) k] >= mag[(size_t) k + 1])
                    peaks[(size_t) np++] = k;

            std::fill (outSpec.begin(), outSpec.end(), cplx());
            int lo = 0;
            for (int j = 0; j < np; ++j)
            {
                const int p = peaks[(size_t) j];
                int hi = nb - 1;
                if (j + 1 < np)
                {
                    const int p2 = peaks[(size_t) j + 1];
                    hi = p;
                    for (int k = p + 1; k < p2; ++k) if (mag[(size_t) k] < mag[(size_t) hi]) hi = k;
                    if (hi == p) hi = (p + p2) / 2;
                }
                const int q = (int) std::lround (p * ratio);
                if (q >= 1 && q < nb)
                {
                    const int shift = q - p;
                    const double theta = c.synPhase[(size_t) q] + omega[(size_t) p] * ratio;
                    const double ref = pha[(size_t) p];
                    for (int k = lo; k <= hi; ++k)
                    {
                        const int k2 = k + shift;
                        if (k2 < 0 || k2 >= nb) continue;
                        outSpec[(size_t) k2] += std::polar (mag[(size_t) k], theta + pha[(size_t) k] - ref);
                    }
                }
                lo = hi + 1;
            }
            for (int k = 0; k < nb; ++k)
            {
                const cplx v = outSpec[(size_t) k];
                if (std::norm (v) > 0) c.synPhase[(size_t) k] = std::arg (v);
                else c.synPhase[(size_t) k] = princArg (c.synPhase[(size_t) k] + omega[(size_t) k] * ratio);
            }
            // 에르미트 대칭으로 전체 스펙트럼 만들기
            for (int k = 0; k < nb; ++k) spec[(size_t) k] = outSpec[(size_t) k];
            spec[0] = cplx (spec[0].real(), 0.0);
            spec[(size_t) N / 2] = cplx (spec[(size_t) N / 2].real(), 0.0);
            for (int k = 1; k < N / 2; ++k) spec[(size_t) (N - k)] = std::conj (spec[(size_t) k]);
        }

        fft.run (spec.data(), true);
        const double norm = 1.0 / (N * 1.5);
        for (int k = 0; k < N; ++k) c.accum[(size_t) k] += spec[(size_t) k].real() * win[(size_t) k] * norm;

        for (int k = 0; k < H; ++k) c.outFifo[(size_t) k] = (float) c.accum[(size_t) k];
        std::copy (c.accum.begin() + H, c.accum.end(), c.accum.begin());
        std::fill (c.accum.end() - H, c.accum.end(), 0.0);
        for (int k = 0; k < Lat; ++k) c.inFifo[(size_t) k] = c.inFifo[(size_t) (k + H)];
    }

    double sr = 0;
    int N = 0, H = 0, Lat = 0, rover = 0;
    Fft fft;
    std::vector<double> win;
    Chan ch[2];
    std::vector<cplx> spec, outSpec;
    std::vector<double> mag, pha, omega;
    std::vector<int> peaks;
};

} // namespace

std::unique_ptr<Device> makePitchShifter() { return std::make_unique<PitchShifter>(); }

} // namespace mc::fx
