// Musicoma Engine — VST3 호스팅 내부 도구(모듈 캐시·창 스레드 호출·SEH 보호·문자열).
// vst3_*.cpp 끼리만 쓴다. 바깥 공개 API 는 vst3host.h / vst3_device.h.
#pragma once
#include <functional>
#include <memory>
#include <string>
#include <vector>

#include "pluginterfaces/base/funknown.h"
#include "pluginterfaces/base/ipluginbase.h"
#include "pluginterfaces/gui/iplugview.h"
#include "pluginterfaces/vst/vsttypes.h"
#include "public.sdk/source/vst/hosting/module.h"

namespace mc::vst3 {

// ── 문자열 ──
std::string toUtf8 (const Steinberg::Vst::TChar* s, int maxLen = -1);
std::u16string toUtf16 (const std::string& s);
std::wstring widen (const std::string& s);
std::string lower (std::string s);

// ── base64 ──
std::string b64encode (const void* data, size_t n);
bool b64decode (const std::string& s, std::vector<uint8_t>& out);

// ── SEH 보호: 플러그인 안에서 접근 위반이 나도 엔진이 죽지 않게 ──
using RawFn = void (*) (void*);
/** fn(ctx) 를 SEH·C++ 예외 보호 아래 부른다. 예외가 나면 false + code */
bool sehCall (RawFn fn, void* ctx, unsigned long* code);

template <typename F>
bool guarded (F&& f, std::string* err = nullptr)
{
    struct Ctx { F* f; bool cppFail = false; std::string msg; } ctx { &f };
    RawFn raw = [] (void* p) {
        auto* c = static_cast<Ctx*> (p);
        try { (*c->f)(); }
        catch (const std::exception& e) { c->cppFail = true; c->msg = e.what(); }
        catch (...) { c->cppFail = true; c->msg = "unknown C++ exception"; }
    };
    unsigned long code = 0;
    if (! sehCall (raw, &ctx, &code))
    {
        if (err) { char b[64]; snprintf (b, sizeof b, "plugin crashed (SEH 0x%08lX)", code); *err = b; }
        return false;
    }
    if (ctx.cppFail)
    {
        if (err) *err = "plugin threw: " + ctx.msg;
        return false;
    }
    return true;
}

// ── 창(UI) 스레드 ──
/** 창 스레드가 돌고 있으면 거기서 fn 을 동기 실행(끝날 때까지 기다림), 아니면 지금 스레드에서 바로.
    JUCE 계열 플러그인은 처음 만든 스레드를 메시지 스레드로 삼으므로, 생성·컨트롤러·편집 창을 모두 한 스레드로 모은다. */
bool uiCall (const std::function<void()>& fn);   // 창 스레드가 20초 넘게 응답 없으면 취소하고 false
bool uiThreadRunning();
bool onUiThread();

// ── 모듈(.vst3 DLL) ──
struct LoadedModule
{
    std::string path;                       // 번들/파일 경로(UTF-8)
    void* hmodule = nullptr;                // HMODULE
    VST3::Hosting::PluginFactory factory { nullptr };
    ~LoadedModule();
};
using ModulePtr = std::shared_ptr<LoadedModule>;

/** 같은 경로는 한 번만 올린다(인스턴스가 살아 있는 동안 공유). 실패 시 nullptr + error */
ModulePtr loadModule (const std::string& path, std::string& error);

/** 호스트 컨텍스트(IHostApplication) — 프로세스 하나 */
Steinberg::FUnknown* hostContext();

// ── 편집 창(창 스레드에서만 만든다/닫는다) ──
class PlugFrameImpl;
struct EditorWindow
{
    Steinberg::IPlugView* view = nullptr;   // 참조 하나 소유
    void* hwnd = nullptr;                   // HWND
    PlugFrameImpl* frame = nullptr;
    bool inResize = false;

    /** controller->createView("editor") 로 만든 뷰를 최상위 창에 붙인다. 실패 시 false + err(뷰는 놓음) */
    bool open (Steinberg::IPlugView* view, const std::string& title, std::string& err);
    void close();
    bool isOpen() const { return hwnd != nullptr; }
    ~EditorWindow() { close(); }
};

} // namespace mc::vst3
