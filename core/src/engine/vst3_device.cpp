// Musicoma Engine — VST3 디바이스: 컴포넌트·컨트롤러 생성/연결, 버스, 처리(이벤트·파라미터·전송 정보), 상태, 프로그램, 편집 창.
// 스레드: 생성·컨트롤러·상태·창은 uiCall(창 스레드 또는 호출 스레드), process 는 오디오 스레드.
// process 안에서는 할당하지 않는다(고정 크기 이벤트·파라미터 큐).
#include <windows.h>

#include <algorithm>
#include <atomic>
#include <cmath>
#include <cstring>
#include <mutex>
#include <set>

#include "vst3_device.h"
#include "vst3_internal.h"
#include "vst3host.h"
#include "../util.h"

#include "pluginterfaces/base/funknownimpl.h"
#include "pluginterfaces/base/ibstream.h"
#include "pluginterfaces/gui/iplugview.h"
#include "pluginterfaces/vst/ivstaudioprocessor.h"
#include "pluginterfaces/vst/ivstcomponent.h"
#include "pluginterfaces/vst/ivsteditcontroller.h"
#include "pluginterfaces/vst/ivstevents.h"
#include "pluginterfaces/vst/ivstmessage.h"
#include "pluginterfaces/vst/ivstmidicontrollers.h"
#include "pluginterfaces/vst/ivstparameterchanges.h"
#include "pluginterfaces/vst/ivstprocesscontext.h"
#include "pluginterfaces/vst/ivstunits.h"
#include "pluginterfaces/vst/vstspeaker.h"
#include "public.sdk/source/common/memorystream.h"

using namespace Steinberg;
using namespace Steinberg::Vst;

namespace mc {

using namespace mc::vst3;

namespace {

// 멤버로 두는 고정 객체용 FUnknown — 플러그인이 addRef/release 해도 지우지 않는다
#define MC_STATIC_FUNKNOWN(Iface)                                                              \
    tresult PLUGIN_API queryInterface (const TUID iid_, void** obj) override                  \
    {                                                                                          \
        if (FUnknownPrivate::iidEqual (iid_, Iface::iid) || FUnknownPrivate::iidEqual (iid_, FUnknown::iid)) \
        { *obj = this; return kResultOk; }                                                     \
        *obj = nullptr; return kNoInterface;                                                   \
    }                                                                                          \
    uint32 PLUGIN_API addRef() override { return 1000; }                                       \
    uint32 PLUGIN_API release() override { return 1000; }

constexpr int kMaxPoints = 64;
constexpr int kMaxQueues = 512;
constexpr int kMaxEvents = 1024;

struct FixedValueQueue : public IParamValueQueue
{
    MC_STATIC_FUNKNOWN (IParamValueQueue)
    ParamID id = kNoParamId;
    int count = 0;
    int32 offs[kMaxPoints];
    ParamValue vals[kMaxPoints];

    ParamID PLUGIN_API getParameterId() override { return id; }
    int32 PLUGIN_API getPointCount() override { return count; }
    tresult PLUGIN_API getPoint (int32 i, int32& off, ParamValue& v) override
    {
        if (i < 0 || i >= count) return kResultFalse;
        off = offs[i]; v = vals[i];
        return kResultTrue;
    }
    tresult PLUGIN_API addPoint (int32 off, ParamValue v, int32& index) override
    {
        if (count > 0 && offs[count - 1] >= off) { offs[count - 1] = std::max (offs[count - 1], off); vals[count - 1] = v; index = count - 1; return kResultTrue; }
        if (count == kMaxPoints) { offs[count - 1] = off; vals[count - 1] = v; index = count - 1; return kResultTrue; }
        offs[count] = off; vals[count] = v; index = count++;
        return kResultTrue;
    }
};

struct FixedParamChanges : public IParameterChanges
{
    MC_STATIC_FUNKNOWN (IParameterChanges)
    FixedValueQueue q[kMaxQueues];
    int used = 0;

