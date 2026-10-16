// Musicoma Engine — 곡 모델 찾기·설명(응답 모양)·직렬화(편집 파일 · 되돌리기)
#include <algorithm>
#include <cctype>
#include <chrono>
#include "eng_model.h"
#include "eng_graph.h"
#include "vst3host.h"

namespace mc {

std::vector<Vst3Desc>& vstPlugins (Engine& e, bool rescan, const std::vector<std::string>& extraDirs);

int64_t nowMs()
{
    using namespace std::chrono;
    return duration_cast<milliseconds> (steady_clock::now().time_since_epoch()).count();
}

static const char* kB64 = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

std::string base64Encode (const std::vector<uint8_t>& d)
{
    std::string o;
    o.reserve ((d.size() + 2) / 3 * 4);
    size_t i = 0;
    for (; i + 2 < d.size(); i += 3)
    {
        uint32_t v = (d[i] << 16) | (d[i + 1] << 8) | d[i + 2];
        o += kB64[(v >> 18) & 63]; o += kB64[(v >> 12) & 63]; o += kB64[(v >> 6) & 63]; o += kB64[v & 63];
    }
    if (i < d.size())
    {
        uint32_t v = d[i] << 16;
        if (i + 1 < d.size()) v |= d[i + 1] << 8;
        o += kB64[(v >> 18) & 63]; o += kB64[(v >> 12) & 63];
        o += (i + 1 < d.size()) ? kB64[(v >> 6) & 63] : '=';
        o += '=';
    }
    return o;
}

std::vector<uint8_t> base64Decode (const std::string& s)
{
    int T[256];
    std::fill (T, T + 256, -1);
    for (int i = 0; i < 64; ++i) T[(unsigned char) kB64[i]] = i;
    std::vector<uint8_t> o;
    o.reserve (s.size() * 3 / 4);
    uint32_t v = 0;
    int bits = 0;
    for (unsigned char c : s)
    {
        if (T[c] < 0) continue;
        v = (v << 6) | (uint32_t) T[c];
        bits += 6;
        if (bits >= 8) { bits -= 8; o.push_back ((uint8_t) ((v >> bits) & 0xFF)); }
    }
    return o;
}

static std::string lowerS (std::string s) { for (auto& c : s) c = (char) std::tolower ((unsigned char) c); return s; }

// ───────────────────────── 찾기 ─────────────────────────
Project& Engine::requireProject()
{
    if (! project) throw CommandError ("no edit open (edit.new or edit.load first)");
    return *project;
}

int Engine::trackIndex (const Json& ref)
{
    auto& P = requireProject();
    if (ref.isNum())
    {
        int i = (int) ref.n;
        if (i < 0 || i >= (int) P.tracks.size()) throw CommandError ("no track " + std::to_string (i));
        return i;
    }
    if (! ref.isStr()) throw CommandError ("missing 'track'");
    for (size_t i = 0; i < P.tracks.size(); ++i) if (P.tracks[i].name == ref.s) return (int) i;
    for (size_t i = 0; i < P.tracks.size(); ++i) if (lowerS (P.tracks[i].name) == lowerS (ref.s)) return (int) i;
    throw CommandError ("no track named '" + ref.s + "'");
}

Track& Engine::track (const Json& ref) { return requireProject().tracks[(size_t) trackIndex (ref)]; }

std::vector<Slot>& Engine::chainFor (const Json& ref)
{
    if (ref.isStr() && lowerS (ref.s) == "master") return requireProject().master;
    return track (ref).slots;
}

Slot& Engine::slot (const Json& p)
{
    auto& chain = chainFor (p["track"]);
    const Json& d = p["device"];
    if (d.isNum())
    {
        int i = (int) d.n;
        if (i < 0 || i >= (int) chain.size()) throw CommandError ("no device " + std::to_string (i) + " on that track");
        return chain[(size_t) i];
    }
    if (d.isStr())
    {
        for (auto& s : chain)
        {
            std::string nm = s.dev ? s.dev->name() : (s.kind == Slot::Send ? "Aux Send" : "Aux Return");
            if (lowerS (nm) == lowerS (d.s) || lowerS (nm).find (lowerS (d.s)) != std::string::npos) return s;
        }
        throw CommandError ("no device named '" + d.s + "' on that track");
    }
    throw CommandError ("missing 'device'");
}

Clip& Engine::clip (const Json& p)
{
    auto& t = track (p["track"]);
    const Json& c = p["clip"];
    if (! c.isNum()) throw CommandError ("missing 'clip' (index)");
    int i = (int) c.n;
    if (i < 0 || i >= (int) t.clips.size()) throw CommandError ("no clip " + std::to_string (i) + " on track '" + t.name + "'");
    return t.clips[(size_t) i];
}

// ───────────────────────── 설명(응답) ─────────────────────────
Json Engine::describeSlot (Slot& s, int index)
{
    Json o = Json::object();
    o.set ("device", Json::number (index));
    switch (s.kind)
    {
        case Slot::Send:
            o.set ("name", Json::string ("Aux Send #" + std::to_string (s.bus + 1)));
            o.set ("type", Json::string ("auxsend"));
            o.set ("enabled", Json::boolean (s.enabled));
            o.set ("num_params", Json::number (1));
            o.set ("bus", Json::number (s.bus));
            o.set ("level_db", Json::number (s.levelDb));
            return o;
        case Slot::Return:
            o.set ("name", Json::string ("Aux Return #" + std::to_string (s.bus + 1)));
            o.set ("type", Json::string ("auxreturn"));
            o.set ("enabled", Json::boolean (s.enabled));
            o.set ("num_params", Json::number (0));
            o.set ("bus", Json::number (s.bus));
            return o;
        default: break;
    }
    o.set ("name", Json::string (s.dev ? s.dev->name() : "?"));
    o.set ("type", Json::string (s.dev ? s.dev->type() : "?"));
    o.set ("enabled", Json::boolean (s.enabled && (! s.dev || s.dev->enabled)));
    o.set ("num_params", Json::number (s.dev ? (double) s.dev->params().size() : 0));
    if (s.kind == Slot::Sfz)
    {
        o.set ("sfz", Json::string (s.sfz));
        o.set ("regions", Json::number (s.regions));
    }
    return o;
}

Json Engine::describeClip (Clip& c, int index)
{
    Json o = Json::object();
    o.set ("clip", Json::number (index));
    o.set ("name", Json::string (c.name));
    o.set ("start", Json::number (c.start));
    o.set ("end", Json::number (c.end()));
    o.set ("type", Json::string (c.midi ? "midi" : "audio"));
    if (c.midi) o.set ("notes", Json::number ((double) c.notes.size()));
    else
    {
        o.set ("path", Json::string (c.path));
        o.set ("offset", Json::number (c.offsetSec));
        o.set ("gain_db", Json::number (c.gainDb));
        o.set ("pan", Json::number (c.pan));
        o.set ("fade_in", Json::number (c.fadeIn));
        o.set ("fade_out", Json::number (c.fadeOut));
        o.set ("reverse", Json::boolean (c.reverse));
    }
    if (c.mute) o.set ("mute", Json::boolean (true));
    return o;
}

Json Engine::describeTrack (int index)
{
    auto& t = requireProject().tracks[(size_t) index];
    Json o = Json::object();
    o.set ("track", Json::number (index));
    o.set ("name", Json::string (t.name));
    o.set ("volume_db", Json::number (t.volumeDb));
    o.set ("pan", Json::number (t.pan));
    o.set ("mute", Json::boolean (t.mute));
    o.set ("solo", Json::boolean (t.solo));
    if (t.armed) o.set ("armed", Json::boolean (true));
    Json devs = Json::array();
    for (size_t i = 0; i < t.slots.size(); ++i) devs.push (describeSlot (t.slots[i], (int) i));
    o.set ("devices", devs);
    Json clips = Json::array();
    for (size_t i = 0; i < t.clips.size(); ++i) clips.push (describeClip (t.clips[i], (int) i));
    o.set ("clips", clips);
    return o;
}

Json Engine::describeProject()
{
    auto& P = requireProject();
    Json o = Json::object();
    o.set ("path", Json::string (P.path));
    o.set ("bpm", Json::number (P.bpm));
    o.set ("time_sig", Json::string (P.timeSig));
    o.set ("length_beats", Json::number (P.lengthBeats()));
    Json tr = Json::array();
    for (size_t i = 0; i < P.tracks.size(); ++i) tr.push (describeTrack ((int) i));
    o.set ("tracks", tr);
    Json m = Json::object();
    Json devs = Json::array();
    for (size_t i = 0; i < P.master.size(); ++i) devs.push (describeSlot (P.master[i], (int) i));
    m.set ("devices", devs);
    m.set ("volume_db", Json::number (P.masterVolumeDb));
    o.set ("master", m);
    return o;
}

// ───────────────────────── 직렬화 ─────────────────────────
static Json slotToJson (Slot& s, bool withState)
{
    Json o = Json::object();
    o.set ("uid", Json::number ((double) s.uid));
    static const char* kinds[] = { "sfz", "builtin", "vst3", "send", "return" };
    o.set ("kind", Json::string (kinds[s.kind]));
    if (s.kind == Slot::Builtin) o.set ("builtin", Json::string (s.builtin));
    if (s.kind == Slot::Sfz) o.set ("sfz", Json::string (s.sfz));
    if (s.kind == Slot::Vst3)
    {
        Json v = Json::object();
        v.set ("name", Json::string (s.vstName));
        v.set ("path", Json::string (s.vstPath));
        v.set ("cid", Json::string (s.vstCid));
        o.set ("vst3", v);
    }
    if (s.kind == Slot::Send || s.kind == Slot::Return) o.set ("bus", Json::number (s.bus));
    if (s.kind == Slot::Send) o.set ("level_db", Json::number (s.levelDb));
    o.set ("enabled", Json::boolean (s.enabled && (! s.dev || s.dev->enabled)));
    if (withState && s.dev) o.set ("state", s.dev->getState());
    if (! s.automation.empty())
    {
        Json a = Json::object();
        for (auto& kv : s.automation)
        {
            Json pts = Json::array();
            for (auto& p : kv.second)
            {
                Json q = Json::array();
                q.push (Json::number (p.beat)); q.push (Json::number (p.value)); q.push (Json::number (p.curve));
                pts.push (q);
            }
            a.set (kv.first, pts);
        }
        o.set ("automation", a);
    }
    return o;
}

static Json clipToJson (const Clip& c)
{
    Json o = Json::object();
    o.set ("name", Json::string (c.name));
    o.set ("midi", Json::boolean (c.midi));
    o.set ("start", Json::number (c.start));
    o.set ("length", Json::number (c.length));
    if (c.mute) o.set ("mute", Json::boolean (true));
    if (c.midi)
    {
        Json n = Json::array();
        for (auto& x : c.notes)
        {
            Json q = Json::array();
            q.push (Json::number (x.pitch)); q.push (Json::number (x.start)); q.push (Json::number (x.length)); q.push (Json::number (x.velocity));
            n.push (q);
        }
        o.set ("notes", n);
        if (! c.cc.empty())
        {
            Json a = Json::array();
            for (auto& x : c.cc) { Json q = Json::array(); q.push (Json::number (x.cc)); q.push (Json::number (x.beat)); q.push (Json::number (x.value)); a.push (q); }
            o.set ("cc", a);
        }
        if (! c.bend.empty())
        {
            Json a = Json::array();
            for (auto& x : c.bend) { Json q = Json::array(); q.push (Json::number (x.beat)); q.push (Json::number (x.value)); a.push (q); }
            o.set ("bend", a);
        }
    }
    else
    {
        o.set ("path", Json::string (c.path));
        o.set ("offset_sec", Json::number (c.offsetSec));
        o.set ("gain_db", Json::number (c.gainDb));
        o.set ("pan", Json::number (c.pan));
        o.set ("fade_in", Json::number (c.fadeIn));
        o.set ("fade_out", Json::number (c.fadeOut));
        o.set ("reverse", Json::boolean (c.reverse));
        o.set ("source_seconds", Json::number (c.sourceSeconds));
    }
    return o;
}

Json Engine::projectToJson (bool withState)
{
    auto& P = requireProject();
    Json o = Json::object();
    o.set ("format", Json::string ("musicoma-edit"));
    o.set ("version", Json::number (1));
    o.set ("name", Json::string (P.name));
    o.set ("bpm", Json::number (P.bpm));
    o.set ("time_sig", Json::string (P.timeSig));
    o.set ("master_volume_db", Json::number (P.masterVolumeDb));
    Json ms = Json::array();
    for (auto& s : P.master) ms.push (slotToJson (s, withState));
    o.set ("master", ms);
    Json tr = Json::array();
    for (auto& t : P.tracks)
    {
        Json to = Json::object();
        to.set ("name", Json::string (t.name));
        to.set ("volume_db", Json::number (t.volumeDb));
        to.set ("pan", Json::number (t.pan));
        to.set ("mute", Json::boolean (t.mute));
        to.set ("solo", Json::boolean (t.solo));
        Json sl = Json::array();
        for (auto& s : t.slots) sl.push (slotToJson (s, withState));
        to.set ("slots", sl);
        Json cl = Json::array();
        for (auto& c : t.clips) cl.push (clipToJson (c));
        to.set ("clips", cl);
        tr.push (to);
    }
    o.set ("tracks", tr);
    return o;
}

void Engine::projectFromJson (const Json& j, bool reuse)
{
    if (j.str ("format") != "musicoma-edit") throw CommandError ("not a Musicoma edit file");
    // 되돌리기: 같은 uid 디바이스는 인스턴스를 다시 쓴다(VST3 다시 만들기는 느림)
    std::map<uint64_t, std::shared_ptr<Device>> old;
    if (reuse && project)
    {
        for (auto& t : project->tracks) for (auto& s : t.slots) if (s.dev) old[s.uid] = s.dev;
        for (auto& s : project->master) if (s.dev) old[s.uid] = s.dev;
    }
    auto P = std::make_unique<Project>();
    P->name = j.str ("name");
    P->path = project && reuse ? project->path : std::string();
    P->bpm = j.num ("bpm", 120);
    P->timeSig = j.str ("time_sig", "4/4");
    P->masterVolumeDb = j.num ("master_volume_db", -3);

    auto loadSlot = [&] (const Json& so) -> Slot
    {
        Slot s;
        std::string kind = so.str ("kind");
        uint64_t uid = (uint64_t) so.num ("uid", 0);
        auto it = old.find (uid);
        if (uid && it != old.end())
        {
            s.uid = uid;
            s.dev = it->second;
            s.kind = kind == "sfz" ? Slot::Sfz : kind == "vst3" ? Slot::Vst3 : Slot::Builtin;
            s.sfz = so.str ("sfz");
            s.builtin = so.str ("builtin");
            if (const Json* v = so.find ("vst3")) { s.vstName = v->str ("name"); s.vstPath = v->str ("path"); s.vstCid = v->str ("cid"); }
        }
        else
        {
            Json req = Json::object();
            if (kind == "sfz") { req.set ("device", Json::string ("sfz")); req.set ("sfz", Json::string (so.str ("sfz"))); }
            else if (kind == "builtin") req.set ("device", Json::string (so.str ("builtin")));
            else if (kind == "vst3") req.set ("device", Json::string (so["vst3"].str ("name")));
            else if (kind == "send") { req.set ("device", Json::string ("send")); req.set ("bus", Json::number (so.num ("bus", 0))); req.set ("level_db", Json::number (so.num ("level_db", -12))); }
            else if (kind == "return") { req.set ("device", Json::string ("return")); req.set ("bus", Json::number (so.num ("bus", 0))); }
            std::string err;
            s = makeSlot (req, err);
            if (! err.empty())
            {
                if (log) log ("load: " + err + " — slot skipped as pass-through");
                s = Slot();
                s.kind = Slot::Builtin;
                s.builtin = "missing";
            }
            if (uid) { s.uid = uid; nextUid = std::max (nextUid, uid + 1); }
            if (s.dev) prepareSlot (s, liveRate);
        }
        s.bus = (int) so.num ("bus", s.bus);
        s.levelDb = so.num ("level_db", s.levelDb);
        s.enabled = so.flag ("enabled", true);
        if (s.dev)
        {
            s.dev->enabled = s.enabled;
            if (const Json* st = so.find ("state")) s.dev->setState (*st);
            if (const Json* sp = so.find ("state_params"))          // 옛 편집에서 옮긴 플러그인 파라미터 값(convert_edit): 이름으로
            {
                for (auto& kv : sp->o) if (kv.second.isNum()) s.dev->setParam (kv.first, kv.second.n);
                for (auto& q : sp->a) if (q["value"].isNum()) s.dev->setParam (q.str ("name"), q["value"].n);
            }
        }
        if (const Json* a = so.find ("automation"))
            for (auto& kv : a->o)
            {
                std::vector<AutoPoint> pts;
                for (auto& q : kv.second.a)
                    if (q.a.size() >= 2) pts.push_back ({ q.a[0].n, q.a[1].n, q.a.size() > 2 ? q.a[2].n : 0.0 });
                s.automation[kv.first] = pts;
            }
        return s;
    };

    for (auto& so : j["master"].a) P->master.push_back (loadSlot (so));
    for (auto& to : j["tracks"].a)
    {
        Track t;
        t.name = to.str ("name");
        t.volumeDb = to.num ("volume_db", 0);
        t.pan = to.num ("pan", 0);
        t.mute = to.flag ("mute", false);
        t.solo = to.flag ("solo", false);
        for (auto& so : to["slots"].a) t.slots.push_back (loadSlot (so));
        for (auto& co : to["clips"].a)
        {
            Clip c;
            c.name = co.str ("name");
            c.midi = co.flag ("midi", true);
            c.start = co.num ("start", 0);
            c.length = co.num ("length", 4);
            c.mute = co.flag ("mute", false);
            for (auto& q : co["notes"].a)
                if (q.a.size() >= 4) c.notes.push_back ({ (int) q.a[0].n, q.a[1].n, q.a[2].n, (int) q.a[3].n });
            for (auto& q : co["cc"].a)
                if (q.a.size() >= 3) c.cc.push_back ({ (int) q.a[0].n, q.a[1].n, (int) q.a[2].n });
            for (auto& q : co["bend"].a)
                if (q.a.size() >= 2) c.bend.push_back ({ q.a[0].n, q.a[1].n });
            if (! c.midi)
            {
                c.path = co.str ("path");
                c.offsetSec = co.num ("offset_sec", 0);
                c.gainDb = co.num ("gain_db", 0);
                c.pan = co.num ("pan", 0);
                c.fadeIn = co.num ("fade_in", 0);
                c.fadeOut = co.num ("fade_out", 0);
                c.reverse = co.flag ("reverse", false);
                c.sourceSeconds = co.num ("source_seconds", 0);
                c.audio = pool.get (c.path);
                if (c.audio) c.sourceSeconds = (double) c.audio->frames / c.audio->sampleRate;
                else if (log) log ("load: audio file not readable: " + c.path);
            }
            t.clips.push_back (std::move (c));
        }
        P->tracks.push_back (std::move (t));
    }
    project = std::move (P);
}

// ───────────────────────── 되돌리기 ─────────────────────────
std::string Engine::snapshot()
{
    return projectToJson (true).dump();
}

void Engine::restore (const std::string& snap)
{
    auto path = project ? project->path : std::string();
    projectFromJson (Json::parse (snap), true);
    project->path = path;
    if (graph) graph->resetAll();
}

void Engine::pushUndo (const std::string& key)
{
    if (! project) return;
    int64_t t = nowMs();
    if (! key.empty() && key == lastUndoKey && t - lastUndoMs < 700) { lastUndoMs = t; return; }   // 노브를 끄는 동안의 같은 조작은 한 번으로
    lastUndoKey = key;
    lastUndoMs = t;
    undoStack.push_back (snapshot());
    if (undoStack.size() > 100) undoStack.pop_front();
    redoStack.clear();
}

} // namespace mc
