// test-fx — 내장 이펙트 시험. scratch/golden/fx/cases.json 의 케이스마다:
//   createBuiltinFx → setParam → params() 를 예전 엔진 응답(params_after)과 대조 → input.wav 를 들쭉날쭉한 블록 크기로 처리
//   → core/build-fx/out/<case>.wav (32비트 float, 마스터 게인·클립 없음 = 이펙트 출력 그대로)
// 추가로 블록 크기 독립성(다른 블록 패턴과 비트 비교), getState/setState 왕복, NaN·장시간 안정성, 다른 샘플레이트를 본다.
//   사용: test-fx [저장소 루트]   (생략하면 실행 파일 위쪽에서 scratch/golden/fx 를 찾는다)
#include "device.h"
#include "../src/audiofile.h"
#include "../src/json.h"
#include "../src/util.h"
#include <windows.h>
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <random>
#include <string>
#include <vector>

using namespace mc;

namespace {

int gFail = 0;
void fail (const std::string& m) { ++gFail; std::printf ("  FAIL %s\n", m.c_str()); }

fs::path findRoot (int argc, char** argv)
{
    if (argc > 1) return u8path (argv[1]);
    wchar_t buf[MAX_PATH];
    GetModuleFileNameW (nullptr, buf, MAX_PATH);
    fs::path p = fs::path (buf).parent_path();
    for (int i = 0; i < 6 && ! p.empty(); ++i, p = p.parent_path())
        if (fs::exists (p / "scratch" / "golden" / "fx" / "cases.json")) return p;
    return u8path ("D:/0.Musicoma");
}

/** 들쭉날쭉한 블록 크기로 처리 */
void runDevice (Device& d, std::vector<float>& L, std::vector<float>& R, const std::vector<int>& pattern, double sr)
{
    ProcessInfo info;
    info.sampleRate = sr; info.bpm = 120; info.playing = true;
    std::vector<MidiEv> ev;
    size_t pos = 0, k = 0;
    const size_t n = L.size();
    while (pos < n)
    {
        int b = pattern[k++ % pattern.size()];
        b = (int) std::min<size_t> ((size_t) b, n - pos);
        info.frame = (int64_t) pos;
        info.beat = (double) pos / sr * info.bpm / 60.0;
        d.process (L.data() + pos, R.data() + pos, b, ev, info);
        pos += (size_t) b;
    }
}

bool approxEq (double a, double b) { return std::fabs (a - b) <= 1e-6 * std::max (1.0, std::fabs (b)); }

void checkParams (Device& d, const Json& after, const std::string& dev)
{
    if (! after.isObj()) return;
    if (after.str ("device") != d.name()) fail ("name '" + d.name() + "' != '" + after.str ("device") + "'");
    auto ps = d.params();
    const Json& gp = after["params"];
    if (gp.a.size() != ps.size()) { fail ("param count " + std::to_string (ps.size()) + " != " + std::to_string (gp.a.size())); return; }
    for (size_t i = 0; i < ps.size(); ++i)
    {
        const Json& g = gp.a[i];
        const auto& p = ps[i];
        const std::string id = g.str ("id");
        if (p.id != id) fail ("param[" + std::to_string (i) + "] id '" + p.id + "' != '" + id + "'");
        if (p.name != g.str ("name")) fail ("param " + id + " name '" + p.name + "' != '" + g.str ("name") + "'");
        if (p.text != g.str ("text")) fail ("param " + id + " text '" + p.text + "' != '" + g.str ("text") + "'");
        // 컴프레서 threshold/ratio 는 예전 엔진이 내부 단위로 보고 → 우리는 사람 단위(의도된 차이)
        const bool humanUnits = dev == "compressor" && (id == "threshold" || id == "ratio");
        if (! humanUnits)
        {
            if (! approxEq (p.value, g.num ("value", 0))) fail ("param " + id + " value " + std::to_string (p.value) + " != " + std::to_string (g.num ("value", 0)));
            if (! approxEq (p.min, g.num ("min", 0)) || ! approxEq (p.max, g.num ("max", 0)))
                fail ("param " + id + " range " + std::to_string (p.min) + ".." + std::to_string (p.max));
        }
    }
}

bool sameParams (const std::vector<ParamInfo>& a, const std::vector<ParamInfo>& b)
{
    if (a.size() != b.size()) return false;
    for (size_t i = 0; i < a.size(); ++i)
        if (a[i].id != b[i].id || a[i].value != b[i].value || a[i].text != b[i].text) return false;
    return true;
}

/** 큰 잡음·임펄스·무음을 긴 시간 넣고 NaN/폭주가 없는지, 무음 뒤 꼬리가 0 으로 가는지 */
void stability (const std::string& dev, double sr)
{
    auto d = createBuiltinFx (dev);
    d->prepare (sr, 4096);
    std::mt19937 rng (3);
    std::normal_distribution<float> nd (0.0f, 0.5f);
    const size_t n = (size_t) (sr * 60);
    std::vector<float> L (n), R (n);
    for (size_t i = 0; i < n; ++i)
    {
        const double t = (double) i / sr;
        float v = 0;
        if (t < 20) v = nd (rng);
        else if (t < 25) v = (float) std::sin (2 * 3.14159265 * 30 * t);
        else if (t < 26) v = (i % 9000 == 0) ? 1.0f : 0.0f;
        L[i] = v; R[i] = -0.7f * v;
    }
    runDevice (*d, L, R, { 512, 1, 77, 4096 }, sr);
    double peak = 0, tail = 0;
    bool finite = true;
    for (size_t i = 0; i < n; ++i)
    {
        if (! std::isfinite (L[i]) || ! std::isfinite (R[i])) finite = false;
        peak = std::max<double> (peak, std::max (std::fabs (L[i]), std::fabs (R[i])));
        if ((double) i / sr > 58) tail = std::max<double> (tail, std::max (std::fabs (L[i]), std::fabs (R[i])));
    }
    std::printf ("  stability %-10s sr %6.0f: finite %s  peak %.2f  tail(58-60s) %.2e\n", dev.c_str(), sr, finite ? "yes" : "NO", peak, tail);
    if (! finite) fail (dev + " produced NaN/Inf");
    if (peak > 50) fail (dev + " blew up");
    if (tail > 1e-4) fail (dev + " tail does not decay");
}

} // namespace

