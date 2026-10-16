// Musicoma Engine — VST3 창 스레드(메시지 루프)·uiCall·플러그인 편집 창(Win32 최상위 창 + IPlugFrame).
#include <windows.h>
#include <ole2.h>

#include <atomic>
#include <memory>

#include "vst3_internal.h"
#include "vst3_device.h"
#include "vst3host.h"
#include "../util.h"

#include "pluginterfaces/base/funknownimpl.h"
#include "pluginterfaces/gui/iplugview.h"

using namespace Steinberg;

namespace mc::vst3 {

static constexpr UINT WM_MC_CALL = WM_APP + 0x31;
static constexpr UINT WM_MC_QUIT = WM_APP + 0x32;
static const wchar_t* kMsgClass = L"MusicomaVst3Msg";
static const wchar_t* kEditorClass = L"MusicomaVst3Editor";

static std::atomic<HWND> gMsgHwnd { nullptr };
static std::atomic<DWORD> gUiThreadId { 0 };

struct UiTask
{
    std::function<void()> fn;
    std::atomic<int> state { 0 };   // 0 대기 1 실행 중 2 끝 3 취소
    HANDLE done = CreateEventW (nullptr, TRUE, FALSE, nullptr);
    ~UiTask() { CloseHandle (done); }
};

static void runTask (std::shared_ptr<UiTask>* holder)
{
    auto t = *holder;
    delete holder;
    int expect = 0;
    if (t->state.compare_exchange_strong (expect, 1))
    {
        std::string err;
        guarded ([&] { t->fn(); }, &err);
        if (! err.empty()) logWarn ("VST3 UI call: " + err);
        t->state = 2;
        SetEvent (t->done);
    }
}

bool uiThreadRunning() { return gMsgHwnd.load() != nullptr; }
bool onUiThread() { return gUiThreadId.load() == GetCurrentThreadId(); }

bool uiCall (const std::function<void()>& fn)
{
    HWND h = gMsgHwnd.load();
    if (h == nullptr || onUiThread())
    {
        fn();
        return true;
    }
    auto t = std::make_shared<UiTask>();
    t->fn = fn;
    auto* holder = new std::shared_ptr<UiTask> (t);
    if (! PostMessageW (h, WM_MC_CALL, 0, (LPARAM) holder))
    {
        delete holder;
        fn();
        return true;
    }
    for (;;)
    {
        if (WaitForSingleObject (t->done, 20000) == WAIT_OBJECT_0)
            return true;
        int expect = 0;
        if (t->state.compare_exchange_strong (expect, 3))
        {
            logWarn ("VST3: window thread did not respond in 20 s — call cancelled");
            return false;
        }
        // 이미 실행 중이면 끝날 때까지 기다린다(플러그인 호출 중)
    }
}

static LRESULT CALLBACK msgProc (HWND h, UINT m, WPARAM w, LPARAM l)
{
    if (m == WM_MC_CALL) { runTask (reinterpret_cast<std::shared_ptr<UiTask>*> (l)); return 0; }
    if (m == WM_MC_QUIT) { PostQuitMessage (0); return 0; }
    return DefWindowProcW (h, m, w, l);
}

// ───────────────────────── 편집 창 ─────────────────────────

class PlugFrameImpl : public U::Implements<U::Directly<IPlugFrame>>
{
public:
    explicit PlugFrameImpl (EditorWindow* w) : win (w) {}
    EditorWindow* win;

