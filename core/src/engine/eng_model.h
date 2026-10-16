// Musicoma Engine — 곡 모델(트랙·디바이스·클립·오토메이션)과 엔진 상태. Tracktion·JUCE 없이 우리 프로토콜 그대로.
// 프로토콜 기준: tests/golden/protocol.json (옛 엔진 응답 기록). 편집 파일: projects/<곡>/<곡>.edit.json (우리 형식)
#pragma once
#include <atomic>
#include <cstdint>
#include <deque>
#include <functional>
#include <map>
#include <memory>
#include <mutex>
#include <string>
#include <vector>
#include "device.h"
#include "samplepool.h"
#include "audioio.h"

namespace mc {

struct Note { int pitch = 60; double start = 0, length = 1; int velocity = 100; };
struct CcEv { int cc = 0; double beat = 0; int value = 0; };
struct BendEv { double beat = 0; double value = 0; };

struct Clip
{
    std::string name;
    bool midi = true;
    double start = 0, length = 4;      // 박
    bool mute = false;
    // MIDI (클립 시작 기준 박)
    std::vector<Note> notes;
    std::vector<CcEv> cc;
    std::vector<BendEv> bend;
    // 오디오
    std::string path;
    double offsetSec = 0, gainDb = 0, pan = 0, fadeIn = 0, fadeOut = 0;   // 페이드 = 초
    bool reverse = false;
    double sourceSeconds = 0;
    std::shared_ptr<const AudioData> audio;   // 읽은 파일(풀 공유)

    double end() const { return start + length; }
};

struct AutoPoint { double beat = 0, value = 0, curve = 0; };

/** 체인의 한 칸 */
struct Slot
{
    enum Kind { Sfz, Builtin, Vst3, Send, Return };
    Kind kind = Builtin;
    uint64_t uid = 0;                // 되돌리기에서 같은 인스턴스를 다시 쓰려고
    std::string builtin;             // "eq" …
    std::string sfz;                 // sfz 경로
    std::string vstName, vstPath, vstCid;
    int bus = 0;
    double levelDb = 0;              // send
    bool enabled = true;
    std::shared_ptr<Device> dev;     // send/return 은 없음
    std::map<std::string, std::vector<AutoPoint>> automation;   // 파라미터 id → 점
    int regions = 0;                 // sfz: 리전 수(응답용)
};

struct Track
{
    std::string name;
    double volumeDb = 0, pan = 0;
    bool mute = false, solo = false, armed = false;
    std::string armInput;
    std::vector<Slot> slots;
    std::vector<Clip> clips;
};

struct Project
{
    std::string name;
    std::string path;                // .edit.json
    double bpm = 120;
    std::string timeSig = "4/4";
    std::vector<Track> tracks;
    std::vector<Slot> master;
    double masterVolumeDb = -3.0;    // 옛 엔진 기본(측정: 마스터 -3 dB)
    /** MIDI 맵(Ableton 의 MIDI Map 모드): 컨트롤러 CC → 트랙 디바이스 파라미터. 곡과 함께 저장. */
    struct MidiMap { int cc = 0; std::string track; int slot = 0; std::string param; double min = 0, max = 1; };
    std::vector<MidiMap> midiMaps;

    double lengthBeats() const
    {
        double L = 0;
        for (auto& t : tracks) for (auto& c : t.clips) L = std::max (L, c.end());
        return L;
    }
};

class CommandError : public std::runtime_error { public: using std::runtime_error::runtime_error; };

class Graph;

/** 엔진 — 곡 하나 + 실시간 출력 + 명령 처리. 모든 곡 변경은 m 잠금 아래. 오디오 스레드는 try_lock(못 잡으면 그 블록은 무음). */
class Engine
{
public:
    explicit Engine (const std::string& rootDir);
    ~Engine();

    /** 명령 하나 처리 → 결과 JSON. 오류는 CommandError. mutated = 곡이 바뀌었나(다른 클라이언트에 알림) */
    Json handle (const std::string& method, const Json& params, bool& mutated);

