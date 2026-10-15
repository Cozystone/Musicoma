#include "render.h"
#include <algorithm>
#include <atomic>
#include <chrono>
#include <mutex>
#include <set>
#include <thread>

namespace mc {

bool applyTuning (Tuning& t, const std::string& k, double v)
{
    if (k == "envExpK") t.envExpK = v;
    else if (k == "fastOff") t.fastOff = v;
    else if (k == "velModel") t.velModel = (int) v;
    else if (k == "ampModMultiply") t.ampModMultiply = v != 0;
    else if (k == "panLaw") t.panLaw = (int) v;
    else if (k == "maxVoices") t.maxVoices = (int) v;
    else if (k == "ccTriggerEnter") t.ccTriggerEnter = v != 0;
    else if (k == "ccTriggerVelFromValue") t.ccTriggerVelFromValue = v != 0;
    else if (k == "deferReleaseOnPedal") t.deferReleaseOnPedal = v != 0;
    else if (k == "defaultCc7") t.defaultCc7 = v != 0;
    else if (k == "defaultCc10") t.defaultCc10 = v != 0;
    else if (k == "offsetCurveLinear") t.offsetCurveLinear = v != 0;
    else if (k == "eventDelay") t.eventDelay = (int) v;
    else if (k == "seqMode") t.seqMode = (int) v;
    else if (k == "filterQBase") t.filterQBase = v;
    else if (k == "polyCountsReleased") t.polyCountsReleased = v != 0;
    else return false;
    return true;
}

namespace {

constexpr int64_t kChunk = 16384;   // 트랙은 이 크기 조각으로 흘려 렌더 → 트랙당 메모리 일정

struct Stereo
{
    std::vector<float> L, R;
    void alloc (int64_t n) { L.assign ((size_t) n, 0.0f); R.assign ((size_t) n, 0.0f); }
};

struct Ctx
{
    const Json& plan;
    int sr = 48000;
    double bpm = 120;
    double startSec = 0;
    int64_t frames = 0;
    SamplePool pool;
    Tuning tuning;
    int mixPanLaw = 3;
    std::mutex sfzLock;
    std::map<std::string, std::shared_ptr<Instrument>> sfzCache;   // 같은 SFZ 는 한 번만 파싱
    std::mutex warnLock;
    std::vector<std::string> warnings;
    std::set<std::string> warned;
    Json trackStats = Json::array();
    std::mutex statsLock;

    // 합치는 곳 (mixLock 으로 보호)
    std::mutex mixLock;
    Stereo master;
    std::map<int, Stereo> buses;

    explicit Ctx (const Json& p) : plan (p) {}

    double beatToSec (double beat) const { return beat * 60.0 / bpm; }
    int64_t secToFrame (double s) const { return (int64_t) std::llround ((s - startSec) * sr); }

    void warn (const std::string& w)
    {
        std::lock_guard<std::mutex> l (warnLock);
        if (warned.insert (w).second) { warnings.push_back (w); logWarn (w); }
    }