    void clear() { for (int i = 0; i < used; ++i) q[i].count = 0; used = 0; }
    int32 PLUGIN_API getParameterCount() override { return used; }
    IParamValueQueue* PLUGIN_API getParameterData (int32 i) override { return (i >= 0 && i < used) ? &q[i] : nullptr; }
    IParamValueQueue* PLUGIN_API addParameterData (const ParamID& id, int32& index) override
    {
        for (int i = 0; i < used; ++i)
            if (q[i].id == id) { index = i; return &q[i]; }
        if (used == kMaxQueues) { index = -1; return nullptr; }
        q[used].id = id; q[used].count = 0;
        index = used;
        return &q[used++];
    }
    void add (ParamID id, int32 off, ParamValue v)
    {
        int32 idx;
        if (auto* qq = addParameterData (id, idx))
            qq->addPoint (off, v, idx);
    }
};

struct FixedEventList : public IEventList
{
    MC_STATIC_FUNKNOWN (IEventList)
    Event ev[kMaxEvents];
    int count = 0;
    void clear() { count = 0; }
    int32 PLUGIN_API getEventCount() override { return count; }
    tresult PLUGIN_API getEvent (int32 i, Event& e) override
    {
        if (i < 0 || i >= count) return kResultFalse;
        e = ev[i];
        return kResultTrue;
    }
    tresult PLUGIN_API addEvent (Event& e) override
    {
        if (count >= kMaxEvents) return kResultFalse;
        ev[count++] = e;
        return kResultTrue;
    }
};

class Vst3Device;

/** IComponentHandler — 플러그인 창에서 바꾼 값을 처리 큐로 */
class ComponentHandler : public U::Implements<U::Directly<IComponentHandler>>
{
public:
    std::atomic<Vst3Device*> dev { nullptr };
    tresult PLUGIN_API beginEdit (ParamID) override { return kResultOk; }
    tresult PLUGIN_API performEdit (ParamID id, ParamValue v) override;
    tresult PLUGIN_API endEdit (ParamID) override { return kResultOk; }
    tresult PLUGIN_API restartComponent (int32 flags) override;
};

struct ParamLite
{
    ParamID id;
    std::string idStr, title, titleLower;
    int32 flags;
    int32 stepCount;
    bool listed;      // params() 에 보일지(JUCE MIDI CC 흉내 파라미터 제외; 숨김 파라미터는 옛 엔진처럼 보인다)
    ParamValue def;
    UnitID unit;
};

class Vst3Device : public Vst3DeviceApi
{
public:
    explicit Vst3Device (const Vst3Desc& d) : desc (d) { pending.reserve (kPendingCap); }
    ~Vst3Device() override { destroy(); }

    bool create (std::string& error);

    std::string type() const override { return "vst"; }
    std::string name() const override { return desc.name; }
    bool isInstrument() const override { return desc.instrument; }

    void prepare (double sampleRate, int maxBlock) override;
    void reset() override;
    void process (float* L, float* R, int n, const std::vector<MidiEv>& events, const ProcessInfo& info) override;

    std::vector<ParamInfo> params() override;
    bool setParam (const std::string& idOrName, double value) override;
    bool setParamText (const std::string& idOrName, const std::string& text) override;

    Json getState() override;
    void setState (const Json& state) override;

    double tailSeconds() const override { return tailSec; }
    int latency() const override;

    bool loadFile (const std::string& path, std::string& error) override;
    std::vector<std::string> programs() override;
    bool setProgram (int index) override;
    std::string currentProgramName() override;
    bool showEditor() override;

    void setOffline (bool off) override { offline = off; }
    bool editorOpen() const override { return editor.isOpen(); }
    void closeEditor() override { uiCall ([&] { editor.close(); }); }
    int droppedControllers() const override { return dropped.load(); }
    bool crashed() const override { return crashedFlag.load(); }
    std::string pluginPath() const override { return desc.path; }

    // ComponentHandler 에서
    void queueParam (ParamID id, ParamValue v)
    {
        std::lock_guard<std::mutex> lk (pendingMutex);
        if (pending.size() < kPendingCap) pending.push_back ({ id, v });
        else pending.back() = { id, v };
    }
    std::atomic<bool> paramsDirty { false }, latencyDirty { false };

private:
    static constexpr size_t kPendingCap = 4096;

    void destroy();
    void processChunk (float* L, float* R, int len, int off, int n, const std::vector<MidiEv>& events, size_t& ei, const ProcessInfo& info);
    void setupBuses();
    void flushParams();
    void collectMidiTargets();
    void refreshParamCache();
    const ParamLite* findParam (const std::string& idOrName);
    bool applyComponentState (const void* data, size_t n, std::string& err);
    void setActiveProcessing (bool on);
    void findPrograms();

    Vst3Desc desc;
    ModulePtr module;                     // 인스턴스가 사는 동안 DLL 유지
    IPtr<IComponent> component;
    IPtr<IEditController> controller;
    IPtr<IAudioProcessor> processor;
    bool singleComponent = false;
    IPtr<IConnectionPoint> cpComp, cpCtrl;
    ComponentHandler* handler = nullptr;
    EditorWindow editor;

    // 버스
    int nIn = 0, nOut = 0, nEvIn = 0;
    std::vector<int> inCh, outCh;          // 버스별 채널 수
    std::vector<std::vector<float>> scratch;
    std::vector<std::vector<float*>> inPtrs, outPtrs;
    std::vector<AudioBusBuffers> inBufs, outBufs;

    // 처리
    double sr = 48000;
    int maxBlock = 0;
    bool offline = false;
    bool active = false;
    std::atomic<bool> crashedFlag { false };
    std::atomic<int> dropped { 0 };
    FixedParamChanges inParams, outParams;
    FixedEventList inEvents, outEvents;
    ProcessContext ctx {};
    ParamID ccMap[130];

    std::mutex pendingMutex;
    std::vector<std::pair<ParamID, ParamValue>> pending;

