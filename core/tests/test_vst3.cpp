// Musicoma Core — VST3 호스팅 시험(test-vst3).
//   스캔 목록 · Surge XT(EP 1.fxp) · Dexed · Dragonfly Hall 렌더(48 kHz, 블록 512, 오프라인) → core/build-vst3/out/*.wav
//   파라미터 목록/설정/문자열 · 상태 왕복 · 블록 크기 64/1024 동일성 · 편집 창 열고 닫기 · 플러그인 8종 적재
// 비교는 tests/golden/compare_vst3.py (옛 엔진 렌더와).
#include <windows.h>

#include <chrono>
#include <cmath>
#include <cstdio>
#include <thread>

#include "vst3host.h"
#include "vst3_device.h"
#include "vst3_internal.h"
#include "audiofile.h"
#include "util.h"

using namespace mc;

static const std::string kRoot = "D:/0.Musicoma";
static const std::string kPlugDir = kRoot + "/sounds/plugins/vst3";
static const std::string kEp1 = kPlugDir + "/Surge Synth Team/SurgeXTData/patches_factory/Keys/EP 1.fxp";
static const std::string kOut = kRoot + "/core/build-vst3/out";
static constexpr double SR = 48000, BPM = 120;
static constexpr int64_t kFrames = 240000;   // 8박(4초) + 꼬리 1초

struct Note { int pitch; double start, len; int vel; };
// compare_vst3.py 의 NOTES 와 같다
static const Note kNotes[] = {
    {60, 0, 2, 100}, {64, 0, 2, 100}, {67, 0, 2, 100},
    {72, 2, 0.5, 96}, {74, 2.5, 0.5, 96}, {76, 3, 0.5, 96}, {79, 3.5, 0.5, 96},
    {65, 4, 2, 90}, {69, 4, 2, 90}, {72, 4, 2, 90},
    {77, 6, 0.5, 100}, {76, 6.5, 0.5, 100}, {74, 7, 1, 100},
};

static int failures = 0;
#define CHECK(cond, ...) do { if (! (cond)) { ++failures; printf ("  FAIL: " __VA_ARGS__); printf ("\n"); } } while (0)

static std::vector<MidiEv> noteEvents()
{
    std::vector<MidiEv> ev;
    const double spb = SR * 60.0 / BPM;
    for (auto& n : kNotes)
    {
        ev.push_back ({ (int64_t) std::llround (n.start * spb), MidiEv::NoteOn, n.pitch, n.vel / 127.0f });
        ev.push_back ({ (int64_t) std::llround ((n.start + n.len) * spb), MidiEv::NoteOff, n.pitch, 0.0f });
    }
    std::stable_sort (ev.begin(), ev.end(), [] (const MidiEv& a, const MidiEv& b) {
        if (a.frame != b.frame) return a.frame < b.frame;
        return a.kind < b.kind;   // 같은 자리면 NoteOff(2) 먼저
    });
    return ev;
}

struct Stereo { std::vector<float> L, R; };

/** 블록 단위 오프라인 렌더. input 이 있으면 이펙트 입력 */
static Stereo render (Device& d, const std::vector<MidiEv>& ev, int block, const Stereo* input = nullptr, int64_t frames = kFrames)
{
    Stereo s;
    s.L.assign ((size_t) frames, 0.0f);
    s.R.assign ((size_t) frames, 0.0f);
    if (input) { s.L = input->L; s.R = input->R; s.L.resize ((size_t) frames); s.R.resize ((size_t) frames); }
    std::vector<MidiEv> blk;
    blk.reserve (256);
    size_t ei = 0;
    for (int64_t off = 0; off < frames; off += block)
    {
        int n = (int) std::min<int64_t> (block, frames - off);
        blk.clear();
        while (ei < ev.size() && ev[ei].frame < off + n)
        {
            auto e = ev[ei++];
            e.frame -= off;
            blk.push_back (e);
        }
        ProcessInfo info;
        info.sampleRate = SR;
        info.bpm = BPM;
        info.beat = off / SR * BPM / 60.0;
        info.playing = true;
        info.frame = off;
        d.process (s.L.data() + off, s.R.data() + off, n, blk, info);
    }
    return s;
}

