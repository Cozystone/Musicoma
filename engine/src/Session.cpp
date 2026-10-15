#include "Session.h"
#include "SfzPlugin.h"
#include "PluginWindow.h"

using namespace std::literals;

//==============================================================================
namespace
{
    juce::DynamicObject::Ptr obj()  { return new juce::DynamicObject(); }

    juce::var arr (const juce::Array<juce::var>& a)  { return juce::var (a); }

    bool has (const juce::var& p, const char* key)
    {
        return p.isObject() && p.getDynamicObject()->hasProperty (key);
    }

    juce::var get (const juce::var& p, const char* key, const juce::var& fallback = {})
    {
        return has (p, key) ? p[key] : fallback;
    }

    juce::var need (const juce::var& p, const char* key)
    {
        if (! has (p, key))
            throw CommandError ("missing param: "s + key);

        return p[key];
    }

    double num (const juce::var& v, const char* what)
    {
        if (! (v.isDouble() || v.isInt() || v.isInt64() || v.isBool()))
            throw CommandError ("expected number for "s + what);

        return (double) v;
    }

    /** 내장 디바이스 이름 → Tracktion 타입 */
    juce::String builtInTypeFor (const juce::String& n)
    {
        auto s = n.toLowerCase().removeCharacters (" _-");

        if (s == "4osc" || s == "fourosc")     return te::FourOscPlugin::xmlTypeName;
        if (s == "sampler")                     return te::SamplerPlugin::xmlTypeName;
        if (s == "eq" || s == "equaliser" || s == "equalizer") return te::EqualiserPlugin::xmlTypeName;
        if (s == "compressor" || s == "comp")   return te::CompressorPlugin::xmlTypeName;
        if (s == "reverb")                      return te::ReverbPlugin::xmlTypeName;
        if (s == "delay")                       return te::DelayPlugin::xmlTypeName;
        if (s == "chorus")                      return te::ChorusPlugin::xmlTypeName;
        if (s == "phaser")                      return te::PhaserPlugin::xmlTypeName;
        if (s == "lowpass" || s == "filter")    return te::LowPassPlugin::xmlTypeName;
        if (s == "pitchshift")                  return te::PitchShiftPlugin::xmlTypeName;
        if (s == "sfz" || s == "sfzsampler")    return SfzPlugin::xmlTypeName;
        if (s == "send" || s == "auxsend")      return te::AuxSendPlugin::xmlTypeName;
        if (s == "return" || s == "auxreturn")  return te::AuxReturnPlugin::xmlTypeName;
        return {};
    }

    const char* builtInNames[] = { "4osc", "sampler", "sfz", "eq", "compressor", "reverb", "delay",
                                   "chorus", "phaser", "lowpass", "pitchshift", "send", "return" };

    bool isMixerPlugin (te::Plugin* p)
    {
        return dynamic_cast<te::VolumeAndPanPlugin*> (p) != nullptr
            || dynamic_cast<te::LevelMeterPlugin*> (p) != nullptr;
    }

    juce::String sanitiseName (juce::String s)
    {
        s = juce::File::createLegalFileName (s.trim());
        return s.isEmpty() ? "untitled" : s;
    }
}

//==============================================================================
/** 되돌리기 기록에 남지 않는 변경(볼륨·팬·파라미터)을 되돌릴 수 있게 감싼다. */
struct LambdaAction : public juce::UndoableAction
{
    LambdaAction (std::function<void()> d, std::function<void()> u) : doIt (std::move (d)), undoIt (std::move (u)) {}
    bool perform() override { doIt(); return true; }
    bool undo() override    { undoIt(); return true; }
    std::function<void()> doIt, undoIt;
};

//==============================================================================
/** 창 없는 엔진용: 진행 막대 대신 그 자리에서 끝까지 돌리고, 경고는 로그로. */
struct HeadlessUIBehaviour : public ExtendedUIBehaviour
{
    void runTaskWithProgressBar (te::ThreadPoolJobWithProgress& t) override
    {
        while (t.runJob() == juce::ThreadPoolJob::jobNeedsRunningAgain) {}
    }

    void showWarningMessage (const juce::String& message) override
    {
        std::cout << "WARN " << message << std::endl;
        lastWarning = message;
    }

    static inline juce::String lastWarning;
};

//==============================================================================
Session::Session (const juce::File& rootDir) : root (rootDir)
{
    engine = std::make_unique<te::Engine> ("MusicomaEngine",
                                           std::make_unique<HeadlessUIBehaviour>(),
                                           std::make_unique<te::EngineBehaviour>());

    engine->getPluginManager().createBuiltInType<SfzPlugin>();
    loadKnownPlugins();
}

Session::~Session()
{
    if (edit != nullptr)
        edit->getTransport().stop (false, true);

    edit.reset();
    engine.reset();
}

//==============================================================================
juce::var Session::describeMethods()
{
    auto o = obj();
    auto add = [&] (const char* m, const char* d) { o->setProperty (m, d); };

    add ("ping", "-> {ok}");
    add ("help", "this list");
    add ("edit.new", "{name, bpm=120, time_sig='4/4'} create project in projects/<name>/");
    add ("edit.load", "{path}");
    add ("edit.save", "{path?}");
    add ("edit.info", "full summary: tempo, tracks, devices, clips (positions in beats)");
    add ("edit.set", "{bpm?, time_sig?}");
    add ("edit.undo", "");
    add ("edit.redo", "");
    add ("track.add", "{name} -> {track}");
    add ("track.remove", "{track}");
    add ("track.set", "{track, name?, volume_db?, pan(-1..1)?, mute?, solo?}");
    add ("device.available", "built-in + scanned VST3 devices");
    add ("device.scan", "{dirs?} scan VST3 folders (default sounds/plugins/vst3)");
    add ("device.add", "{track|'master', device, index?, sfz?, bus?, level_db?} -> {device}. send/return: put 'return' (bus n) on a bus track, 'send' (bus n, level_db) on source tracks");
    add ("device.remove", "{track, device}");
    add ("device.params", "{track, device, filter?} list parameters with ranges and current values");
    add ("device.set", "{track, device, params:{id|name: value | 'text'}, enabled?}");
    add ("device.show", "{track, device} open the device window for manual control");
    add ("device.preset_save", "{track, device, name}");
    add ("device.preset_load", "{track, device, name|path}");
    add ("device.load_file", "{track, device, path} load a plugin patch file (.fxp / raw state) e.g. Surge XT patches");
    add ("device.programs", "{track, device} list the plugin's built-in programs");
    add ("device.program", "{track, device, program: index|name}");
    add ("clip.add_midi", "{track, start, length, name?, notes:[{pitch,start,length,velocity}], cc?:[{cc,beat,value 0-127}], bend?:[{beat,value -1..1}]} beats relative to clip. cc64=sustain pedal, cc11=expression, cc1=modwheel");
    add ("clip.list", "{track}");
    add ("clip.notes", "{track, clip}");
    add ("clip.controllers", "{track, clip} → cc / bend events");
    add ("clip.set_notes", "{track, clip, notes, replace=true}");
    add ("clip.remove", "{track, clip}");
    add ("clip.import_midi", "{track, path, start=0, midi_track?}");
    add ("clip.add_audio", "{track, path, start=0, offset(sec in file)=0, length(beats)?, gain_db?, pan?, fade_in?, fade_out?, reverse?}");
    add ("clip.set", "{track, clip, name?, mute?, start?, length?, offset?, gain_db?, pan?, fade_in?, fade_out?, reverse?}");
    add ("automation.set", "{track, device, param, points:[{beat, value, curve?}], clear=true}");
    add ("transport.play", "{from?, loop:[startBeat,endBeat]?}");
    add ("transport.stop", "");
    add ("transport.state", "");
    add ("meters", "peak levels (dB) per track [L,R] and master — poll while playing");
    add ("clip.duplicate", "{track, clip, start?} copy a clip (default: right after the original)");
    add ("clip.split", "{track, clip, at (beat)} split a clip in two");
    add ("audio.devices", "list output devices per driver type (Windows Audio, ASIO...) and the current one");
    add ("audio.set", "{device, type?, buffer?} choose the playback output");
    add ("transport.record", "{} start recording on armed tracks (stop with transport.stop — takes become clips)");
    add ("transport.metronome", "{enabled, volume?(0.2..1)} click track");
    add ("inputs.list", "MIDI and audio inputs (keyboards, controllers, interfaces)");
    add ("track.arm", "{track, armed=true, input?(device name; default = first MIDI keyboard)} record-arm a track");
    add ("render", "{path?, start?, end?, tail=2, lufs?, sample_rate=48000, bit_depth=24, tracks?} -> wav");
    return juce::var (o.get());
}

