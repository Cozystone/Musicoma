// Musicoma Engine — VST3 모듈 올리기·스캔·공용 도구(문자열·base64·SEH·호스트 컨텍스트).
// Steinberg VST3 SDK 3.8.1(MIT)의 hosting/module.cpp(PluginFactory·ClassInfo)와 hostclasses.cpp 를 쓴다.
#include <windows.h>

#include <algorithm>
#include <cstring>
#include <map>
#include <mutex>

#include "vst3_internal.h"
#include "vst3host.h"
#include "../json.h"
#include "../util.h"

#include "pluginterfaces/vst/ivstaudioprocessor.h"
#include "pluginterfaces/vst/ivstcomponent.h"
#include "public.sdk/source/vst/hosting/hostclasses.h"

using namespace Steinberg;

namespace mc::vst3 {

// ───────────────────────── 문자열 ─────────────────────────

std::string toUtf8 (const Vst::TChar* s, int maxLen)
{
    if (s == nullptr) return {};
    int len = 0;
    while ((maxLen < 0 || len < maxLen) && s[len] != 0) ++len;
    if (len == 0) return {};
    auto* w = reinterpret_cast<const wchar_t*> (s);
    int n = WideCharToMultiByte (CP_UTF8, 0, w, len, nullptr, 0, nullptr, nullptr);
    std::string out ((size_t) n, '\0');
    WideCharToMultiByte (CP_UTF8, 0, w, len, out.data(), n, nullptr, nullptr);
    return out;
}

std::wstring widen (const std::string& s)
{
    if (s.empty()) return {};
    int n = MultiByteToWideChar (CP_UTF8, 0, s.data(), (int) s.size(), nullptr, 0);
    std::wstring out ((size_t) n, L'\0');
    MultiByteToWideChar (CP_UTF8, 0, s.data(), (int) s.size(), out.data(), n);
    return out;
}

std::u16string toUtf16 (const std::string& s)
{
    auto w = widen (s);
    return std::u16string (w.begin(), w.end());
}

std::string lower (std::string s)
{
    for (auto& c : s)
        if (c >= 'A' && c <= 'Z') c = (char) (c - 'A' + 'a');
    return s;
}

// ───────────────────────── base64 ─────────────────────────

static const char* kB64 = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

std::string b64encode (const void* data, size_t n)
{
    auto* p = static_cast<const uint8_t*> (data);
    std::string out;
    out.reserve ((n + 2) / 3 * 4);
    size_t i = 0;
    for (; i + 2 < n; i += 3)
    {
        uint32_t v = (uint32_t) p[i] << 16 | (uint32_t) p[i + 1] << 8 | p[i + 2];
        out += kB64[v >> 18 & 63]; out += kB64[v >> 12 & 63]; out += kB64[v >> 6 & 63]; out += kB64[v & 63];
    }
    if (i < n)
    {
        uint32_t v = (uint32_t) p[i] << 16 | (i + 1 < n ? (uint32_t) p[i + 1] << 8 : 0);
        out += kB64[v >> 18 & 63]; out += kB64[v >> 12 & 63];
        out += i + 1 < n ? kB64[v >> 6 & 63] : '=';
        out += '=';
    }
    return out;
}

bool b64decode (const std::string& s, std::vector<uint8_t>& out)
{
    int8_t tbl[256];
    memset (tbl, -1, sizeof tbl);
    for (int i = 0; i < 64; ++i) tbl[(uint8_t) kB64[i]] = (int8_t) i;
    tbl[(uint8_t) '-'] = 62; tbl[(uint8_t) '_'] = 63;   // url-safe 도 받아 준다
    out.clear();
    out.reserve (s.size() * 3 / 4);
    uint32_t acc = 0;
    int bits = 0;
    for (char ch : s)
    {
        if (ch == '=' ) break;
        if (ch == '\n' || ch == '\r' || ch == ' ' || ch == '\t') continue;
        int v = tbl[(uint8_t) ch];
        if (v < 0) return false;
        acc = acc << 6 | (uint32_t) v;
        bits += 6;
        if (bits >= 8) { bits -= 8; out.push_back ((uint8_t) (acc >> bits & 0xFF)); }
    }
    return true;
}

// ───────────────────────── SEH ─────────────────────────

bool sehCall (RawFn fn, void* ctx, unsigned long* code)
{
    __try
    {
        fn (ctx);
        return true;
    }
    __except (EXCEPTION_EXECUTE_HANDLER)
    {
        if (code) *code = GetExceptionCode();
        return false;
    }
}

// ───────────────────────── 호스트 컨텍스트 ─────────────────────────

namespace {
class MusicomaHostApp : public Vst::HostApplication
{
public:
    tresult PLUGIN_API getName (Vst::String128 name) override
    {
        const char16_t* n = u"Musicoma";
        int i = 0;
        for (; n[i] && i < 127; ++i) name[i] = n[i];
        name[i] = 0;
        return kResultOk;
    }
};
} // namespace

FUnknown* hostContext()
{
    static MusicomaHostApp* app = new MusicomaHostApp();   // 프로세스 끝까지 둔다(플러그인이 잡고 있을 수 있음)
    return app;
}

// ───────────────────────── 모듈 ─────────────────────────

using GetFactoryProc = IPluginFactory* (PLUGIN_API*) ();
using InitExitProc = bool (PLUGIN_API*) ();

static std::mutex gModMutex;
static std::map<std::string, std::weak_ptr<LoadedModule>> gModules;

LoadedModule::~LoadedModule()
{
    // 팩토리를 먼저 놓고 ExitDll → FreeLibrary
    std::string err;
    guarded ([&] {
        factory = VST3::Hosting::PluginFactory (nullptr);
        if (hmodule)
            if (auto ex = (InitExitProc) GetProcAddress ((HMODULE) hmodule, "ExitDll"))
                ex();
    }, &err);
    if (! err.empty()) logWarn ("VST3 unload " + path + ": " + err);
    if (hmodule) FreeLibrary ((HMODULE) hmodule);
}

/** 번들이면 Contents/x86_64-win/<이름>.vst3, 아니면 파일 그대로 */
static fs::path binaryPath (const fs::path& p)
{
    std::error_code ec;
    if (fs::is_directory (p, ec))
        return p / "Contents" / "x86_64-win" / p.filename();
    return p;
}

ModulePtr loadModule (const std::string& path, std::string& error)
{
    std::lock_guard<std::mutex> lk (gModMutex);
    auto key = lower (path);
    if (auto it = gModules.find (key); it != gModules.end())
        if (auto m = it->second.lock())
            return m;

    fs::path bin = binaryPath (u8path (path));
    std::error_code ec;
    if (! fs::exists (bin, ec))
    {
        error = "VST3 binary not found: " + pathToU8 (bin);
        return nullptr;
    }
    HMODULE h = nullptr;
    std::string gerr;
    bool ok = guarded ([&] {
        h = LoadLibraryExW (bin.wstring().c_str(), nullptr, LOAD_WITH_ALTERED_SEARCH_PATH);
    }, &gerr);
    if (! ok || h == nullptr)
    {
        error = "LoadLibrary failed for " + pathToU8 (bin) + (gerr.empty() ? " (error " + std::to_string (GetLastError()) + ")" : ": " + gerr);
        return nullptr;
    }
    auto m = std::make_shared<LoadedModule>();
    m->path = path;
    m->hmodule = h;

    auto getFactory = (GetFactoryProc) GetProcAddress (h, "GetPluginFactory");
    if (getFactory == nullptr)
    {
        error = "not a VST3 module (no GetPluginFactory): " + path;
        return nullptr;   // m 소멸자가 FreeLibrary
    }
    IPluginFactory* raw = nullptr;
    bool initOk = true;
    ok = guarded ([&] {
        if (auto init = (InitExitProc) GetProcAddress (h, "InitDll"))
            initOk = init();
        if (initOk)
            raw = getFactory();
    }, &gerr);
    if (! ok) { error = "InitDll/GetPluginFactory crashed: " + gerr; m->hmodule = nullptr; return nullptr; }  // 망가진 DLL 은 내리지 않는다
    if (! initOk) { error = "InitDll failed: " + path; return nullptr; }
    if (raw == nullptr) { error = "GetPluginFactory returned null: " + path; return nullptr; }
    m->factory = VST3::Hosting::PluginFactory (owned (raw));
    guarded ([&] { m->factory.setHostContext (hostContext()); });
    gModules[key] = m;
    return m;
}

} // namespace mc::vst3

