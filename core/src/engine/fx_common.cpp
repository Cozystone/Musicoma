// Musicoma Engine — 내장 이펙트 공통 부품 구현 + 공장(createBuiltinFx)
#include "fx_common.h"
#include <algorithm>
#include <cstdlib>
#include <cstring>

namespace mc {

std::unique_ptr<Device> createBuiltinFx (const std::string& name)
{
    using namespace fx;
    if (equalsNoCase (name, "eq") || equalsNoCase (name, "4bandeq"))                 return makeEq();
    if (equalsNoCase (name, "compressor"))                                              return makeCompressor();
    if (equalsNoCase (name, "reverb"))                                                  return makeReverb();
    if (equalsNoCase (name, "delay"))                                                   return makeDelay();
    if (equalsNoCase (name, "chorus"))                                                  return makeChorus();
    if (equalsNoCase (name, "phaser"))                                                  return makePhaser();
    if (equalsNoCase (name, "lowpass") || equalsNoCase (name, "filter"))                return makeLowpass();
    if (equalsNoCase (name, "pitchshift") || equalsNoCase (name, "pitchshifter"))       return makePitchShifter();
    if (equalsNoCase (name, "drive") || equalsNoCase (name, "overdrive") || equalsNoCase (name, "distortion")) return makeDrive();
    return nullptr;
}

std::vector<std::string> builtinFxNames()
{
    return { "eq", "compressor", "reverb", "delay", "chorus", "phaser", "lowpass", "pitchshift", "drive" };
}

namespace fx {

static std::string sprintfStr (const char* f, double v)
{
    char b[64];
    std::snprintf (b, sizeof (b), f, v);
    return b;
}

std::string fmtHz (double v)      { char b[64]; std::snprintf (b, sizeof (b), "%lld Hz", (long long) std::llround (v)); return b; }
std::string fmtDb (double v)      { return sprintfStr ("%+.2f dB", v + 0.0); }   // -0.0 → +0.00
std::string fmtQ (double v)       { return sprintfStr ("%.3f", v); }
std::string fmtMs (double v)      { return sprintfStr ("%.1f ms", v); }
std::string fmtRatio (double v)   { return sprintfStr ("%.2f : 1", v); }
std::string fmtPercent (double v) { char b[64]; std::snprintf (b, sizeof (b), "%lld%%", (long long) std::llround (v * 100.0)); return b; }

bool parseNumberText (const std::string& text, double& out)
{
    std::string t;
    for (char c : text) t += (char) ((c >= 'A' && c <= 'Z') ? c - 'A' + 'a' : c);
    if (t.find ("-inf") != std::string::npos) { out = -1e9; return true; }
    const char* s = t.c_str();
    while (*s && ! ((*s >= '0' && *s <= '9') || *s == '-' || *s == '+' || *s == '.')) ++s;
    if (! *s) return false;
    char* end = nullptr;
    double v = std::strtod (s, &end);
    if (end == s) return false;
    while (*end == ' ') ++end;
    if (*end == 'k') v *= 1000.0;
    if (t.find ('%') != std::string::npos) v /= 100.0;
    out = v;
    return true;
}

void FxBase::defineParams (std::vector<ParamDef> d)
{
    defs = std::move (d);
    values.resize (defs.size());
    for (size_t i = 0; i < defs.size(); ++i) values[i] = defs[i].def;
}

int FxBase::findParam (const std::string& idOrName) const
{
    for (size_t i = 0; i < defs.size(); ++i)
        if (equalsNoCase (defs[i].id, idOrName)) return (int) i;
    for (size_t i = 0; i < defs.size(); ++i)
        if (equalsNoCase (defs[i].name, idOrName)) return (int) i;
    return -1;
}

std::vector<ParamInfo> FxBase::params()
{
    std::vector<ParamInfo> out;
    out.reserve (defs.size());
    for (size_t i = 0; i < defs.size(); ++i)
    {
        ParamInfo p;
        p.id = defs[i].id;
        p.name = defs[i].name;
        p.value = values[i];
        p.min = defs[i].min;
        p.max = defs[i].max;
        p.def = defs[i].def;
        p.text = defs[i].format ? defs[i].format (values[i]) : sprintfStr ("%g", values[i]);
        out.push_back (std::move (p));
    }
    return out;
}

bool FxBase::setParam (const std::string& idOrName, double value)
{
    int i = findParam (idOrName);
    if (i < 0) return false;
    if (! std::isfinite (value)) return true;
    double v = std::clamp (value, defs[(size_t) i].min, defs[(size_t) i].max);
    values[(size_t) i] = v;
    paramChanged (i);
    return true;
}

bool FxBase::setParamText (const std::string& idOrName, const std::string& text)
{
    int i = findParam (idOrName);
    if (i < 0) return false;
    double v;
    if (! parseSpecialText (i, text, v) && ! parseNumberText (text, v)) return false;
    return setParam (defs[(size_t) i].id, v);
}

Json FxBase::getState()
{
    Json j = Json::object();
    for (size_t i = 0; i < defs.size(); ++i) j.set (defs[i].id, Json::number (values[i]));
    return j;
}

void FxBase::setState (const Json& state)
{
    if (! state.isObj()) return;
    for (auto& kv : state.o)
        if (kv.second.isNum())
            setParam (kv.first, kv.second.n);
}

// ── RBJ Audio EQ Cookbook ──
static inline double clampF (double sr, double f) { return std::clamp (f, 1.0, sr * 0.4999); }

void Biquad2::lowpass (double sr, double f, double q)
{
    f = clampF (sr, f);
    double w = 2 * kPi * f / sr, c = std::cos (w), al = std::sin (w) / (2 * q);
    setNorm ((1 - c) / 2, 1 - c, (1 - c) / 2, 1 + al, -2 * c, 1 - al);
}

void Biquad2::highpass (double sr, double f, double q)
{
    f = clampF (sr, f);
    double w = 2 * kPi * f / sr, c = std::cos (w), al = std::sin (w) / (2 * q);
    setNorm ((1 + c) / 2, -(1 + c), (1 + c) / 2, 1 + al, -2 * c, 1 - al);
}

void Biquad2::peak (double sr, double f, double q, double gainDb)
{
    f = clampF (sr, f);
    double A = std::pow (10.0, gainDb / 40.0);
    double w = 2 * kPi * f / sr, c = std::cos (w), al = std::sin (w) / (2 * q);
    setNorm (1 + al * A, -2 * c, 1 - al * A, 1 + al / A, -2 * c, 1 - al / A);
}

void Biquad2::lowShelf (double sr, double f, double q, double gainDb)
{
    f = clampF (sr, f);
    double A = std::pow (10.0, gainDb / 40.0);
    double w = 2 * kPi * f / sr, c = std::cos (w), al = std::sin (w) / (2 * q), sq = 2 * std::sqrt (A) * al;
    setNorm (A * ((A + 1) - (A - 1) * c + sq), 2 * A * ((A - 1) - (A + 1) * c), A * ((A + 1) - (A - 1) * c - sq),
             (A + 1) + (A - 1) * c + sq, -2 * ((A - 1) + (A + 1) * c), (A + 1) + (A - 1) * c - sq);
}

void Biquad2::highShelf (double sr, double f, double q, double gainDb)
{
    f = clampF (sr, f);
    double A = std::pow (10.0, gainDb / 40.0);
    double w = 2 * kPi * f / sr, c = std::cos (w), al = std::sin (w) / (2 * q), sq = 2 * std::sqrt (A) * al;
    setNorm (A * ((A + 1) + (A - 1) * c + sq), -2 * A * ((A - 1) + (A + 1) * c), A * ((A + 1) + (A - 1) * c - sq),
             (A + 1) - (A - 1) * c + sq, 2 * ((A - 1) - (A + 1) * c), (A + 1) - (A - 1) * c - sq);
}

} // namespace fx
} // namespace mc