juce::var Session::handle (const juce::String& method, const juce::var& p, bool& mutated)
{
    static const juce::StringArray readOnly { "ping", "help", "edit.info", "edit.save", "device.available",
                                              "device.params", "device.show", "device.preset_save", "device.programs", "clip.list",
                                              "clip.notes", "clip.controllers", "transport.play", "transport.stop", "transport.state",
                                              "render", "device.scan", "audio.devices", "audio.set", "meters",
                                              "transport.record", "inputs.list" };
    mutated = ! readOnly.contains (method);

    if (mutated && edit != nullptr && ! method.startsWith ("edit.undo") && ! method.startsWith ("edit.redo"))
    {
        // 노브·페이더를 끄는 동안 쏟아지는 같은 조작은 되돌리기 한 번으로 묶는다(0.7초 안)
        auto key = method + "|" + get (p, "track", "").toString() + "|" + get (p, "device", "").toString();
        auto now = juce::Time::getMillisecondCounter();

        if (key != lastTxnKey || now - lastTxnTime > 700)
            edit->getUndoManager().beginNewTransaction (method);

        lastTxnKey = key;
        lastTxnTime = now;
    }

    if (method == "ping")
    {
        auto o = obj();
        o->setProperty ("ok", true);
        o->setProperty ("version", "0.1.0");
        o->setProperty ("edit", editFile.getFullPathName());
        return juce::var (o.get());
    }

    if (method == "help")               return describeMethods();
    if (method == "edit.new")           return editNew (p);
    if (method == "edit.load")          return editLoad (p);
    if (method == "edit.save")          return editSave (p);
    if (method == "edit.info")          return editInfo (p);
    if (method == "edit.set")           return editSet (p);
    if (method == "edit.undo")          { requireEdit().getUndoManager().undo(); return editInfo (p); }
    if (method == "edit.redo")          { requireEdit().getUndoManager().redo(); return editInfo (p); }
    if (method == "track.add")          return trackAdd (p);
    if (method == "track.remove")       return trackRemove (p);
    if (method == "track.set")          return trackSet (p);
    if (method == "device.available")   return deviceAvailable (p);
    if (method == "device.scan")        return deviceScan (p);
    if (method == "device.add")         return deviceAdd (p);
    if (method == "device.remove")      return deviceRemove (p);
    if (method == "device.params")      return deviceParams (p);
    if (method == "device.set")         return deviceSet (p);
    if (method == "device.show")        return deviceShow (p);
    if (method == "device.preset_save") return devicePresetSave (p);
    if (method == "device.preset_load") return devicePresetLoad (p);
    if (method == "device.load_file")   return deviceLoadFile (p);
    if (method == "device.programs")    return devicePrograms (p);
    if (method == "device.program")     return deviceProgram (p);
    if (method == "clip.add_midi")      return clipAddMidi (p);
    if (method == "clip.list")          return clipList (p);
    if (method == "clip.notes")         return clipNotes (p);
    if (method == "clip.controllers")   return clipControllers (p);
    if (method == "clip.set_notes")     return clipSetNotes (p);
    if (method == "clip.remove")        return clipRemove (p);
    if (method == "clip.import_midi")   return clipImportMidi (p);
    if (method == "clip.add_audio")     return clipAddAudio (p);
    if (method == "clip.set")           return clipSet (p);
    if (method == "automation.set")     return automationSet (p);
    if (method == "transport.play")     return transportPlay (p);
    if (method == "transport.stop")     return transportStop (p);
    if (method == "transport.state")    return transportState (p);
    if (method == "render")             return render (p);
    if (method == "audio.devices")      return audioDevices (p);
    if (method == "transport.record")   return transportRecord (p);
    if (method == "transport.metronome") return transportMetronome (p);
    if (method == "inputs.list")        return inputsList (p);
    if (method == "track.arm")          return trackArm (p);
    if (method == "meters")             return meters (p);
    if (method == "clip.duplicate")     return clipDuplicate (p);
    if (method == "clip.split")         return clipSplit (p);
    if (method == "audio.set")          return audioSet (p);

    mutated = false;
    throw CommandError ("unknown method: " + method + " (see 'help')");
}

//==============================================================================
te::Edit& Session::requireEdit()
{
    if (edit == nullptr)
        throw CommandError ("no edit open: call edit.new or edit.load first");

    return *edit;
}

te::TimePosition Session::beatsToTime (double beats)
{
    return requireEdit().tempoSequence.toTime (te::BeatPosition::fromBeats (beats));
}

double Session::timeToBeats (te::TimePosition t)
{
    return requireEdit().tempoSequence.toBeats (t).inBeats();
}

void Session::prepareEdit()
{
    edit->getTransport().ensureContextAllocated();
    meterClients.clear();

    // 마스터에도 미터를 하나 둔다(화면의 마스터 레벨용, 디바이스 목록엔 안 보임)
    auto& master = edit->getMasterPluginList();
    if (master.getPluginsOfType<te::LevelMeterPlugin>().isEmpty())
        if (auto lm = edit->getPluginCache().createNewPlugin (te::LevelMeterPlugin::xmlTypeName, {}))
            master.insertPlugin (lm, master.size(), nullptr);
}

juce::var Session::meters (Params)
{
    auto& e = requireEdit();

    auto read = [this] (te::LevelMeterPlugin* lm, const juce::String& key) -> juce::var
    {
        if (lm == nullptr)
            return {};

        auto& client = meterClients[key];

        if (client == nullptr)
        {
            client = std::make_unique<te::LevelMeasurer::Client>();
            lm->measurer.addClient (*client);
            meterOwners[key] = lm;
        }

        juce::Array<juce::var> lr;
        lr.add (client->getAndClearAudioLevel (0).dB);
        lr.add (client->getAndClearAudioLevel (1).dB);
        return lr;
    };

    auto o = obj();
    auto tracks = obj();

    for (auto t : te::getAudioTracks (e))
        tracks->setProperty (t->getName(), read (t->getLevelMeterPlugin(), t->itemID.toString()));

    o->setProperty ("tracks", juce::var (tracks.get()));
    auto ms = e.getMasterPluginList().getPluginsOfType<te::LevelMeterPlugin>();
    o->setProperty ("master", read (ms.isEmpty() ? nullptr : ms.getFirst(), "master"));
    return juce::var (o.get());
}

juce::var Session::clipDuplicate (Params p)
{
    auto& e = requireEdit();
    auto& t = getTrack (need (p, "track"));
    auto& c = getClip (p);
    auto len = c.getPosition().getLength();
    auto start = has (p, "start") ? beatsToTime (num (p["start"], "start")) : c.getPosition().getEnd();

    auto v = c.state.createCopy();
    e.createNewItemID().writeID (v, nullptr);
    auto* nc = t.insertClipWithState (v);

    if (nc == nullptr)
        throw CommandError ("could not duplicate clip");

    nc->setStart (start, false, true);
    nc->setLength (len, false);

    auto o = obj();
    o->setProperty ("clip", t.getClips().indexOf (nc));
    return juce::var (o.get());
}