    // 파라미터·프로그램
    std::vector<ParamLite> plist;
    std::set<ParamID> midiTargets;   // IMidiMapping 이 가리키는 파라미터(모든 채널)
    ParamID progParam = kNoParamId;
    int32 progSteps = 0;
    std::vector<std::string> progNames;

    double tailSec = 0;
    mutable int latencySamples = 0;
};

tresult PLUGIN_API ComponentHandler::performEdit (ParamID id, ParamValue v)
{
    if (auto* d = dev.load()) d->queueParam (id, v);
    return kResultOk;
}

tresult PLUGIN_API ComponentHandler::restartComponent (int32 flags)
{
    if (auto* d = dev.load())
    {
        if (flags & (kParamTitlesChanged | kReloadComponent | kParamValuesChanged)) d->paramsDirty = true;
        if (flags & kLatencyChanged) d->latencyDirty = true;
    }
    return kResultOk;
}

// ───────────────────────── 생성·소멸 ─────────────────────────

bool Vst3Device::create (std::string& error)
{
    for (auto& c : ccMap) c = kNoParamId;
    bool ok = false;
    uiCall ([&] {
        module = loadModule (desc.path, error);
        if (! module) return;
        auto uid = VST3::UID::fromString (desc.cid, false);
        if (! uid) { error = "bad class id: " + desc.cid; return; }
        std::string gerr;
        bool g = guarded ([&] {
            component = module->factory.createInstance<IComponent> (*uid);
            if (! component) { error = "cannot create component " + desc.name; return; }
            if (component->initialize (hostContext()) != kResultOk) { error = "component initialize failed"; component = nullptr; return; }

            // 컨트롤러: 단일 컴포넌트면 같은 객체, 아니면 클래스 ID 로 따로
            controller = U::cast<IEditController> (component);
            if (controller) singleComponent = true;
            else
            {
                TUID ccid;
                if (component->getControllerClassId (ccid) == kResultTrue)
                {
                    controller = module->factory.createInstance<IEditController> (VST3::UID (ccid));
                    if (controller && controller->initialize (hostContext()) != kResultOk)
                        controller = nullptr;
                }
            }
            if (! controller) { error = "no edit controller for " + desc.name; return; }

            processor = U::cast<IAudioProcessor> (component);
            if (! processor) { error = "component is not an audio processor"; return; }
            if (processor->canProcessSampleSize (kSample32) != kResultTrue) { error = "plugin cannot process 32-bit float"; return; }

            // 연결점: 컴포넌트 ↔ 컨트롤러
            if (! singleComponent)
            {
                cpComp = U::cast<IConnectionPoint> (component);
                cpCtrl = U::cast<IConnectionPoint> (controller);
                if (cpComp && cpCtrl)
                {
                    cpComp->connect (cpCtrl);
                    cpCtrl->connect (cpComp);
                }
            }

            // 처음 상태를 컨트롤러에 맞춘다
            {
                auto s = owned (new MemoryStream());
                if (component->getState (s) == kResultOk)
                {
                    s->seek (0, IBStream::kIBSeekSet, nullptr);
                    controller->setComponentState (s);
                }
            }

            handler = new ComponentHandler();
            handler->dev = this;
            controller->setComponentHandler (handler);

            setupBuses();
            collectMidiTargets();
            refreshParamCache();
            findPrograms();
            uint32 tail = processor->getTailSamples();
            tailSec = tail == kInfiniteTail ? 30.0 : std::min (30.0, tail / 48000.0);
            ok = true;
        }, &gerr);
        if (! g) { error = desc.name + ": " + gerr; ok = false; crashedFlag = true; }
    });
    return ok;
}

void Vst3Device::destroy()
{
    uiCall ([&] {
        editor.close();
        std::string err;
        guarded ([&] {
            if (processor && active) { processor->setProcessing (false); }
            if (component && active) component->setActive (false);
            active = false;
            if (cpComp && cpCtrl) { cpComp->disconnect (cpCtrl); cpCtrl->disconnect (cpComp); }
            cpComp = nullptr; cpCtrl = nullptr;
            if (controller) controller->setComponentHandler (nullptr);
            if (controller && ! singleComponent) controller->terminate();
            if (component) component->terminate();
        }, &err);
        if (! err.empty()) logWarn ("VST3 " + desc.name + " shutdown: " + err);
        guarded ([&] {
            processor = nullptr;
            controller = nullptr;
            component = nullptr;
        });
        if (handler) { handler->dev = nullptr; handler->release(); handler = nullptr; }
        module.reset();   // 마지막 인스턴스면 여기(창 스레드)서 DLL 내림
    });
}

static int channelsOf (SpeakerArrangement a) { return SpeakerArr::getChannelCount (a); }

void Vst3Device::setupBuses()
{
    nIn = component->getBusCount (kAudio, kInput);
    nOut = component->getBusCount (kAudio, kOutput);
    nEvIn = component->getBusCount (kEvent, kInput);
    std::vector<SpeakerArrangement> ia ((size_t) std::max (nIn, 1)), oa ((size_t) std::max (nOut, 1));
    for (int i = 0; i < nIn; ++i) { ia[i] = 0; processor->getBusArrangement (kInput, i, ia[i]); }
    for (int i = 0; i < nOut; ++i) { oa[i] = 0; processor->getBusArrangement (kOutput, i, oa[i]); }
    // 메인 버스를 스테레오로(안 되면 플러그인이 정한 대로)
    auto want = ia; auto wantO = oa;
    if (nIn > 0) want[0] = SpeakerArr::kStereo;
    if (nOut > 0) wantO[0] = SpeakerArr::kStereo;
    if (processor->setBusArrangements (nIn ? want.data() : nullptr, nIn, nOut ? wantO.data() : nullptr, nOut) != kResultTrue)
    {
        // 출력만 스테레오로 다시
        if (nIn > 0) want[0] = ia[0];
        processor->setBusArrangements (nIn ? want.data() : nullptr, nIn, nOut ? wantO.data() : nullptr, nOut);
    }
    inCh.assign ((size_t) nIn, 0);
    outCh.assign ((size_t) nOut, 0);
    for (int i = 0; i < nIn; ++i) { SpeakerArrangement a = 0; processor->getBusArrangement (kInput, i, a); inCh[i] = channelsOf (a); }
    for (int i = 0; i < nOut; ++i) { SpeakerArrangement a = 0; processor->getBusArrangement (kOutput, i, a); outCh[i] = channelsOf (a); }
    // 메인만 켠다
    for (int i = 0; i < nIn; ++i) component->activateBus (kAudio, kInput, i, i == 0);
    for (int i = 0; i < nOut; ++i) component->activateBus (kAudio, kOutput, i, i == 0);
    for (int i = 0; i < nEvIn; ++i) component->activateBus (kEvent, kInput, i, i == 0);
    int nEvOut = component->getBusCount (kEvent, kOutput);
    for (int i = 0; i < nEvOut; ++i) component->activateBus (kEvent, kOutput, i, false);
}

void Vst3Device::setActiveProcessing (bool on)
{
    if (on == active) return;
    if (on)
    {
        component->setActive (true);
        processor->setProcessing (true);   // kNotImplemented 도 괜찮다
        active = true;
    }
    else
    {
        processor->setProcessing (false);
        component->setActive (false);
        active = false;
    }
}

void Vst3Device::prepare (double sampleRate, int maxBlk)
{
    if (! component || crashedFlag) return;
    sr = sampleRate;
    maxBlock = std::max (16, maxBlk);
    uiCall ([&] {
        std::string err;
        bool g = guarded ([&] {
            setActiveProcessing (false);
            ProcessSetup ps { offline ? kOffline : kRealtime, kSample32, maxBlock, sr };
            if (processor->setupProcessing (ps) != kResultOk)
                logWarn ("VST3 " + desc.name + ": setupProcessing refused");

            // 버퍼: 버스별 채널 × maxBlock(0 으로 채움)
            scratch.clear(); inPtrs.assign ((size_t) nIn, {}); outPtrs.assign ((size_t) nOut, {});
            inBufs.assign ((size_t) nIn, AudioBusBuffers()); outBufs.assign ((size_t) nOut, AudioBusBuffers());
            int total = 0;
            for (int c : inCh) total += c;
            for (int c : outCh) total += c;
            scratch.assign ((size_t) total, std::vector<float> ((size_t) maxBlock, 0.0f));
            int k = 0;
            for (int b = 0; b < nIn; ++b)
            {
                for (int c = 0; c < inCh[b]; ++c) inPtrs[b].push_back (scratch[k++].data());
                inBufs[b].numChannels = inCh[b];
                inBufs[b].channelBuffers32 = inPtrs[b].empty() ? nullptr : inPtrs[b].data();
            }
            for (int b = 0; b < nOut; ++b)
            {
                for (int c = 0; c < outCh[b]; ++c) outPtrs[b].push_back (scratch[k++].data());
                outBufs[b].numChannels = outCh[b];
                outBufs[b].channelBuffers32 = outPtrs[b].empty() ? nullptr : outPtrs[b].data();
            }

            // MIDI CC·벤드 → 파라미터 매핑
            for (auto& c : ccMap) c = kNoParamId;
            auto mm = U::cast<IMidiMapping> (controller);
            if (! mm) mm = U::cast<IMidiMapping> (component);
            if (mm)
                for (int cc = 0; cc < 130; ++cc)
                {
                    ParamID id;
                    if (mm->getMidiControllerAssignment (0, 0, (CtrlNumber) cc, id) == kResultTrue) ccMap[cc] = id;
                }

            setActiveProcessing (true);
            latencySamples = processor->getLatencySamples();
            latencyDirty = false;
            uint32 tail = processor->getTailSamples();
            tailSec = tail == kInfiniteTail ? 30.0 : std::min (30.0, tail / sr);
        }, &err);
        if (! g) { logWarn ("VST3 " + desc.name + " prepare: " + err); crashedFlag = true; }
    });
}

void Vst3Device::reset()
{
    if (! component || crashedFlag || ! active) return;
    uiCall ([&] {
        std::string err;
        if (! guarded ([&] { setActiveProcessing (false); setActiveProcessing (true); }, &err))
        { logWarn ("VST3 " + desc.name + " reset: " + err); crashedFlag = true; }
    });
}

int Vst3Device::latency() const
{
    if (latencyDirty && processor)
    {
        guarded ([&] { latencySamples = (int) const_cast<Vst3Device*> (this)->processor->getLatencySamples(); });
        const_cast<Vst3Device*> (this)->latencyDirty = false;
    }
    return latencySamples;
}

// ───────────────────────── 처리 ─────────────────────────

void Vst3Device::process (float* L, float* R, int n, const std::vector<MidiEv>& events, const ProcessInfo& info)
{
    if (! active || crashedFlag || n <= 0 || maxBlock <= 0) return;   // 멈춘 플러그인: 이펙트는 통과, 악기는 무음
    size_t ei = 0;
    for (int off = 0; off < n; off += maxBlock)
    {
        int len = std::min (maxBlock, n - off);
        processChunk (L + off, R + off, len, off, n, events, ei, info);
        if (crashedFlag) return;
    }
}

void Vst3Device::processChunk (float* L, float* R, int len, int off, int n, const std::vector<MidiEv>& events, size_t& ei, const ProcessInfo& info)
{
    inParams.clear(); outParams.clear(); inEvents.clear(); outEvents.clear();

    // 창·setParam 에서 온 값(오프셋 0)
    if (pendingMutex.try_lock())
    {
        for (auto& p : pending) inParams.add (p.first, 0, p.second);
        pending.clear();
        pendingMutex.unlock();
    }

    // 이벤트: 이 조각 [off, off+len) 에 드는 것
    const double beatsPerSample = info.bpm / 60.0 / info.sampleRate;
    while (ei < events.size())
    {
        const auto& e = events[ei];
        int64_t f = std::clamp<int64_t> (e.frame, 0, n - 1);
        if (f >= off + len) break;
        ++ei;
        int32 so = (int32) (f - off);
        if (e.kind == MidiEv::NoteOn || e.kind == MidiEv::NoteOff)
        {
            Event ev {};
            ev.busIndex = 0;
            ev.sampleOffset = so;
            ev.ppqPosition = info.beat + (double) f * beatsPerSample;
            ev.flags = Event::kIsLive;
            bool on = e.kind == MidiEv::NoteOn && e.v > 0.0f;
            if (on)
            {
                ev.type = Event::kNoteOnEvent;
                ev.noteOn.channel = 0;
                ev.noteOn.pitch = (int16) std::clamp (e.a, 0, 127);
                ev.noteOn.tuning = 0;
                ev.noteOn.velocity = std::clamp (e.v, 0.0f, 1.0f);
                ev.noteOn.length = 0;
                ev.noteOn.noteId = -1;
            }
            else
            {
                ev.type = Event::kNoteOffEvent;
                ev.noteOff.channel = 0;
                ev.noteOff.pitch = (int16) std::clamp (e.a, 0, 127);
                ev.noteOff.velocity = e.kind == MidiEv::NoteOff ? std::clamp (e.v, 0.0f, 1.0f) : 0.0f;
                ev.noteOff.noteId = -1;
                ev.noteOff.tuning = 0;
            }
            if (nEvIn > 0) inEvents.addEvent (ev);
        }
        else
        {
            int cc = e.kind == MidiEv::Bend ? (int) kPitchBend : e.a;
            if (cc < 0 || cc >= 130 || ccMap[cc] == kNoParamId) { dropped.fetch_add (1, std::memory_order_relaxed); continue; }
            double v = e.kind == MidiEv::Bend ? (std::clamp (e.v, -1.0f, 1.0f) + 1.0) * 0.5 : std::clamp (e.v, 0.0f, 1.0f);
            inParams.add (ccMap[cc], so, v);
        }
    }

    // 전송 정보
    ctx = {};
    ctx.sampleRate = info.sampleRate;
    ctx.projectTimeSamples = info.frame + off;
    ctx.continousTimeSamples = info.frame + off;
    ctx.tempo = info.bpm;
    ctx.projectTimeMusic = info.beat + off * beatsPerSample;
    ctx.barPositionMusic = std::floor (ctx.projectTimeMusic / 4.0) * 4.0;
    ctx.timeSigNumerator = 4;
    ctx.timeSigDenominator = 4;
    ctx.state = ProcessContext::kTempoValid | ProcessContext::kProjectTimeMusicValid | ProcessContext::kBarPositionValid
              | ProcessContext::kTimeSigValid | ProcessContext::kContTimeValid | (info.playing ? ProcessContext::kPlaying : 0);

    // 입력: 메인 버스에 L/R
    if (nIn > 0 && inCh[0] > 0)
    {
        float** ch = inBufs[0].channelBuffers32;
        if (inCh[0] == 1)
            for (int i = 0; i < len; ++i) ch[0][i] = 0.5f * (L[i] + R[i]);
        else
        {
            memcpy (ch[0], L, sizeof (float) * (size_t) len);
            memcpy (ch[1], R, sizeof (float) * (size_t) len);
            for (int c = 2; c < inCh[0]; ++c) memset (ch[c], 0, sizeof (float) * (size_t) len);
        }
        inBufs[0].silenceFlags = 0;
    }
    for (int b = 0; b < nOut; ++b) outBufs[b].silenceFlags = 0;

    ProcessData data;
    data.processMode = offline ? kOffline : kRealtime;
    data.symbolicSampleSize = kSample32;
    data.numSamples = len;
    data.numInputs = nIn;
    data.numOutputs = nOut;
    data.inputs = nIn ? inBufs.data() : nullptr;
    data.outputs = nOut ? outBufs.data() : nullptr;
    data.inputParameterChanges = &inParams;
    data.outputParameterChanges = &outParams;
    data.inputEvents = nEvIn > 0 ? &inEvents : nullptr;
    data.outputEvents = &outEvents;
    data.processContext = &ctx;

    tresult r = kResultOk;
    if (! guarded ([&] { r = processor->process (data); }))
    {
        crashedFlag = true;
        return;
    }
    (void) r;

    // 출력: 메인 버스 → L/R (악기는 더하고 이펙트는 바꿈)
    if (nOut > 0 && outCh[0] > 0)
    {
        float** ch = outBufs[0].channelBuffers32;
        const float* oL = ch[0];
        const float* oR = outCh[0] > 1 ? ch[1] : ch[0];
        if (desc.instrument)
            for (int i = 0; i < len; ++i) { L[i] += oL[i]; R[i] += oR[i]; }
        else
        {
            memcpy (L, oL, sizeof (float) * (size_t) len);
            memcpy (R, oR, sizeof (float) * (size_t) len);
        }
    }
}

/** 0 샘플 process — 파라미터만 넘긴다(VST3 규약상 허용). 명령 스레드에서 부르며 엔진이 오디오와 겹치지 않게 보장 */
void Vst3Device::flushParams()
{
    if (! active || crashedFlag) return;
    {
        std::lock_guard<std::mutex> lk (pendingMutex);
        if (pending.empty()) return;
    }
    inParams.clear(); outParams.clear(); inEvents.clear(); outEvents.clear();
    {
        std::lock_guard<std::mutex> lk (pendingMutex);
        for (auto& p : pending) inParams.add (p.first, 0, p.second);
        pending.clear();
    }
    ctx = {};
    ctx.sampleRate = sr;
    ProcessData data;
    data.processMode = offline ? kOffline : kRealtime;
    data.symbolicSampleSize = kSample32;
    data.numSamples = 0;
    data.numInputs = nIn;
    data.numOutputs = nOut;
    data.inputs = nIn ? inBufs.data() : nullptr;
    data.outputs = nOut ? outBufs.data() : nullptr;
    data.inputParameterChanges = &inParams;
    data.outputParameterChanges = &outParams;
    data.inputEvents = nEvIn > 0 ? &inEvents : nullptr;
    data.outputEvents = &outEvents;
    data.processContext = &ctx;
    if (! guarded ([&] { processor->process (data); })) crashedFlag = true;
}

// ───────────────────────── 파라미터 ─────────────────────────

void Vst3Device::collectMidiTargets()
{
    midiTargets.clear();
    auto mm = U::cast<IMidiMapping> (controller);
    if (! mm) return;
    for (int16 ch = 0; ch < 16; ++ch)
        for (int cc = 0; cc < 130; ++cc)
        {
            ParamID id;
            if (mm->getMidiControllerAssignment (0, ch, (CtrlNumber) cc, id) == kResultTrue) midiTargets.insert (id);
        }
}

void Vst3Device::refreshParamCache()
{
    plist.clear();
    int32 n = controller->getParameterCount();
    plist.reserve ((size_t) std::max (0, n));
    for (int32 i = 0; i < n; ++i)
    {
        ParameterInfo pi {};
        if (controller->getParameterInfo (i, pi) != kResultOk) continue;
        ParamLite p;
        p.id = pi.id;
        p.idStr = std::to_string (pi.id);
        p.title = toUtf8 (pi.title, 128);
        p.titleLower = lower (p.title);
        p.flags = pi.flags;
        p.stepCount = pi.stepCount;
        p.def = pi.defaultNormalizedValue;
        p.unit = pi.unitId;
        // JUCE 래퍼는 MIDI CC 를 16채널×130개 파라미터(자동화 불가)로 흉내 낸다 — 목록에서는 뺀다(옛 엔진과 같은 개수)
        p.listed = ! (midiTargets.size() >= 128 && (pi.flags & ParameterInfo::kCanAutomate) == 0 && midiTargets.count (pi.id));
        plist.push_back (std::move (p));
    }
    paramsDirty = false;
}

const ParamLite* Vst3Device::findParam (const std::string& idOrName)
{
    if (paramsDirty) uiCall ([&] { guarded ([&] { refreshParamCache(); }); });
    for (auto& p : plist) if (p.idStr == idOrName) return &p;
    auto l = lower (idOrName);
    for (auto& p : plist) if (p.titleLower == l) return &p;
    return nullptr;
}

std::vector<ParamInfo> Vst3Device::params()
{
    std::vector<ParamInfo> out;
    if (! controller) return out;
    uiCall ([&] {
        guarded ([&] {
            if (paramsDirty) refreshParamCache();
            out.reserve (plist.size());
            for (auto& p : plist)
            {
                if (! p.listed) continue;
                ParamInfo pi;
                pi.id = p.idStr;
                pi.name = p.title;
                pi.value = controller->getParamNormalized (p.id);
                pi.min = 0; pi.max = 1;
                pi.def = p.def;
                String128 s {};
                if (controller->getParamStringByValue (p.id, pi.value, s) == kResultOk) pi.text = toUtf8 (s, 128);
                pi.automatable = (p.flags & ParameterInfo::kCanAutomate) != 0;
                out.push_back (std::move (pi));
            }
        });
    });
    return out;
}

bool Vst3Device::setParam (const std::string& idOrName, double value)
{
    if (! controller) return false;
    auto* p = findParam (idOrName);
    if (! p) return false;
    ParamID id = p->id;
    double v = std::clamp (value, 0.0, 1.0);
    uiCall ([&] { guarded ([&] { controller->setParamNormalized (id, v); }); });
    queueParam (id, v);
    return true;
}

bool Vst3Device::setParamText (const std::string& idOrName, const std::string& text)
{
    if (! controller) return false;
    auto* p = findParam (idOrName);
    if (! p) return false;
    ParamID id = p->id;
    bool ok = false;
    ParamValue v = 0;
    uiCall ([&] {
        guarded ([&] {
            auto w = toUtf16 (text);
            std::vector<TChar> buf (w.begin(), w.end());
            buf.push_back (0);
            ok = controller->getParamValueByString (id, buf.data(), v) == kResultOk;
        });
    });
    if (! ok) return false;
    return setParam (std::to_string (id), v);
}

// ───────────────────────── 상태 ─────────────────────────

static std::string streamBytes (MemoryStream* s)
{
    return std::string (s->getData() ? s->getData() : "", (size_t) s->getSize());
}

Json Vst3Device::getState()
{
    Json j = Json::object();
    if (! component) return j;
    flushParams();   // setParam 으로 큐에만 있는 값을 처리기에 먼저 넘긴다(그래야 컴포넌트 상태에 들어감)
    std::string comp, ctrl;
    uiCall ([&] {
        guarded ([&] {
            auto s = owned (new MemoryStream());
            if (component->getState (s) == kResultOk) comp = streamBytes (s);
            auto c = owned (new MemoryStream());
            if (controller->getState (c) == kResultOk) ctrl = streamBytes (c);
        });
    });
    j.set ("component", Json::string (b64encode (comp.data(), comp.size())));
    j.set ("controller", Json::string (b64encode (ctrl.data(), ctrl.size())));
    return j;
}

bool Vst3Device::applyComponentState (const void* data, size_t n, std::string& err)
{
    bool ok = false;
    uiCall ([&] {
        std::string g;
        guarded ([&] {
            auto s = owned (new MemoryStream (const_cast<void*> (data), (TSize) n));
            tresult r = component->setState (s);
            if (r != kResultOk) { err = "component rejected state (" + std::to_string (r) + ")"; return; }
            s->seek (0, IBStream::kIBSeekSet, nullptr);
            controller->setComponentState (s);
            ok = true;
        }, &g);
        if (! g.empty()) err = g;
        paramsDirty = true;
    });
    return ok;
}

void Vst3Device::setState (const Json& state)
{
    if (! component) return;
    std::vector<uint8_t> comp, ctrl;
    if (! b64decode (state.str ("component"), comp)) { logWarn ("VST3 setState: bad component base64"); return; }
    b64decode (state.str ("controller"), ctrl);
    std::string err;
    if (! comp.empty() && ! applyComponentState (comp.data(), comp.size(), err))
        logWarn ("VST3 " + desc.name + " setState: " + err);
    if (! ctrl.empty())
        uiCall ([&] {
            guarded ([&] {
                auto s = owned (new MemoryStream (ctrl.data(), (TSize) ctrl.size()));
                controller->setState (s);
            });
        });
}

bool Vst3Device::loadFile (const std::string& path, std::string& error)
{
    if (! component) { error = "plugin not loaded"; return false; }
    std::vector<uint8_t> bytes;
    if (! readFileBytes (u8path (path), bytes)) { error = "cannot read " + path; return false; }
    const uint8_t* data = bytes.data();
    size_t n = bytes.size();
    // .fxp 프로그램 청크: "CcnK" … "FPCh", 크기(빅엔디언) @56, 청크 @60
    if (n >= 60 && memcmp (data, "CcnK", 4) == 0 && memcmp (data + 8, "FPCh", 4) == 0)
    {
        uint32_t sz = (uint32_t) data[56] << 24 | (uint32_t) data[57] << 16 | (uint32_t) data[58] << 8 | data[59];
        size_t avail = n - 60;
        data += 60;
        n = std::min<size_t> (sz, avail);
    }
    else if (n >= 8 && memcmp (data, "CcnK", 4) == 0)
    {
        error = "unsupported .fxp/.fxb type (only FPCh program chunks)";
        return false;
    }
    if (n == 0) { error = "empty patch"; return false; }
    return applyComponentState (data, n, error);
}

// ───────────────────────── 프로그램 ─────────────────────────

void Vst3Device::findPrograms()
{
    progParam = kNoParamId;
    progSteps = 0;
    progNames.clear();
    UnitID progUnit = kRootUnitId;
    for (auto& p : plist)
        if (p.flags & ParameterInfo::kIsProgramChange) { progParam = p.id; progSteps = p.stepCount; progUnit = p.unit; break; }

    if (auto ui = U::cast<IUnitInfo> (controller))
    {
        ProgramListID listId = kNoProgramListId;
        int32 nu = ui->getUnitCount();
        for (int32 i = 0; i < nu; ++i)
        {
            UnitInfo u {};
            if (ui->getUnitInfo (i, u) == kResultOk && u.id == progUnit && u.programListId != kNoProgramListId)
                listId = u.programListId;
        }
        int32 nl = ui->getProgramListCount();
        for (int32 i = 0; i < nl; ++i)
        {
            ProgramListInfo pl {};
            if (ui->getProgramListInfo (i, pl) != kResultOk) continue;
            if (listId != kNoProgramListId && pl.id != listId) continue;
            for (int32 k = 0; k < pl.programCount; ++k)
            {
                String128 s {};
                ui->getProgramName (pl.id, k, s);
                progNames.push_back (toUtf8 (s, 128));
            }
            break;
        }
    }
    // 목록이 없으면 프로그램 파라미터의 단계 이름으로
    if (progNames.empty() && progParam != kNoParamId && progSteps > 0 && progSteps < 4096)
        for (int32 k = 0; k <= progSteps; ++k)
        {
            String128 s {};
            controller->getParamStringByValue (progParam, (double) k / progSteps, s);
            progNames.push_back (toUtf8 (s, 128));
        }
    // 이름 하나뿐인 목록(기본 프로그램)은 프로그램 없음으로 본다
    if (progNames.size() <= 1 && progParam == kNoParamId) progNames.clear();
}

std::vector<std::string> Vst3Device::programs() { return progNames; }

bool Vst3Device::setProgram (int index)
{
    if (progParam == kNoParamId || index < 0 || index >= (int) progNames.size()) return false;
    double v = progSteps > 0 ? (double) index / progSteps : 0.0;
    return setParam (std::to_string (progParam), v);
}

std::string Vst3Device::currentProgramName()
{
    if (progParam == kNoParamId || progNames.empty()) return {};
    double v = 0;
    uiCall ([&] { guarded ([&] { v = controller->getParamNormalized (progParam); }); });
    int idx = progSteps > 0 ? (int) std::lround (v * progSteps) : 0;
    return idx >= 0 && idx < (int) progNames.size() ? progNames[(size_t) idx] : std::string();
}

// ───────────────────────── 편집 창 ─────────────────────────

bool Vst3Device::showEditor()
{
    if (! controller) return false;
    if (! uiThreadRunning() && ! onUiThread())
    {
        logWarn ("VST3 showEditor: window thread not running");
        return false;
    }
    bool ok = false;
    uiCall ([&] {
        if (editor.isOpen())
        {
            ShowWindow ((HWND) editor.hwnd, SW_SHOWNORMAL);
            SetForegroundWindow ((HWND) editor.hwnd);
            ok = true;
            return;
        }
        IPlugView* view = nullptr;
        std::string err;
        guarded ([&] { view = controller->createView (ViewType::kEditor); }, &err);
        if (! view) { logWarn ("VST3 " + desc.name + ": no editor view " + err); return; }
        ok = editor.open (view, desc.name, err);
        if (! ok) logWarn ("VST3 " + desc.name + " editor: " + err);
    });
    return ok;
}

} // namespace

// ───────────────────────── 공개 API ─────────────────────────

std::unique_ptr<Device> createVst3 (const Vst3Desc& desc, std::string& error)
{
    auto d = std::make_unique<Vst3Device> (desc);
    if (! d->create (error))
    {
        if (error.empty()) error = "cannot create " + desc.name;
        return nullptr;   // 소멸자가 정리
    }
    return d;
}

} // namespace mc
