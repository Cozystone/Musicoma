#pragma once

#include <JuceHeader.h>
#include <stdexcept>
#include <map>

namespace te = tracktion;

/** 엔진 상태 하나(=열린 Edit 하나)와 그 위의 명령들.
    Claude(MCP) 와 화면(UI) 이 같은 명령을 쓴다. 메시지 스레드에서만 호출할 것. */
class Session
{
public:
    explicit Session (const juce::File& rootDir);
    ~Session();

    /** 명령 실행. 잘못된 입력은 std::runtime_error. mutated = 상태를 바꿨는지. */
    juce::var handle (const juce::String& method, const juce::var& params, bool& mutated);

    static juce::var describeMethods();

private:
    using Params = const juce::var&;

    // 편집 단위
    juce::var editNew (Params);
    juce::var editLoad (Params);
    juce::var editSave (Params);
    juce::var editInfo (Params);
    juce::var editSet (Params);

    // 트랙
    juce::var trackAdd (Params);
    juce::var trackRemove (Params);
    juce::var trackSet (Params);

    // 디바이스(악기·이펙트)
    juce::var deviceAvailable (Params);
    juce::var deviceScan (Params);
    juce::var deviceAdd (Params);
    juce::var deviceRemove (Params);
    juce::var deviceParams (Params);
    juce::var deviceSet (Params);
    juce::var deviceShow (Params);
    juce::var devicePresetSave (Params);
    juce::var devicePresetLoad (Params);
    juce::var deviceLoadFile (Params);
    juce::var devicePrograms (Params);
    juce::var deviceProgram (Params);

    // 클립
    juce::var clipAddMidi (Params);
    juce::var clipList (Params);
    juce::var clipNotes (Params);
    juce::var clipSetNotes (Params);
    juce::var clipRemove (Params);
    juce::var clipImportMidi (Params);
    juce::var clipAddAudio (Params);
    juce::var clipSet (Params);
    void applyAudioClipSettings (te::AudioClipBase&, Params);

    // 오토메이션 · 재생 · 렌더
    juce::var automationSet (Params);
    juce::var transportPlay (Params);
    juce::var transportStop (Params);
    juce::var transportState (Params);
    juce::var render (Params);
    juce::var audioDevices (Params);
    juce::var meters (Params);
    juce::var clipDuplicate (Params);
    juce::var clipSplit (Params);
    juce::var audioSet (Params);
    juce::var transportRecord (Params);
    juce::var transportMetronome (Params);
    juce::var inputsList (Params);
    juce::var trackArm (Params);

    // 도움
    te::Edit& requireEdit();
    te::AudioTrack& getTrack (const juce::var&);
    te::PluginList& getPluginListFor (const juce::var& trackRef, te::AudioTrack** trackOut = nullptr);
    juce::Array<te::Plugin*> getDevices (const juce::var& trackRef);
    te::Plugin& getDevice (Params);
    te::AutomatableParameter& getParam (te::Plugin&, const juce::var& ref);
    te::Clip& getClip (Params);
    juce::var describeTrack (te::AudioTrack&, int index);
    juce::var describeDevice (te::Plugin&, int index);
    juce::var describeParam (te::AutomatableParameter&);
    void setNotes (te::MidiClip&, const juce::var& notes, bool replace);
    void setControllers (te::MidiClip&, Params, bool replace);
    juce::var clipControllers (Params);

    te::TimePosition beatsToTime (double beats);
    double timeToBeats (te::TimePosition);

    void loadKnownPlugins();
    void saveKnownPlugins();
    void prepareEdit();

    juce::File root;
    std::unique_ptr<te::Engine> engine;
    std::unique_ptr<te::Edit> edit;
    juce::File editFile;
    juce::String lastTxnKey;
    juce::uint32 lastTxnTime = 0;
    std::map<juce::String, std::unique_ptr<te::LevelMeasurer::Client>> meterClients;
    std::map<juce::String, te::LevelMeterPlugin*> meterOwners;
};

struct CommandError : std::runtime_error
{
    explicit CommandError (const juce::String& s) : std::runtime_error (s.toStdString()) {}
};