juce::var Session::clipSplit (Params p)
{
    auto& t = getTrack (need (p, "track"));
    auto& c = getClip (p);
    auto at = beatsToTime (num (need (p, "at"), "at"));

    if (at <= c.getPosition().getStart() || at >= c.getPosition().getEnd())
        throw CommandError ("split point must be inside the clip");

    t.splitClip (c, at);
    return clipList (p);
}

//==============================================================================
juce::var Session::editNew (Params p)
{
    auto name = sanitiseName (get (p, "name", "untitled").toString());
    auto dir = root.getChildFile ("projects").getChildFile (name);
    dir.createDirectory();
    auto f = dir.getChildFile (name + ".tracktionedit");

    if (edit != nullptr)
        edit->getTransport().stop (false, true);

    edit.reset();
    edit = te::createEmptyEdit (*engine, f);
    editFile = f;

    for (auto t : te::getAudioTracks (*edit))
        edit->deleteTrack (t);

    edit->tempoSequence.getTempo (0)->setBpm (num (get (p, "bpm", 120.0), "bpm"));
    edit->tempoSequence.getTimeSig (0)->setStringTimeSig (get (p, "time_sig", "4/4").toString());
    prepareEdit();
    edit->getUndoManager().clearUndoHistory();
    te::EditFileOperations (*edit).writeToFile (editFile, false);
    return editInfo ({});
}

juce::var Session::editLoad (Params p)
{
    juce::File f (need (p, "path").toString());

    if (! f.existsAsFile())
        throw CommandError ("file not found: " + f.getFullPathName());

    if (edit != nullptr)
        edit->getTransport().stop (false, true);

    edit.reset();
    edit = te::loadEditFromFile (*engine, f);
    editFile = f;
    prepareEdit();
    return editInfo ({});
}

juce::var Session::editSave (Params p)
{
    auto& e = requireEdit();
    auto f = has (p, "path") ? juce::File (p["path"].toString()) : editFile;
    f.getParentDirectory().createDirectory();

    if (! te::EditFileOperations (e).writeToFile (f, false))
        throw CommandError ("save failed: " + f.getFullPathName());

    editFile = f;
    auto o = obj();
    o->setProperty ("path", f.getFullPathName());
    return juce::var (o.get());
}

juce::var Session::editSet (Params p)
{
    auto& e = requireEdit();

    if (has (p, "bpm"))
        e.tempoSequence.getTempo (0)->setBpm (num (p["bpm"], "bpm"));

    if (has (p, "time_sig"))
        e.tempoSequence.getTimeSig (0)->setStringTimeSig (p["time_sig"].toString());

    return editInfo ({});
}

juce::var Session::editInfo (Params)
{
    auto& e = requireEdit();
    auto o = obj();
    o->setProperty ("path", editFile.getFullPathName());
    o->setProperty ("bpm", e.tempoSequence.getTempo (0)->getBpm());
    o->setProperty ("time_sig", e.tempoSequence.getTimeSig (0)->getStringTimeSig());
    o->setProperty ("length_beats", timeToBeats (te::TimePosition() + e.getLength()));

    juce::Array<juce::var> tracks;
    int i = 0;

    for (auto t : te::getAudioTracks (e))
        tracks.add (describeTrack (*t, i++));

    o->setProperty ("tracks", arr (tracks));

    auto m = obj();
    juce::Array<juce::var> md;
    int di = 0;

    for (auto pl : e.getMasterPluginList().getPlugins())
        if (! isMixerPlugin (pl))
            md.add (describeDevice (*pl, di++));

    m->setProperty ("devices", arr (md));

    if (auto mv = e.getMasterVolumePlugin())
        m->setProperty ("volume_db", mv->getVolumeDb());

    o->setProperty ("master", juce::var (m.get()));
    return juce::var (o.get());
}

//==============================================================================
te::AudioTrack& Session::getTrack (const juce::var& ref)
{
    auto tracks = te::getAudioTracks (requireEdit());

    if (ref.isInt() || ref.isInt64() || ref.isDouble())
    {
        auto idx = (int) ref;

        if (! juce::isPositiveAndBelow (idx, tracks.size()))
            throw CommandError ("track index out of range: " + juce::String (idx));

        return *tracks[idx];
    }

    auto name = ref.toString();

    for (auto t : tracks)
        if (t->getName().equalsIgnoreCase (name))
            return *t;

    throw CommandError ("no track named '" + name + "'");
}

te::PluginList& Session::getPluginListFor (const juce::var& ref, te::AudioTrack** trackOut)
{
    if (ref.toString().equalsIgnoreCase ("master"))
        return requireEdit().getMasterPluginList();

    auto& t = getTrack (ref);

    if (trackOut != nullptr)
        *trackOut = &t;

    return t.pluginList;
}

juce::Array<te::Plugin*> Session::getDevices (const juce::var& ref)
{
    juce::Array<te::Plugin*> result;

    for (auto pl : getPluginListFor (ref).getPlugins())
        if (! isMixerPlugin (pl))
            result.add (pl);

    return result;
}

te::Plugin& Session::getDevice (Params p)
{
    auto devices = getDevices (need (p, "track"));
    auto ref = need (p, "device");

    if (ref.isInt() || ref.isInt64() || ref.isDouble())
    {
        auto idx = (int) ref;

        if (! juce::isPositiveAndBelow (idx, devices.size()))
            throw CommandError ("device index out of range: " + juce::String (idx));

        return *devices[idx];
    }

    for (auto d : devices)
        if (d->getName().containsIgnoreCase (ref.toString()))
            return *d;

    throw CommandError ("no device matching '" + ref.toString() + "'");
}

te::AutomatableParameter& Session::getParam (te::Plugin& plugin, const juce::var& ref)
{
    auto params = plugin.getAutomatableParameters();

    if (ref.isInt() || ref.isInt64())
    {
        auto idx = (int) ref;

        if (! juce::isPositiveAndBelow (idx, params.size()))
            throw CommandError ("param index out of range: " + juce::String (idx));

        return *params[idx];
    }

    auto s = ref.toString();

    for (auto pr : params)
        if (pr->paramID == s)
            return *pr;

    for (auto pr : params)
        if (pr->getParameterName().equalsIgnoreCase (s))
            return *pr;

    for (auto pr : params)
        if (pr->getParameterName().containsIgnoreCase (s))
            return *pr;

    throw CommandError ("no param '" + s + "' on " + plugin.getName());
}

te::Clip& Session::getClip (Params p)
{
    auto& t = getTrack (need (p, "track"));
    auto clips = t.getClips();
    auto ref = need (p, "clip");

    if (ref.isInt() || ref.isInt64() || ref.isDouble())
    {
        auto idx = (int) ref;

        if (! juce::isPositiveAndBelow (idx, clips.size()))
            throw CommandError ("clip index out of range: " + juce::String (idx));

        return *clips[idx];
    }

    for (auto c : clips)
        if (c->getName().equalsIgnoreCase (ref.toString()))
            return *c;

    throw CommandError ("no clip named '" + ref.toString() + "'");
}

juce::var Session::describeParam (te::AutomatableParameter& pr)
{
    auto o = obj();
    o->setProperty ("id", pr.paramID);
    o->setProperty ("name", pr.getParameterName());
    o->setProperty ("value", pr.getCurrentValue());
    o->setProperty ("text", pr.getCurrentValueAsString());
    o->setProperty ("min", pr.getValueRange().getStart());
    o->setProperty ("max", pr.getValueRange().getEnd());

    if (pr.hasAutomationPoints())
        o->setProperty ("automated", true);

    return juce::var (o.get());
}

