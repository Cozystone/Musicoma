// Musicoma Core — 오프라인 렌더러 (C1)
//   musicoma-core.exe render plan.json out.wav [--sr 48000] [--bits 24] [--threads N] [--stats s.json] [--tune key=value]...
//   musicoma-core.exe sfzinfo file.sfz        SFZ 를 읽어 리전 수·무시한 opcode·빠진 샘플을 JSON 으로
#include <chrono>
#include <iostream>
#include "audiofile.h"
#include "json.h"
#include "render.h"
#include "sfz.h"

#ifdef _WIN32
 #define WIN32_LEAN_AND_MEAN
 #define NOMINMAX
 #include <windows.h>
 #include <shellapi.h>
 #define PSAPI_VERSION 2
 #include <psapi.h>
#endif

using namespace mc;

static double peakRamMb()
{
#ifdef _WIN32
    PROCESS_MEMORY_COUNTERS pmc {};
    if (GetProcessMemoryInfo (GetCurrentProcess(), &pmc, sizeof pmc))
        return (double) pmc.PeakWorkingSetSize / 1048576.0;
#endif
    return 0;
}

static int usage()
{
    std::cerr << "usage:\n"
                 "  musicoma-core render <plan.json> <out.wav> [--sr 48000] [--bits 24|16|32] [--threads N] [--stats file.json] [--tune key=value]\n"
                 "  musicoma-core sfzinfo <file.sfz>\n"
                 "  musicoma-core decode <sample.flac|wav> <out.wav>   (decoder check, 32-bit float)\n";
    return 2;
}

static int cmdSfzInfo (const std::string& path, int listKey = -1)
{
    std::string err;
    auto inst = loadSfz (path, err);
    if (! inst) { std::cerr << "ERROR " << err << std::endl; return 1; }
    Json o = Json::object();
    o.set ("sfz", Json::string (path));
    o.set ("regions", Json::number ((double) inst->regions.size()));
    int missing = 0, silence = 0;
    std::map<std::string, bool> seen;
    for (auto& r : inst->regions)
    {
        if (r.silence) { ++silence; continue; }
        if (seen.count (r.sample)) continue;
        seen[r.sample] = fs::exists (u8path (r.sample));
        if (! seen[r.sample]) { if (missing < 5) std::cerr << "missing: " << r.sample << std::endl; ++missing; }
    }
    o.set ("sample_files", Json::number ((double) seen.size()));
    o.set ("missing_files", Json::number (missing));
    o.set ("silence_regions", Json::number (silence));
    Json un = Json::object();
    for (auto& [k, n] : inst->unsupported) un.set (k, Json::number (n));
    o.set ("ignored_opcodes", un);
    Json w = Json::array();
    for (auto& s : inst->warnings) w.push (Json::string (s));
    o.set ("warnings", w);
    if (listKey >= 0)
    {
        Json list = Json::array();
        for (auto& r : inst->regions)
        {
            if (listKey < r.lokey || listKey > r.hikey) continue;
            Json x = Json::object();
            x.set ("i", Json::number (r.index));
            x.set ("sample", Json::string (r.silence ? std::string ("*silence") : pathToU8 (u8path (r.sample).filename())));
            x.set ("vel", Json::string (std::to_string (r.lovel) + "-" + std::to_string (r.hivel)));
            x.set ("trigger", Json::number ((int) r.trigger));
            x.set ("group", Json::number ((double) r.group));
            if (r.hasOffBy) x.set ("off_by", Json::number ((double) r.offBy));
            x.set ("seq", Json::string (std::to_string (r.seqPosition) + "/" + std::to_string (r.seqLength)));
            std::string cond;
            for (auto& c : r.ccConditions) cond += "cc" + std::to_string (c.cc) + "[" + std::to_string ((int) c.lo) + "," + std::to_string ((int) c.hi) + "] ";
            if (! cond.empty()) x.set ("cc", Json::string (cond));
            if (! r.ccTriggers.empty()) x.set ("on_cc", Json::number (r.ccTriggers[0].cc));
            list.push (x);
        }
        o.set ("regions_for_key", list);
    }
    std::cout << o.dump (1) << std::endl;
    return 0;
}