    std::shared_ptr<Instrument> instrument (const std::string& path, std::string& err)
    {
        std::lock_guard<std::mutex> l (sfzLock);
        auto it = sfzCache.find (path);
        if (it != sfzCache.end()) return it->second;
        auto inst = loadSfz (path, err);
        sfzCache[path] = inst;
        return inst;
    }
};

void mixPan (int law, float pan, float& gl, float& gr)
{
    float p = clampv (pan, -1.0f, 1.0f);
    switch (law)
    {
        case 1:  gl = std::cos ((p + 1) * (float) kPi / 4); gr = std::sin ((p + 1) * (float) kPi / 4); break;        // 일정 전력, 가운데 -3dB
        case 2:  gl = std::sqrt (2.0f) * std::cos ((p + 1) * (float) kPi / 4); gr = std::sqrt (2.0f) * std::sin ((p + 1) * (float) kPi / 4); break;
        case 3:  gl = 1 - p; gr = 1 + p; break;                                                                          // 엔진 측정값: 가운데 0dB, 끝 +6dB
        default: gl = p > 0 ? 1 - p : 1.0f; gr = p < 0 ? 1 + p : 1.0f; break;                                          // 0: 밸런스, 가운데 0dB
    }
}

std::vector<MidiEv> buildEvents (Ctx& c, const Json& track)
{
    std::vector<MidiEv> ev;
    for (auto& clip : track["midi_clips"].a)
    {
        if (clip.flag ("mute", false)) continue;
        double sb = clip.num ("start_beat", 0), eb = clip.num ("end_beat", sb);
        double len = eb - sb;
        int64_t clipEnd = c.secToFrame (c.beatToSec (eb));
        for (auto& n : clip["notes"].a)
        {
            double s = n.num ("start", 0), L = n.num ("length", 0);
            if (s < 0 || s >= len || L <= 0) continue;
            int64_t on = c.secToFrame (c.beatToSec (sb + s));
            int64_t off = std::min (clipEnd, c.secToFrame (c.beatToSec (sb + s + L)));
            if (off <= on) off = on + 1;
            int p = (int) n.num ("pitch", 60);
            float v = (float) clampv (n.num ("velocity", 100), 1.0, 127.0) / 127.0f;
            ev.push_back ({ on, MidiEv::NoteOn, p, v });
            ev.push_back ({ off, MidiEv::NoteOff, p, 0.0f });
        }
        for (auto& x : clip["cc"].a)
        {
            double b = x.num ("beat", 0);
            if (b < 0 || b >= len) continue;
            ev.push_back ({ c.secToFrame (c.beatToSec (sb + b)), MidiEv::CC, (int) x.num ("cc", 0),
                            (float) clampv (x.num ("value", 0), 0.0, 127.0) / 127.0f });
        }
        for (auto& x : clip["bend"].a)
        {
            double b = x.num ("beat", 0);
            if (b < 0 || b >= len) continue;
            ev.push_back ({ c.secToFrame (c.beatToSec (sb + b)), MidiEv::Bend, 0, (float) clampv (x.num ("value", 0), -1.0, 1.0) });
        }
    }
    // 시작 전 이벤트는 0 으로(상태만 반영), 같은 시점이면 CC·벤드 → 노트오프 → 노트온
    for (auto& e : ev) if (e.frame < 0) e.frame = 0;
    std::stable_sort (ev.begin(), ev.end(), [] (const MidiEv& a, const MidiEv& b)
                      { return a.frame != b.frame ? a.frame < b.frame : a.kind < b.kind; });
    return ev;
}

//==============================================================================
struct AudioClipPlay
{
    std::shared_ptr<const AudioData> smp;
    int64_t f0 = 0, f1 = 0;
    double offSec = 0, lenSec = 0, fin = 0, fout = 0;
    float gain = 1, gl = 1, gr = 1;
    bool rev = false;