juce::var Session::describeDevice (te::Plugin& pl, int index)
{
    auto o = obj();
    o->setProperty ("device", index);
    o->setProperty ("name", pl.getName());
    o->setProperty ("type", pl.getPluginType());
    o->setProperty ("enabled", pl.isEnabled());
    o->setProperty ("num_params", pl.getAutomatableParameters().size());

    if (auto sfz = dynamic_cast<SfzPlugin*> (&pl))
    {
        o->setProperty ("sfz", sfz->getSfzPath());
        o->setProperty ("regions", sfz->getNumRegions());
    }

    return juce::var (o.get());
}

juce::var Session::describeTrack (te::AudioTrack& t, int index)
{
    auto o = obj();
    o->setProperty ("track", index);
    o->setProperty ("name", t.getName());

    if (auto v = t.getVolumePlugin())
    {
        o->setProperty ("volume_db", v->getVolumeDb());
        o->setProperty ("pan", v->getPan());
    }

    o->setProperty ("mute", t.isMuted (false));
    o->setProperty ("solo", t.isSolo (false));

    juce::Array<juce::var> devices;
    int di = 0;

    for (auto pl : t.pluginList.getPlugins())
        if (! isMixerPlugin (pl))
            devices.add (describeDevice (*pl, di++));

    o->setProperty ("devices", arr (devices));

    juce::Array<juce::var> clips;
    int ci = 0;

    for (auto c : t.getClips())
    {
        auto co = obj();
        co->setProperty ("clip", ci++);
        co->setProperty ("name", c->getName());
        co->setProperty ("start", timeToBeats (c->getPosition().getStart()));
        co->setProperty ("end", timeToBeats (c->getPosition().getEnd()));

        if (auto mc = dynamic_cast<te::MidiClip*> (c))
        {
            co->setProperty ("type", "midi");
            co->setProperty ("notes", mc->getSequence().getNotes().size());
        }
        else
        {
            co->setProperty ("type", "audio");
            if (auto* ac = dynamic_cast<te::AudioClipBase*> (c))
                co->setProperty ("gain_db", ac->getGainDB());
        }

        clips.add (juce::var (co.get()));
    }

    o->setProperty ("clips", arr (clips));
    return juce::var (o.get());
}

//==============================================================================
juce::var Session::trackAdd (Params p)
{
    auto& e = requireEdit();
    auto tracks = te::getAudioTracks (e);
    auto t = e.insertNewAudioTrack (te::TrackInsertPoint (nullptr, tracks.getLast()), nullptr);

    if (t == nullptr)
        throw CommandError ("could not add track");

    t->setName (get (p, "name", "Track " + juce::String (tracks.size() + 1)).toString());
    return describeTrack (*t, tracks.size());
}

juce::var Session::trackRemove (Params p)
{
    auto& t = getTrack (need (p, "track"));
    requireEdit().deleteTrack (&t);
    return editInfo ({});
}

juce::var Session::trackSet (Params p)
{
    auto& t = getTrack (need (p, "track"));

    if (has (p, "name"))      t.setName (p["name"].toString());
    if (has (p, "mute"))      t.setMute ((bool) p["mute"]);
    if (has (p, "solo"))      t.setSolo ((bool) p["solo"]);

    if (auto v = t.getVolumePlugin())
    {
        auto& um = requireEdit().getUndoManager();
        te::VolumeAndPanPlugin::Ptr vp (v);

        if (has (p, "volume_db"))
        {
            auto oldDb = vp->getVolumeDb(), newDb = (float) num (p["volume_db"], "volume_db");
            um.perform (new LambdaAction ([vp, newDb] { vp->setVolumeDb (newDb); }, [vp, oldDb] { vp->setVolumeDb (oldDb); }));
        }

        if (has (p, "pan"))
        {
            auto oldPan = vp->getPan(), newPan = (float) juce::jlimit (-1.0, 1.0, num (p["pan"], "pan"));
            um.perform (new LambdaAction ([vp, newPan] { vp->setPan (newPan); }, [vp, oldPan] { vp->setPan (oldPan); }));
        }
    }

    return describeTrack (t, te::getAudioTracks (requireEdit()).indexOf (&t));
}

//==============================================================================
void Session::loadKnownPlugins()
{
    auto f = root.getChildFile ("engine/known_plugins.xml");

    if (auto xml = juce::parseXML (f))
        engine->getPluginManager().knownPluginList.recreateFromXml (*xml);
}

void Session::saveKnownPlugins()
{
    if (auto xml = engine->getPluginManager().knownPluginList.createXml())
        xml->writeTo (root.getChildFile ("engine/known_plugins.xml"));
}

juce::var Session::deviceScan (Params p)
{
    auto& pm = engine->getPluginManager();
    juce::AudioPluginFormat* vst3 = nullptr;

    for (auto f : pm.pluginFormatManager.getFormats())
        if (f->getName() == "VST3")
            vst3 = f;

    if (vst3 == nullptr)
        throw CommandError ("VST3 hosting not available");

    juce::FileSearchPath path;

    if (has (p, "dirs") && p["dirs"].isArray())
        for (auto& d : *p["dirs"].getArray())
            path.add (juce::File (d.toString()));
    else
        path.add (root.getChildFile ("sounds/plugins/vst3"));

    auto pedal = root.getChildFile ("engine/scan_dead_mans_pedal.txt");
    juce::PluginDirectoryScanner scanner (pm.knownPluginList, *vst3, path, true, pedal, false);

    juce::String name;
    while (scanner.scanNextFile (true, name)) {}

    saveKnownPlugins();

    auto o = obj();
    o->setProperty ("failed", juce::var (scanner.getFailedFiles()));
    o->setProperty ("available", deviceAvailable ({}));
    return juce::var (o.get());
}

juce::var Session::deviceAvailable (Params)
{
    juce::Array<juce::var> builtIn, external;

    for (auto n : builtInNames)
        builtIn.add (n);

    for (auto& d : engine->getPluginManager().knownPluginList.getTypes())
    {
        auto o = obj();
        o->setProperty ("name", d.name);
        o->setProperty ("vendor", d.manufacturerName);
        o->setProperty ("instrument", d.isInstrument);
        o->setProperty ("category", d.category);
        external.add (juce::var (o.get()));
    }

    auto o = obj();
    o->setProperty ("built_in", arr (builtIn));
    o->setProperty ("vst3", arr (external));
    return juce::var (o.get());
}