int main (int argc, char** argv)
{
    SetConsoleOutputCP (CP_UTF8);
    const fs::path root = findRoot (argc, argv);
    const fs::path gdir = root / "scratch" / "golden" / "fx";
    const fs::path outDir = root / "core" / "build-fx" / "out";
    fs::create_directories (outDir);

    std::string text, err;
    if (! readFileText (gdir / "cases.json", text)) { std::printf ("cannot read cases.json under %s\n", pathToU8 (gdir).c_str()); return 2; }
    Json cases = Json::parse (text);
    AudioData in;
    if (! readAudioFile (gdir / "input.wav", in, err)) { std::printf ("input.wav: %s\n", err.c_str()); return 2; }
    const double sr = in.sampleRate;
    const size_t n = (size_t) in.frames;
    std::printf ("input %zu frames @ %.0f Hz\n", n, sr);

    // 공장 기본 검사
    if (createBuiltinFx ("nosuch")) fail ("unknown name must return nullptr");
    if (! createBuiltinFx ("filter") || createBuiltinFx ("filter")->type() != "lowpass") fail ("alias 'filter' -> lowpass");
    for (auto& nm : builtinFxNames()) if (! createBuiltinFx (nm)) fail ("builtinFxNames entry '" + nm + "' not creatable");

    // 프로토콜 골든(tests/golden/protocol.json)의 기본값 응답: device.params(note = 이펙트 이름) 와 대조
    {
        std::string pt;
        if (readFileText (root / "tests" / "golden" / "protocol.json", pt))
        {
            Json proto = Json::parse (pt);
            int checked = 0;
            for (auto& call : proto["calls"].a)
            {
                if (call.str ("method") == "device.add" && call["params"].str ("track") == "FX")
                {
                    auto d = createBuiltinFx (call["params"].str ("device"));
                    if (! d) continue;
                    const Json& r = call["result"];
                    if (d->type() != r.str ("type") || d->name() != r.str ("name")
                        || (double) d->params().size() != r.num ("num_params", -1))
                        fail ("device.add " + call["params"].str ("device") + ": type/name/num_params " + d->type() + "/" + d->name());
                    else std::printf ("[protocol add] %s -> %s / %s\n", call["params"].str ("device").c_str(), d->type().c_str(), d->name().c_str());
                    continue;
                }
                if (call.str ("method") != "device.params") continue;
                const std::string note = call.str ("note");
                const std::vector<std::string> fxn = builtinFxNames();
                if (std::find (fxn.begin(), fxn.end(), note) == fxn.end()) continue;
                auto d = createBuiltinFx (note);
                d->prepare (48000, 4096);
                std::printf ("[protocol default] %s\n", note.c_str());
                checkParams (*d, call["result"], note);
                ++checked;
            }
            if (checked < 8) fail ("protocol.json: only " + std::to_string (checked) + " default device.params checked");
        }
        else fail ("cannot read tests/golden/protocol.json");
    }

    const std::vector<int> patA { 64, 517, 4096, 1, 300, 2048, 33 };
    Json meta = Json::object();
    const std::vector<int> patB { 128 };

    for (auto& c : cases["cases"].a)
    {
        const Json* dv = c.find ("device");
        if (! dv || ! dv->isStr()) continue;   // dry · 믹서 · 센드 케이스는 건너뜀
        const std::string name = c.str ("name"), dev = dv->s;
        std::printf ("[%s] %s\n", name.c_str(), dev.c_str());
        auto d = createBuiltinFx (dev);
        if (! d) { fail ("createBuiltinFx(" + dev + ") == nullptr"); continue; }
        d->prepare (sr, 4096);
        for (auto& kv : c["params"].o)
            if (! d->setParam (kv.first, kv.second.n)) fail ("setParam '" + kv.first + "' not found");
        checkParams (*d, c["params_after"], dev);

        std::vector<float> L = in.ch[0], R = in.ch.size() > 1 ? in.ch[1] : in.ch[0];
        auto t0 = std::chrono::steady_clock::now();
        runDevice (*d, L, R, patA, sr);
        double secs = std::chrono::duration<double> (std::chrono::steady_clock::now() - t0).count();

        // 블록 독립성: 새 인스턴스 + 상태 복원 + 다른 블록 패턴 → 같은 출력이어야 한다
        auto d2 = createBuiltinFx (dev);
        d2->prepare (sr, 4096);
        d2->setState (d->getState());
        if (! sameParams (d->params(), d2->params())) fail ("getState/setState round trip");
        std::vector<float> L2 = in.ch[0], R2 = in.ch.size() > 1 ? in.ch[1] : in.ch[0];
        runDevice (*d2, L2, R2, patB, sr);
        double maxDiff = 0;
        bool finite = true;
        for (size_t i = 0; i < n; ++i)
        {
            maxDiff = std::max<double> (maxDiff, std::max (std::fabs (L[i] - L2[i]), std::fabs (R[i] - R2[i])));
            if (! std::isfinite (L[i]) || ! std::isfinite (R[i])) finite = false;
        }
        if (maxDiff > 1e-6) fail ("block-size dependence, max diff " + std::to_string (maxDiff));
        if (! finite) fail ("NaN/Inf in output");
        std::printf ("  %.1fx realtime, latency %d, tail %.2fs, block diff %.1e\n", (double) n / sr / std::max (secs, 1e-9), d->latency(), d->tailSeconds(), maxDiff);

        if (! writeWav (outDir / (name + ".wav"), { L, R }, (int64_t) n, (int) sr, 32, err)) fail ("write: " + err);
        Json m = Json::object();
        m.set ("device", Json::string (dev));
        m.set ("type", Json::string (d->type()));
        m.set ("latency", Json::number (d->latency()));
        m.set ("tail", Json::number (d->tailSeconds()));
        m.set ("realtime_x", Json::number ((double) n / sr / std::max (secs, 1e-9)));
        m.set ("block_diff", Json::number (maxDiff));
        m.set ("state", d->getState());
        meta.set (name, m);
    }
    {
        std::string js = meta.dump (1);
        FILE* f = _wfopen ((outDir / "meta.json").wstring().c_str(), L"wb");
        if (f) { std::fwrite (js.data(), 1, js.size(), f); std::fclose (f); }
    }

    std::printf ("[stability]\n");
    for (auto& dev : builtinFxNames())
        for (double s : { 44100.0, 48000.0, 96000.0 })
            stability (dev, s);

    std::printf (gFail ? "\n%d FAILURES\n" : "\nALL OK\n", gFail);
    return gFail ? 1 : 0;
}
