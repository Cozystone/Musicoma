#include "SfzPlugin.h"

const char* SfzPlugin::xmlTypeName = "musicomaSfz";

//==============================================================================
// sfizz.dll 을 실행 중에 불러온다 (import 라이브러리 없이).
namespace
{
    struct SfizzApi
    {
        using CreateFn      = sfizz_synth_t* (*)();
        using FreeFn        = void (*) (sfizz_synth_t*);
        using LoadFn        = bool (*) (sfizz_synth_t*, const char*);
        using IntFn         = void (*) (sfizz_synth_t*, int);
        using FloatFn       = void (*) (sfizz_synth_t*, float);
        using NoteFn        = void (*) (sfizz_synth_t*, int, int, int);
        using HdNoteFn      = void (*) (sfizz_synth_t*, int, int, float);
        using PitchFn       = void (*) (sfizz_synth_t*, int, int);
        using RenderFn      = void (*) (sfizz_synth_t*, float**, int, int);
        using VoidFn        = void (*) (sfizz_synth_t*);
        using RegionsFn     = int (*) (sfizz_synth_t*);

        CreateFn create = nullptr;
        FreeFn free = nullptr;
        LoadFn loadFile = nullptr;
        IntFn setBlock = nullptr;
        FloatFn setRate = nullptr;
        FloatFn setVolume = nullptr;
        HdNoteFn noteOn = nullptr;
        NoteFn noteOff = nullptr;
        NoteFn cc = nullptr;
        PitchFn pitchWheel = nullptr;
        RenderFn render = nullptr;
        VoidFn allSoundOff = nullptr;
        VoidFn freewheelOn = nullptr;
        VoidFn freewheelOff = nullptr;
        RegionsFn numRegions = nullptr;

        bool ok = false;

        SfizzApi()
        {
            auto exeDir = juce::File::getSpecialLocation (juce::File::currentExecutableFile).getParentDirectory();

            for (auto f : { exeDir.getChildFile ("sfizz.dll"),
                            exeDir.getChildFile ("../../../third_party/sfizz/bin/Release/sfizz.dll"),
                            juce::File ("D:/0.Musicoma/third_party/sfizz/bin/Release/sfizz.dll") })
                if (f.existsAsFile() && lib.open (f.getFullPathName()))
                    break;

            auto get = [this] (auto& fn, const char* name) { fn = reinterpret_cast<std::remove_reference_t<decltype (fn)>> (lib.getFunction (name)); return fn != nullptr; };

            ok = get (create, "sfizz_create_synth")
              && get (free, "sfizz_free")
              && get (loadFile, "sfizz_load_file")
              && get (setBlock, "sfizz_set_samples_per_block")
              && get (setRate, "sfizz_set_sample_rate")
              && get (setVolume, "sfizz_set_volume")
              && get (noteOn, "sfizz_send_hd_note_on")
              && get (noteOff, "sfizz_send_note_off")
              && get (cc, "sfizz_send_cc")
              && get (pitchWheel, "sfizz_send_pitch_wheel")
              && get (render, "sfizz_render_block")
              && get (allSoundOff, "sfizz_all_sound_off")
              && get (freewheelOn, "sfizz_enable_freewheeling")
              && get (freewheelOff, "sfizz_disable_freewheeling")
              && get (numRegions, "sfizz_get_num_regions");
        }

        juce::DynamicLibrary lib;
    };

    SfizzApi& api()
    {
        static SfizzApi a;
        return a;
    }

    const juce::Identifier sfzFileID ("sfzFile");
    const juce::Identifier volumeID ("volume");
}

//==============================================================================
SfzPlugin::SfzPlugin (te::PluginCreationInfo info) : te::Plugin (info)
{
    auto um = getUndoManager();
    sfzFile.referTo (state, sfzFileID, um, {});
    volumeDb.referTo (state, volumeID, um, 0.0f);

    volumeParam = addParam ("volume", "Volume", { -60.0f, 12.0f },
                            [] (float v) { return juce::String (v, 1) + " dB"; },
                            [] (const juce::String& s) { return s.getFloatValue(); });
    volumeParam->attachToCurrentValue (volumeDb);

    if (api().ok)
        synth = api().create();
}

SfzPlugin::~SfzPlugin()
{
    notifyListenersOfDeletion();
    volumeParam->detachFromCurrentValue();

    const juce::ScopedLock sl (synthLock);

    if (synth != nullptr)
        api().free (synth);
}