juce::var Session::deviceAdd (Params p)
{
    auto& e = requireEdit();
    auto trackRef = need (p, "track");
    auto& list = getPluginListFor (trackRef);
    auto name = need (p, "device").toString();

    te::Plugin::Ptr plugin;
    auto type = builtInTypeFor (name);

    if (type.isNotEmpty())
    {
        plugin = e.getPluginCache().createNewPlugin (type, {});
    }
    else
    {
        juce::PluginDescription found;
        bool ok = false;

        for (auto& d : engine->getPluginManager().knownPluginList.getTypes())
            if (d.name.equalsIgnoreCase (name)) { found = d; ok = true; break; }

        if (! ok)
            for (auto& d : engine->getPluginManager().knownPluginList.getTypes())
                if (d.name.containsIgnoreCase (name)) { found = d; ok = true; break; }

        if (! ok)
            throw CommandError ("unknown device '" + name + "' (see device.available, or device.scan)");

        plugin = e.getPluginCache().createNewPlugin (te::ExternalPlugin::xmlTypeName, found);
    }

    if (plugin == nullptr)
        throw CommandError ("could not create device '" + name + "'");

    // 사용자 디바이스는 믹서(볼륨·미터) 앞에 넣는다.
    auto all = list.getPlugins();
    int mixerIndex = all.size();

    for (int i = 0; i < all.size(); ++i)
        if (isMixerPlugin (all[i].get())) { mixerIndex = i; break; }

    auto devices = getDevices (trackRef);
    int pos = mixerIndex;

    if (has (p, "index"))
    {
        auto want = (int) p["index"];

        if (juce::isPositiveAndBelow (want, devices.size()))
            pos = all.indexOf (devices[want]);
    }

    // 센드/리턴: 같은 bus 번호끼리 연결 (리턴 트랙에 return, 보낼 트랙에 send).
    if (dynamic_cast<te::AuxSendPlugin*> (plugin.get()) != nullptr || dynamic_cast<te::AuxReturnPlugin*> (plugin.get()) != nullptr)
        plugin->state.setProperty (te::IDs::busNum, (int) get (p, "bus", 0), nullptr);

    list.insertPlugin (plugin, pos, nullptr);

    if (auto send = dynamic_cast<te::AuxSendPlugin*> (plugin.get()))
        if (has (p, "level_db"))
            send->setGainDb ((float) num (p["level_db"], "level_db"));

    if (auto sfz = dynamic_cast<SfzPlugin*> (plugin.get()))
        if (has (p, "sfz"))
        {
            auto r = sfz->loadSfz (juce::File (p["sfz"].toString()));

            if (r.failed())
                throw CommandError (r.getErrorMessage());
        }

    auto after = getDevices (trackRef);
    return describeDevice (*plugin, after.indexOf (plugin.get()));
}

juce::var Session::deviceRemove (Params p)
{
    auto& d = getDevice (p);
    d.deleteFromParent();
    return editInfo ({});
}

juce::var Session::deviceParams (Params p)
{
    auto& d = getDevice (p);
    auto filter = get (p, "filter", "").toString();
    juce::Array<juce::var> list;
    int i = 0;

    for (auto pr : d.getAutomatableParameters())
    {
        if (filter.isEmpty() || pr->getParameterName().containsIgnoreCase (filter) || pr->paramID.containsIgnoreCase (filter))
        {
            auto v = describeParam (*pr);
            v.getDynamicObject()->setProperty ("index", i);
            list.add (v);
        }

        ++i;
    }

    auto o = obj();
    o->setProperty ("device", d.getName());
    o->setProperty ("params", arr (list));
    return juce::var (o.get());
}

juce::var Session::deviceSet (Params p)
{
    auto& d = getDevice (p);

    if (has (p, "enabled"))
        d.setEnabled ((bool) p["enabled"]);

    if (auto sfz = dynamic_cast<SfzPlugin*> (&d))
        if (has (p, "sfz"))
        {
            auto r = sfz->loadSfz (juce::File (p["sfz"].toString()));

            if (r.failed())
                throw CommandError (r.getErrorMessage());
        }

    juce::Array<juce::var> changed;

    if (has (p, "params"))
    {
        auto* po = p["params"].getDynamicObject();

        if (po == nullptr)
            throw CommandError ("params must be an object {id|name: value}");

        for (auto& kv : po->getProperties())
        {
            auto& pr = getParam (d, kv.name.toString());

            // 내장 컴프레서는 내부 단위가 사람 단위와 다르다: threshold=선형 이득, ratio=1-1/r.
            if (dynamic_cast<te::CompressorPlugin*> (&d) != nullptr && (pr.paramID == "threshold" || pr.paramID == "ratio"))
            {
                auto v = kv.value.isString() ? kv.value.toString().retainCharacters ("-0123456789.").getFloatValue()
                                             : (float) (double) kv.value;
                if (pr.paramID == "threshold")
                    pr.setParameter (juce::Decibels::decibelsToGain (juce::jmin (0.0f, v)), juce::sendNotification);
                else
                    pr.setParameter (juce::jlimit (0.05f, 0.95f, 1.0f / juce::jmax (1.0f, v)), juce::sendNotification);   // 화면 표시 = 1/값

                changed.add (describeParam (pr));
                continue;
            }

            auto newV = kv.value.isString() ? pr.stringToValue (kv.value.toString()) : (float) num (kv.value, "param value");
            auto oldV = pr.getCurrentValue();
            te::AutomatableParameter::Ptr pp (&pr);
            requireEdit().getUndoManager().perform (new LambdaAction (
                [pp, newV] { pp->setParameter (newV, juce::sendNotification); },
                [pp, oldV] { pp->setParameter (oldV, juce::sendNotification); }));

            changed.add (describeParam (pr));
        }
    }

    auto o = obj();
    o->setProperty ("device", d.getName());
    o->setProperty ("changed", arr (changed));
    return juce::var (o.get());
}

juce::var Session::deviceShow (Params p)
{
    auto& d = getDevice (p);
    d.showWindowExplicitly();
    auto o = obj();
    o->setProperty ("shown", d.getName());
    return juce::var (o.get());
}

juce::var Session::devicePresetSave (Params p)
{
    auto& d = getDevice (p);
    d.flushPluginStateToValueTree();

    auto dir = root.getChildFile ("sounds/presets").getChildFile (sanitiseName (d.getName()));
    dir.createDirectory();
    auto f = dir.getChildFile (sanitiseName (need (p, "name").toString()) + ".xml");

    if (auto xml = d.state.createXml())
        xml->writeTo (f);

    auto o = obj();
    o->setProperty ("path", f.getFullPathName());
    return juce::var (o.get());
}

juce::var Session::devicePresetLoad (Params p)
{
    auto& d = getDevice (p);
    juce::File f;

    if (has (p, "path"))
        f = juce::File (p["path"].toString());
    else
        f = root.getChildFile ("sounds/presets").getChildFile (sanitiseName (d.getName()))
                .getChildFile (sanitiseName (need (p, "name").toString()) + ".xml");

    auto xml = juce::parseXML (f);

    if (xml == nullptr)
        throw CommandError ("preset not found: " + f.getFullPathName());

    auto v = juce::ValueTree::fromXml (*xml);

    // 플러그인 정체(type/uid/id)는 그대로 두고 나머지 속성만 덮어쓴다.
    static const juce::Array<juce::Identifier> keep { te::IDs::type, te::IDs::id, te::IDs::uid,
                                                      te::IDs::filename, te::IDs::name, te::IDs::manufacturer };
    for (int i = 0; i < v.getNumProperties(); ++i)
    {
        auto id = v.getPropertyName (i);

        if (! keep.contains (id))
            d.state.setProperty (id, v[id], d.getUndoManager());
    }

    d.restorePluginStateFromValueTree (d.state);
    return describeDevice (d, getDevices (need (p, "track")).indexOf (&d));
}

//==============================================================================
void Session::setNotes (te::MidiClip& clip, const juce::var& notes, bool replace)
{
    auto um = &requireEdit().getUndoManager();
    auto& seq = clip.getSequence();

    if (replace)
        seq.clear (um);

    if (! notes.isArray())
        throw CommandError ("notes must be an array");

    for (auto& n : *notes.getArray())
    {
        auto pitch = (int) num (need (n, "pitch"), "pitch");
        auto start = num (need (n, "start"), "note start");
        auto len   = num (need (n, "length"), "note length");
        auto vel   = (int) num (get (n, "velocity", 100), "velocity");

        if (len <= 0)
            throw CommandError ("note length must be > 0");

        seq.addNote (juce::jlimit (0, 127, pitch), te::BeatPosition::fromBeats (start),
                     te::BeatDuration::fromBeats (len), juce::jlimit (1, 127, vel), 0, um);
    }
}