static void save (const Stereo& s, const std::string& name)
{
    std::string err;
    if (! writeWav (u8path (kOut + "/" + name), { s.L, s.R }, (int64_t) s.L.size(), (int) SR, 32, err))
        printf ("  write %s failed: %s\n", name.c_str(), err.c_str());
}

static double peak (const Stereo& s)
{
    double p = 0;
    for (size_t i = 0; i < s.L.size(); ++i) p = std::max (p, (double) std::max (std::fabs (s.L[i]), std::fabs (s.R[i])));
    return p;
}

static double rmsDb (const Stereo& s)
{
    double a = 0;
    for (size_t i = 0; i < s.L.size(); ++i) a += s.L[i] * s.L[i] + s.R[i] * s.R[i];
    return gainToDb (std::sqrt (a / (2.0 * std::max<size_t> (1, s.L.size()))));
}

/** 최대 차이(dB, 피크 대비) */
static double diffDb (const Stereo& a, const Stereo& b)
{
    double m = 0;
    size_t n = std::min (a.L.size(), b.L.size());
    for (size_t i = 0; i < n; ++i) m = std::max (m, (double) std::max (std::fabs (a.L[i] - b.L[i]), std::fabs (a.R[i] - b.R[i])));
    return gainToDb (m / std::max (1e-9, peak (a)));
}

static Stereo makeHit()
{
    // compare_vst3.py hit_signal() 과 같은 식
    Stereo s;
    s.L.assign ((size_t) kFrames, 0.0f);
    int n = (int) (0.25 * SR);
    uint64_t state = 12345;
    for (int i = 0; i < n; ++i)
    {
        double t = i / SR;
        state = (state * 1103515245ULL + 12345ULL) & 0x7FFFFFFFULL;
        double noise = (double) state / 0x7FFFFFFF * 2.0 - 1.0;
        double env = std::exp (-t * 30.0);
        s.L[(size_t) i] = (float) ((0.6 * std::sin (2 * 3.14159265358979323846 * 80 * t) + 0.4 * noise * std::exp (-t * 60.0)) * env * 0.5);
    }
    s.R = s.L;
    return s;
}

static const Vst3Desc* findDesc (const std::vector<Vst3Desc>& list, const std::string& name)
{
    for (auto& d : list) if (d.name == name) return &d;
    return nullptr;
}

static std::unique_ptr<Device> make (const std::vector<Vst3Desc>& list, const std::string& name, int block = 512)
{
    auto* d = findDesc (list, name);
    if (! d) { ++failures; printf ("  FAIL: %s not in scan\n", name.c_str()); return nullptr; }
    std::string err;
    auto t0 = std::chrono::steady_clock::now();
    auto dev = createVst3 (*d, err);
    if (! dev) { ++failures; printf ("  FAIL: create %s: %s\n", name.c_str(), err.c_str()); return nullptr; }
    if (auto* api = dynamic_cast<Vst3DeviceApi*> (dev.get())) api->setOffline (true);
    dev->prepare (SR, block);
    auto ms = std::chrono::duration<double, std::milli> (std::chrono::steady_clock::now() - t0).count();
    printf ("  created %s (%.0f ms)\n", name.c_str(), ms);
    return dev;
}

static void pumpWait (int ms) { std::this_thread::sleep_for (std::chrono::milliseconds (ms)); }

