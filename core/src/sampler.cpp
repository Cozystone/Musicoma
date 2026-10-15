#include "sampler.h"
#include <algorithm>
#include <cstdio>
#include <cstdlib>
#include <cstring>

namespace mc {

namespace {
enum Stage { sDelay, sAttack, sHold, sDecay, sSustain, sRelease, sDone };

struct FilterRun
{
    int kind = 0;               // 0 없음, 1 1극, 2 바이쿼드 단
    OnePole op;
    Biquad bq[3];
    int stages = 0;
    inline float process (float x, int c)
    {
        if (kind == 1) return op.process (x, c);
        for (int s = 0; s < stages; ++s) x = bq[s].process (x, c);
        return x;
    }
};
} // namespace

struct SfzSynth::Voice
{
    bool active = false;
    const Region* r = nullptr;
    std::shared_ptr<const AudioData> smp;
    int key = 0;
    float vel = 0;
    uint64_t order = 0;
    bool releaseTrig = false;
    bool released = false, pedalHeld = false, oneShot = false;
    double pos = 0, stepBase = 1;
    int64_t delayLeft = 0;
    // 엔벨로프
    int stage = sDone;
    float env = 0, sustain = 1, attackInc = 1, decayMul = 1, releaseMul = 1;
    int64_t stageLeft = 0, holdLen = 0, decayLen = 0;
    // 이득
    float staticGain = 1;
    float gL = 0, gR = 0, tgL = 0, tgR = 0;
    double step = 1;
    // 루프/끝
    bool looping = false;
    int64_t loopStart = 0, loopEnd = 0, endFrame = 0;
    FilterRun fil[2];
    Biquad eq[3];
    bool eqOn[3] = { false, false, false };
    int nFil = 0;
};

SfzSynth::SfzSynth (std::shared_ptr<const Instrument> i, SamplePool& p, double sampleRate, const Tuning& t)
    : inst (std::move (i)), pool (p), sr (sampleRate), tune (t), rng (12345u)
{
    voices.resize ((size_t) std::max (8, tune.maxVoices));
    seqCounter.assign (inst->regions.size(), 0);
    def7.assign (inst->regions.size(), 0);
    def10.assign (inst->regions.size(), 0);
    def11.assign (inst->regions.size(), 0);
    for (auto& r : inst->regions)
    {
        bool has7 = false, has10 = false, has11 = false;
        for (auto& m : r.mods)
        {
            if (m.cc == 7 && (m.target == ModTarget::Amplitude || m.target == ModTarget::Volume)) has7 = true;
            if (m.cc == 10 && m.target == ModTarget::Pan) has10 = true;
            if (m.cc == 11 && (m.target == ModTarget::Amplitude || m.target == ModTarget::Volume)) has11 = true;
        }
        def7[(size_t) r.index] = tune.defaultCc7 && ! has7;
        def10[(size_t) r.index] = tune.defaultCc10 && ! has10;
        def11[(size_t) r.index] = tune.defaultCc11 >= 0 && ! has11;
    }
    cc = inst->defaultCc;
    currentSw = inst->swDefault;
}

SfzSynth::~SfzSynth() = default;

//==============================================================================
float SfzSynth::ccMod (const Region& r, ModTarget t) const
{
    float sum = 0;
    for (auto& m : r.mods)
        if (m.target == t)
        {
            int curve = (t == ModTarget::Offset && tune.offsetCurveLinear) ? 0 : m.curve;
            sum += m.depth * inst->curve (curve).eval (cc[(size_t) m.cc]);
        }
    return sum;
}

float SfzSynth::velocityGain (const Region& r, float vel) const
{
    float c;
    if (! r.velPoints.empty())
    {
        // amp_velcurve_N 점들 사이 선형, 끝점 기본 (0,0) (127,1)
        float x = vel * 127.0f;
        int px = 0; float py = 0;
        bool found = false;
        c = 1.0f;
        for (auto& [vx, vy] : r.velPoints)
        {
            if (x <= (float) vx)
            {
                float span = (float) (vx - px);
                c = span <= 0 ? vy : py + (vy - py) * (x - (float) px) / span;
                found = true;
                break;
            }
            px = vx; py = vy;
        }
        if (! found)
        {
            float span = 127.0f - (float) px;
            c = span <= 0 ? py : py + (1.0f - py) * (x - (float) px) / span;
        }
    }
    else
        c = vel * vel;

    float t = (r.ampVeltrack + ccMod (r, ModTarget::AmpVeltrack)) / 100.0f;
    if (tune.velModel == 1)
    {
        if (c <= 0) return t > 0 ? 0.0f : 1.0f;
        return t >= 0 ? std::pow (c, t) : std::pow (c, t);   // 음수 = 반대로 (드묾)
    }
    if (t >= 0) return 1.0f - t + t * c;
    return 1.0f + t * c;    // 음수: 세게 칠수록 작게
}

bool SfzSynth::regionOk (const Region& r, int key, int vel127) const
{
    if (key < r.lokey || key > r.hikey) return false;
    if (vel127 < r.lovel || vel127 > r.hivel) return false;
    if (r.swLast >= 0 && currentSw != r.swLast) return false;
    if (r.swDown >= 0 && ! held[r.swDown]) return false;
    if (r.swUp >= 0 && held[r.swUp]) return false;
    for (auto& c : r.ccConditions)
    {
        float v = cc[(size_t) clampv (c.cc, 0, 127)] * 127.0f;
        if (v < c.lo - 1e-3f || v > c.hi + 1e-3f) return false;
    }
    return true;
}

bool SfzSynth::seqStep (const Region& r, int key, int vel127)
{
    // 라운드로빈 카운터를 언제 올리나: 0 = 모든 조건이 맞을 때, 1 = 건반 범위만 맞으면, 2 = 모든 노트온
    bool keyIn = key >= r.lokey && key <= r.hikey;
    bool ok = regionOk (r, key, vel127);
    bool count = tune.seqMode == 0 ? ok : tune.seqMode == 1 ? keyIn : true;
    bool seqOk = true;
    if (r.seqLength > 1)
    {
        int& c = seqCounter[(size_t) r.index];
        seqOk = (c % r.seqLength) == r.seqPosition - 1;
        if (count) ++c;
    }
    return ok && seqOk;
}

SfzSynth::Voice* SfzSynth::allocVoice()
{
    Voice* oldest = nullptr;
    Voice* oldestReleased = nullptr;
    for (auto& v : voices)
    {
        if (! v.active) return &v;
        if (! oldest || v.order < oldest->order) oldest = &v;
        if ((v.released || v.stage == sRelease) && (! oldestReleased || v.order < oldestReleased->order)) oldestReleased = &v;
    }
    ++stats.stolen;
    Voice* s = oldestReleased ? oldestReleased : oldest;
    s->active = false;
    return s;
}

void SfzSynth::release (Voice& v, OffMode mode, float time)
{
    if (v.stage == sDone) return;
    float T = mode == OffMode::Fast ? (float) tune.fastOff : mode == OffMode::Time ? time : v.r->egRelease + ccMod (*v.r, ModTarget::EgRelease);
    if (mode == OffMode::Normal) T = v.r->egRelease + ccMod (*v.r, ModTarget::EgRelease);
    T = std::max (T, 0.0005f);
    v.released = true;
    v.pedalHeld = false;
    v.stage = sRelease;
    v.stageLeft = (int64_t) (T * sr) + 1;
    v.releaseMul = (float) std::exp (-tune.envExpK / (T * sr));
}

//==============================================================================
void SfzSynth::startVoices (std::vector<const Region*>& regs, int key, float vel, bool releaseTrig, double rtSeconds)
{
    // 같은 이벤트로 시작하는 보이스끼리는 서로 끄지 않는다 → 먼저 초크, 그다음 시작
    uint64_t eventStart = order;
    for (auto* r : regs)
    {
        for (auto& v : voices)
        {
            if (! v.active || v.order > eventStart) continue;
            if (v.r->hasOffBy && v.r->offBy == r->group && v.stage != sRelease)
                release (v, v.r->offMode, v.r->offTime);
        }
        if (r->notePolyphony > 0 || r->polyphony > 0)
        {
            std::vector<Voice*> same, grp;
            for (auto& v : voices)
            {
                if (! v.active || (v.stage == sRelease && ! tune.polyCountsReleased) || v.r->group != r->group) continue;
                grp.push_back (&v);
                if (v.key == key) same.push_back (&v);
            }
            auto killOldest = [&] (std::vector<Voice*>& list, int limit)
            {
                std::sort (list.begin(), list.end(), [] (Voice* a, Voice* b) { return a->order < b->order; });
                for (size_t k = 0; k + (size_t) limit <= list.size() && k < list.size(); ++k)
                {
                    Voice& kv = *list[k];
                    if (kv.stage == sRelease)
                    {
                        // 이미 놓인 보이스: 남은 릴리스가 off_time 보다 길면 off_time 으로 줄인다
                        float T = kv.r->offMode == OffMode::Fast ? (float) tune.fastOff : kv.r->offTime;
                        if (kv.r->offMode != OffMode::Normal && (double) kv.stageLeft > T * sr) release (kv, kv.r->offMode, kv.r->offTime);
                    }
                    else
                        release (kv, kv.r->offMode, kv.r->offTime);
                }
            };
            if (r->notePolyphony > 0) killOldest (same, r->notePolyphony);
            if (r->polyphony > 0) killOldest (grp, r->polyphony);
        }
    }
    for (auto* r : regs)
        startVoice (*r, key, vel, releaseTrig, rtSeconds);
}

void SfzSynth::startVoice (const Region& r, int key, float vel, bool releaseTrig, double rtSeconds)
{
    if (r.silence) return;     // *silence: 초크만 하고 소리는 없음
    auto smp = pool.get (r.sample);
    if (! smp || smp->frames <= 0) { ++stats.missingSampleHits; return; }

    Voice* vp = allocVoice();
    Voice& v = *vp;
    v = Voice();
    v.active = true;
    v.r = &r;
    v.smp = smp;
    v.key = key;
    v.vel = vel;
    v.order = ++order;
    v.releaseTrig = releaseTrig;
    v.oneShot = r.loopMode == LoopMode::OneShot;
    ++stats.voicesStarted;

    // 음높이
    double cents = (key - r.keycenter) * r.pitchKeytrack + r.transpose * 100.0 + r.tune + ccMod (r, ModTarget::Pitch);
    v.stepBase = smp->sampleRate / sr * std::pow (2.0, cents / 1200.0);

    // 시작 위치·끝·루프
    int64_t off = r.offset + (int64_t) ccMod (r, ModTarget::Offset);
    v.endFrame = smp->frames;
    if (r.end > 0) v.endFrame = std::min<int64_t> (smp->frames, r.end + 1);
    v.pos = (double) clampv<int64_t> (off, 0, std::max<int64_t> (0, v.endFrame - 1));
    LoopMode lm = r.loopMode;
    int64_t ls = r.loopStart >= 0 ? r.loopStart : smp->loopStart;
    int64_t le = r.loopEnd >= 0 ? r.loopEnd : smp->loopEnd;
    if (lm == LoopMode::Unset) lm = (smp->loopStart >= 0 && smp->loopEnd > smp->loopStart) ? LoopMode::Continuous : LoopMode::NoLoop;
    v.looping = (lm == LoopMode::Continuous || lm == LoopMode::Sustain) && ls >= 0 && le > ls && le < smp->frames;
    v.loopStart = ls; v.loopEnd = le;

    // 엔벨로프
    float egDelay = std::max (0.0f, r.egDelay + ccMod (r, ModTarget::EgDelay)) + std::max (0.0f, r.delay + ccMod (r, ModTarget::Delay));
    float att = std::max (0.0f, r.egAttack + ccMod (r, ModTarget::EgAttack));
    float hold = std::max (0.0f, r.egHold + ccMod (r, ModTarget::EgHold));
    float dec = std::max (0.0f, r.egDecay + ccMod (r, ModTarget::EgDecay));
    float sus = clampv ((r.egSustain + ccMod (r, ModTarget::EgSustain)) / 100.0f, 0.0f, 1.0f);
    v.sustain = sus;
    v.delayLeft = (int64_t) (egDelay * sr);
    v.attackInc = att > 0 ? (float) (1.0 / (att * sr)) : 1.0f;
    v.decayMul = dec > 0 ? (float) std::exp (-tune.envExpK / (dec * sr)) : 0.0f;
    v.stage = sAttack;
    v.env = att > 0 ? 0.0f : 1.0f;
    if (att <= 0) { v.stage = sHold; }
    v.holdLen = (int64_t) (hold * sr);
    v.decayLen = (int64_t) (dec * sr);
    v.stageLeft = att > 0 ? (int64_t) (att * sr) + 1 : v.holdLen;

    // 정적 이득: 볼륨·벨로시티·키 크로스페이드·rt_decay·amp_keytrack
    double gainDb = r.volume + r.groupVolume + r.masterVolume + r.globalVolume + r.ampKeytrack * (key - r.ampKeycenter);
    if (releaseTrig && r.rtDecay > 0) gainDb -= r.rtDecay * rtSeconds;
    float g = dbToGain (gainDb) * (r.amplitude / 100.0f) * velocityGain (r, vel);

    auto xf = [] (float x, float lo, float hi, bool fadeIn, bool power) -> float
    {
        float t;
        if (fadeIn) { if (x <= lo) return 0.0f; if (x >= hi) return 1.0f; t = (x - lo) / std::max (1e-6f, hi - lo); }
        else        { if (x <= lo) return 1.0f; if (x >= hi) return 0.0f; t = 1.0f - (x - lo) / std::max (1e-6f, hi - lo); }
        return power ? std::sqrt (t) : t;
    };
    float v127 = vel * 127.0f;
    if (r.xfinHivel > 0) g *= xf (v127, (float) r.xfinLovel, (float) r.xfinHivel, true, r.xfVelPower);
    if (r.xfoutLovel < 127) g *= xf (v127, (float) r.xfoutLovel, (float) r.xfoutHivel, false, r.xfVelPower);
    if (r.xfinHikey > 0) g *= xf ((float) key, (float) r.xfinLokey, (float) r.xfinHikey, true, r.xfKeyPower);
    if (r.xfoutLokey < 127) g *= xf ((float) key, (float) r.xfoutLokey, (float) r.xfoutHikey, false, r.xfKeyPower);
    v.staticGain = g;

    // 필터·EQ (노트온 때 한 번 계산)
    v.nFil = 0;
    for (int fi = 0; fi < 2; ++fi)
    {
        const auto& f = r.fil[fi];
        if (f.type == FilterType::None || f.cutoff <= 0) continue;
        double fc = f.cutoff * std::pow (2.0, (f.keytrack * (key - f.keycenter) + f.veltrack * vel
                                              + ccMod (r, fi == 0 ? ModTarget::Cutoff1 : ModTarget::Cutoff2)) / 1200.0);
        double res = f.resonance + ccMod (r, fi == 0 ? ModTarget::Resonance1 : ModTarget::Resonance2);
        double q = tune.filterQBase * std::pow (10.0, res / 20.0);   // 엔진 측정: resonance 0dB → Q 1
        auto& run = v.fil[v.nFil++];
        switch (f.type)
        {
            case FilterType::Lpf1p: run.kind = 1; run.op.set (sr, fc, false); break;
            case FilterType::Hpf1p: run.kind = 1; run.op.set (sr, fc, true); break;
            case FilterType::Lpf2p: case FilterType::Lpf4p: case FilterType::Lpf6p:
                run.kind = 2; run.stages = f.type == FilterType::Lpf2p ? 1 : f.type == FilterType::Lpf4p ? 2 : 3;
                for (int s = 0; s < run.stages; ++s) run.bq[s].lowpass (sr, fc, q);
                break;
            case FilterType::Hpf2p: case FilterType::Hpf4p: case FilterType::Hpf6p:
                run.kind = 2; run.stages = f.type == FilterType::Hpf2p ? 1 : f.type == FilterType::Hpf4p ? 2 : 3;
                for (int s = 0; s < run.stages; ++s) run.bq[s].highpass (sr, fc, q);
                break;
            case FilterType::Bpf2p: run.kind = 2; run.stages = 1; run.bq[0].bandpass (sr, fc, q); break;
            case FilterType::Brf2p: run.kind = 2; run.stages = 1; run.bq[0].notch (sr, fc, q); break;
            default: --v.nFil; break;
        }
    }
    static const float eqDefFreq[3] = { 50.0f, 500.0f, 5000.0f };
    for (int e = 0; e < 3; ++e)
    {
        float gdb = r.eq[e].gain + ccMod (r, (ModTarget) ((int) ModTarget::Eq1Gain + e));
        if (std::fabs (gdb) < 0.01f) continue;
        float fq = (r.eq[e].freq > 0 ? r.eq[e].freq : eqDefFreq[e]) + ccMod (r, (ModTarget) ((int) ModTarget::Eq1Freq + e));
        v.eq[e].peak (sr, fq, r.eq[e].bw, gdb);
        v.eqOn[e] = true;
    }

    v.gL = v.gR = 0;
    updateDynamic (v, true);

    static const bool debug = std::getenv ("MC_DEBUG_VOICES") != nullptr;
    if (debug)
        std::fprintf (stderr, "voice t=%.4f key=%d vel=%.3f region=%d grp=%lld gain=%.4f gL=%.4f gR=%.4f step=%.5f rel=%d %s\n",
                      (double) now / sr, key, vel, r.index, (long long) r.group, v.staticGain, v.gL, v.gR, v.stepBase, (int) releaseTrig, r.sample.c_str());

    int active = 0;
    for (auto& x : voices) active += x.active ? 1 : 0;
    stats.maxActive = std::max (stats.maxActive, active);
}

//==============================================================================
void SfzSynth::updateDynamic (Voice& v, bool snap)
{
    const Region& r = *v.r;
    float g = v.staticGain * outputGain;

    // CC 로 움직이는 볼륨·진폭·팬 (블록마다)
    float volDb = 0, pan = r.pan;
    float amp = 1.0f;
    float ampAdd = 0;
    for (auto& m : r.mods)
    {
        float x = inst->curve (m.curve).eval (cc[(size_t) m.cc]);
        switch (m.target)
        {
            case ModTarget::Volume: volDb += m.depth * x; break;
            case ModTarget::Pan: pan += m.depth * x; break;
            case ModTarget::Amplitude:
                if (tune.ampModMultiply) amp *= m.depth / 100.0f * x;
                else ampAdd += m.depth * x / 100.0f;
                break;
            default: break;
        }
    }
    if (def7[(size_t) r.index]) amp *= inst->curve (4).eval (cc[7]);
    if (def10[(size_t) r.index]) pan += 100.0f * inst->curve (1).eval (cc[10]);
    if (def11[(size_t) r.index]) amp *= inst->curve (tune.defaultCc11).eval (cc[11]);
    g *= dbToGain (volDb) * (tune.ampModMultiply ? amp : std::max (0.0f, 1.0f + ampAdd));

    auto xfcc = [&] (const std::vector<CcRange>& list, bool in)
    {
        float k = 1;
        for (auto& c : list)
        {
            float x = cc[(size_t) clampv (c.cc, 0, 127)] * 127.0f, t;
            if (in) t = x <= c.lo ? 0.0f : x >= c.hi ? 1.0f : (x - c.lo) / std::max (1e-6f, c.hi - c.lo);
            else    t = x <= c.lo ? 1.0f : x >= c.hi ? 0.0f : 1.0f - (x - c.lo) / std::max (1e-6f, c.hi - c.lo);
            k *= r.xfCcPower ? std::sqrt (t) : t;
        }
        return k;
    };
    if (! r.xfinCc.empty()) g *= xfcc (r.xfinCc, true);
    if (! r.xfoutCc.empty()) g *= xfcc (r.xfoutCc, false);

    float p = clampv (pan / 100.0f, -1.0f, 1.0f);
    float pl, pr;
    if (tune.panLaw == 1)       { pl = std::cos ((p + 1) * (float) kPi / 4); pr = std::sin ((p + 1) * (float) kPi / 4); }
    else if (tune.panLaw == 2)  { pl = p > 0 ? 1 - p : 1.0f; pr = p < 0 ? 1 + p : 1.0f; }
    else                        { pl = std::sqrt (2.0f) * std::cos ((p + 1) * (float) kPi / 4); pr = std::sqrt (2.0f) * std::sin ((p + 1) * (float) kPi / 4); }
    v.tgL = g * pl;
    v.tgR = g * pr;
    if (snap) { v.gL = v.tgL; v.gR = v.tgR; }

    double bc = bendSmoothed >= 0 ? bendSmoothed * r.bendUp : -bendSmoothed * r.bendDown;
    v.step = v.stepBase * std::pow (2.0, bc / 1200.0);
}

//==============================================================================
void SfzSynth::renderVoice (Voice& v, int64_t n, float* L, float* R)
{
    const auto& tbl = SincTable::get();
    const AudioData& s = *v.smp;
    const float* c0 = s.ch[0].data();
    const float* c1 = s.channels > 1 ? s.ch[1].data() : c0;
    const int64_t frames = s.frames;
    const int64_t loopLen = v.loopEnd - v.loopStart + 1;
    float co[SincTable::kTaps];
    const float dgL = (v.tgL - v.gL) / (float) std::max<int64_t> (1, n);
    const float dgR = (v.tgR - v.gR) / (float) std::max<int64_t> (1, n);

    for (int64_t i = 0; i < n; ++i)
    {
        v.gL += dgL; v.gR += dgR;
        if (v.delayLeft > 0) { --v.delayLeft; continue; }

        // 엔벨로프 한 칸
        switch (v.stage)
        {
            case sAttack:
                v.env += v.attackInc;
                if (v.env >= 1.0f || --v.stageLeft <= 0) { v.env = 1.0f; v.stage = sHold; v.stageLeft = v.holdLen; }
                break;
            case sHold:
                if (v.stageLeft-- <= 0) { v.stage = sDecay; v.stageLeft = v.decayLen; }
                break;
            case sDecay:
                v.env = v.sustain + (v.env - v.sustain) * v.decayMul;
                if (v.stageLeft-- <= 0) { v.env = v.sustain; v.stage = sSustain; }
                break;
            case sSustain: break;
            case sRelease:
                v.env *= v.releaseMul;
                if (--v.stageLeft <= 0) { v.stage = sDone; }
                break;
            default: break;
        }
        if (v.stage == sDone) { v.active = false; return; }

        // 보간 읽기
        int64_t ip = (int64_t) v.pos;
        double frac = v.pos - (double) ip;
        tbl.coeffs (frac, co);
        int64_t base = ip - SincTable::kHalf + 1;
        float a = 0, b = 0;
        if (base >= 0 && base + SincTable::kTaps <= frames && (! v.looping || base + SincTable::kTaps <= v.loopEnd + 1))
        {
            const float* p0 = c0 + base;
            const float* p1 = c1 + base;
            for (int k = 0; k < SincTable::kTaps; ++k) { a += co[k] * p0[k]; b += co[k] * p1[k]; }
        }
        else
        {
            for (int k = 0; k < SincTable::kTaps; ++k)
            {
                int64_t idx = base + k;
                if (v.looping && idx > v.loopEnd) idx = v.loopStart + (idx - v.loopStart) % loopLen;
                if (idx < 0 || idx >= frames) continue;
                a += co[k] * c0[idx];
                b += co[k] * c1[idx];
            }
        }

        for (int f = 0; f < v.nFil; ++f) { a = v.fil[f].process (a, 0); b = v.fil[f].process (b, 1); }
        for (int e = 0; e < 3; ++e) if (v.eqOn[e]) { a = v.eq[e].process (a, 0); b = v.eq[e].process (b, 1); }

        L[i] += a * v.env * v.gL;
        R[i] += b * v.env * v.gR;

        v.pos += v.step;
        if (v.looping && ! (v.released && v.r->loopMode == LoopMode::Sustain))
        {
            while (v.pos >= (double) (v.loopEnd + 1)) v.pos -= (double) loopLen;
        }
        else if (v.pos >= (double) v.endFrame)
        {
            v.active = false;
            return;
        }
    }
}

//==============================================================================
void SfzSynth::noteOn (int key, float vel)
{
    key += inst->noteOffset;
    if (key < 0 || key > 127) return;
    if (inst->swLokey >= 0 && key >= inst->swLokey && key <= inst->swHikey) currentSw = key;

    bool othersHeld = false;
    for (int k = 0; k < 128; ++k) if (held[k] && k != key) othersHeld = true;

    held[key] = true;
    noteVel[key] = vel;
    noteOnFrame[key] = now;

    int v127 = clampv ((int) std::lround (vel * 127.0f), 1, 127);
    float rnd = std::uniform_real_distribution<float> (0.0f, 1.0f) (rng);
    std::vector<const Region*> regs;
    for (auto& r : inst->regions)
    {
        if (! (r.trigger == Trigger::Attack || r.trigger == Trigger::First || r.trigger == Trigger::Legato)) continue;
        if (! r.ccTriggers.empty()) continue;   // CC 로 울리는 리전은 건반으로 안 울림
        if (! seqStep (r, key, v127)) continue;
        if (rnd < r.lorand || (rnd >= r.hirand && r.hirand < 1.0f)) continue;
        if (r.trigger == Trigger::First && othersHeld) continue;
        if (r.trigger == Trigger::Legato && ! othersHeld) continue;
        regs.push_back (&r);
    }
    startVoices (regs, key, vel, false, 0);
}

void SfzSynth::triggerRelease (int key)
{
    float vel = noteVel[key];
    int v127 = clampv ((int) std::lround (vel * 127.0f), 1, 127);
    double rt = (double) (now - noteOnFrame[key]) / sr;
    float rnd = std::uniform_real_distribution<float> (0.0f, 1.0f) (rng);
    std::vector<const Region*> regs;
    for (auto& r : inst->regions)
    {
        if (r.trigger != Trigger::Release && r.trigger != Trigger::ReleaseKey) continue;
        if (! seqStep (r, key, v127)) continue;
        if (rnd < r.lorand || (rnd >= r.hirand && r.hirand < 1.0f)) continue;
        regs.push_back (&r);
    }
    startVoices (regs, key, vel, true, rt);
}

void SfzSynth::noteOff (int key)
{
    key += inst->noteOffset;
    if (key < 0 || key > 127) return;
    held[key] = false;
    bool pedal = cc[64] >= 0.5f;

    for (auto& v : voices)
    {
        if (! v.active || v.key != key || v.releaseTrig || v.released || v.oneShot) continue;
        if (v.r->trigger == Trigger::Release || v.r->trigger == Trigger::ReleaseKey) continue;
        if (! v.r->ccTriggers.empty()) continue;
        if (pedal) v.pedalHeld = true;
        else release (v, OffMode::Normal, 0);
    }

    // trigger=release_key 는 페달과 상관없이, release 는 페달이 눌렸으면 뗄 때까지 미룬다
    if (pedal && tune.deferReleaseOnPedal)
        deferredRelease.push_back (key);
    else
        triggerRelease (key);
}

void SfzSynth::controlChange (int num, float v)
{
    if (num < 0 || num > 127) return;
    float prev = cc[(size_t) num];
    cc[(size_t) num] = v;

    if (num == 64 && prev >= 0.5f && v < 0.5f)
    {
        for (auto& vc : voices)
            if (vc.active && vc.pedalHeld && ! held[vc.key])
                release (vc, OffMode::Normal, 0);
        auto keys = deferredRelease;
        deferredRelease.clear();
        for (int k : keys)
            if (! held[k]) triggerRelease (k);
    }

    // CC 로 울리는 리전 (예: 피아노 페달 소리)
    std::vector<const Region*> regs;
    float x = v * 127.0f, px = prev * 127.0f;
    float rnd = std::uniform_real_distribution<float> (0.0f, 1.0f) (rng);
    for (auto& r : inst->regions)
        for (auto& t : r.ccTriggers)
        {
            if (t.cc != num) continue;
            float lo = t.lo < 0 ? 0.0f : t.lo, hi = t.hi < 0 ? 127.0f : t.hi;
            bool in = x >= lo - 1e-3f && x <= hi + 1e-3f;
            bool wasIn = px >= lo - 1e-3f && px <= hi + 1e-3f;
            if (! in || (tune.ccTriggerEnter && wasIn)) continue;
            bool condOk = true;
            for (auto& c : r.ccConditions)
            {
                float cv = cc[(size_t) clampv (c.cc, 0, 127)] * 127.0f;
                if (cv < c.lo - 1e-3f || cv > c.hi + 1e-3f) condOk = false;
            }
            if (! condOk) continue;
            if (r.swLast >= 0 && currentSw != r.swLast) continue;
            if (rnd < r.lorand || (rnd >= r.hirand && r.hirand < 1.0f)) continue;
            regs.push_back (&r);
        }
    if (! regs.empty())
        for (auto* r : regs)
        {
            std::vector<const Region*> one { r };
            startVoices (one, r->keycenter, tune.ccTriggerVelFromValue ? v : 1.0f, false, 0);
        }

    for (auto& vc : voices)
        if (vc.active) updateDynamic (vc, false);
}

//==============================================================================
void SfzSynth::render (const std::vector<MidiEv>& events, int64_t frames, float* L, float* R)
{
    renderPos = 0;
    eventPos = 0;
    process (events, frames, L, R);
}

void SfzSynth::process (const std::vector<MidiEv>& events, int64_t n, float* L, float* R)
{
    // 이어서 렌더: renderPos(절대 프레임)부터 n 프레임. L/R 은 이 조각의 시작을 가리킨다.
    const int64_t block = 64;
    const int64_t end = renderPos + n;
    int64_t f = renderPos;
    while (f < end)
    {
        if (tune.bendBlock > 0 && f % tune.bendBlock == 0)
        {
            // 블록 시작: 이 블록 안의 마지막 벤드 값을 블록 전체에 (블록 단위 처리 흉내)
            for (size_t k = eventPos; k < events.size() && events[k].frame + tune.eventDelay < f + tune.bendBlock; ++k)
                if (events[k].kind == MidiEv::Bend) bend = events[k].v;
        }
        while (eventPos < events.size() && events[eventPos].frame + tune.eventDelay <= f)
        {
            const auto& e = events[eventPos++];
            now = f;
            switch (e.kind)
            {
                case MidiEv::NoteOn:  noteOn (e.a, e.v); break;
                case MidiEv::NoteOff: noteOff (e.a); break;
                case MidiEv::CC:      controlChange (e.a, e.v); break;
                case MidiEv::Bend:
                    if (tune.bendBlock == 0) bend = e.v;
                    else if (tune.bendBlock < 0) pendingBends.push_back ({ e.frame + tune.eventDelay, e.v });
                    break;
            }
        }
        if (! pendingBends.empty())
        {
            // 블록 격자: 이벤트가 든 블록의 시작(+N) 또는 끝(-N) 에서 적용
            const int64_t B = std::abs (tune.bendBlock);
            while (! pendingBends.empty())
            {
                int64_t at = tune.bendBlock > 0 ? (pendingBends.front().first / B) * B : (pendingBends.front().first / B + 1) * B;
                if (at > f) break;
                bend = pendingBends.front().second;
                pendingBends.erase (pendingBends.begin());
            }
        }
        int64_t next = std::min (end, f + block);
        if (tune.bendBlock != 0)
        {
            const int64_t B = std::abs (tune.bendBlock);
            next = std::min (next, (f / B + 1) * B);
        }
        if (tune.bendSmoothMs > 0)
        {
            double a = 1.0 - std::exp (-(double) block / (tune.bendSmoothMs * 0.001 * sr));
            bendSmoothed += (bend - bendSmoothed) * a;
        }
        else
            bendSmoothed = bend;
        if (eventPos < events.size()) next = std::min (next, std::max (f + 1, events[eventPos].frame + tune.eventDelay));
        for (auto& v : voices)
            if (v.active)
            {
                updateDynamic (v, false);
                renderVoice (v, next - f, L + (f - renderPos), R + (f - renderPos));
            }
        f = next;
    }
    renderPos = end;
}

} // namespace mc
