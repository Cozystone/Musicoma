#include "util.h"
#include <fstream>
#include <iostream>
#include <mutex>

#ifdef _WIN32
 #define WIN32_LEAN_AND_MEAN
 #define NOMINMAX
 #include <windows.h>
#endif

namespace mc {

fs::path u8path (const std::string& s)
{
#ifdef _WIN32
    if (s.empty()) return {};
    int n = MultiByteToWideChar (CP_UTF8, 0, s.data(), (int) s.size(), nullptr, 0);
    std::wstring w ((size_t) n, L'\0');
    MultiByteToWideChar (CP_UTF8, 0, s.data(), (int) s.size(), w.data(), n);
    return fs::path (w);
#else
    return fs::path (s);
#endif
}

std::string pathToU8 (const fs::path& p)
{
#ifdef _WIN32
    auto w = p.wstring();
    if (w.empty()) return {};
    int n = WideCharToMultiByte (CP_UTF8, 0, w.data(), (int) w.size(), nullptr, 0, nullptr, nullptr);
    std::string s ((size_t) n, '\0');
    WideCharToMultiByte (CP_UTF8, 0, w.data(), (int) w.size(), s.data(), n, nullptr, nullptr);
    return s;
#else
    return p.string();
#endif
}

bool readFileBytes (const fs::path& p, std::vector<uint8_t>& out)
{
    std::ifstream f (p, std::ios::binary);
    if (! f) return false;
    f.seekg (0, std::ios::end);
    auto n = (size_t) f.tellg();
    f.seekg (0, std::ios::beg);
    out.resize (n);
    if (n > 0) f.read ((char*) out.data(), (std::streamsize) n);
    return (bool) f || f.eof();
}

bool readFileText (const fs::path& p, std::string& out)
{
    std::vector<uint8_t> b;
    if (! readFileBytes (p, b)) return false;
    size_t skip = (b.size() >= 3 && b[0] == 0xEF && b[1] == 0xBB && b[2] == 0xBF) ? 3 : 0;
    out.assign ((const char*) b.data() + skip, b.size() - skip);
    return true;
}

void logWarn (const std::string& msg)
{
    static std::mutex m;
    std::lock_guard<std::mutex> l (m);
    std::cerr << "WARN " << msg << std::endl;
}

} // namespace mc