    std::string root;
    std::recursive_mutex m;
    std::unique_ptr<Project> project;
    SamplePool pool;
    Tuning tuning;

    // 실시간
    AudioOutput output;
    std::string outputName;
    int outputBuffer = 480;
    double liveRate = 48000;
    std::unique_ptr<Graph> graph;

    // 재생 상태(오디오 스레드가 갱신)
    std::atomic<bool> playing { false }, recording { false }, metronome { false };
    std::atomic<double> positionBeat { 0.0 };
    double loopStart = 0, loopEnd = 0;
    bool looping = false;
    float metronomeVolume = 0.5f;

    // MIDI 입력(녹음·모니터)
    struct LiveMidi { double beat; MidiEv ev; };
    std::mutex liveLock;
    std::vector<MidiEv> liveQueue;                 // 다음 블록에 넣을 실시간 입력
    std::vector<std::unique_ptr<MidiInput>> midiInputs;
    struct RecNote { int pitch; double start; int vel; double length = 0; };
    std::vector<RecNote> recHeld, recDone;
    std::vector<CcEv> recCc;
    double recStartBeat = 0;
    std::atomic<int64_t> lastBlockMs { 0 };
    std::atomic<double> lastBlockBeat { 0.0 };
    std::atomic<int> focusTrack { -1 };            // 선택한 트랙 — 녹음 대기 트랙이 없으면 연주가 여기로(Ableton 처럼 고르면 바로 연주)
    std::atomic<int> lastCc { -1 }, lastCcValue { 0 };   // MIDI 배우기: 마지막으로 움직인 컨트롤러
    std::atomic<uint64_t> lastCcSeq { 0 };
    std::atomic<uint64_t> noteSeq { 0 };            // 들어온 음표 수(화면의 MIDI 입력 표시등)

    // 되돌리기
    std::deque<std::string> undoStack, redoStack;
    std::string lastUndoKey;
    int64_t lastUndoMs = 0;

    uint64_t nextUid = 1;
    std::vector<struct Vst3Desc>* vstList = nullptr;   // 스캔 결과(eng_devices.cpp)

    // ── 도우미 ──
    Project& requireProject();
    Track& track (const Json& ref);                  // 이름 또는 번호
    int trackIndex (const Json& ref);
    std::vector<Slot>& chainFor (const Json& ref);   // 'master' 포함
    Slot& slot (const Json& params);                  // {track, device}
    Clip& clip (const Json& params);

    // 직렬화
    Json projectToJson (bool withState);
    void projectFromJson (const Json& j, bool reuseDevices);
    Json describeProject();
    Json describeTrack (int index);
    Json describeSlot (Slot& s, int index);
    Json describeClip (Clip& c, int index);

    // 디바이스
    Slot makeSlot (const Json& params, std::string& error);   // device.add
    void prepareSlot (Slot& s, double sr);
    void prepareAll (double sr);
    std::vector<Json> availableBuiltins();

    // 실시간
    bool startOutput (std::string& error);
    void stopPlayback();
    void audioCallback (float* L, float* R, int n);
    void onMidiIn (const MidiInMsg& msg);
    void openMidiInputs();                          // 연결된 MIDI 입력을 모두 연다(시작할 때 — 녹음 대기 없이도 연주·매핑)
    void applyMidiMaps (std::vector<MidiEv>& evs);   // 오디오 스레드(잠금 안): 매핑된 CC → 파라미터, 그 CC 는 악기로 안 보냄
    void finishRecording();

    // 되돌리기
    void pushUndo (const std::string& key);
    std::string snapshot();
    void restore (const std::string& snap);

    std::function<void (const std::string&)> log;
};

std::string base64Encode (const std::vector<uint8_t>& data);
std::vector<uint8_t> base64Decode (const std::string& s);
int64_t nowMs();

} // namespace mc