    /** 절대 프레임 [cf, cf+n) 을 L/R 에 더한다 */
    void render (int sr, int64_t cf, int64_t n, float* L, float* R) const
    {
        const auto& tbl = SincTable::get();
        const float* s0 = smp->ch[0].data();
        const float* s1 = smp->channels > 1 ? smp->ch[1].data() : s0;
        float co[SincTable::kTaps];
        int64_t a0 = std::max (cf, f0), a1 = std::min (cf + n, f1);
        for (int64_t f = a0; f < a1; ++f)
        {
            double t = (double) (f - f0) / sr;
            double srcPos = (offSec + t) * smp->sampleRate;
            if (rev) srcPos = (double) (smp->frames - 1) - srcPos;
            int64_t ip = (int64_t) std::floor (srcPos);
            tbl.coeffs (srcPos - (double) ip, co);
            float a = 0, b = 0;
            int64_t base = ip - SincTable::kHalf + 1;
            if (base >= 0 && base + SincTable::kTaps <= smp->frames)
                for (int k = 0; k < SincTable::kTaps; ++k) { a += co[k] * s0[base + k]; b += co[k] * s1[base + k]; }
            else
                for (int k = 0; k < SincTable::kTaps; ++k)
                {
                    int64_t idx = base + k;
                    if (idx < 0 || idx >= smp->frames) continue;
                    a += co[k] * s0[idx];
                    b += co[k] * s1[idx];
                }
            float env = 1.0f;
            if (fin > 0 && t < fin) env *= (float) (t / fin);
            if (fout > 0 && t > lenSec - fout) env *= (float) std::max (0.0, (lenSec - t) / fout);
            L[f - cf] += a * gain * env * gl;
            R[f - cf] += b * gain * env * gr;
        }
    }
};

std::vector<AudioClipPlay> prepareAudioClips (Ctx& c, const Json& track)
{
    std::vector<AudioClipPlay> out;
    for (auto& clip : track["audio_clips"].a)
    {
        if (clip.flag ("mute", false)) continue;
        std::string file = clip.str ("file");
        if (file.empty()) { c.warn ("audio clip without file on track " + track.str ("name")); continue; }
        AudioClipPlay p;
        p.smp = c.pool.get (file);
        if (! p.smp) { c.warn ("audio file not readable: " + file); continue; }
        double startSec = clip.num ("start_sec", c.beatToSec (clip.num ("start_beat", 0)));
        p.lenSec = clip.num ("length_sec", c.beatToSec (clip.num ("end_beat", 0) - clip.num ("start_beat", 0)));
        p.offSec = clip.num ("offset_sec", 0);
        p.gain = dbToGain (clip.num ("gain_db", 0));
        mixPan (c.mixPanLaw, (float) clip.num ("pan", 0), p.gl, p.gr);
        p.fin = clip.num ("fade_in_sec", 0);
        p.fout = clip.num ("fade_out_sec", 0);
        p.rev = clip.flag ("reverse", false);
        p.f0 = c.secToFrame (startSec);
        p.f1 = c.secToFrame (startSec + p.lenSec);
        out.push_back (std::move (p));
    }
    return out;
}

//==============================================================================
/** 체인의 한 칸 (조각 사이 상태를 들고 있음) */
struct Node
{
    enum Kind { Synth, Silent, Send, Return, Lowpass, Comp, Pass } kind = Pass;
    std::unique_ptr<SfzSynth> synth;
    int bus = 0;
    float gain = 1;
    Biquad bq;
    Compressor comp;
};

void setupCompressor (Compressor& comp, const Json& d)
{
    comp.thresholdDb = d.num ("threshold_db", -12);
    comp.ratio = d.num ("ratio", 2);
    comp.attackMs = d.num ("attack_ms", 10);
    comp.releaseMs = d.num ("release_ms", 100);
    comp.outputDb = d.num ("output_db", 0);
}

void setupFilter (Biquad& b, const Json& d, double sr)
{
    if (d.str ("mode") == "highpass") b.highpass (sr, d.num ("frequency", 4000), 0.7071067811865476);
    else b.lowpass (sr, d.num ("frequency", 4000), 0.7071067811865476);
}

void renderTrack (Ctx& c, const Json& track)
{
    std::string tname = track.str ("name");
    auto t0 = std::chrono::steady_clock::now();
    Json st = Json::object();
    st.set ("track", Json::string (tname));

    // 체인 준비
    std::vector<Node> nodes;
    bool hasMidi = ! track["midi_clips"].a.empty();
    bool hadInstrument = false;
    for (auto& d : track["chain"].a)
    {
        if (! d.flag ("enabled", true)) continue;
        std::string kind = d.str ("kind");
        Node n;
        if (kind == "sfz")
        {
            hadInstrument = true;
            std::string err;
            auto inst = c.instrument (d.str ("sfz"), err);
            if (! inst) { c.warn (tname + ": " + err); n.kind = Node::Silent; }
            else
            {
                n.kind = Node::Synth;
                n.synth = std::make_unique<SfzSynth> (inst, c.pool, c.sr, c.tuning);
                n.synth->outputGain = dbToGain (d.num ("volume_db", 0));
                st.set ("sfz", Json::string (d.str ("sfz")));
                st.set ("regions", Json::number ((double) inst->regions.size()));
            }
        }
        else if (kind == "vst3" || kind == "builtin_synth")
        {
            hadInstrument = true;
            n.kind = Node::Silent;
            c.warn (tname + ": instrument '" + d.str ("name") + "' (" + kind + ") not supported in C1 — silent");
        }
        else if (kind == "send") { n.kind = Node::Send; n.bus = (int) d.num ("bus", 0); n.gain = dbToGain (d.num ("level_db", 0)); }
        else if (kind == "return") { n.kind = Node::Return; n.bus = (int) d.num ("bus", 0); }
        else if (kind == "lowpass") { n.kind = Node::Lowpass; setupFilter (n.bq, d, c.sr); }
        else if (kind == "compressor") { n.kind = Node::Comp; setupCompressor (n.comp, d); }
        else
        {
            n.kind = Node::Pass;
            c.warn (tname + ": effect '" + kind + "' (" + d.str ("name") + ") not implemented in C1 — passed through");
        }
        nodes.push_back (std::move (n));
    }
    if (hasMidi && ! hadInstrument)
        c.warn (tname + ": MIDI clips but no instrument");

    auto events = buildEvents (c, track);
    auto clips = prepareAudioClips (c, track);
    float gl, gr;
    mixPan (c.mixPanLaw, (float) track.num ("pan", 0), gl, gr);
    float vol = dbToGain (track.num ("volume_db", 0));
    gl *= vol; gr *= vol;

    std::vector<float> L ((size_t) kChunk), R ((size_t) kChunk);
    for (int64_t cf = 0; cf < c.frames; cf += kChunk)
    {
        int64_t n = std::min (kChunk, c.frames - cf);
        std::fill (L.begin(), L.end(), 0.0f);
        std::fill (R.begin(), R.end(), 0.0f);

        // 오디오 클립은 체인 맨 앞에서 들어온다
        for (auto& p : clips) p.render (c.sr, cf, n, L.data(), R.data());

        for (auto& nd : nodes)
        {
            switch (nd.kind)
            {
                case Node::Synth:
                    // 엔진의 SFZ 디바이스는 버퍼를 지우고 자기 소리만 낸다
                    std::fill (L.begin(), L.end(), 0.0f);
                    std::fill (R.begin(), R.end(), 0.0f);
                    nd.synth->process (events, n, L.data(), R.data());
                    break;
                case Node::Silent:
                    std::fill (L.begin(), L.end(), 0.0f);
                    std::fill (R.begin(), R.end(), 0.0f);
                    break;
                case Node::Send:
                {
                    std::lock_guard<std::mutex> l (c.mixLock);
                    auto& b = c.buses.at (nd.bus);
                    for (int64_t i = 0; i < n; ++i) { b.L[(size_t) (cf + i)] += L[(size_t) i] * nd.gain; b.R[(size_t) (cf + i)] += R[(size_t) i] * nd.gain; }
                    break;
                }
                case Node::Return:
                {
                    // 이 버스로 보내는 트랙은 모두 끝난 뒤라 잠그지 않아도 된다
                    auto it = c.buses.find (nd.bus);
                    if (it != c.buses.end())
                        for (int64_t i = 0; i < n; ++i) { L[(size_t) i] += it->second.L[(size_t) (cf + i)]; R[(size_t) i] += it->second.R[(size_t) (cf + i)]; }
                    break;
                }
                case Node::Lowpass:
                    for (int64_t i = 0; i < n; ++i) { L[(size_t) i] = nd.bq.process (L[(size_t) i], 0); R[(size_t) i] = nd.bq.process (R[(size_t) i], 1); }
                    break;
                case Node::Comp:
                    nd.comp.process (L.data(), R.data(), n, c.sr);
                    break;
                case Node::Pass: break;
            }
        }

        std::lock_guard<std::mutex> l (c.mixLock);
        for (int64_t i = 0; i < n; ++i)
        {
            c.master.L[(size_t) (cf + i)] += L[(size_t) i] * gl;
            c.master.R[(size_t) (cf + i)] += R[(size_t) i] * gr;
        }
    }

    for (auto& nd : nodes)
        if (nd.kind == Node::Synth)
        {
            auto& s = nd.synth->stats;
            st.set ("voices_started", Json::number ((double) s.voicesStarted));
            st.set ("max_voices", Json::number (s.maxActive));
            st.set ("stolen", Json::number ((double) s.stolen));
            if (s.missingSampleHits) st.set ("missing_sample_hits", Json::number ((double) s.missingSampleHits));
        }
    double ms = std::chrono::duration<double, std::milli> (std::chrono::steady_clock::now() - t0).count();
    st.set ("render_ms", Json::number (std::round (ms)));
    std::lock_guard<std::mutex> l (c.statsLock);
    c.trackStats.push (st);
}

void processMasterFx (Ctx& c, const Json& d)
{
    std::string kind = d.str ("kind");
    const int64_t n = (int64_t) c.master.L.size();
    if (kind == "lowpass")
    {
        Biquad b;
        setupFilter (b, d, c.sr);
        for (int64_t i = 0; i < n; ++i) { c.master.L[(size_t) i] = b.process (c.master.L[(size_t) i], 0); c.master.R[(size_t) i] = b.process (c.master.R[(size_t) i], 1); }
    }
    else if (kind == "compressor")
    {
        Compressor comp;
        setupCompressor (comp, d);
        comp.process (c.master.L.data(), c.master.R.data(), n, c.sr);
    }
    else
        c.warn ("master: effect '" + kind + "' (" + d.str ("name") + ") not implemented in C1 — passed through");
}

} // namespace

//==============================================================================
RenderResult renderPlan (const Json& plan, const RenderOptions& opt)
{
    if (plan.str ("format") != "musicoma-render-plan")
        throw std::runtime_error ("not a musicoma render plan");

    Ctx c (plan);
    const Json& r = plan["render"];
    c.sr = opt.sampleRate > 0 ? opt.sampleRate : (int) r.num ("sample_rate", 48000);
    c.bpm = plan.num ("bpm", 120);
    if (plan["tempo"].a.size() > 1) c.warn ("tempo changes not supported in C1 — using first tempo");
    double sb = r.num ("start_beat", 0), eb = r.num ("end_beat", plan.num ("length_beats", 0));
    double tail = r.num ("tail_sec", 2.0);
    c.startSec = c.beatToSec (sb);
    double endSec = c.beatToSec (eb) + tail;
    if (endSec <= c.startSec) throw std::runtime_error ("nothing to render");
    c.frames = (int64_t) std::llround ((endSec - c.startSec) * c.sr);
    c.tuning = opt.tuning;
    for (auto& kv : plan["core_tuning"].o)
        if (kv.second.isNum() && ! applyTuning (c.tuning, kv.first, kv.second.n) && kv.first != "mixPanLaw")
            c.warn ("unknown core_tuning key " + kv.first);
    c.mixPanLaw = opt.mixPanLaw >= 0 ? opt.mixPanLaw : (int) plan["core_tuning"].num ("mixPanLaw", 3);

    const auto& tracks = plan["tracks"].a;
    bool anySolo = false;
    for (auto& t : tracks) anySolo |= t.flag ("solo", false);

    auto returnsOf = [] (const Json& t) { std::set<int> b; for (auto& d : t["chain"].a) if (d.str ("kind") == "return" && d.flag ("enabled", true)) b.insert ((int) d.num ("bus", 0)); return b; };
    auto sendsOf = [] (const Json& t) { std::set<int> b; for (auto& d : t["chain"].a) if (d.str ("kind") == "send" && d.flag ("enabled", true)) b.insert ((int) d.num ("bus", 0)); return b; };

    std::vector<const Json*> todo;
    for (auto& t : tracks)
    {
        if (t.flag ("mute", false)) continue;
        if (anySolo && ! t.flag ("solo", false) && returnsOf (t).empty()) continue;   // 솔로가 있어도 리턴 버스는 살린다
        todo.push_back (&t);
    }

    c.master.alloc (c.frames);
    for (auto* t : todo)
        for (int b : sendsOf (*t))
            if (! c.buses.count (b)) c.buses[b].alloc (c.frames);   // 버스는 미리 (렌더 중 map 구조가 안 바뀌게)

    unsigned hw = std::max (1u, std::thread::hardware_concurrency());
    unsigned nThreads = opt.threads > 0 ? (unsigned) opt.threads : hw;

    // 리턴이 없는 트랙부터, 리턴 트랙은 그 버스로 보내는 트랙이 다 끝난 뒤
    std::vector<const Json*> pending = todo;
    int guard = 0;
    while (! pending.empty() && guard++ < 64)
    {
        std::vector<const Json*> ready, later;
        for (auto* t : pending)
        {
            bool ok = true;
            for (int b : returnsOf (*t))
                for (auto* o : pending)
                    if (o != t && sendsOf (*o).count (b)) ok = false;
            (ok ? ready : later).push_back (t);
        }
        if (ready.empty()) { c.warn ("send/return cycle — rendering remaining tracks anyway"); ready = later; later.clear(); }

        std::atomic<size_t> next { 0 };
        std::exception_ptr failure;
        std::mutex failLock;
        auto worker = [&]
        {
            while (true)
            {
                size_t i = next++;
                if (i >= ready.size()) break;
                try { renderTrack (c, *ready[i]); }
                catch (...) { std::lock_guard<std::mutex> l (failLock); failure = std::current_exception(); }
            }
        };
        std::vector<std::thread> pool;
        for (unsigned k = 0; k < std::min<size_t> (nThreads, ready.size()); ++k) pool.emplace_back (worker);
        for (auto& th : pool) th.join();
        if (failure) std::rethrow_exception (failure);
        pending = later;
    }

    for (auto& d : plan["master"]["chain"].a)
        if (d.flag ("enabled", true)) processMasterFx (c, d);
    float mv = dbToGain (plan["master"].num ("volume_db", 0));
    for (size_t i = 0; i < c.master.L.size(); ++i) { c.master.L[i] *= mv; c.master.R[i] *= mv; }

    RenderResult res;
    res.frames = c.frames;
    res.audioSeconds = (double) c.frames / c.sr;
    res.out.push_back (std::move (c.master.L));
    res.out.push_back (std::move (c.master.R));
    res.warnings = c.warnings;

    Json unsup = Json::object();
    for (auto& [path, inst] : c.sfzCache)
    {
        if (! inst) continue;
        Json m = Json::object();
        for (auto& [op, n] : inst->unsupported) m.set (op, Json::number (n));
        unsup.set (path, m);
    }
    res.stats.set ("tracks", c.trackStats);
    res.stats.set ("ignored_opcodes", unsup);
    res.stats.set ("samples_loaded", Json::number ((double) c.pool.filesLoaded()));
    res.stats.set ("sample_mb", Json::number (std::round (c.pool.bytesLoaded() / 1048576.0)));
    res.stats.set ("samples_failed", Json::number ((double) c.pool.filesFailed()));
    res.stats.set ("threads", Json::number (nThreads));
    return res;
}

} // namespace mc