void Session::setControllers (te::MidiClip& clip, Params p, bool replace)
{
    // 연주 정보: cc=[{cc, beat, value 0..127}] · bend=[{beat, value -1..1}] (beat 는 클립 시작 기준)
    auto um = &requireEdit().getUndoManager();
    auto& seq = clip.getSequence();

    if (replace && (has (p, "cc") || has (p, "bend")))
        seq.removeAllControllers (um);

    if (has (p, "cc") && p["cc"].isArray())
        for (auto& c : *p["cc"].getArray())
            seq.addControllerEvent (te::BeatPosition::fromBeats (num (need (c, "beat"), "beat")),
                                    juce::jlimit (0, 127, (int) num (need (c, "cc"), "cc")),
                                    juce::jlimit (0, 127, (int) num (need (c, "value"), "value")) << 7, um);

    if (has (p, "bend") && p["bend"].isArray())
        for (auto& b : *p["bend"].getArray())
        {
            auto v = juce::jlimit (-1.0, 1.0, num (need (b, "value"), "value"));
            seq.addControllerEvent (te::BeatPosition::fromBeats (num (need (b, "beat"), "beat")),
                                    te::MidiControllerEvent::pitchWheelType,
                                    juce::jlimit (0, 16383, (int) std::round ((v + 1.0) * 8191.5)), um);
        }
}

juce::var Session::clipAddMidi (Params p)
{
    auto& t = getTrack (need (p, "track"));
    auto start = num (need (p, "start"), "start");
    auto length = num (need (p, "length"), "length");

    if (length <= 0)
        throw CommandError ("length must be > 0");

    te::TimeRange range (beatsToTime (start), beatsToTime (start + length));
    auto clip = t.insertMIDIClip (get (p, "name", "MIDI").toString(), range, nullptr);

    if (clip == nullptr)
        throw CommandError ("could not create clip");

    if (has (p, "notes"))
        setNotes (*clip, p["notes"], true);

    setControllers (*clip, p, true);

    auto o = obj();
    o->setProperty ("clip", t.getClips().indexOf (clip.get()));
    o->setProperty ("notes", clip->getSequence().getNotes().size());
    return juce::var (o.get());
}

juce::var Session::clipList (Params p)
{
    auto& t = getTrack (need (p, "track"));
    return describeTrack (t, te::getAudioTracks (requireEdit()).indexOf (&t))["clips"];
}

juce::var Session::clipNotes (Params p)
{
    auto* mc = dynamic_cast<te::MidiClip*> (&getClip (p));

    if (mc == nullptr)
        throw CommandError ("not a MIDI clip");

    juce::Array<juce::var> list;

    for (auto n : mc->getSequence().getNotes())
    {
        auto o = obj();
        o->setProperty ("pitch", n->getNoteNumber());
        o->setProperty ("start", n->getStartBeat().inBeats());
        o->setProperty ("length", n->getLengthBeats().inBeats());
        o->setProperty ("velocity", n->getVelocity());
        list.add (juce::var (o.get()));
    }

    return arr (list);
}

juce::var Session::clipSetNotes (Params p)
{
    auto* mc = dynamic_cast<te::MidiClip*> (&getClip (p));

    if (mc == nullptr)
        throw CommandError ("not a MIDI clip");

    setNotes (*mc, need (p, "notes"), (bool) get (p, "replace", true));
    setControllers (*mc, p, (bool) get (p, "replace", true));
    auto o = obj();
    o->setProperty ("notes", mc->getSequence().getNotes().size());
    return juce::var (o.get());
}

juce::var Session::clipRemove (Params p)
{
    getClip (p).removeFromParent();
    return clipList (p);
}

juce::var Session::clipImportMidi (Params p)
{
    auto& t = getTrack (need (p, "track"));
    juce::File f (need (p, "path").toString());
    juce::FileInputStream in (f);
    juce::MidiFile mf;

    if (! in.openedOk() || ! mf.readFrom (in))
        throw CommandError ("could not read MIDI: " + f.getFullPathName());

    mf.convertTimestampTicksToSeconds();
    juce::MidiMessageSequence seq;
    int which = (int) get (p, "midi_track", -1);

    for (int i = 0; i < mf.getNumTracks(); ++i)
        if (which < 0 || which == i)
            seq.addSequence (*mf.getTrack (i), 0.0);

    seq.updateMatchedPairs();
    auto startBeat = num (get (p, "start", 0.0), "start");
    auto startTime = beatsToTime (startBeat);
    auto len = juce::jmax (seq.getEndTime(), 0.1);
    te::TimeRange range (startTime, startTime + te::TimeDuration::fromSeconds (len));
    auto clip = t.insertMIDIClip (f.getFileNameWithoutExtension(), range, nullptr);

    seq.addTimeToMessages (startTime.inSeconds());
    clip->mergeInMidiSequence (seq, te::MidiList::NoteAutomationType::none);

    auto o = obj();
    o->setProperty ("clip", t.getClips().indexOf (clip.get()));
    o->setProperty ("notes", clip->getSequence().getNotes().size());
    return juce::var (o.get());
}

juce::var Session::clipAddAudio (Params p)
{
    auto& t = getTrack (need (p, "track"));
    juce::File f (need (p, "path").toString());

    if (! f.existsAsFile())
        throw CommandError ("file not found: " + f.getFullPathName());

    te::AudioFile af (*engine, f);

    if (! af.isValid())
        throw CommandError ("not a readable audio file: " + f.getFullPathName());

    auto startBeat = num (get (p, "start", 0.0), "start");
    auto start = beatsToTime (startBeat);
    auto offset = te::TimeDuration::fromSeconds (num (get (p, "offset", 0.0), "offset"));
    auto available = te::TimeDuration::fromSeconds (af.getLength()) - offset;

    // length 는 박자 단위. 없으면 파일 끝까지.
    auto length = has (p, "length") ? beatsToTime (startBeat + num (p["length"], "length")) - start : available;

    te::ClipPosition pos { { start, length }, offset };
    auto clip = t.insertWaveClip (get (p, "name", f.getFileNameWithoutExtension()).toString(), f, pos, false);

    if (clip == nullptr)
        throw CommandError ("could not create audio clip");

    applyAudioClipSettings (*clip, p);

    auto o = obj();
    o->setProperty ("clip", t.getClips().indexOf (clip.get()));
    o->setProperty ("source_seconds", af.getLength());
    o->setProperty ("source_bpm_note", "engine plays audio at original speed; prepare tempo/pitch with the crate tools");
    return juce::var (o.get());
}

void Session::applyAudioClipSettings (te::AudioClipBase& clip, Params p)
{
    // 샘플 가공(배속·피치)은 crate 도구가 파일로 미리 만든다. 여기선 믹스용 손잡이만.
    clip.setTimeStretchMode (te::TimeStretcher::disabled);
    clip.setAutoTempo (false);
    clip.setAutoPitch (false);

    if (has (p, "gain_db"))   clip.setGainDB ((float) num (p["gain_db"], "gain_db"));
    if (has (p, "pan"))       clip.setPan ((float) juce::jlimit (-1.0, 1.0, num (p["pan"], "pan")));
    if (has (p, "fade_in"))   clip.setFadeIn (te::TimeDuration::fromSeconds (num (p["fade_in"], "fade_in")));
    if (has (p, "fade_out"))  clip.setFadeOut (te::TimeDuration::fromSeconds (num (p["fade_out"], "fade_out")));
    if (has (p, "reverse"))   clip.setIsReversed ((bool) p["reverse"]);
}