// ───────────────────────── 스캔 ─────────────────────────

namespace mc {

using namespace mc::vst3;

static std::string cidHex (const VST3::UID& uid)
{
    return uid.toString (false);
}

/** moduleinfo.json(Contents/Resources) 으로 목록 만들기 — 팩토리를 못 올릴 때 */
static bool scanModuleInfo (const fs::path& bundle, std::vector<Vst3Desc>& out, std::string& err)
{
    fs::path mi = bundle / "Contents" / "Resources" / "moduleinfo.json";
    std::string text;
    if (! readFileText (mi, text)) { err = "no moduleinfo.json"; return false; }
    Json j;
    try { j = Json::parse (text); }
    catch (const std::exception& e) { err = std::string ("moduleinfo.json parse: ") + e.what(); return false; }
    std::string fvendor = j["Factory Info"].str ("Vendor");
    auto* classes = j.find ("Classes");
    if (! classes || ! classes->isArr()) { err = "moduleinfo.json: no Classes"; return false; }
    bool any = false;
    for (auto& c : classes->a)
    {
        if (c.str ("Category") != kVstAudioEffectClass) continue;
        Vst3Desc d;
        d.name = c.str ("Name");
        d.vendor = c.str ("Vendor", fvendor);
        if (d.vendor.empty()) d.vendor = fvendor;
        d.cid = c.str ("CID");
        std::string cat;
        if (auto* sc = c.find ("Sub Categories"); sc && sc->isArr())
            for (auto& s : sc->a) { if (! cat.empty()) cat += "|"; cat += s.s; }
        d.category = cat;
        d.instrument = cat.find ("Instrument") != std::string::npos;
        d.path = pathToU8 (bundle);
        out.push_back (d);
        any = true;
    }
    if (! any) err = "moduleinfo.json: no audio module classes";
    return any;
}

static void scanOne (const fs::path& p, std::vector<Vst3Desc>& out, std::vector<std::string>* warnings)
{
    std::string path = pathToU8 (p);
    std::string err;
    auto mod = loadModule (path, err);
    if (mod)
    {
        std::string ferr;
        std::vector<Vst3Desc> found;
        bool ok = guarded ([&] {
            auto finfo = mod->factory.info();
            std::string fvendor = finfo.vendor();
            for (auto& ci : mod->factory.classInfos())
            {
                if (ci.category() != kVstAudioEffectClass) continue;
                Vst3Desc d;
                d.name = ci.name();
                d.vendor = ci.vendor().empty() ? fvendor : ci.vendor();
                d.category = ci.subCategoriesString();
                d.cid = cidHex (ci.ID());
                d.instrument = d.category.find ("Instrument") != std::string::npos;
                d.path = path;
                found.push_back (d);
            }
        }, &ferr);
        if (ok && ! found.empty())
        {
            out.insert (out.end(), found.begin(), found.end());
            return;
        }
        err = ok ? "no audio module classes in factory" : "factory query crashed: " + ferr;
    }
    // 팩토리 실패 → moduleinfo.json
    std::string merr;
    if (scanModuleInfo (p, out, merr))
    {
        if (warnings) warnings->push_back (path + ": factory failed (" + err + "), used moduleinfo.json");
        return;
    }
    if (warnings) warnings->push_back (path + ": " + err + "; " + merr);
}

std::vector<Vst3Desc> scanVst3 (const std::vector<std::string>& dirs, std::vector<std::string>* warnings)
{
    std::vector<Vst3Desc> out;
    uiCall ([&] {
        std::vector<fs::path> mods;
        for (auto& d : dirs)
        {
            fs::path root = u8path (d);
            std::error_code ec;
            if (! fs::exists (root, ec))
            {
                if (warnings) warnings->push_back (d + ": folder not found");
                continue;
            }
            if (lower (pathToU8 (root.extension())) == ".vst3") { mods.push_back (root); continue; }
            fs::recursive_directory_iterator it (root, fs::directory_options::skip_permission_denied, ec), end;
            for (; ! ec && it != end; it.increment (ec))
            {
                const auto& e = *it;
                if (lower (pathToU8 (e.path().extension())) != ".vst3") continue;
                mods.push_back (e.path());
                std::error_code ec2;
                if (e.is_directory (ec2)) it.disable_recursion_pending();   // 번들 안은 보지 않는다
            }
        }
        std::sort (mods.begin(), mods.end());
        for (auto& m : mods)
            scanOne (m, out, warnings);
    });
    return out;
}

} // namespace mc