    tresult PLUGIN_API resizeView (IPlugView* view, ViewRect* r) override
    {
        if (win == nullptr || win->hwnd == nullptr || r == nullptr || view != win->view) return kInvalidArgument;
        HWND h = (HWND) win->hwnd;
        RECT rc { 0, 0, r->getWidth(), r->getHeight() };
        AdjustWindowRectEx (&rc, (DWORD) GetWindowLongPtrW (h, GWL_STYLE), FALSE, (DWORD) GetWindowLongPtrW (h, GWL_EXSTYLE));
        win->inResize = true;
        SetWindowPos (h, nullptr, 0, 0, rc.right - rc.left, rc.bottom - rc.top, SWP_NOMOVE | SWP_NOZORDER | SWP_NOACTIVATE);
        RECT cr;
        GetClientRect (h, &cr);
        ViewRect nr (0, 0, cr.right, cr.bottom);
        view->onSize (&nr);
        win->inResize = false;
        return kResultTrue;
    }
};

static LRESULT CALLBACK editorProc (HWND h, UINT m, WPARAM w, LPARAM l)
{
    auto* ew = reinterpret_cast<EditorWindow*> (GetWindowLongPtrW (h, GWLP_USERDATA));
    switch (m)
    {
        case WM_SIZE:
            if (ew && ew->view && ! ew->inResize && w != SIZE_MINIMIZED)
            {
                guarded ([&] {
                    if (ew->view->canResize() == kResultTrue)
                    {
                        ViewRect r (0, 0, LOWORD (l), HIWORD (l));
                        ew->view->checkSizeConstraint (&r);
                        ew->view->onSize (&r);
                    }
                });
            }
            return 0;
        case WM_CLOSE:
            if (ew) ew->close();
            else DestroyWindow (h);
            return 0;
        case WM_ERASEBKGND:
            return 1;
        default:
            break;
    }
    return DefWindowProcW (h, m, w, l);
}

static void registerClasses()
{
    static bool done = false;
    if (done) return;
    done = true;
    WNDCLASSEXW wc { sizeof wc };
    wc.lpfnWndProc = msgProc;
    wc.hInstance = GetModuleHandleW (nullptr);
    wc.lpszClassName = kMsgClass;
    RegisterClassExW (&wc);

    WNDCLASSEXW ec { sizeof ec };
    ec.style = CS_DBLCLKS;
    ec.lpfnWndProc = editorProc;
    ec.hInstance = GetModuleHandleW (nullptr);
    ec.hCursor = LoadCursor (nullptr, IDC_ARROW);
    ec.hbrBackground = (HBRUSH) GetStockObject (BLACK_BRUSH);
    ec.hIcon = LoadIcon (nullptr, IDI_APPLICATION);
    ec.lpszClassName = kEditorClass;
    RegisterClassExW (&ec);
}

bool EditorWindow::open (IPlugView* v, const std::string& title, std::string& err)
{
    registerClasses();
    view = v;
    bool ok = false;
    std::string gerr;
    guarded ([&] {
        if (view->isPlatformTypeSupported (kPlatformTypeHWND) != kResultTrue)
        {
            err = "editor does not support HWND";
            return;
        }
        ViewRect r;
        if (view->getSize (&r) != kResultTrue || r.getWidth() <= 0 || r.getHeight() <= 0)
            r = ViewRect (0, 0, 640, 480);
        bool resizable = view->canResize() == kResultTrue;
        DWORD style = resizable ? WS_OVERLAPPEDWINDOW : (WS_OVERLAPPED | WS_CAPTION | WS_SYSMENU | WS_MINIMIZEBOX);
        RECT rc { 0, 0, r.getWidth(), r.getHeight() };
        AdjustWindowRectEx (&rc, style, FALSE, 0);
        auto wt = widen (title);
        HWND h = CreateWindowExW (0, kEditorClass, wt.c_str(), style, CW_USEDEFAULT, CW_USEDEFAULT,
                                  rc.right - rc.left, rc.bottom - rc.top, nullptr, nullptr, GetModuleHandleW (nullptr), nullptr);
        if (h == nullptr) { err = "CreateWindow failed"; return; }
        hwnd = h;
        SetWindowLongPtrW (h, GWLP_USERDATA, (LONG_PTR) this);
        frame = new PlugFrameImpl (this);
        view->setFrame (frame);
        if (view->attached (h, kPlatformTypeHWND) != kResultOk)
        {
            err = "IPlugView::attached failed";
            return;
        }
        ShowWindow (h, SW_SHOWNORMAL);
        SetForegroundWindow (h);
        ok = true;
    }, &gerr);
    if (! gerr.empty()) err = gerr;
    if (! ok)
    {
        // attached 전이면 removed 를 부르지 않는다
        guarded ([&] { if (view) { view->setFrame (nullptr); view->release(); } });
        view = nullptr;
        if (frame) { frame->win = nullptr; frame->release(); frame = nullptr; }
        if (hwnd) { SetWindowLongPtrW ((HWND) hwnd, GWLP_USERDATA, 0); DestroyWindow ((HWND) hwnd); hwnd = nullptr; }
    }
    return ok;
}

void EditorWindow::close()
{
    if (view)
    {
        std::string err;
        guarded ([&] {
            view->removed();
            view->setFrame (nullptr);
            view->release();
        }, &err);
        if (! err.empty()) logWarn ("VST3 editor close: " + err);
        view = nullptr;
    }
    if (frame) { frame->win = nullptr; frame->release(); frame = nullptr; }
    if (hwnd)
    {
        HWND h = (HWND) hwnd;
        hwnd = nullptr;
        SetWindowLongPtrW (h, GWLP_USERDATA, 0);
        DestroyWindow (h);
    }
}

} // namespace mc::vst3

namespace mc {

using namespace mc::vst3;

void runVst3WindowThread()
{
    HRESULT ole = OleInitialize (nullptr);   // 드래그·드롭·클립보드를 쓰는 플러그인용(STA)
    registerClasses();
    HWND h = CreateWindowExW (0, kMsgClass, L"", 0, 0, 0, 0, 0, HWND_MESSAGE, nullptr, GetModuleHandleW (nullptr), nullptr);
    if (h == nullptr)
    {
        logWarn ("VST3 window thread: cannot create message window");
        if (SUCCEEDED (ole)) OleUninitialize();
        return;
    }
    gUiThreadId = GetCurrentThreadId();
    gMsgHwnd = h;

    MSG msg;
    while (GetMessageW (&msg, nullptr, 0, 0) > 0)
    {
        TranslateMessage (&msg);
        DispatchMessageW (&msg);
    }

    // 새 호출은 바로 실행되게 하고, 남은 호출은 여기서 처리
    gMsgHwnd = nullptr;
    while (PeekMessageW (&msg, h, WM_MC_CALL, WM_MC_CALL, PM_REMOVE))
        runTask (reinterpret_cast<std::shared_ptr<UiTask>*> (msg.lParam));
    DestroyWindow (h);
    gUiThreadId = 0;
    if (SUCCEEDED (ole)) OleUninitialize();
}

void stopVst3WindowThread()
{
    if (HWND h = gMsgHwnd.load())
        PostMessageW (h, WM_MC_QUIT, 0, 0);
}

} // namespace mc
