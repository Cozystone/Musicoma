// Musicoma Engine — 곡 그래프 처리(eng_graph.h)
#include "eng_graph.h"
#include <algorithm>
#include <cmath>
#include "dsp.h"

namespace mc {

double automationValue (const std::vector<AutoPoint>& pts, double beat)
{
    if (pts.empty()) return 0;
    if (beat <= pts.front().beat) return pts.front().value;
    if (beat >= pts.back().beat) return pts.back().value;
    for (size_t i = 1; i < pts.size(); ++i)
        if (beat < pts[i].beat)
        {
            const auto& a = pts[i - 1];
            const auto& b = pts[i];
            double t = (beat - a.beat) / std::max (1e-9, b.beat - a.beat);
            if (std::abs (a.curve) > 1e-6)
            {
                double k = a.curve * 4.0;                       // 휨: 지수 곡선
                t = (std::exp (k * t) - 1) / (std::exp (k) - 1);
            }
            return a.value + (b.value - a.value) * t;
        }
    return pts.back().value;
}

void Graph::prepare (double sampleRate, int block)
{
    sr = sampleRate;
    maxBlock = block;
    tL.assign ((size_t) block, 0); tR.assign ((size_t) block, 0);
    mL.assign ((size_t) block, 0); mR.assign ((size_t) block, 0);
    buses.clear();
    for (int b = 0; b < 16; ++b) buses[b] = { std::vector<float> ((size_t) block, 0.0f), std::vector<float> ((size_t) block, 0.0f) };
    ev.clear();
    ev.reserve (8192);
}

void Graph::resetAll()
{
    for (auto& kv : pdc) { std::fill (kv.second.L.begin(), kv.second.L.end(), 0.0f); std::fill (kv.second.R.begin(), kv.second.R.end(), 0.0f); }
    if (! eng.project) return;
    for (auto& t : eng.project->tracks)
        for (auto& s : t.slots) if (s.dev) s.dev->reset();
    for (auto& s : eng.project->master) if (s.dev) s.dev->reset();
}

const std::vector<double>& Graph::noteEnds (const Clip& c)
{
    // 같은 음이 앞 음이 끝나기 전에 다시 울리면 앞 음은 뒤 음 시작에서 끝난다(옛 엔진과 같게 — 안 그러면 앞 음의
    // 노트오프가 새로 친 음을 끊어 '빈 공기'가 생김, 10-16 「Half Past Three」 인트로)
    uint64_t sig = 1469598103934665603ull ^ (uint64_t) c.notes.size();
    for (auto& nt : c.notes)
    {
        uint64_t h = (uint64_t) nt.pitch * 1000003u + (uint64_t) std::llround (nt.start * 9600) * 31u + (uint64_t) std::llround (nt.length * 9600);
        sig = (sig ^ h) * 1099511628211ull;
    }
    auto& e = ends[&c];
    if (e.sig == sig && e.end.size() == c.notes.size()) return e.end;
    e.sig = sig;
    e.end.assign (c.notes.size(), 0);
    std::vector<size_t> idx (c.notes.size());
    for (size_t i = 0; i < idx.size(); ++i) idx[i] = i;
    std::stable_sort (idx.begin(), idx.end(), [&] (size_t a, size_t b)
                      { return c.notes[a].pitch != c.notes[b].pitch ? c.notes[a].pitch < c.notes[b].pitch : c.notes[a].start < c.notes[b].start; });
    for (size_t k = 0; k < idx.size(); ++k)
    {
        const auto& a = c.notes[idx[k]];
        double end = a.start + a.length;
        if (k + 1 < idx.size() && c.notes[idx[k + 1]].pitch == a.pitch && c.notes[idx[k + 1]].start < end && c.notes[idx[k + 1]].start > a.start)
            end = c.notes[idx[k + 1]].start;
        e.end[idx[k]] = end;
    }
    return e.end;
}

void Graph::collectEvents (Track& t, int64_t f0, int n)
{
    ev.clear();
    const double fpb = sr * 60.0 / eng.project->bpm;           // 박당 샘플
    auto fr = [&] (double beat) { return (int64_t) std::llround (beat * fpb); };
    const int64_t f1 = f0 + n;
    for (auto& c : t.clips)
    {
        if (! c.midi || c.mute) continue;
        int64_t cs = fr (c.start), ce = fr (c.end());
        if (ce <= f0 || cs >= f1 + (int64_t) fpb * 64) { if (ce <= f0) continue; }
        const auto& nend = noteEnds (c);
        for (size_t ni = 0; ni < c.notes.size(); ++ni)
        {
            const auto& nt = c.notes[ni];
            if (nt.start < 0 || nt.start >= c.length || nt.length <= 0) continue;
            int64_t on = fr (c.start + nt.start);
            int64_t off = std::min (ce, fr (c.start + nend[ni]));
            if (off <= on) off = on + 1;
            if (on >= f0 && on < f1) ev.push_back ({ on - f0, MidiEv::NoteOn, nt.pitch, (float) std::clamp (nt.velocity, 1, 127) / 127.0f });
            if (off >= f0 && off < f1) ev.push_back ({ off - f0, MidiEv::NoteOff, nt.pitch, 0.0f });
        }
        for (auto& x : c.cc)
        {
            if (x.beat < 0 || x.beat >= c.length) continue;
            int64_t f = fr (c.start + x.beat);
            if (f >= f0 && f < f1) ev.push_back ({ f - f0, MidiEv::CC, x.cc, (float) std::clamp (x.value, 0, 127) / 127.0f });
        }
        for (auto& x : c.bend)
        {
            if (x.beat < 0 || x.beat >= c.length) continue;
            int64_t f = fr (c.start + x.beat) + eng.tuning.bendOffset;   // 옛 엔진: 벤드가 약 3.5 ms 일찍(측정)
            if (f < f0 && fr (c.start + x.beat) >= f0) f = f0;
            if (f >= f0 && f < f1) ev.push_back ({ f - f0, MidiEv::Bend, 0, (float) std::clamp (x.value, -1.0, 1.0) });
        }
    }
    std::stable_sort (ev.begin(), ev.end(), [] (const MidiEv& a, const MidiEv& b)
                      { return a.frame != b.frame ? a.frame < b.frame : a.kind < b.kind; });
}

void Graph::applyAutomation (Slot& s, double beat)
{
    if (! s.dev) return;
    for (auto& kv : s.automation)
        if (! kv.second.empty())
            s.dev->setParam (kv.first, automationValue (kv.second, beat));
}

void Graph::renderAudioClip (const Clip& c, int64_t f0, int n, float* L, float* R)
{
    if (! c.audio || c.mute || c.audio->frames <= 0) return;
    const double spb = 60.0 / eng.project->bpm;
    const double startSec = c.start * spb, lenSec = c.length * spb;
    const int64_t cs = (int64_t) std::llround (startSec * sr), ce = (int64_t) std::llround ((startSec + lenSec) * sr);
    const int64_t a0 = std::max (f0, cs), a1 = std::min (f0 + n, ce);
    if (a1 <= a0) return;
    const auto& smp = *c.audio;
    const float* s0 = smp.ch[0].data();
    const float* s1 = smp.channels > 1 ? smp.ch[1].data() : s0;
    const auto& tbl = SincTable::get();
    float co[SincTable::kTaps];
    float gain = dbToGain (c.gainDb), gl, gr;
    panGains (c.pan, gl, gr);
    const double ratio = smp.sampleRate / sr;
    for (int64_t f = a0; f < a1; ++f)
    {
        double t = (double) (f - cs) / sr;
        double srcPos = (c.offsetSec + t) * smp.sampleRate;
        if (c.reverse) srcPos = (double) (smp.frames - 1) - srcPos;
        float a = 0, b = 0;
        if (std::abs (ratio - 1.0) < 1e-12 && std::abs (srcPos - std::round (srcPos)) < 1e-6)
        {
            int64_t i = (int64_t) std::llround (srcPos);
            if (i >= 0 && i < smp.frames) { a = s0[i]; b = s1[i]; }
        }
        else
        {
            int64_t ip = (int64_t) std::floor (srcPos);
            tbl.coeffs (srcPos - (double) ip, co);
            int64_t base = ip - SincTable::kHalf + 1;
            for (int k = 0; k < SincTable::kTaps; ++k)
            {
                int64_t idx = base + k;
                if (idx < 0 || idx >= smp.frames) continue;
                a += co[k] * s0[idx];
                b += co[k] * s1[idx];
            }
        }
        float env = 1.0f;
        if (c.fadeIn > 0 && t < c.fadeIn) env *= (float) (t / c.fadeIn);
        if (c.fadeOut > 0 && t > lenSec - c.fadeOut) env *= (float) std::max (0.0, (lenSec - t) / c.fadeOut);
        L[f - f0] += a * gain * env * gl;
        R[f - f0] += b * gain * env * gr;
    }
}

void Graph::renderTrack (Track& t, int n, int64_t f0, bool playing, const std::vector<MidiEv>* live)
{
    std::fill_n (tL.data(), n, 0.0f);
    std::fill_n (tR.data(), n, 0.0f);
    if (playing)
    {
        for (auto& c : t.clips) if (! c.midi) renderAudioClip (c, f0, n, tL.data(), tR.data());
        collectEvents (t, f0, n);
    }
    else
        ev.clear();
    if (live && ! live->empty())
    {
        ev.insert (ev.end(), live->begin(), live->end());
        std::stable_sort (ev.begin(), ev.end(), [] (const MidiEv& a, const MidiEv& b)
                          { return a.frame != b.frame ? a.frame < b.frame : a.kind < b.kind; });
    }

    ProcessInfo info;
    info.sampleRate = sr;
    info.bpm = eng.project->bpm;
    info.frame = f0;
    info.beat = (double) f0 / sr * eng.project->bpm / 60.0;
    info.playing = playing;

    for (auto& s : t.slots)
    {
        if (! s.enabled) continue;
        switch (s.kind)
        {
            case Slot::Send:
            {
                auto it = buses.find (s.bus);
                if (it == buses.end()) break;
                float g = dbToGain (s.levelDb);
                for (int i = 0; i < n; ++i) { it->second.first[(size_t) i] += tL[(size_t) i] * g; it->second.second[(size_t) i] += tR[(size_t) i] * g; }
                break;
            }
            case Slot::Return:
            {
                auto it = buses.find (s.bus);
                if (it == buses.end()) break;
                for (int i = 0; i < n; ++i) { tL[(size_t) i] += it->second.first[(size_t) i]; tR[(size_t) i] += it->second.second[(size_t) i]; }
                break;
            }
            default:
                if (! s.dev || ! s.dev->enabled) break;
                applyAutomation (s, info.beat);
                if (s.dev->isInstrument())
                {
                    // 악기는 들어온 신호를 지우고 자기 소리만(옛 엔진 SFZ 디바이스와 같게)
                    std::fill_n (tL.data(), n, 0.0f);
                    std::fill_n (tR.data(), n, 0.0f);
                }
                s.dev->process (tL.data(), tR.data(), n, ev, info);
                break;
        }
    }
}

void Graph::metronomeClick (float* L, float* R, int n, int64_t f0)
{
    const double fpb = sr * 60.0 / eng.project->bpm;
    int beatsPerBar = 4;
    try { beatsPerBar = std::max (1, std::stoi (eng.project->timeSig)); } catch (...) {}
    const int64_t clickLen = (int64_t) (0.03 * sr);
    int64_t firstBeat = (int64_t) std::floor ((double) (f0 - clickLen) / fpb);
    for (int64_t b = std::max<int64_t> (0, firstBeat); ; ++b)
    {
        int64_t bf = (int64_t) std::llround (b * fpb);
        if (bf >= f0 + n) break;
        double freq = (b % beatsPerBar == 0) ? 1500.0 : 1000.0;
        for (int64_t f = std::max (f0, bf); f < std::min (f0 + n, bf + clickLen); ++f)
        {
            double t = (double) (f - bf) / sr;
            float v = (float) (std::sin (2 * kPi * freq * t) * std::exp (-t * 120.0)) * eng.metronomeVolume * 0.5f;
            L[f - f0] += v; R[f - f0] += v;
        }
    }
}

int Graph::trackLatency (const Track& t) const
{
    int lat = 0;
    for (auto& s : t.slots) if (s.enabled && s.dev && s.dev->enabled) lat += std::max (0, s.dev->latency());
    return lat;
}

int Graph::latency()
{
    int m = 0;
    if (eng.project) for (auto& t : eng.project->tracks) m = std::max (m, trackLatency (t));
    return m;
}

void Graph::process (float* L, float* R, int n, int64_t f0, bool playing,
                     const std::set<std::string>* only, const std::vector<MidiEv>* live, int liveTrack)
{
    std::fill_n (mL.data(), n, 0.0f);
    std::fill_n (mR.data(), n, 0.0f);
    for (auto& b : buses) { std::fill_n (b.second.first.data(), n, 0.0f); std::fill_n (b.second.second.data(), n, 0.0f); }
    auto& P = *eng.project;

    bool anySolo = false;
    for (auto& t : P.tracks) anySolo |= t.solo;
    const int maxLat = latency();
    auto hasReturn = [] (const Track& t) { for (auto& s : t.slots) if (s.kind == Slot::Return && s.enabled) return true; return false; };

    // 리턴이 없는 트랙 먼저(센드가 버스를 채움), 리턴 트랙은 나중
    for (int pass = 0; pass < 2; ++pass)
        for (size_t ti = 0; ti < P.tracks.size(); ++ti)
        {
            auto& t = P.tracks[ti];
            if (hasReturn (t) != (pass == 1)) continue;
            bool silent = t.mute || (anySolo && ! t.solo && ! hasReturn (t)) || (only && ! only->empty() && ! only->count (t.name));
            const std::vector<MidiEv>* lv = ((int) ti == liveTrack) ? live : nullptr;
            if (silent && ! lv)
            {
                peak[t.name] = { 0, 0 };            // 뮤트·솔로 밖·렌더 대상 아님: 처리하지 않음(센드도 없음)
                continue;
            }
            renderTrack (t, n, f0, playing, lv);
            // 지연 보정: 이 트랙보다 지연이 큰 트랙(피치 시프터 등)에 맞춰 늦춘다
            if (int d = maxLat - trackLatency (t); d > 0)
            {
                auto& dl = pdc[t.name];
                if (dl.len != d) { dl.L.assign ((size_t) d, 0.0f); dl.R.assign ((size_t) d, 0.0f); dl.pos = 0; dl.len = d; }
                for (int i = 0; i < n; ++i)
                {
                    float a = dl.L[dl.pos], b = dl.R[dl.pos];
                    dl.L[dl.pos] = tL[(size_t) i]; dl.R[dl.pos] = tR[(size_t) i];
                    tL[(size_t) i] = a; tR[(size_t) i] = b;
                    if (++dl.pos >= (size_t) d) dl.pos = 0;
                }
            }
            float gl, gr;
            panGains (t.pan, gl, gr);
            float v = dbToGain (t.volumeDb);
            gl *= v; gr *= v;
            float pl = 0, pr = 0;
            for (int i = 0; i < n; ++i)
            {
                float a = tL[(size_t) i] * gl, b = tR[(size_t) i] * gr;
                mL[(size_t) i] += a; mR[(size_t) i] += b;
                pl = std::max (pl, std::abs (a)); pr = std::max (pr, std::abs (b));
            }
            auto& pk = peak[t.name];
            pk[0] = std::max (pl, pk[0] * 0.85f); pk[1] = std::max (pr, pk[1] * 0.85f);
        }

    ProcessInfo info;
    info.sampleRate = sr; info.bpm = P.bpm; info.frame = f0; info.playing = playing;
    info.beat = (double) f0 / sr * P.bpm / 60.0;
    static const std::vector<MidiEv> none;
    for (auto& s : P.master)
        if (s.enabled && s.dev && s.dev->enabled && ! s.dev->isInstrument())
        {
            applyAutomation (s, info.beat);
            s.dev->process (mL.data(), mR.data(), n, none, info);
        }
    float mv = dbToGain (P.masterVolumeDb);
    float pl = 0, pr = 0;
    for (int i = 0; i < n; ++i)
    {
        L[i] = mL[(size_t) i] * mv; R[i] = mR[(size_t) i] * mv;
        pl = std::max (pl, std::abs (L[i])); pr = std::max (pr, std::abs (R[i]));
    }
    if (playing && eng.metronome.load()) metronomeClick (L, R, n, f0);

    for (auto& kv : peak)
        meters[kv.first] = { (float) std::max (-100.0, gainToDb (kv.second[0])), (float) std::max (-100.0, gainToDb (kv.second[1])) };
    static float mpl = 0, mpr = 0;
    mpl = std::max (pl, mpl * 0.85f); mpr = std::max (pr, mpr * 0.85f);
    masterMeter = { (float) std::max (-100.0, gainToDb (mpl)), (float) std::max (-100.0, gainToDb (mpr)) };
}

} // namespace mc
