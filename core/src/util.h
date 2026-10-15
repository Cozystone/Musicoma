// Musicoma Core — 공용 도구 (파일 경로, dB, 로그)
#pragma once
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <filesystem>
#include <string>
#include <vector>

namespace mc {

namespace fs = std::filesystem;

/** UTF-8 문자열 → 경로 (Windows 에서 한글 경로가 깨지지 않게) */
fs::path u8path (const std::string& s);
std::string pathToU8 (const fs::path& p);

bool readFileBytes (const fs::path& p, std::vector<uint8_t>& out);
bool readFileText (const fs::path& p, std::string& out);

inline float dbToGain (double db)   { return db <= -150.0 ? 0.0f : (float) std::pow (10.0, db / 20.0); }
inline double gainToDb (double g)   { return g <= 1e-9 ? -180.0 : 20.0 * std::log10 (g); }

template <typename T> T clampv (T v, T lo, T hi) { return v < lo ? lo : (v > hi ? hi : v); }

void logWarn (const std::string& msg);

} // namespace mc
