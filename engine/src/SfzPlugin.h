#pragma once

#include <JuceHeader.h>

namespace te = tracktion;

struct sfizz_synth_t;

/** sfizz(DLL) 를 감싼 내장 SFZ 샘플러.
    악기 파일 경로가 상태(sfzFile)에 들어 있어서 Claude 가 경로만 지정하면 된다. */
class SfzPlugin : public te::Plugin
{
public:
    SfzPlugin (te::PluginCreationInfo);
    ~SfzPlugin() override;

    static const char* getPluginName()  { return "SFZ Sampler"; }
    static const char* xmlTypeName;

    juce::String getName() const override                       { return getPluginName(); }
    juce::String getPluginType() override                       { return xmlTypeName; }
    juce::String getShortName (int) override                    { return "SFZ"; }
    juce::String getSelectableDescription() override            { return getName(); }
    bool isSynth() override                                     { return true; }
    bool takesMidiInput() override                              { return true; }
    bool takesAudioInput() override                             { return false; }
    bool producesAudioWhenNoAudioInput() override               { return true; }
    int getNumOutputChannelsGivenInputs (int) override          { return 2; }
    BusLayout getBusses() const override                        { return BusLayout::singleStereoInOut(); }

    void initialise (const te::PluginInitialisationInfo&) override;
    void deinitialise() override;
    void reset() override;
    void applyToBuffer (const te::PluginRenderContext&) override;
    void restorePluginStateFromValueTree (const juce::ValueTree&) override;

    /** 악기 파일을 불러온다. 실패하면 이유를 돌려준다. */
    juce::Result loadSfz (const juce::File&);
    juce::String getSfzPath() const                             { return sfzFile.get(); }
    int getNumRegions() const;

    juce::CachedValue<juce::String> sfzFile;
    juce::CachedValue<float> volumeDb;
    te::AutomatableParameter::Ptr volumeParam;

private:
    void valueTreePropertyChanged (juce::ValueTree&, const juce::Identifier&) override;
    void loadIntoSynth();

    juce::CriticalSection synthLock;
    sfizz_synth_t* synth = nullptr;
    double sampleRate = 48000.0;
    int blockSize = 512;
    bool freewheeling = false;
    juce::String loadedPath;

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR (SfzPlugin)
};
