// Musicoma Engine — 실시간 재생·루프·메트로놈·MIDI 입력 녹음.
// 안쪽은 늘 kInternalRate(48 kHz)로 돌고, 출력 장치 레이트(원격 오디오 44.1 kHz 등)로는 마지막에 바꾼다
// → 재생과 렌더가 같은 소리, 장치가 바뀌어도 디바이스를 다시 준비할 필요 없음.
#include <algorithm>
#include <cmath>
#include <chrono>
#include <thread>
#include "eng_model.h"
#include "eng_graph.h"

namespace mc {

constexpr double kInternalRate = 48000.0;
constexpr int kBlock = 512;

namespace {
// 장치 레이트 변환용 FIFO (안쪽 48 kHz 프레임)
struct Fifo
{
    std::vector<float> L, R;
    size_t head = 0, count = 0;
    double frac = 0;          // 다음 출력 샘플의 소수 위치
    void init (size_t cap) { L.assign (cap, 0); R.assign (cap, 0); head = count = 0; frac = 0; }
    float at (const std::vector<float>& v, size_t i) const { return v[(head + i) % v.size()]; }
    void push (const float* l, const float* r, int n)
    {
        for (int i = 0; i < n && count < L.size(); ++i) { size_t p = (head + count) % L.size(); L[p] = l[i]; R[p] = r[i]; ++count; }
    }
    void drop (size_t k) { k = std::min (k, count); head = (head + k) % L.size(); count -= k; }
};
Fifo gFifo;
std::vector<float> gBL, gBR;
int64_t gPlayFrame = 0;       // 안쪽 레이트 기준 곡 위치(샘플)
std::vector<MidiEv> gLive;
}

static int64_t beatToFrame (double beat, double bpm) { return (int64_t) std::llround (beat * 60.0 / bpm * kInternalRate); }

namespace {
// 출력 장치가 없을 때(원격 접속이 끊겨 오디오 장치가 사라진 경우 등): 가짜 시계로 재생 위치·미터·녹음은 그대로 돈다
std::thread gNullClock;
std::atomic<bool> gNullRun { false };
}

bool Engine::startOutput (std::string& error)
{
    if (output.isOpen() || gNullRun.load()) return true;
    gFifo.init (1 << 15);
    gBL.assign (kBlock, 0); gBR.assign (kBlock, 0);
    gLive.reserve (1024);
    if (output.open (outputName, outputBuffer, [this] (float* L, float* R, int n) { audioCallback (L, R, n); }, error))
        return true;
    if (log) log ("no audio output (" + error + ") — running on a silent clock; render still works");
    error.clear();
    gNullRun = true;
    gNullClock = std::thread ([this]
    {
        std::vector<float> L (480), R (480);
        auto next = std::chrono::steady_clock::now();
        while (gNullRun.load())
        {
            audioCallback (L.data(), R.data(), 480);
            next += std::chrono::milliseconds (10);
            std::this_thread::sleep_until (next);
            if (! output.isOpen() && ! outputName.empty()) {}   // 장치를 고르면 audio.set 이 다시 연다
        }
    });
    return true;
}

void stopNullClock()
{
    gNullRun = false;
    if (gNullClock.joinable()) gNullClock.join();
}

void Engine::stopPlayback()
{
    playing = false;
    if (recording.load()) finishRecording();
    recording = false;
    if (graph) graph->resetAll();
}

void Engine::audioCallback (float* L, float* R, int n)
{
    std::unique_lock<std::recursive_mutex> lk (m, std::try_to_lock);
    if (! lk.owns_lock() || ! project || ! graph || graph->sampleRate() != kInternalRate)
    {
        std::fill_n (L, n, 0.0f); std::fill_n (R, n, 0.0f);
        return;
    }
    const double devRate = output.isOpen() && output.sampleRate() > 0 ? output.sampleRate() : kInternalRate;
    const double step = kInternalRate / devRate;
    const double bpm = project->bpm;

    // 실시간 입력(모니터) — 첫 번째 녹음 대기 트랙, 없으면 선택한 트랙
    int liveTrack = -1;
    for (size_t i = 0; i < project->tracks.size(); ++i) if (project->tracks[i].armed) { liveTrack = (int) i; break; }
    if (liveTrack < 0 && focusTrack.load() >= 0 && focusTrack.load() < (int) project->tracks.size()) liveTrack = focusTrack.load();
    {
        std::lock_guard<std::mutex> l (liveLock);
        gLive.swap (liveQueue);
        liveQueue.clear();
    }
    applyMidiMaps (gLive);

    size_t need = (size_t) std::ceil (gFifo.frac + n * step) + 4;
    while (gFifo.count < need)
    {
        bool play = playing.load();
        int len = kBlock;
        if (play && looping && loopEnd > loopStart)
        {
            int64_t le = beatToFrame (loopEnd, bpm);
            if (gPlayFrame >= le) { gPlayFrame = beatToFrame (loopStart, bpm); graph->resetAll(); }
            len = (int) std::min<int64_t> (kBlock, std::max<int64_t> (1, le - gPlayFrame));
        }
        graph->process (gBL.data(), gBR.data(), len, gPlayFrame, play, nullptr, gLive.empty() ? nullptr : &gLive, liveTrack);
        gLive.clear();
        gFifo.push (gBL.data(), gBR.data(), len);
        if (play) gPlayFrame += len;
    }
    // 4점 3차 보간으로 장치 레이트로
    for (int i = 0; i < n; ++i)
    {
        size_t k = (size_t) gFifo.frac;
        double t = gFifo.frac - (double) k;
        auto interp = [&] (const std::vector<float>& v)
        {
            float y0 = gFifo.at (v, k), y1 = gFifo.at (v, k + 1), y2 = gFifo.at (v, k + 2), y3 = gFifo.at (v, k + 3);
            float c1 = 0.5f * (y2 - y0), c2 = y0 - 2.5f * y1 + 2.0f * y2 - 0.5f * y3, c3 = 0.5f * (y3 - y0) + 1.5f * (y1 - y2);
            float tt = (float) t;
            return ((c3 * tt + c2) * tt + c1) * tt + y1;
        };
        L[i] = interp (gFifo.L); R[i] = interp (gFifo.R);
        gFifo.frac += step;
    }
    size_t used = (size_t) gFifo.frac;
    gFifo.drop (used);
    gFifo.frac -= (double) used;

    double beat = (double) gPlayFrame / kInternalRate * bpm / 60.0;
    positionBeat = beat;
    lastBlockBeat = beat;
    lastBlockMs = nowMs();
}

void Engine::applyMidiMaps (std::vector<MidiEv>& evs)
{
    if (! project || project->midiMaps.empty()) return;
    auto& P = *project;
    evs.erase (std::remove_if (evs.begin(), evs.end(), [&] (const MidiEv& e)
    {
        if (e.kind != MidiEv::CC) return false;
        bool used = false;
        for (auto& mm : P.midiMaps)
        {
            if (mm.cc != e.a) continue;
            for (auto& t : P.tracks)
                if (t.name == mm.track && mm.slot >= 0 && mm.slot < (int) t.slots.size() && t.slots[(size_t) mm.slot].dev)
                    t.slots[(size_t) mm.slot].dev->setParam (mm.param, mm.min + (mm.max - mm.min) * (double) e.v);
            used = true;
        }
        return used;
    }), evs.end());
}

void Engine::openMidiInputs()
{
    for (auto& mi : MidiInput::list())
    {
        bool open = false;
        for (auto& in : midiInputs) if (in->name() == mi.name) open = true;
        if (open) continue;
        auto in = std::make_unique<MidiInput>();
        std::string err;
        if (in->open (mi.index, [this] (const MidiInMsg& msg) { onMidiIn (msg); }, err)) midiInputs.push_back (std::move (in));
        else if (log) log ("midi input: " + err);
    }
}

void Engine::onMidiIn (const MidiInMsg& msg)
{
    uint8_t st = msg.status & 0xF0;
    if (st == 0xB0) { lastCc = msg.data1; lastCcValue = msg.data2; ++lastCcSeq; }
    if (st == 0x90 && msg.data2 > 0) ++noteSeq;
    MidiEv e { 0, MidiEv::CC, 0, 0 };
    if (st == 0x90 && msg.data2 > 0) e = { 0, MidiEv::NoteOn, msg.data1, msg.data2 / 127.0f };
    else if (st == 0x80 || (st == 0x90 && msg.data2 == 0)) e = { 0, MidiEv::NoteOff, msg.data1, 0.0f };
    else if (st == 0xB0) e = { 0, MidiEv::CC, msg.data1, msg.data2 / 127.0f };
    else if (st == 0xE0) e = { 0, MidiEv::Bend, 0, (float) (((msg.data2 << 7) | msg.data1) - 8192) / 8192.0f };
    else return;
    {
        std::lock_guard<std::mutex> l (liveLock);
        liveQueue.push_back (e);
    }
    if (! recording.load() || ! project) return;
    double bpm = project->bpm;
    double beat = lastBlockBeat.load() + (double) (nowMs() - lastBlockMs.load()) / 1000.0 * bpm / 60.0;
    std::lock_guard<std::mutex> l (liveLock);
    if (e.kind == MidiEv::NoteOn) recHeld.push_back ({ e.a, beat, (int) msg.data2 });
    else if (e.kind == MidiEv::NoteOff)
    {
        for (size_t i = 0; i < recHeld.size(); ++i)
            if (recHeld[i].pitch == e.a)
            {
                auto h = recHeld[i];
                recHeld.erase (recHeld.begin() + (long) i);
                h.length = beat - h.start;
                recDone.push_back (h);
                break;
            }
    }
    else if (e.kind == MidiEv::CC) recCc.push_back ({ msg.data1, beat, msg.data2 });
}

void Engine::finishRecording()
{
    if (! project) return;
    int ti = -1;
    for (size_t i = 0; i < project->tracks.size(); ++i) if (project->tracks[i].armed) { ti = (int) i; break; }
    std::lock_guard<std::mutex> l (liveLock);
    double endBeat = positionBeat.load();
    if (ti >= 0 && (! recDone.empty() || ! recHeld.empty()))
    {
        Clip c;
        c.name = "take";
        c.midi = true;
        c.start = std::floor (recStartBeat);
        c.length = std::max (1.0, std::ceil (endBeat) - c.start);
        for (auto& d : recDone) c.notes.push_back ({ d.pitch, d.start - c.start, std::max (0.05, d.length), d.vel });
        for (auto& x : recCc) c.cc.push_back ({ x.cc, x.beat - c.start, x.value });
        for (auto& h : recHeld) c.notes.push_back ({ h.pitch, h.start - c.start, std::max (0.05, endBeat - h.start), h.vel });
        project->tracks[(size_t) ti].clips.push_back (std::move (c));
    }
    recDone.clear(); recHeld.clear(); recCc.clear();
}

/** 렌더·재생 전에 모든 디바이스를 안쪽 레이트로 */
void Engine::prepareAll (double sr)
{
    if (! project) return;
    for (auto& t : project->tracks) for (auto& s : t.slots) prepareSlot (s, sr);
    for (auto& s : project->master) prepareSlot (s, sr);
}

int64_t playFrameNow() { return gPlayFrame; }
void setPlayFrame (int64_t f) { gPlayFrame = f; }

} // namespace mc