int main (int argc, char** argv)
{
#ifdef _WIN32
    // 명령행 인자를 UTF-8 로 (한글 경로)
    int wargc = 0;
    LPWSTR* wargv = CommandLineToArgvW (GetCommandLineW(), &wargc);
    std::vector<std::string> args;
    for (int i = 0; i < wargc; ++i)
    {
        int n = WideCharToMultiByte (CP_UTF8, 0, wargv[i], -1, nullptr, 0, nullptr, nullptr);
        std::string s ((size_t) std::max (0, n - 1), '\0');
        WideCharToMultiByte (CP_UTF8, 0, wargv[i], -1, s.data(), n, nullptr, nullptr);
        args.push_back (s);
    }
    LocalFree (wargv);
    SetConsoleOutputCP (CP_UTF8);
#else
    std::vector<std::string> args (argv, argv + argc);
#endif
    (void) argc; (void) argv;
    if (args.size() < 3) return usage();

    try
    {
        if (args[1] == "sfzinfo") return cmdSfzInfo (args[2], args.size() >= 5 && args[3] == "--key" ? std::stoi (args[4]) : -1);
        if (args[1] == "decode" && args.size() >= 4)
        {
            // 디코더 점검용: 샘플 파일 → 32비트 float WAV
            AudioData d;
            std::string err;
            if (! readAudioFile (u8path (args[2]), d, err)) { std::cerr << "ERROR " << err << std::endl; return 1; }
            if (! writeWav (u8path (args[3]), d.ch, d.frames, (int) d.sampleRate, 32, err)) { std::cerr << "ERROR " << err << std::endl; return 1; }
            std::cout << "frames " << d.frames << " channels " << d.channels << " rate " << d.sampleRate << std::endl;
            return 0;
        }
        if (args[1] != "render" || args.size() < 4) return usage();

        RenderOptions opt;
        int bits = 24;
        std::string statsPath;
        for (size_t i = 4; i < args.size(); ++i)
        {
            auto& a = args[i];
            auto nextv = [&] { if (i + 1 >= args.size()) throw std::runtime_error ("missing value for " + a); return args[++i]; };
            if (a == "--sr") opt.sampleRate = std::stoi (nextv());
            else if (a == "--bits") bits = std::stoi (nextv());
            else if (a == "--threads") opt.threads = std::stoi (nextv());
            else if (a == "--stats") statsPath = nextv();
            else if (a == "--tune")
            {
                auto kv = nextv();
                auto eq = kv.find ('=');
                if (eq == std::string::npos) throw std::runtime_error ("--tune needs key=value");
                std::string k = kv.substr (0, eq);
                double v = std::stod (kv.substr (eq + 1));
                if (k == "mixPanLaw") opt.mixPanLaw = (int) v;
                else if (! applyTuning (opt.tuning, k, v)) throw std::runtime_error ("unknown tune key " + k);
            }
            else throw std::runtime_error ("unknown option " + a);
        }
        if (bits != 16 && bits != 24 && bits != 32) throw std::runtime_error ("--bits must be 16, 24 or 32");

        std::string text;
        if (! readFileText (u8path (args[2]), text)) throw std::runtime_error ("cannot read plan " + args[2]);
        Json plan = Json::parse (text);
        if (opt.sampleRate <= 0) opt.sampleRate = (int) plan["render"].num ("sample_rate", 48000);

        auto t0 = std::chrono::steady_clock::now();
        RenderResult res = renderPlan (plan, opt);
        double renderSec = std::chrono::duration<double> (std::chrono::steady_clock::now() - t0).count();

        float peak = 0;
        for (auto& ch : res.out) for (float x : ch) peak = std::max (peak, std::fabs (x));

        std::string err;
        if (! writeWav (u8path (args[3]), res.out, res.frames, opt.sampleRate, bits, err))
            throw std::runtime_error (err);

        Json st = res.stats;
        st.set ("out", Json::string (args[3]));
        st.set ("sample_rate", Json::number (opt.sampleRate));
        st.set ("seconds", Json::number (res.audioSeconds));
        st.set ("render_sec", Json::number (std::round (renderSec * 1000) / 1000));
        st.set ("realtime_x", Json::number (std::round (res.audioSeconds / std::max (1e-6, renderSec) * 10) / 10));
        st.set ("peak_dbfs", Json::number (std::round (gainToDb (peak) * 100) / 100));
        st.set ("peak_ram_mb", Json::number (std::round (peakRamMb())));
        Json w = Json::array();
        for (auto& s : res.warnings) w.push (Json::string (s));
        st.set ("warnings", w);
        std::string dump = st.dump (1);
        if (! statsPath.empty())
        {
            FILE* f = _wfopen (u8path (statsPath).c_str(), L"wb");
            if (f) { fwrite (dump.data(), 1, dump.size(), f); fclose (f); }
        }
        std::cout << dump << std::endl;
        std::cout << "RENDER_OK" << std::endl;
        return 0;
    }
    catch (const std::exception& ex)
    {
        std::cerr << "ERROR " << ex.what() << std::endl;
        return 1;
    }
}