juce::var Session::clipSet (Params p)
{
    auto& c = getClip (p);

    if (has (p, "name"))  c.setName (p["name"].toString());
    if (has (p, "mute"))  c.setMuted ((bool) p["mute"]);

    if (has (p, "start"))
        c.setStart (beatsToTime (num (p["start"], "start")), false, true);

    if (has (p, "length"))
    {
        auto s = c.getPosition().getStart();
        c.setLength (beatsToTime (timeToBeats (s) + num (p["length"], "length")) - s, false);
    }

    if (auto ac = dynamic_cast<te::AudioClipBase*> (&c))
    {
        if (has (p, "offset"))
            c.setOffset (te::TimeDuration::fromSeconds (num (p["offset"], "offset")));

        applyAudioClipSettings (*ac, p);
    }

    return clipList (p);
}

//==============================================================================
juce::var Session::automationSet (Params p)
{
    auto& d = getDevice (p);
    auto& pr = getParam (d, need (p, "param"));
    auto um = &requireEdit().getUndoManager();
    auto& curve = pr.getCurve();

    if ((bool) get (p, "clear", true))
        curve.clear (um);

    auto pts = need (p, "points");

    if (! pts.isArray())
        throw CommandError ("points must be an array");

    for (auto& pt : *pts.getArray())
    {
        auto v = need (pt, "value");
        float value = v.isString() ? pr.stringToValue (v.toString()) : (float) num (v, "value");
        curve.addPoint (beatsToTime (num (need (pt, "beat"), "beat")), value,
                        (float) num (get (pt, "curve", 0.0), "curve"), um);
    }

    auto o = obj();
    o->setProperty ("param", pr.getParameterName());
    o->setProperty ("points", curve.getNumPoints());
    return juce::var (o.get());
}

juce::var Session::transportPlay (Params p)
{
    auto& tc = requireEdit().getTransport();

    if (has (p, "loop") && p["loop"].isArray() && p["loop"].size() == 2)
    {
        tc.setLoopRange ({ beatsToTime (num (p["loop"][0], "loop start")), beatsToTime (num (p["loop"][1], "loop end")) });
        tc.looping = true;
    }
    else if (has (p, "loop"))
    {
        tc.looping = false;
    }

    if (has (p, "from"))
        tc.setPosition (beatsToTime (num (p["from"], "from")));

    tc.play (false);
    return transportState ({});
}

juce::var Session::transportStop (Params)
{
    requireEdit().getTransport().stop (false, false);
    return transportState ({});
}

juce::var Session::transportState (Params)
{
    auto& tc = requireEdit().getTransport();
    auto o = obj();
    o->setProperty ("playing", tc.isPlaying());
    o->setProperty ("position", timeToBeats (tc.getPosition()));
    o->setProperty ("looping", tc.looping.get());
    o->setProperty ("recording", tc.isRecording());
    o->setProperty ("metronome", requireEdit().clickTrackEnabled.get());
    auto lr = tc.getLoopRange();
    juce::Array<juce::var> loop { timeToBeats (lr.getStart()), timeToBeats (lr.getEnd()) };
    o->setProperty ("loop", loop);

    auto& dm = engine->getDeviceManager().deviceManager;

    if (auto dev = dm.getCurrentAudioDevice())
        o->setProperty ("audio_device", dev->getName() + " (" + dev->getTypeName() + ")");

    return juce::var (o.get());
}

//==============================================================================
juce::var Session::render (Params p)
{
    auto& e = requireEdit();
    e.getTransport().stop (false, true);

    auto start = beatsToTime (num (get (p, "start", 0.0), "start"));
    auto end = has (p, "end") ? beatsToTime (num (p["end"], "end"))
                              : te::TimePosition() + e.getLength();
    auto tail = te::TimeDuration::fromSeconds (num (get (p, "tail", 2.0), "tail"));

    if (end <= start)
        throw CommandError ("nothing to render (edit is empty or end <= start)");

    juce::File out;

    if (has (p, "path"))
        out = juce::File (p["path"].toString());
    else
        out = root.getChildFile ("renders")
                  .getChildFile (editFile.getFileNameWithoutExtension() + "_"
                                 + juce::Time::getCurrentTime().formatted ("%Y%m%d-%H%M%S") + ".wav");

    out.getParentDirectory().createDirectory();

    // 기존 파일 위에 쓰면 헤더가 깨진다 → 먼저 지우고, 잠겨 있으면 새 이름
    for (int k = 2; out.existsAsFile() && ! out.deleteFile(); ++k)
        out = out.getSiblingFile (out.getFileNameWithoutExtension().upToLastOccurrenceOf ("__", false, false)
                                  + "__" + juce::String (k) + out.getFileExtension());

    te::Renderer::Parameters rp (e);
    rp.destFile = out;
    rp.audioFormat = engine->getAudioFileFormatManager().getWavFormat();
    rp.bitDepth = (int) get (p, "bit_depth", 24);
    rp.sampleRateForAudio = num (get (p, "sample_rate", 48000.0), "sample_rate");
    rp.blockSizeForAudio = 512;
    rp.time = { start, end + tail };
    rp.usePlugins = true;
    rp.useMasterPlugins = true;
    rp.canRenderInMono = false;
    rp.realTimeRender = false;

    // 비어 있으면 Renderer 가 아무것도 안 그린다 → 기본은 전체 트랙.
    rp.tracksToDo = te::toBitSet (te::getAllTracks (e));

    if (has (p, "tracks") && p["tracks"].isArray())
    {
        juce::Array<te::Track*> ts;

        for (auto& tr : *p["tracks"].getArray())
            ts.add (&getTrack (tr));

        rp.tracksToDo = te::toBitSet (ts);
    }

    if (has (p, "lufs"))
    {
        rp.shouldNormaliseByLUFS = true;
        rp.normaliseToLevelDb = (float) num (p["lufs"], "lufs");
        rp.limitTruePeak = true;
        rp.truePeakCeilingDb = -1.0f;
    }

    auto t0 = juce::Time::getMillisecondCounterHiRes();
    HeadlessUIBehaviour::lastWarning = {};
    auto result = te::Renderer::renderToFile ("Render", rp);

    if (! result.existsAsFile())
        throw CommandError ("render failed: " + (HeadlessUIBehaviour::lastWarning.isNotEmpty()
                                                     ? HeadlessUIBehaviour::lastWarning : juce::String ("no audio produced")));

    auto o = obj();
    o->setProperty ("path", result.getFullPathName());
    o->setProperty ("seconds", (end + tail - start).inSeconds());
    o->setProperty ("render_ms", juce::Time::getMillisecondCounterHiRes() - t0);
    return juce::var (o.get());
}

//==============================================================================
static juce::AudioPluginInstance& requireInstance (te::Plugin& d)
{
    auto* ext = dynamic_cast<te::ExternalPlugin*> (&d);

    if (ext == nullptr || ext->getAudioPluginInstance() == nullptr)
        throw CommandError (d.getName() + " is not a loaded VST3 plugin");

    return *ext->getAudioPluginInstance();
}

juce::var Session::deviceLoadFile (Params p)
{
    auto& d = getDevice (p);
    auto& inst = requireInstance (d);
    juce::File f (need (p, "path").toString());
    juce::MemoryBlock data;

    if (! f.loadFileAsData (data))
        throw CommandError ("cannot read " + f.getFullPathName());

    // .fxp (CcnK/FPCh 불투명 청크): 60바이트 헤더 뒤가 플러그인 상태.
    auto* b = static_cast<const char*> (data.getData());

    if (data.getSize() > 60 && memcmp (b, "CcnK", 4) == 0 && memcmp (b + 8, "FPCh", 4) == 0)
    {
        auto size = (size_t) juce::ByteOrder::bigEndianInt (b + 56);
        size = juce::jmin (size, data.getSize() - 60);
        inst.setStateInformation (b + 60, (int) size);
    }
    else
    {
        inst.setStateInformation (data.getData(), (int) data.getSize());
    }

    d.flushPluginStateToValueTree();

    auto o = obj();
    o->setProperty ("device", d.getName());
    o->setProperty ("loaded", f.getFileNameWithoutExtension());
    o->setProperty ("program", inst.getProgramName (inst.getCurrentProgram()));
    return juce::var (o.get());
}

