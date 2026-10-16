// Musicoma Engine — 명령 처리(프로토콜: tests/golden/protocol.json 의 옛 엔진 응답 모양)
#include <algorithm>
#include <cctype>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <set>
#include "eng_model.h"
#include "eng_graph.h"
#include "audiofile.h"
#include "vst3host.h"

namespace mc {

std::vector<Vst3Desc>& vstPlugins (Engine& e, bool rescan, const std::vector<std::string>& extraDirs);
bool importMidiFile (const std::string& path, int wantTrack, double bpmHint, Clip& out, std::string& err);
int64_t playFrameNow();
void setPlayFrame (int64_t f);
void stopNullClock();

static const char* kVersion = "0.4.0";

namespace {

std::string lower (std::string s) { for (auto& c : s) c = (char) std::tolower ((unsigned char) c); return s; }

double needNum (const Json& p, const char* key)
{
    const Json* v = p.find (key);
    if (! v || ! v->isNum()) throw CommandError (std::string ("missing or non-numeric '") + key + "'");
    return v->n;
}

std::string sanitise (std::string s)
{
    for (auto& c : s) if (std::string ("\\/:*?\"<>|").find (c) != std::string::npos) c = '_';
    return s;
}

Json paramJson (const ParamInfo& p, int index, bool withIndex)
{
    Json o = Json::object();
    o.set ("id", Json::string (p.id));
    o.set ("name", Json::string (p.name));
    o.set ("value", Json::number (p.value));
    o.set ("text", Json::string (p.text));
    o.set ("min", Json::number (p.min));
    o.set ("max", Json::number (p.max));
    if (withIndex) o.set ("index", Json::number (index));
    return o;
}

const std::vector<std::pair<std::string, std::string>>& helpList()
{
    static const std::vector<std::pair<std::string, std::string>> h {
        { "ping", "-> {ok}" }, { "help", "this list" },
        { "edit.new", "{name, bpm=120, time_sig='4/4'} create project in projects/<name>/" },
        { "edit.load", "{path}" }, { "edit.save", "{path?}" },
        { "edit.info", "full summary: tempo, tracks, devices, clips (positions in beats)" },
        { "edit.set", "{bpm?, time_sig?, master_volume_db?}" }, { "edit.undo", "" }, { "edit.redo", "" },
        { "track.add", "{name} -> {track}" }, { "track.remove", "{track}" },
        { "track.set", "{track, name?, volume_db?, pan(-1..1)?, mute?, solo?}" },
        { "device.available", "built-in + scanned VST3 devices" },
        { "device.scan", "{dirs?} scan VST3 folders (default sounds/plugins/vst3)" },
        { "device.add", "{track|'master', device, index?, sfz?, bus?, level_db?} -> {device}. send/return: put 'return' (bus n) on a bus track, 'send' (bus n, level_db) on source tracks" },
        { "device.remove", "{track, device}" },
        { "device.params", "{track, device, filter?} list parameters with ranges and current values" },
        { "device.set", "{track, device, params:{id|name: value | 'text'}, enabled?}" },
        { "device.show", "{track, device} open the device window for manual control" },
        { "device.preset_save", "{track, device, name}" }, { "device.preset_load", "{track, device, name|path}" },
        { "device.load_file", "{track, device, path} load a plugin patch file (.fxp / raw state) e.g. Surge XT patches" },
        { "device.programs", "{track, device} list the plugin's built-in programs" },
        { "device.program", "{track, device, program: index|name}" },
        { "clip.add_midi", "{track, start, length, name?, notes:[{pitch,start,length,velocity}], cc?:[{cc,beat,value 0-127}], bend?:[{beat,value -1..1}]}" },
        { "clip.list", "{track}" }, { "clip.notes", "{track, clip}" }, { "clip.controllers", "{track, clip} → cc / bend events" },
        { "clip.set_notes", "{track, clip, notes, replace=true}" }, { "clip.remove", "{track, clip}" },
        { "clip.import_midi", "{track, path, start=0, midi_track?}" },
        { "clip.add_audio", "{track, path, start=0, offset(sec in file)=0, length(beats)?, gain_db?, pan?, fade_in?, fade_out?, reverse?}" },
        { "clip.set", "{track, clip, name?, mute?, start?, length?, offset?, gain_db?, pan?, fade_in?, fade_out?, reverse?}" },
        { "clip.duplicate", "{track, clip, start?} copy a clip (default: right after the original)" },
        { "clip.split", "{track, clip, at (beat)} split a clip in two" },
        { "automation.set", "{track, device, param, points:[{beat, value, curve?}], clear=true}" },
        { "transport.play", "{from?, loop:[startBeat,endBeat]?}" }, { "transport.stop", "" }, { "transport.state", "" },
        { "transport.record", "{} start recording on armed tracks (stop with transport.stop — takes become clips)" },
        { "transport.metronome", "{enabled, volume?(0.2..1)} click track" },
        { "meters", "peak levels (dB) per track [L,R] and master — poll while playing" },
        { "audio.devices", "list output devices and the current one" },
        { "audio.set", "{device, buffer?} choose the playback output" },
        { "inputs.list", "MIDI and audio inputs (keyboards, controllers, interfaces)" },
        { "track.arm", "{track, armed=true, input?(device name; default = first MIDI keyboard)} record-arm a track" },
        { "render", "{path?, start?, end?, tail=2, sample_rate=48000, bit_depth=24, tracks?} -> wav" },
        { "midi.inject", "{messages:[[status,data1,data2],...]} virtual keyboard: same path as a MIDI input (monitor + record)" },
    };
    return h;
}

const std::set<std::string>& readOnly()
{
    static const std::set<std::string> r { "ping", "help", "edit.info", "edit.save", "device.available", "device.params", "device.show",
        "device.preset_save", "device.programs", "clip.list", "clip.notes", "clip.controllers", "transport.play", "transport.stop",
        "transport.state", "render", "device.scan", "audio.devices", "audio.set", "meters", "transport.record", "inputs.list",
        "transport.metronome", "midi.inject" };
    return r;
}

} // namespace

Engine::Engine (const std::string& rootDir) : root (rootDir)
{
    graph = std::make_unique<Graph> (*this);
    log = [] (const std::string& s) { std::fprintf (stderr, "[engine] %s\n", s.c_str()); std::fflush (stderr); };
}

Engine::~Engine()
{
    playing = false;
    output.close();
    stopNullClock();
    for (auto& mi : midiInputs) mi->close();
}

static Json transportState (Engine& e)
{
    Json o = Json::object();
    o.set ("playing", Json::boolean (e.playing.load()));
    o.set ("position", Json::number (e.positionBeat.load()));
    o.set ("looping", Json::boolean (e.looping));
    o.set ("recording", Json::boolean (e.recording.load()));
    o.set ("metronome", Json::boolean (e.metronome.load()));
    Json lp = Json::array(); lp.push (Json::number (e.loopStart)); lp.push (Json::number (e.loopEnd));
    o.set ("loop", lp);
    o.set ("audio_device", Json::string (e.output.isOpen() ? e.output.deviceName() + " (Windows Audio)" : std::string ("(no output — silent clock)")));
    return o;
}

// ───────────────────────── 렌더 ─────────────────────────
static Json doRender (Engine& e, const Json& p)
{
    auto& P = e.requireProject();
    bool wasPlaying = e.playing.load();
    e.playing = false;
    int sr = (int) p.num ("sample_rate", 48000);
    int bits = (int) p.num ("bit_depth", 24);
    double startBeat = p.num ("start", 0);
    double endBeat = p.num ("end", P.lengthBeats());
    double tail = p.num ("tail", 2.0);
    std::set<std::string> only;
    for (auto& t : p["tracks"].a) if (t.isStr()) only.insert (t.s);
    std::string path = p.str ("path");
    if (path.empty())
    {
        fs::path d = u8path (e.root) / "renders";
        fs::create_directories (d);
        path = pathToU8 (d / (P.name + ".wav"));
    }
    double spb = 60.0 / P.bpm;
    int64_t f0 = (int64_t) std::llround (startBeat * spb * sr);
    int64_t f1 = (int64_t) std::llround ((endBeat * spb + tail) * sr);
    if (f1 <= f0) throw CommandError ("nothing to render");
    auto t0 = std::chrono::steady_clock::now();

    if (sr != 48000) e.prepareAll (sr);
    Graph g (e);
    const int block = 2048;
    g.prepare (sr, block);
    g.resetAll();
    std::vector<std::vector<float>> ch (2, std::vector<float> ((size_t) (f1 - f0), 0.0f));
    std::vector<float> L (block), R (block);
    const int64_t lat = g.latency();          // 지연 보정(PDC): 곡 전체가 lat 샘플 늦게 나오므로 그만큼 더 돌리고 앞을 버린다
    for (int64_t f = f0; f < f1 + lat; f += block)
    {
        int n = (int) std::min<int64_t> (block, f1 + lat - f);
        g.process (L.data(), R.data(), n, f, true, only.empty() ? nullptr : &only, nullptr, -1);
        for (int i = 0; i < n; ++i)
        {
            int64_t o = f + i - lat - f0;
            if (o >= 0 && o < f1 - f0) { ch[0][(size_t) o] = L[(size_t) i]; ch[1][(size_t) o] = R[(size_t) i]; }
        }
    }
    g.resetAll();
    if (sr != 48000) e.prepareAll (48000);
    if (e.graph) e.graph->resetAll();
    (void) wasPlaying;

    fs::create_directories (u8path (path).parent_path());
    std::string err;
    if (! writeWav (u8path (path), ch, f1 - f0, sr, bits == 16 ? 16 : bits == 32 ? 32 : 24, err))
        throw CommandError ("render: cannot write " + path + ": " + err);
    double ms = std::chrono::duration<double, std::milli> (std::chrono::steady_clock::now() - t0).count();
    Json o = Json::object();
    o.set ("path", Json::string (path));
    o.set ("seconds", Json::number (std::round ((double) (f1 - f0) / sr * 10) / 10));
    o.set ("render_ms", Json::number (ms));
    return o;
}

// ───────────────────────── 명령 ─────────────────────────
Json Engine::handle (const std::string& method, const Json& p, bool& mutated)
{
    std::lock_guard<std::recursive_mutex> lk (m);
    mutated = ! readOnly().count (method);

    if (mutated && project && method != "edit.undo" && method != "edit.redo" && method != "edit.new" && method != "edit.load")
        pushUndo (method + "|" + p["track"].dump() + "|" + p["device"].dump());

    // ── 기본 ──
    if (method == "ping")
    {
        Json o = Json::object();
        o.set ("ok", Json::boolean (true));
        o.set ("version", Json::string (kVersion));
        o.set ("edit", Json::string (project ? project->path : std::string()));
        return o;
    }
    if (method == "help")
    {
        Json o = Json::object();
        for (auto& kv : helpList()) o.set (kv.first, Json::string (kv.second));
        return o;
    }

    // ── 편집(곡) ──
    if (method == "edit.new")
    {
        stopPlayback();
        auto P = std::make_unique<Project>();
        std::string path = p.str ("path");
        if (path.empty())
        {
            std::string name = p.str ("name", "untitled");
            fs::path d = u8path (root) / "projects" / sanitise (name);
            fs::create_directories (d);
            path = pathToU8 (d / (sanitise (name) + ".edit.json"));
            P->name = name;
        }
        else
        {
            fs::path f = u8path (path);
            if (f.extension() == ".tracktionedit") f.replace_extension (".edit.json");
            if (f.extension() != ".json") f += ".edit.json";
            fs::create_directories (f.parent_path());
            path = pathToU8 (f);
            std::string stem = pathToU8 (f.filename());
            P->name = stem.substr (0, stem.find ('.'));
        }
        P->path = path;
        P->bpm = p.num ("bpm", 120);
        P->timeSig = p.str ("time_sig", "4/4");
        project = std::move (P);
        undoStack.clear(); redoStack.clear();
        setPlayFrame (0);
        positionBeat = 0;
        return describeProject();
    }
    if (method == "edit.load")
    {
        std::string path = p.str ("path");
        if (path.empty()) throw CommandError ("missing 'path'");
        fs::path f = u8path (path);
        if (f.extension() == ".tracktionedit")
        {
            fs::path j = f; j.replace_extension (".edit.json");
            if (! fs::exists (j))
                throw CommandError ("old Tracktion edit file (no longer supported) — rebuild the song from its spec.json: " + path);
            f = j;
        }
        std::string text;
        if (! readFileText (f, text)) throw CommandError ("cannot read " + pathToU8 (f));
        stopPlayback();
        projectFromJson (Json::parse (text), false);
        project->path = pathToU8 (f);
        prepareAll (48000);
        undoStack.clear(); redoStack.clear();
        setPlayFrame (0);
        positionBeat = 0;
        return describeProject();
    }
    if (method == "edit.save")
    {
        auto& P = requireProject();
        std::string path = p.str ("path", P.path);
        fs::path f = u8path (path);
        if (f.extension() == ".tracktionedit") f.replace_extension (".edit.json");
        fs::create_directories (f.parent_path());
        std::string text = projectToJson (true).dump (1);
        FILE* fp = _wfopen (f.wstring().c_str(), L"wb");
        if (! fp) throw CommandError ("cannot write " + pathToU8 (f));
        std::fwrite (text.data(), 1, text.size(), fp);
        std::fclose (fp);
        if (! p.find ("path")) P.path = pathToU8 (f);
        Json o = Json::object();
        o.set ("path", Json::string (pathToU8 (f)));
        return o;
    }
    if (method == "edit.info") return describeProject();
    if (method == "edit.set")
    {
        auto& P = requireProject();
        if (p.find ("bpm")) P.bpm = std::clamp (needNum (p, "bpm"), 20.0, 400.0);
        if (p.find ("time_sig")) P.timeSig = p.str ("time_sig", P.timeSig);
        if (p.find ("master_volume_db")) P.masterVolumeDb = needNum (p, "master_volume_db");
        return describeProject();
    }
    if (method == "edit.undo" || method == "edit.redo")
    {
        requireProject();
        auto& from = method == "edit.undo" ? undoStack : redoStack;
        auto& to = method == "edit.undo" ? redoStack : undoStack;
        if (! from.empty())
        {
            to.push_back (snapshot());
            std::string s = from.back();
            from.pop_back();
            restore (s);
        }
        lastUndoKey.clear();
        return describeProject();
    }

    // ── 트랙 ──
    if (method == "track.add")
    {
        auto& P = requireProject();
        Track t;
        t.name = p.str ("name", "Track " + std::to_string (P.tracks.size() + 1));
        P.tracks.push_back (std::move (t));
        return describeTrack ((int) P.tracks.size() - 1);
    }
    if (method == "track.remove")
    {
        auto& P = requireProject();
        int i = trackIndex (p["track"]);
        P.tracks.erase (P.tracks.begin() + i);
        return describeProject();
    }
    if (method == "track.set")
    {
        int i = trackIndex (p["track"]);
        auto& t = requireProject().tracks[(size_t) i];
        if (p.find ("name")) t.name = p.str ("name", t.name);
        if (p.find ("volume_db")) t.volumeDb = std::clamp (needNum (p, "volume_db"), -100.0, 12.0);
        if (p.find ("pan")) t.pan = std::clamp (needNum (p, "pan"), -1.0, 1.0);
        if (p.find ("mute")) t.mute = p.flag ("mute", t.mute);
        if (p.find ("solo")) t.solo = p.flag ("solo", t.solo);
        return describeTrack (i);
    }
    if (method == "track.arm")
    {
        int i = trackIndex (p["track"]);
        auto& t = requireProject().tracks[(size_t) i];
        t.armed = p.flag ("armed", true);
        t.armInput = p.str ("input");
        // MIDI 입력 열기(아직 안 열렸으면)
        if (t.armed && midiInputs.empty())
        {
            auto list = MidiInput::list();
            for (auto& mi : list)
            {
                if (! t.armInput.empty() && lower (mi.name).find (lower (t.armInput)) == std::string::npos) continue;
                auto in = std::make_unique<MidiInput>();
                std::string err;
                if (in->open (mi.index, [this] (const MidiInMsg& msg) { onMidiIn (msg); }, err)) midiInputs.push_back (std::move (in));
                else if (log) log ("midi input: " + err);
            }
        }
        Json o = describeTrack (i);
        o.set ("armed", Json::boolean (t.armed));
        Json ins = Json::array();
        for (auto& mi : midiInputs) ins.push (Json::string (mi->name()));
        o.set ("inputs", ins);
        return o;
    }

    // ── 디바이스 ──
    if (method == "device.available" || method == "device.scan")
    {
        std::vector<std::string> extra;
        for (auto& d : p["dirs"].a) if (d.isStr()) extra.push_back (d.s);
        auto& list = vstPlugins (*this, method == "device.scan", extra);
        Json o = Json::object();
        Json bi = Json::array();
        for (auto& b : availableBuiltins()) bi.push (b);
        o.set ("built_in", bi);
        Json v = Json::array();
        for (auto& d : list)
        {
            Json x = Json::object();
            x.set ("name", Json::string (d.name));
            x.set ("vendor", Json::string (d.vendor));
            x.set ("instrument", Json::boolean (d.instrument));
            x.set ("category", Json::string (d.category));
            v.push (x);
        }
        o.set ("vst3", v);
        return o;
    }
    if (method == "device.add")
    {
        auto& chain = chainFor (p["track"]);
        std::string err;
        Slot s = makeSlot (p, err);
        if (! err.empty()) throw CommandError (err);
        prepareSlot (s, 48000);
        int idx = (int) chain.size();
        if (p.find ("index")) idx = std::clamp ((int) needNum (p, "index"), 0, (int) chain.size());
        chain.insert (chain.begin() + idx, std::move (s));
        return describeSlot (chain[(size_t) idx], idx);
    }
    if (method == "device.remove")
    {
        auto& chain = chainFor (p["track"]);
        Slot& s = slot (p);
        for (size_t i = 0; i < chain.size(); ++i) if (&chain[i] == &s) { chain.erase (chain.begin() + (long) i); break; }
        return describeProject();
    }
    if (method == "device.params")
    {
        Slot& s = slot (p);
        Json arr = Json::array();
        Json o = Json::object();
        if (s.kind == Slot::Send)
        {
            ParamInfo q; q.id = "send level"; q.name = "Send level"; q.min = -100; q.max = 6; q.value = s.levelDb;
            char b[32]; std::snprintf (b, sizeof b, "%+.2f dB", s.levelDb); q.text = b;
            arr.push (paramJson (q, 0, true));
            o.set ("device", Json::string ("Aux Send #" + std::to_string (s.bus + 1)));
            o.set ("params", arr);
            return o;
        }
        o.set ("device", Json::string (s.dev ? s.dev->name() : std::string ("Aux Return")));
        if (s.dev)
        {
            std::string filter = lower (p.str ("filter"));
            auto ps = s.dev->params();
            for (size_t i = 0; i < ps.size(); ++i)
            {
                if (! filter.empty() && lower (ps[i].name).find (filter) == std::string::npos && lower (ps[i].id).find (filter) == std::string::npos) continue;
                arr.push (paramJson (ps[i], (int) i, true));
            }
        }
        o.set ("params", arr);
        return o;
    }
    if (method == "device.set")
    {
        Slot& s = slot (p);
        Json changed = Json::array();
        if (p.find ("enabled"))
        {
            s.enabled = p.flag ("enabled", true);
            if (s.dev) s.dev->enabled = s.enabled;
        }
        for (auto& kv : p["params"].o)
        {
            if (s.kind == Slot::Send && (lower (kv.first).find ("level") != std::string::npos))
            {
                if (kv.second.isNum()) s.levelDb = kv.second.n;
                continue;
            }
            if (! s.dev) throw CommandError ("device has no parameters");
            double v = kv.second.isNum() ? kv.second.n : (kv.second.type == Json::Bool && kv.second.b ? 1.0 : 0.0);
            bool ok = kv.second.isStr() ? s.dev->setParamText (kv.first, kv.second.s) : s.dev->setParam (kv.first, v);
            if (! ok) throw CommandError ("no parameter '" + kv.first + "' on " + s.dev->name() + " (see device.params)");
            auto ps = s.dev->params();
            for (size_t i = 0; i < ps.size(); ++i)
                if (lower (ps[i].id) == lower (kv.first) || lower (ps[i].name) == lower (kv.first)) { changed.push (paramJson (ps[i], (int) i, false)); break; }
        }
        Json o = Json::object();
        o.set ("device", Json::string (s.dev ? s.dev->name() : std::string ("send")));
        o.set ("changed", changed);
        return o;
    }
    if (method == "device.show")
    {
        Slot& s = slot (p);
        if (! s.dev || ! s.dev->showEditor()) throw CommandError ("this device has no window");
        Json o = Json::object();
        o.set ("shown", Json::string (s.dev->name()));
        return o;
    }
    if (method == "device.preset_save" || method == "device.preset_load")
    {
        Slot& s = slot (p);
        if (! s.dev) throw CommandError ("device has no state");
        fs::path f;
        if (p.find ("path")) f = u8path (p.str ("path"));
        else f = u8path (root) / "sounds" / "presets" / sanitise (s.dev->name()) / (sanitise (p.str ("name")) + ".json");
        if (method == "device.preset_save")
        {
            fs::create_directories (f.parent_path());
            Json j = Json::object();
            j.set ("format", Json::string ("musicoma-preset"));
            j.set ("device", Json::string (s.dev->name()));
            j.set ("state", s.dev->getState());
            std::string text = j.dump (1);
            FILE* fp = _wfopen (f.wstring().c_str(), L"wb");
            if (! fp) throw CommandError ("cannot write " + pathToU8 (f));
            std::fwrite (text.data(), 1, text.size(), fp);
            std::fclose (fp);
            Json o = Json::object();
            o.set ("path", Json::string (pathToU8 (f)));
            return o;
        }
        if (f.extension() == ".xml") f.replace_extension (".json");     // 옛 엔진 프리셋 이름으로 불러도
        std::string text;
        if (! readFileText (f, text)) throw CommandError ("preset not found: " + pathToU8 (f));
        Json j = Json::parse (text);
        s.dev->setState (j["state"]);
        int idx = 0;
        auto& chain = chainFor (p["track"]);
        for (size_t i = 0; i < chain.size(); ++i) if (&chain[i] == &s) idx = (int) i;
        return describeSlot (s, idx);
    }
    if (method == "device.load_file")
    {
        Slot& s = slot (p);
        if (! s.dev) throw CommandError ("device cannot load files");
        std::string err;
        if (! s.dev->loadFile (p.str ("path"), err)) throw CommandError (err);
        Json o = Json::object();
        o.set ("device", Json::string (s.dev->name()));
        o.set ("loaded", Json::string (pathToU8 (u8path (p.str ("path")).stem())));
        o.set ("program", Json::string (s.dev->currentProgramName()));
        return o;
    }
    if (method == "device.programs")
    {
        Slot& s = slot (p);
        Json o = Json::object();
        Json arr = Json::array();
        int cur = 0;
        if (s.dev)
        {
            auto pr = s.dev->programs();
            std::string cn = s.dev->currentProgramName();
            for (size_t i = 0; i < pr.size(); ++i) { arr.push (Json::string (std::to_string (i) + ": " + pr[i])); if (pr[i] == cn) cur = (int) i; }
        }
        o.set ("current", Json::number (cur));
        o.set ("programs", arr);
        return o;
    }
    if (method == "device.program")
    {
        Slot& s = slot (p);
        if (! s.dev) throw CommandError ("no programs");
        auto pr = s.dev->programs();
        int idx = -1;
        if (p["program"].isNum()) idx = (int) p["program"].n;
        else for (size_t i = 0; i < pr.size(); ++i) if (lower (pr[i]).find (lower (p.str ("program"))) != std::string::npos) { idx = (int) i; break; }
        if (idx < 0 || ! s.dev->setProgram (idx)) throw CommandError ("no such program");
        Json o = Json::object();
        o.set ("program", Json::string (idx < (int) pr.size() ? pr[(size_t) idx] : std::string()));
        return o;
    }

    // ── 클립 ──
    auto readNotes = [] (const Json& arr, std::vector<Note>& out)
    {
        if (! arr.isArr()) throw CommandError ("notes must be an array");
        for (auto& n : arr.a)
        {
            Note x;
            x.pitch = std::clamp ((int) needNum (n, "pitch"), 0, 127);
            x.start = needNum (n, "start");
            x.length = needNum (n, "length");
            x.velocity = std::clamp ((int) n.num ("velocity", 100), 1, 127);
            if (x.length <= 0) throw CommandError ("note length must be > 0");
            out.push_back (x);
        }
    };
    if (method == "clip.add_midi")
    {
        auto& t = track (p["track"]);
        Clip c;
        c.midi = true;
        c.name = p.str ("name", "MIDI");
        c.start = p.num ("start", 0);
        c.length = needNum (p, "length");
        readNotes (p["notes"], c.notes);
        for (auto& x : p["cc"].a) c.cc.push_back ({ (int) x.num ("cc", 0), x.num ("beat", 0), (int) x.num ("value", 0) });
        for (auto& x : p["bend"].a) c.bend.push_back ({ x.num ("beat", 0), x.num ("value", 0) });
        t.clips.push_back (std::move (c));
        Json o = Json::object();
        o.set ("clip", Json::number ((double) t.clips.size() - 1));
        o.set ("notes", Json::number ((double) t.clips.back().notes.size()));
        return o;
    }
    if (method == "clip.list")
    {
        auto& t = track (p["track"]);
        Json arr = Json::array();
        for (size_t i = 0; i < t.clips.size(); ++i) arr.push (describeClip (t.clips[i], (int) i));
        return arr;
    }
    if (method == "clip.notes")
    {
        auto& c = clip (p);
        Json arr = Json::array();
        for (auto& n : c.notes)
        {
            Json o = Json::object();
            o.set ("pitch", Json::number (n.pitch)); o.set ("start", Json::number (n.start));
            o.set ("length", Json::number (n.length)); o.set ("velocity", Json::number (n.velocity));
            arr.push (o);
        }
        return arr;
    }
    if (method == "clip.controllers")
    {
        auto& c = clip (p);
        Json o = Json::object();
        Json cc = Json::array(), bd = Json::array();
        for (auto& x : c.cc) { Json q = Json::object(); q.set ("beat", Json::number (x.beat)); q.set ("cc", Json::number (x.cc)); q.set ("value", Json::number (x.value)); cc.push (q); }
        for (auto& x : c.bend) { Json q = Json::object(); q.set ("beat", Json::number (x.beat)); q.set ("value", Json::number (x.value)); bd.push (q); }
        o.set ("cc", cc); o.set ("bend", bd);
        return o;
    }
    if (method == "clip.set_notes")
    {
        auto& c = clip (p);
        std::vector<Note> ns;
        readNotes (p["notes"], ns);
        if (p.flag ("replace", true)) c.notes = ns;
        else c.notes.insert (c.notes.end(), ns.begin(), ns.end());
        Json o = Json::object();
        o.set ("notes", Json::number ((double) c.notes.size()));
        return o;
    }
    if (method == "clip.remove")
    {
        auto& t = track (p["track"]);
        auto& c = clip (p);
        for (size_t i = 0; i < t.clips.size(); ++i) if (&t.clips[i] == &c) { t.clips.erase (t.clips.begin() + (long) i); break; }
        Json arr = Json::array();
        for (size_t i = 0; i < t.clips.size(); ++i) arr.push (describeClip (t.clips[i], (int) i));
        return arr;
    }
    if (method == "clip.import_midi")
    {
        auto& t = track (p["track"]);
        Clip c;
        std::string err;
        if (! importMidiFile (p.str ("path"), (int) p.num ("midi_track", -1), requireProject().bpm, c, err)) throw CommandError (err);
        c.start = p.num ("start", 0);
        t.clips.push_back (std::move (c));
        Json o = Json::object();
        o.set ("clip", Json::number ((double) t.clips.size() - 1));
        o.set ("notes", Json::number ((double) t.clips.back().notes.size()));
        return o;
    }
    if (method == "clip.add_audio")
    {
        auto& t = track (p["track"]);
        std::string path = p.str ("path");
        if (! fs::exists (u8path (path))) throw CommandError ("file not found: " + path);
        auto data = pool.get (path);
        if (! data) throw CommandError ("not a readable audio file: " + path);
        Clip c;
        c.midi = false;
        c.path = path;
        c.audio = data;
        c.name = p.str ("name", pathToU8 (u8path (path).stem()));
        c.start = p.num ("start", 0);
        c.offsetSec = p.num ("offset", 0);
        c.sourceSeconds = (double) data->frames / data->sampleRate;
        double avail = std::max (0.0, c.sourceSeconds - c.offsetSec);
        c.length = p.find ("length") ? needNum (p, "length") : avail * requireProject().bpm / 60.0;
        c.gainDb = p.num ("gain_db", 0);
        c.pan = p.num ("pan", 0);
        c.fadeIn = p.num ("fade_in", 0);
        c.fadeOut = p.num ("fade_out", 0);
        c.reverse = p.flag ("reverse", false);
        t.clips.push_back (std::move (c));
        Json o = Json::object();
        o.set ("clip", Json::number ((double) t.clips.size() - 1));
        o.set ("source_seconds", Json::number (t.clips.back().sourceSeconds));
        o.set ("source_bpm_note", Json::string ("engine plays audio at original speed; prepare tempo/pitch with the crate tools"));
        return o;
    }
    if (method == "clip.set")
    {
        auto& t = track (p["track"]);
        auto& c = clip (p);
        if (p.find ("name")) c.name = p.str ("name", c.name);
        if (p.find ("mute")) c.mute = p.flag ("mute", c.mute);
        if (p.find ("start")) c.start = needNum (p, "start");
        if (p.find ("length")) c.length = std::max (0.001, needNum (p, "length"));
        if (p.find ("offset")) c.offsetSec = needNum (p, "offset");
        if (p.find ("gain_db")) c.gainDb = needNum (p, "gain_db");
        if (p.find ("pan")) c.pan = std::clamp (needNum (p, "pan"), -1.0, 1.0);
        if (p.find ("fade_in")) c.fadeIn = needNum (p, "fade_in");
        if (p.find ("fade_out")) c.fadeOut = needNum (p, "fade_out");
        if (p.find ("reverse")) c.reverse = p.flag ("reverse", c.reverse);
        Json arr = Json::array();
        for (size_t i = 0; i < t.clips.size(); ++i) arr.push (describeClip (t.clips[i], (int) i));
        return arr;
    }
    if (method == "clip.duplicate")
    {
        auto& t = track (p["track"]);
        Clip c = clip (p);
        c.start = p.num ("start", c.end());
        t.clips.push_back (std::move (c));
        Json o = Json::object();
        o.set ("clip", Json::number ((double) t.clips.size() - 1));
        return o;
    }
    if (method == "clip.split")
    {
        auto& t = track (p["track"]);
        int ci = (int) needNum (p, "clip");
        Clip& c = clip (p);
        double at = needNum (p, "at");
        if (at <= c.start || at >= c.end()) throw CommandError ("split point must be inside the clip");
        Clip right = c;
        double cut = at - c.start;
        right.start = at;
        right.length = c.end() - at;
        c.length = cut;
        if (c.midi)
        {
            std::vector<Note> a, b;
            for (auto& n : c.notes)
            {
                if (n.start < cut) { Note x = n; x.length = std::min (x.length, cut - x.start); a.push_back (x); }
                else { Note x = n; x.start -= cut; b.push_back (x); }
            }
            c.notes = a; right.notes = b;
            std::vector<CcEv> ca, cb; for (auto& x : c.cc) (x.beat < cut ? ca : cb).push_back (x.beat < cut ? x : CcEv { x.cc, x.beat - cut, x.value });
            c.cc = ca; right.cc = cb;
            std::vector<BendEv> ba, bb; for (auto& x : c.bend) (x.beat < cut ? ba : bb).push_back (x.beat < cut ? x : BendEv { x.beat - cut, x.value });
            c.bend = ba; right.bend = bb;
        }
        else
            right.offsetSec = c.offsetSec + cut * 60.0 / requireProject().bpm;
        t.clips.insert (t.clips.begin() + ci + 1, std::move (right));
        Json arr = Json::array();
        for (size_t i = 0; i < t.clips.size(); ++i) arr.push (describeClip (t.clips[i], (int) i));
        return arr;
    }

    // ── 오토메이션 ──
    if (method == "automation.set")
    {
        Slot& s = slot (p);
        if (! s.dev) throw CommandError ("device has no parameters");
        std::string want = p.str ("param");
        auto ps = s.dev->params();
        const ParamInfo* found = nullptr;
        for (auto& q : ps) if (lower (q.id) == lower (want) || lower (q.name) == lower (want)) { found = &q; break; }
        if (! found) throw CommandError ("no parameter '" + want + "' (see device.params)");
        auto& pts = s.automation[found->id];
        if (p.flag ("clear", true)) pts.clear();
        for (auto& x : p["points"].a) pts.push_back ({ x.num ("beat", 0), x.num ("value", 0), x.num ("curve", 0) });
        std::sort (pts.begin(), pts.end(), [] (const AutoPoint& a, const AutoPoint& b) { return a.beat < b.beat; });
        Json o = Json::object();
        o.set ("param", Json::string (found->name));
        o.set ("points", Json::number ((double) pts.size()));
        return o;
    }

    // ── 재생 ──
    if (method == "transport.play" || method == "transport.record")
    {
        auto& P = requireProject();
        std::string err;
        if (! startOutput (err)) throw CommandError ("audio output: " + err);
        double from = p.num ("from", playing.load() ? positionBeat.load() : positionBeat.load());
        if (p.find ("from")) { graph->resetAll(); setPlayFrame ((int64_t) std::llround (from * 60.0 / P.bpm * 48000.0)); positionBeat = from; }
        if (p["loop"].isArr() && p["loop"].a.size() == 2)
        {
            loopStart = p["loop"].a[0].n; loopEnd = p["loop"].a[1].n; looping = loopEnd > loopStart;
        }
        else if (p.find ("loop")) looping = false;
        if (method == "transport.record")
        {
            bool any = false;
            for (auto& t : P.tracks) any |= t.armed;
            if (! any) throw CommandError ("no armed track (track.arm first)");
            recStartBeat = positionBeat.load();
            recording = true;
        }
        playing = true;
        return transportState (*this);
    }
    if (method == "transport.stop")
    {
        stopPlayback();
        mutated = true;   // 녹음이 클립이 됐을 수 있음
        return transportState (*this);
    }
    if (method == "transport.state") return transportState (*this);
    if (method == "transport.metronome")
    {
        metronome = p.flag ("enabled", true);
        if (p.find ("volume")) metronomeVolume = (float) std::clamp (needNum (p, "volume"), 0.0, 1.0);
        return transportState (*this);
    }
    if (method == "meters")
    {
        Json o = Json::object();
        Json tr = Json::object();
        if (project)
            for (auto& t : project->tracks)
            {
                auto it = graph->meters.find (t.name);
                Json v = Json::array();
                float a = -100, b = -100;
                if (it != graph->meters.end() && playing.load()) { a = it->second[0]; b = it->second[1]; }
                v.push (Json::number (a)); v.push (Json::number (b));
                tr.set (t.name, v);
            }
        o.set ("tracks", tr);
        Json mm = Json::array();
        mm.push (Json::number (playing.load() ? graph->masterMeter[0] : -100)); mm.push (Json::number (playing.load() ? graph->masterMeter[1] : -100));
        o.set ("master", mm);
        return o;
    }
    if (method == "audio.devices")
    {
        Json o = Json::object();
        Json types = Json::array();
        Json t = Json::object();
        t.set ("type", Json::string ("Windows Audio"));
        Json outs = Json::array();
        for (auto& d : AudioOutput::list()) outs.push (Json::string (d.name));
        t.set ("outputs", outs);
        types.push (t);
        o.set ("types", types);
        o.set ("current", Json::string (output.isOpen() ? output.deviceName() : outputName));
        o.set ("current_type", Json::string ("Windows Audio"));
        o.set ("sample_rate", Json::number (output.isOpen() ? output.sampleRate() : 0));
        o.set ("buffer", Json::number (output.isOpen() ? output.bufferFrames() : outputBuffer));
        o.set ("internal_rate", Json::number (48000));
        return o;
    }
    if (method == "audio.set")
    {
        outputName = p.str ("device", outputName);
        if (p.find ("buffer")) outputBuffer = (int) needNum (p, "buffer");
        bool was = playing.load();
        playing = false;
        output.close();
        stopNullClock();
        std::string err;
        if (! startOutput (err)) throw CommandError ("audio output: " + err);
        playing = was;
        return handle ("audio.devices", Json::object(), mutated);
    }
    if (method == "inputs.list")
    {
        Json o = Json::object();
        Json mi = Json::array();
        for (auto& d : MidiInput::list())
        {
            Json x = Json::object();
            x.set ("name", Json::string (d.name));
            bool open = false;
            for (auto& in : midiInputs) if (in->name() == d.name) open = true;
            x.set ("enabled", Json::boolean (open));
            mi.push (x);
        }
        o.set ("midi", mi);
        o.set ("audio", Json::array());
        return o;
    }
    if (method == "midi.inject")
    {
        // 가상 건반 / 시험용: 실제 MIDI 입력과 똑같은 길(모니터 + 녹음)로 메시지를 넣는다. messages: [[status, data1, data2], …]
        int count = 0;
        for (auto& m : p["messages"].a)
            if (m.a.size() >= 2)
            {
                MidiInMsg msg;
                msg.status = (uint8_t) m.a[0].n; msg.data1 = (uint8_t) m.a[1].n; msg.data2 = m.a.size() > 2 ? (uint8_t) m.a[2].n : 0;
                onMidiIn (msg);
                ++count;
            }
        Json o = Json::object();
        o.set ("sent", Json::number (count));
        return o;
    }
    if (method == "render") return doRender (*this, p);

    throw CommandError ("unknown method: " + method + " (see 'help')");
}

} // namespace mc