void SfzPlugin::initialise (const te::PluginInitialisationInfo& info)
{
    const juce::ScopedLock sl (synthLock);
    sampleRate = info.sampleRate;
    blockSize = info.blockSizeSamples;

    if (synth != nullptr)
    {
        api().setRate (synth, (float) sampleRate);
        api().setBlock (synth, juce::jmax (blockSize, 1024));
    }

    if (loadedPath != sfzFile.get())
        loadIntoSynth();
}

void SfzPlugin::deinitialise() {}

void SfzPlugin::reset()
{
    const juce::ScopedLock sl (synthLock);

    if (synth != nullptr)
        api().allSoundOff (synth);
}

void SfzPlugin::restorePluginStateFromValueTree (const juce::ValueTree& v)
{
    te::copyPropertiesToCachedValues (v, sfzFile, volumeDb);

    for (auto p : getAutomatableParameters())
        p->updateFromAttachedValue();

    loadIntoSynth();
}

void SfzPlugin::valueTreePropertyChanged (juce::ValueTree& v, const juce::Identifier& id)
{
    if (v == state && id == sfzFileID)
    {
        sfzFile.forceUpdateOfCachedValue();
        loadIntoSynth();
    }

    te::Plugin::valueTreePropertyChanged (v, id);
}

void SfzPlugin::loadIntoSynth()
{
    const juce::ScopedLock sl (synthLock);

    if (synth == nullptr)
        return;

    auto path = sfzFile.get();

    if (path.isNotEmpty() && juce::File (path).existsAsFile())
    {
        api().setRate (synth, (float) sampleRate);
        api().loadFile (synth, path.toRawUTF8());
    }

    loadedPath = path;
}

juce::Result SfzPlugin::loadSfz (const juce::File& f)
{
    if (! api().ok)
        return juce::Result::fail ("sfizz.dll 을 찾지 못함");

    if (! f.existsAsFile())
        return juce::Result::fail ("파일 없음: " + f.getFullPathName());

    sfzFile = f.getFullPathName();
    loadIntoSynth();

    if (getNumRegions() <= 0)
        return juce::Result::fail ("SFZ 를 읽었지만 리전이 0개: " + f.getFullPathName());

    return juce::Result::ok();
}

int SfzPlugin::getNumRegions() const
{
    auto& self = const_cast<SfzPlugin&> (*this);
    const juce::ScopedLock sl (self.synthLock);
    return synth != nullptr ? api().numRegions (synth) : 0;
}

void SfzPlugin::applyToBuffer (const te::PluginRenderContext& fc)
{
    if (fc.destBuffer == nullptr)
        return;

    te::clearChannels (*fc.destBuffer, 2, -1, fc.bufferStartSample, fc.bufferNumSamples);

    const juce::ScopedTryLock sl (synthLock);

    if (! sl.isLocked() || synth == nullptr)
        return;

    // 오프라인 렌더에서는 샘플을 끝까지 읽고 넘어가야 빠지는 음이 없다.
    if (fc.isRendering != freewheeling)
    {
        freewheeling = fc.isRendering;
        freewheeling ? api().freewheelOn (synth) : api().freewheelOff (synth);
    }

    api().setVolume (synth, volumeParam->getCurrentValue());

    if (auto* midi = fc.bufferForMidiMessages)
    {
        if (midi->isAllNotesOff)
            api().allSoundOff (synth);

        for (auto& m : *midi)
        {
            auto delay = juce::jlimit (0, fc.bufferNumSamples - 1, juce::roundToInt (m.getTimeStamp() * sampleRate));

            if (m.isNoteOn())
                api().noteOn (synth, delay, m.getNoteNumber(), m.getFloatVelocity());
            else if (m.isNoteOff())
                api().noteOff (synth, delay, m.getNoteNumber(), m.getVelocity());
            else if (m.isController())
                api().cc (synth, delay, m.getControllerNumber(), m.getControllerValue());
            else if (m.isPitchWheel())
                api().pitchWheel (synth, delay, m.getPitchWheelValue() - 8192);
            else if (m.isAllNotesOff() || m.isAllSoundOff())
                api().allSoundOff (synth);
        }
    }

    float* chans[2] = { fc.destBuffer->getWritePointer (0, fc.bufferStartSample),
                        fc.destBuffer->getWritePointer (fc.destBuffer->getNumChannels() > 1 ? 1 : 0, fc.bufferStartSample) };

    api().render (synth, chans, 2, fc.bufferNumSamples);
}