juce::var Session::devicePrograms (Params p)
{
    auto& inst = requireInstance (getDevice (p));
    juce::Array<juce::var> list;

    for (int i = 0; i < inst.getNumPrograms(); ++i)
        list.add (juce::String (i) + ": " + inst.getProgramName (i));

    auto o = obj();
    o->setProperty ("current", inst.getCurrentProgram());
    o->setProperty ("programs", arr (list));
    return juce::var (o.get());
}

juce::var Session::deviceProgram (Params p)
{
    auto& d = getDevice (p);
    auto& inst = requireInstance (d);
    auto ref = need (p, "program");
    int idx = -1;

    if (ref.isInt() || ref.isInt64() || ref.isDouble())
        idx = (int) ref;
    else
        for (int i = 0; i < inst.getNumPrograms(); ++i)
            if (inst.getProgramName (i).trim().equalsIgnoreCase (ref.toString().trim())
                || (idx < 0 && inst.getProgramName (i).containsIgnoreCase (ref.toString())))
                idx = i;

    if (! juce::isPositiveAndBelow (idx, inst.getNumPrograms()))
        throw CommandError ("no program '" + ref.toString() + "' (see device.programs)");

    inst.setCurrentProgram (idx);
    d.flushPluginStateToValueTree();

    auto o = obj();
    o->setProperty ("program", juce::String (idx) + ": " + inst.getProgramName (idx));
    return juce::var (o.get());
}

//==============================================================================
juce::var Session::audioDevices (Params)
{
    auto& dm = engine->getDeviceManager().deviceManager;
    juce::Array<juce::var> types;

    for (auto* t : dm.getAvailableDeviceTypes())
    {
        t->scanForDevices();
        auto o = obj();
        o->setProperty ("type", t->getTypeName());
        o->setProperty ("outputs", juce::var (t->getDeviceNames (false)));
        types.add (juce::var (o.get()));
    }

    auto o = obj();
    o->setProperty ("types", arr (types));

    if (auto* dev = dm.getCurrentAudioDevice())
    {
        o->setProperty ("current", dev->getName());
        o->setProperty ("current_type", dev->getTypeName());
        o->setProperty ("sample_rate", dev->getCurrentSampleRate());
        o->setProperty ("buffer", dev->getCurrentBufferSizeSamples());
    }

    return juce::var (o.get());
}

juce::var Session::audioSet (Params p)
{
    auto& dm = engine->getDeviceManager().deviceManager;

    if (has (p, "type"))
        dm.setCurrentAudioDeviceType (p["type"].toString(), true);

    auto setup = dm.getAudioDeviceSetup();
    auto want = need (p, "device").toString();
    juce::String found;

    if (auto* t = dm.getCurrentDeviceTypeObject())
        for (auto& n : t->getDeviceNames (false))
            if (n.equalsIgnoreCase (want) || (found.isEmpty() && n.containsIgnoreCase (want)))
                found = n;

    if (found.isEmpty())
        throw CommandError ("no output device matching '" + want + "' (see audio.devices)");

    setup.outputDeviceName = found;

    if (has (p, "buffer"))
        setup.bufferSize = (int) p["buffer"];

    auto err = dm.setAudioDeviceSetup (setup, true);

    if (err.isNotEmpty())
        throw CommandError (err);

    return audioDevices ({});
}

juce::var Session::clipControllers (Params p)
{
    auto* mc = dynamic_cast<te::MidiClip*> (&getClip (p));

    if (mc == nullptr)
        throw CommandError ("not a MIDI clip");

    juce::Array<juce::var> cc, bend;

    for (auto e : mc->getSequence().getControllerEvents())
    {
        auto o = obj();
        o->setProperty ("beat", e->getBeatPosition().inBeats());

        if (e->getType() == te::MidiControllerEvent::pitchWheelType)
        {
            o->setProperty ("value", e->getControllerValue() / 8191.5 - 1.0);
            bend.add (juce::var (o.get()));
        }
        else if (e->getType() < 128)
        {
            o->setProperty ("cc", e->getType());
            o->setProperty ("value", e->getControllerValue() >> 7);
            cc.add (juce::var (o.get()));
        }
    }

    auto o = obj();
    o->setProperty ("cc", arr (cc));
    o->setProperty ("bend", arr (bend));
    return juce::var (o.get());
}

//==============================================================================
// 녹음 · 메트로놈 · 입력 (Ableton: 메트로놈 버튼, 녹음 버튼, 트랙 암, MIDI 키보드)
juce::var Session::transportRecord (Params)
{
    auto& tc = requireEdit().getTransport();
    tc.record (false, true);
    return transportState ({});
}

juce::var Session::transportMetronome (Params p)
{
    auto& e = requireEdit();
    e.clickTrackEnabled = (bool) get (p, "enabled", ! e.clickTrackEnabled.get());
    if (has (p, "volume"))
        e.clickTrackGain = (float) num (p["volume"], "volume");
    return transportState ({});
}

juce::var Session::inputsList (Params)
{
    auto& dm = engine->getDeviceManager();
    juce::Array<juce::var> midi, wave;
    for (int i = 0; i < dm.getNumMidiInDevices(); ++i)
        if (auto d = dm.getMidiInDevice (i))
        {
            auto o = obj();
            o->setProperty ("name", d->getName());
            o->setProperty ("enabled", d->isEnabled());
            midi.add (juce::var (o.get()));
        }
    for (int i = 0; i < dm.getNumWaveInDevices(); ++i)
        if (auto d = dm.getWaveInDevice (i))
        {
            auto o = obj();
            o->setProperty ("name", d->getName());
            o->setProperty ("enabled", d->isEnabled());
            wave.add (juce::var (o.get()));
        }
    auto o = obj();
    o->setProperty ("midi", midi);
    o->setProperty ("audio", wave);
    return juce::var (o.get());
}

juce::var Session::trackArm (Params p)
{
    auto& e = requireEdit();
    auto& t = getTrack (p["track"]);
    const bool armed = (bool) get (p, "armed", true);
    const auto want = get (p, "input", "").toString();
    juce::String used;

    // 기본 입력: 실제 MIDI 키보드 → 없으면 'All MIDI Ins'(가상, 꽂으면 바로 들어옴)
    te::InputDeviceInstance* pick = nullptr;
    for (int pass = 0; pass < 2 && pick == nullptr; ++pass)
        for (auto* in : e.getAllInputDevices())
        {
            auto& dev = in->getInputDevice();
            auto type = dev.getDeviceType();
            const bool match = want.isNotEmpty() ? dev.getName() == want
                             : pass == 0 ? type == te::InputDevice::physicalMidiDevice
                                         : type == te::InputDevice::virtualMidiDevice;
            if (match) { pick = in; break; }
        }

    for (auto* in : { pick })
    {
        if (in == nullptr)
            continue;
        auto& dev = in->getInputDevice();

        if (armed)
        {
            if (auto r = in->setTarget (t.itemID, true, &e.getUndoManager(), 0); ! r)
                throw CommandError ("arm: " + r.error());
            in->setRecordingEnabled (t.itemID, true);
        }
        else
        {
            in->setRecordingEnabled (t.itemID, false);
        }
        used = dev.getName();
        break;
    }

    if (used.isEmpty())
        throw CommandError (want.isNotEmpty() ? "input not found: " + want : "no MIDI input connected");

    auto o = obj();
    o->setProperty ("track", t.getName());
    o->setProperty ("armed", armed);
    o->setProperty ("input", used);
    return juce::var (o.get());
}
