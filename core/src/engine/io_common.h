// Musicoma Engine — io_* 공용 도우미(UTF-8 변환·COM 초기화). Windows 전용.
#pragma once
#include <windows.h>
#include <objbase.h>
#include <cstdio>
#include <string>

namespace mc::io {

inline std::string toUtf8 (const wchar_t* w)
{
    if (! w || ! *w) return {};
    int n = WideCharToMultiByte (CP_UTF8, 0, w, -1, nullptr, 0, nullptr, nullptr);
    if (n <= 1) return {};
    std::string s ((size_t) n - 1, '\0');
    WideCharToMultiByte (CP_UTF8, 0, w, -1, s.data(), n, nullptr, nullptr);
    return s;
}

inline std::wstring fromUtf8 (const std::string& s)
{
    if (s.empty()) return {};
    int n = MultiByteToWideChar (CP_UTF8, 0, s.data(), (int) s.size(), nullptr, 0);
    std::wstring w ((size_t) n, L'\0');
    MultiByteToWideChar (CP_UTF8, 0, s.data(), (int) s.size(), w.data(), n);
    return w;
}

inline std::wstring lowerW (std::wstring w)
{
    if (! w.empty()) CharLowerBuffW (w.data(), (DWORD) w.size());   // 유니코드 소문자화(한글은 그대로)
    return w;
}

/** 스레드 단위 COM 초기화. 이미 다른 모드로 초기화돼 있으면(RPC_E_CHANGED_MODE) 그대로 쓰고 해제하지 않는다. */
struct ComScope
{
    HRESULT hr;
    ComScope()  { hr = CoInitializeEx (nullptr, COINIT_MULTITHREADED); }
    ~ComScope() { if (SUCCEEDED (hr)) CoUninitialize(); }
    bool ok() const { return SUCCEEDED (hr) || hr == RPC_E_CHANGED_MODE; }
};

inline std::string hrText (const char* what, HRESULT hr)
{
    char buf[160];
    snprintf (buf, sizeof (buf), "%s 실패 (HRESULT 0x%08lX)", what, (unsigned long) hr);
    return buf;
}

} // namespace mc::io
