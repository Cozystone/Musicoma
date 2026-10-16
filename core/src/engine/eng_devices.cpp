// Musicoma Engine — 디바이스 만들기(SFZ 샘플러 · 내장 이펙트 · VST3 · 센드/리턴)
#include <algorithm>
#include <cctype>
#include <cstdio>
#include "eng_model.h"
#include "sfz.h"
#include "sampler.h"
#include "vst3host.h"

namespace mc {

namespace {

std::string lower (std::string s) { for (auto& c : s) c = (char) std::tolower ((unsigned char) c); return s; }

std::string fmtDb (double v)
{
    char b[32];
    std::snprintf (b, sizeof b, "%+.2f dB", v);
    return b;
}

/** 자체 SFZ 샘플러 디바이스(옛 엔진의 musicomaSfz 와 같은 이름·파라미터 'volume') */
class SfzDevice : public Device
{
public:
    SfzDevice (std::shared_ptr<const Instrument> i, SamplePool& p, const Tuning& t, std::string path)
        : inst (std::move (i)), pool (p), tune (t), sfzPath (std::move (path)) {}

    std::string type() const override { return "musicomaSfz"; }
    std::string name() const override { return "SFZ Sampler"; }
    bool isInstrument() const override { return true; }

    void prepare (double sampleRate, int) override
    {
        if (synth && sr == sampleRate) return;
        sr = sampleRate;
        synth = std::make_unique<SfzSynth> (inst, pool, sr, tune);
        synth->outputGain = dbToGain (volumeDb);
    }
    void reset() override { if (synth) synth->allNotesOff(); }

    void process (float* L, float* R, int n, const std::vector<MidiEv>& events, const ProcessInfo&) override
    {
        if (! synth) return;
        synth->outputGain = dbToGain (volumeDb);
        synth->processBlock (events, n, L, R);
    }

    std::vector<ParamInfo> params() override
    {
        ParamInfo p;
        p.id = "volume"; p.name = "Volume"; p.min = -60; p.max = 12; p.def = 0; p.value = volumeDb; p.text = fmtDb (volumeDb);
        return { p };
    }
    bool setParam (const std::string& id, double v) override
    {
        if (lower (id) != "volume") return false;
        volumeDb = std::clamp (v, -60.0, 12.0);
        return true;
    }
    Json getState() override { Json j = Json::object(); j.set ("volume", Json::number (volumeDb)); return j; }
    void setState (const Json& s) override { volumeDb = s.num ("volume", volumeDb); }
    double tailSeconds() const override { return 3.0; }

    int regions() const { return (int) inst->regions.size(); }

private:
    std::shared_ptr<const Instrument> inst;
    SamplePool& pool;
    Tuning tune;
    std::string sfzPath;
    std::unique_ptr<SfzSynth> synth;
    double sr = 0;
    double volumeDb = 0;
};

std::vector<Vst3Desc> gVst;
bool gVstScanned = false;

} // namespace

std::vector<Vst3Desc>& vstPlugins (Engine& e, bool rescan, const std::vector<std::string>& extraDirs)
{
    if (! gVstScanned || rescan)
    {
        std::vector<std::string> dirs { e.root + "/sounds/plugins/vst3" };
        dirs.insert (dirs.end(), extraDirs.begin(), extraDirs.end());
        std::vector<std::string> warn;
        gVst = scanVst3 (dirs, &warn);
        for (auto& w : warn) if (e.log) e.log ("vst3 scan: " + w);
        gVstScanned = true;
    }
    return gVst;
}

std::vector<Json> Engine::availableBuiltins()
{
    std::vector<Json> out;
    out.push_back (Json::string ("sfz"));
    for (auto& n : builtinFxNames()) out.push_back (Json::string (n));
    out.push_back (Json::string ("send"));
    out.push_back (Json::string ("return"));
    return out;
}

void Engine::prepareSlot (Slot& s, double sr)
{
    if (s.dev) s.dev->prepare (sr, 4096);
}

Slot Engine::makeSlot (const Json& p, std::string& error)
{
    Slot s;
    s.uid = nextUid++;
    std::string dev = p.str ("device");
    if (dev.empty()) { error = "missing 'device'"; return s; }
    std::string d = lower (dev);
    if (d == "sfz" || d == "sampler" || d == "musicomasfz")
    {
        std::string path = p.str ("sfz", p.str ("path"));
        if (path.empty()) { error = "sfz device needs 'sfz' (path to .sfz)"; return s; }
        std::string err;
        auto inst = loadSfz (path, err);
        if (! inst) { error = "cannot load sfz: " + err; return s; }
        s.kind = Slot::Sfz;
        s.sfz = path;
        s.regions = (int) inst->regions.size();
        s.dev = std::make_shared<SfzDevice> (inst, pool, tuning, path);
        return s;
    }
    if (d == "send" || d == "auxsend")
    {
        s.kind = Slot::Send;
        s.bus = (int) p.num ("bus", 0);
        s.levelDb = p.num ("level_db", -12);
        return s;
    }
    if (d == "return" || d == "auxreturn")
    {
        s.kind = Slot::Return;
        s.bus = (int) p.num ("bus", 0);
        return s;
    }
    if (auto fx = createBuiltinFx (d))
    {
        s.kind = Slot::Builtin;
        s.builtin = d == "filter" ? "lowpass" : d;
        s.dev = std::move (fx);
        return s;
    }
    // VST3: 이름이 같은 것 → 포함하는 것
    auto& list = vstPlugins (*this, false, {});
    const Vst3Desc* found = nullptr;
    for (auto& v : list) if (lower (v.name) == d) { found = &v; break; }
    if (! found) for (auto& v : list) if (lower (v.name).find (d) != std::string::npos) { found = &v; break; }
    if (! found) { error = "unknown device '" + dev + "' (see device.available, or device.scan)"; return s; }
    std::string err;
    auto inst = createVst3 (*found, err);
    if (! inst) { error = "cannot load " + found->name + ": " + err; return s; }
    s.kind = Slot::Vst3;
    s.vstName = found->name;
    s.vstPath = found->path;
    s.vstCid = found->cid;
    s.dev = std::move (inst);
    return s;
}

} // namespace mc
