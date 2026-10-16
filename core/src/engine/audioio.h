// Musicoma Engine — 실시간 오디오 출력(WASAPI 공유 모드) · MIDI 입력(WinMM). 구현: core/src/engine/io_*.cpp
#pragma once
#include <cstdint>
#include <functional>
#include <memory>
#include <string>
#include <vector>

namespace mc {

struct AudioOutputInfo
{
    std::string type = "Windows Audio";   // 지금은 WASAPI 공유 모드만
    std::string name;                     // 장치 이름(표시명)
    std::string id;                       // 엔드포인트 ID
    bool isDefault = false;
};

/** 출력 콜백: 스테레오 n 프레임을 채운다(오디오 스레드). */
using AudioCallback = std::function<void (float* L, float* R, int n)>;

class AudioOutput
{
public:
    static std::vector<AudioOutputInfo> list();
    AudioOutput();
    ~AudioOutput();
    /** name 이 비면 기본 장치. bufferFrames 는 희망값(장치가 정한 값으로 바뀔 수 있음). */
    bool open (const std::string& name, int bufferFrames, AudioCallback cb, std::string& error);
    void close();
    bool isOpen() const;
    double sampleRate() const;
    int bufferFrames() const;
    std::string deviceName() const;
private:
    struct Impl;
    std::unique_ptr<Impl> impl;
};

struct MidiInputInfo { std::string name; int index = 0; };

/** MIDI 메시지 하나(짧은 메시지만). timeSec = 입력 연 뒤 경과 초 */
struct MidiInMsg { uint8_t status = 0, data1 = 0, data2 = 0; double timeSec = 0; };

class MidiInput
{
public:
    static std::vector<MidiInputInfo> list();
    MidiInput();
    ~MidiInput();
    bool open (int index, std::function<void (const MidiInMsg&)> cb, std::string& error);
    void close();
    bool isOpen() const;
    std::string name() const;
private:
    struct Impl;
    std::unique_ptr<Impl> impl;
};

} // namespace mc