int main()
{
    SetConsoleOutputCP (CP_UTF8);
    fs::create_directories (u8path (kOut));

    std::thread ui ([] { runVst3WindowThread(); });
    for (int i = 0; i < 200 && ! vst3::uiThreadRunning(); ++i) pumpWait (5);
    printf ("window thread: %s\n", vst3::uiThreadRunning() ? "running" : "NOT running");

    // ── 1. 스캔 ──
    printf ("\n[scan] %s\n", kPlugDir.c_str());
    std::vector<std::string> warns;
    auto t0 = std::chrono::steady_clock::now();
    auto list = scanVst3 ({ kPlugDir }, &warns);
    printf ("  %zu classes in %.0f ms\n", list.size(), std::chrono::duration<double, std::milli> (std::chrono::steady_clock::now() - t0).count());
    for (auto& d : list)
        printf ("  - %-28s | %-32s | %-22s | %s | %s\n", d.name.c_str(), d.vendor.c_str(), d.category.c_str(),
                d.instrument ? "instrument" : "effect    ", d.cid.c_str());
    for (auto& w : warns) printf ("  warning: %s\n", w.c_str());
    struct Expect { const char* name; const char* vendor; const char* cat; bool inst; };
    const Expect expect[] = {
        {"Surge XT", "Surge Synth Team", "Instrument|Synth", true},
        {"Surge XT Effects", "Surge Synth Team", "Fx", false},
        {"Dragonfly Room Reverb", "Michael Willis", "Fx|Reverb|Stereo", false},
        {"Dragonfly Plate Reverb", "Michael Willis", "Fx|Reverb|Stereo", false},
        {"Dragonfly Hall Reverb", "Michael Willis and Rob vd Berg", "Fx|Reverb|Stereo", false},
        {"Dragonfly Early Reflections", "Michael Willis", "Fx|Reverb|Stereo", false},
        {"Dexed", "Digital Suburban", "Instrument|Synth", true},
        {"Airwindows Consolidated", "Airwindows", "Fx", false},
    };
    for (auto& e : expect)
    {
        auto* d = findDesc (list, e.name);
        CHECK (d != nullptr, "missing %s", e.name);
        if (d)
            CHECK (d->vendor == e.vendor && d->category == e.cat && d->instrument == e.inst,
                   "%s: got vendor '%s' cat '%s' inst %d", e.name, d->vendor.c_str(), d->category.c_str(), (int) d->instrument);
    }
    CHECK (list.size() == 8, "expected 8 classes, got %zu", list.size());

    auto notes = noteEvents();

    // ── 2. Surge XT + EP 1.fxp ──
    printf ("\n[Surge XT]\n");
    Stereo surge512;
    Json surgeState;
    if (auto surge = make (list, "Surge XT"))
    {
        auto p0 = surge->params();
        printf ("  params %zu, programs %zu, latency %d, tail %.2f s, current program '%s'\n", p0.size(),
                surge->programs().size(), surge->latency(), surge->tailSeconds(), surge->currentProgramName().c_str());
        std::string err;
        // 진단용: 패치를 올리지 않은 기본(Init) 소리
        if (auto s0 = make (list, "Surge XT"))
        {
            auto r0 = render (*s0, notes, 512);
            save (r0, "surge_default.wav");
            printf ("  surge_default.wav (no patch) peak %.3f rms %.1f dB\n", peak (r0), rmsDb (r0));
        }
        bool ok = surge->loadFile (kEp1, err);
        CHECK (ok, "loadFile EP 1: %s", err.c_str());
        auto p1 = surge->params();
        int changed = 0;
        for (size_t i = 0; i < std::min (p0.size(), p1.size()); ++i) if (std::fabs (p0[i].value - p1[i].value) > 1e-6) ++changed;
        printf ("  after EP 1.fxp: %d params changed, program '%s'\n", changed, surge->currentProgramName().c_str());
        CHECK (changed > 5, "EP 1 load changed only %d params", changed);
        for (auto& p : p1)
            if (p.name == "Global Volume" || p.name == "A Volume" || p.name == "A Osc 1 Type")
                printf ("    %s (id %s) = %.6f '%s' def %.3f auto %d\n", p.name.c_str(), p.id.c_str(), p.value, p.text.c_str(), p.def, (int) p.automatable);

        surge512 = render (*surge, notes, 512);
        save (surge512, "surge_ep1.wav");
        printf ("  surge_ep1.wav peak %.3f rms %.1f dB, crashed %d\n", peak (surge512), rmsDb (surge512),
                (int) dynamic_cast<Vst3DeviceApi*> (surge.get())->crashed());
        CHECK (peak (surge512) > 0.01, "Surge render silent");
        surgeState = surge->getState();
        printf ("  state: component %zu b64 chars, controller %zu\n", surgeState.str ("component").size(), surgeState.str ("controller").size());

        // 편집 창
        printf ("  editor: ");
        bool shown = surge->showEditor();
        pumpWait (2500);
        auto* api = dynamic_cast<Vst3DeviceApi*> (surge.get());
        printf ("show %d, open %d", (int) shown, (int) api->editorOpen());
        CHECK (shown && api->editorOpen(), "Surge editor did not open");
        api->closeEditor();
        pumpWait (300);
        printf (", after close open %d\n", (int) api->editorOpen());
        CHECK (! api->editorOpen(), "Surge editor did not close");
        // 다시 열고 인스턴스째 지우기(창 열린 채 소멸)
        surge->showEditor();
        pumpWait (800);
    }

    // ── 3. 상태 왕복 · 블록 크기 ──
    printf ("\n[Surge XT state round trip / block sizes]\n");
    if (! surgeState.isNull())
    {
        // 기준: 새 인스턴스에 같은 .fxp 를 다시 올려 렌더 — 플러그인 자체가 결정적인지
        if (auto s1 = make (list, "Surge XT"))
        {
            std::string err;
            s1->loadFile (kEp1, err);
            auto r = render (*s1, notes, 512);
            printf ("  fresh instance + same fxp: max diff vs original %.1f dB, rms %.2f vs %.2f dB\n", diffDb (surge512, r), rmsDb (r), rmsDb (surge512));
        }
        for (int block : { 512, 64, 1024 })
        {
            auto s2 = make (list, "Surge XT", block);
            if (! s2) break;
            s2->setState (surgeState);
            auto r = render (*s2, notes, block);
            double dd = diffDb (surge512, r);
            printf ("  block %4d: max diff vs original %.1f dB (peak-relative)%s\n", block, dd, block == 512 ? "  [state round trip]" : "");
            if (block == 512) save (r, "surge_ep1_state.wav");
            else save (r, "surge_ep1_b" + std::to_string (block) + ".wav");
            // Surge 는 인스턴스마다 위상·랜덤이 달라 샘플 단위로는 안 맞는다(위 "fresh instance" 기준) → 라우드니스·상태 바이트로 본다
            double rd = rmsDb (r) - rmsDb (surge512);
            printf ("              rms diff %+.2f dB\n", rd);
            CHECK (std::fabs (rd) < 0.5, "Surge block %d rms differs %.2f dB", block, rd);
            if (block == 512)
            {
                auto st2 = s2->getState();
                std::vector<uint8_t> a, b;
                vst3::b64decode (surgeState.str ("component"), a);
                vst3::b64decode (st2.str ("component"), b);
                size_t same = 0;
                for (size_t i = 0; i < std::min (a.size(), b.size()); ++i) same += a[i] == b[i];
                printf ("              state bytes: %zu vs %zu, identical %zu (%s)\n", a.size(), b.size(), same, a == b ? "exact" : "differs");
                CHECK (a.size() == b.size(), "Surge state size changed in round trip");
            }
        }
    }

    // ── 4. Dexed ──
    printf ("\n[Dexed]\n");
    Stereo dexed512;
    Json dexedState;
    if (auto dx = make (list, "Dexed"))
    {
        auto ps = dx->params();
        printf ("  params %zu, programs %zu, current '%s'\n", ps.size(), dx->programs().size(), dx->currentProgramName().c_str());
        auto progs = dx->programs();
        for (size_t i = 0; i < std::min<size_t> (4, progs.size()); ++i) printf ("    program %zu: %s\n", i, progs[i].c_str());
        dexedState = dx->getState();
        dexed512 = render (*dx, notes, 512);
        save (dexed512, "dexed.wav");
        printf ("  dexed.wav peak %.3f rms %.1f dB\n", peak (dexed512), rmsDb (dexed512));
        CHECK (peak (dexed512) > 0.01, "Dexed render silent");
        // 파라미터 설정·문자열
        for (auto& p : ps) if (p.name == "Cutoff") printf ("    Cutoff id %s = %.3f '%s'\n", p.id.c_str(), p.value, p.text.c_str());
        CHECK (dx->setParam ("cutoff", 0.25), "setParam by name");
        for (auto& p : dx->params()) if (p.name == "Cutoff") { printf ("    after setParam(cutoff,0.25): %.3f '%s'\n", p.value, p.text.c_str()); CHECK (std::fabs (p.value - 0.25) < 0.01, "cutoff not set"); }
        for (auto& p : ps)
            if (p.name == "Cutoff")
            {
                CHECK (dx->setParam (p.id, 1.0), "setParam by id");
                printf ("    setParamText(Cutoff, \"0.5\") returned %d (Dexed parses its own text)\n", (int) dx->setParamText (p.id, "0.5"));
                for (auto& q : dx->params()) if (q.id == p.id) printf ("    setParamText(Cutoff, \"0.5\") -> %.3f '%s'\n", q.value, q.text.c_str());
            }
        // 프로그램 바꾸기
        if (progs.size() > 2)
        {
            bool ok = dx->setProgram (2);
            printf ("  setProgram(2) %d → current '%s'\n", (int) ok, dx->currentProgramName().c_str());
            CHECK (ok && dx->currentProgramName() == progs[2], "setProgram(2) failed");
        }
        // CC 매핑: 모드휠·서스테인·벤드
        std::vector<MidiEv> cc = { { 0, MidiEv::CC, 1, 0.5f }, { 10, MidiEv::CC, 64, 1.0f }, { 20, MidiEv::Bend, 0, 0.3f },
                                   { 30, MidiEv::CC, 7, 0.8f }, { 40, MidiEv::CC, 10, 0.5f }, { 50, MidiEv::CC, 11, 0.9f } };
        auto* api = dynamic_cast<Vst3DeviceApi*> (dx.get());
        int before = api->droppedControllers();
        render (*dx, cc, 512, nullptr, 4096);
        printf ("  CC 1/64/bend/7/10/11 → dropped (no mapping) %d of 6\n", api->droppedControllers() - before);
        printf ("  editor: ");
        bool shown = dx->showEditor();
        pumpWait (1500);
        printf ("show %d open %d\n", (int) shown, (int) api->editorOpen());
        api->closeEditor();
    }
    if (! dexedState.isNull())
        for (int block : { 64, 1024 })
            if (auto d2 = make (list, "Dexed", block))
            {
                d2->setState (dexedState);
                auto r = render (*d2, notes, block);
                double dd = diffDb (dexed512, r);
                printf ("  Dexed block %4d (from state): max diff %.1f dB\n", block, dd);
                CHECK (dd < -60, "Dexed block %d differs: %.1f dB", block, dd);
            }

    // ── 5. Dragonfly Hall ──
    printf ("\n[Dragonfly Hall Reverb]\n");
    if (auto hall = make (list, "Dragonfly Hall Reverb"))
    {
        auto ps = hall->params();
        printf ("  params %zu, latency %d, tail %.2f s\n", ps.size(), hall->latency(), hall->tailSeconds());
        for (auto& p : ps) printf ("    [%s] %-16s = %.4f '%s' (def %.4f, auto %d)\n", p.id.c_str(), p.name.c_str(), p.value, p.text.c_str(), p.def, (int) p.automatable);
        auto hit = makeHit();
        auto r = render (*hall, {}, 512, &hit);
        save (r, "dragonfly_hall.wav");
        printf ("  dragonfly_hall.wav peak %.3f rms %.1f dB\n", peak (r), rmsDb (r));
        CHECK (peak (r) > 0.01, "Hall render silent");
        // 블록 크기 동일성
        if (auto h2 = make (list, "Dragonfly Hall Reverb", 64))
        {
            auto r2 = render (*h2, {}, 64, &hit);
            double dd = diffDb (r, r2);
            printf ("  block 64 vs 512: max diff %.1f dB\n", dd);
            CHECK (dd < -60, "Hall block 64 differs %.1f dB", dd);
        }
        // setParam / setParamText
        if (! ps.empty())
        {
            const ParamInfo* pp = &ps[0];
            for (auto& q : ps) if (q.name == "Dry Level") pp = &q;
            const auto& p = *pp;
            size_t pi = (size_t) (pp - ps.data());
            bool a = hall->setParamText (p.id, "50");
            auto after = hall->params();
            printf ("  setParamText(%s, \"50\") %d → %.4f '%s'\n", p.name.c_str(), (int) a, after[pi].value, after[pi].text.c_str());
            bool b = hall->setParam (p.name, 0.3);
            after = hall->params();
            printf ("  setParam(%s, 0.3) %d → %.4f '%s'\n", p.name.c_str(), (int) b, after[pi].value, after[pi].text.c_str());
            CHECK (b && std::fabs (after[pi].value - 0.3) < 1e-3, "Hall setParam failed");
            // 처리 쪽에도 반영됐나: 상태 왕복 후 같은 값
            // DPF 는 0 샘플 process 의 파라미터를 무시한다 → 실제 엔진처럼 한 블록 돌린 뒤 상태를 받는다
            render (*hall, {}, 512, nullptr, 512);
            auto st = hall->getState();
            if (auto h3 = make (list, "Dragonfly Hall Reverb"))
            {
                h3->setState (st);
                auto p3 = h3->params();
                printf ("  state round trip: %s = %.4f '%s'\n", p3[pi].name.c_str(), p3[pi].value, p3[pi].text.c_str());
                CHECK (std::fabs (p3[pi].value - 0.3) < 1e-3, "Hall state round trip lost param");
            }
        }
    }

    // ── 6. 8종 적재 ──
    printf ("\n[all plugins]\n");
    for (auto& d : list)
    {
        std::string err;
        auto dev = createVst3 (d, err);
        if (! dev) { ++failures; printf ("  FAIL %-28s %s\n", d.name.c_str(), err.c_str()); continue; }
        auto* api = dynamic_cast<Vst3DeviceApi*> (dev.get());
        api->setOffline (true);
        dev->prepare (SR, 512);
        Stereo in = makeHit();
        auto ev = noteEvents();
        auto r = render (*dev, d.instrument ? ev : std::vector<MidiEv> {}, 512, d.instrument ? nullptr : &in, 48000);
        auto st = dev->getState();
        bool shown = dev->showEditor();
        pumpWait (700);
        bool open = api->editorOpen();
        api->closeEditor();
        printf ("  %-28s params %4zu programs %4zu latency %4d tail %5.2fs peak %.3f state %6zu/%zu editor %d/%d crashed %d\n",
                d.name.c_str(), dev->params().size(), dev->programs().size(), dev->latency(), dev->tailSeconds(), peak (r),
                st.str ("component").size(), st.str ("controller").size(), (int) shown, (int) open, (int) api->crashed());
        CHECK (! api->crashed(), "%s crashed", d.name.c_str());
    }

    // ── 7. 잘못된 입력 ──
    printf ("\n[errors]\n");
    {
        std::string err;
        Vst3Desc bad { "Nope", "", "", kRoot + "/nope.vst3", "00000000000000000000000000000000", false };
        auto dev = createVst3 (bad, err);
        printf ("  missing module: %s → '%s'\n", dev ? "created?!" : "null", err.c_str());
        CHECK (! dev, "bad module created");
        if (auto* d = findDesc (list, "Dexed"))
        {
            Vst3Desc wrong = *d;
            wrong.cid = "0123456789ABCDEF0123456789ABCDEF";
            err.clear();
            auto dev2 = createVst3 (wrong, err);
            printf ("  wrong cid: %s → '%s'\n", dev2 ? "created?!" : "null", err.c_str());
            CHECK (! dev2, "wrong cid created");
        }
        if (auto surge = make (list, "Surge XT"))
        {
            err.clear();
            bool ok = surge->loadFile (kRoot + "/nope.fxp", err);
            printf ("  missing fxp: %d '%s'\n", (int) ok, err.c_str());
        }
    }

    stopVst3WindowThread();
    ui.join();
    printf ("\n%s (%d failures)\n", failures ? "FAILED" : "ALL OK", failures);
    return failures ? 1 : 0;
}
