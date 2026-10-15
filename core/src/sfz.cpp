#include "sfz.h"
#include <algorithm>
#include <cctype>
#include <cstdlib>
#include <cstring>

namespace mc {

//==============================================================================
int parseNoteOrNumber (const std::string& raw)
{
    std::string s;
    for (char c : raw) if (! std::isspace ((unsigned char) c)) s += c;
    if (s.empty()) return -1000;

    char c0 = (char) std::tolower ((unsigned char) s[0]);
    if (c0 >= 'a' && c0 <= 'g')
    {
        static const int base[] = { 9, 11, 0, 2, 4, 5, 7 };   // a b c d e f g
        int semi = base[c0 - 'a'];
        size_t i = 1;
        if (i < s.size() && s[i] == '#') { ++semi; ++i; }
        else if (i < s.size() && (s[i] == 'b' || s[i] == 'B') && i + 1 < s.size()) { --semi; ++i; }
        char* end = nullptr;
        long oct = std::strtol (s.c_str() + i, &end, 10);
        if (end == s.c_str() + i) return -1000;
        return (int) ((oct + 1) * 12 + semi);
    }
    char* end = nullptr;
    double v = std::strtod (s.c_str(), &end);
    if (end == s.c_str()) return -1000;
    return (int) std::lround (v);
}

const Curve& Instrument::curve (int index) const
{
    auto it = curves.find (index);
    if (it != curves.end()) return it->second;
    return curves.at (0);
}

namespace {

double toF (const std::string& v, double fallback = 0.0)
{
    char* end = nullptr;
    double d = std::strtod (v.c_str(), &end);
    return end == v.c_str() ? fallback : d;
}

bool isIdent (char c) { return std::isalnum ((unsigned char) c) || c == '_'; }

/** 'xfin_locc12' → base='xfin_locc', num=12 (끝의 숫자를 뗀다) */
bool splitTrailingNumber (const std::string& name, std::string& base, int& num)
{
    size_t i = name.size();
    while (i > 0 && std::isdigit ((unsigned char) name[i - 1])) --i;
    if (i == name.size() || i == 0) return false;
    base = name.substr (0, i);
    num = std::atoi (name.c_str() + i);
    return true;
}

std::string genericName (const std::string& name)
{
    std::string out;
    bool inNum = false;
    for (char c : name)
    {
        if (std::isdigit ((unsigned char) c)) { if (! inNum) out += 'N'; inNum = true; }
        else { out += c; inNum = false; }
    }
    return out;
}

//==============================================================================
// 전처리: 주석 제거, #define / #include 를 앞에서부터 차례로 펼친다.
struct Pre
{
    fs::path rootDir;
    std::map<std::string, std::string> defines;
    Instrument* inst = nullptr;
    int depth = 0;
    std::string out;

    std::string substitute (const std::string& s)
    {
        if (s.find ('$') == std::string::npos) return s;
        std::string r;
        for (size_t i = 0; i < s.size();)
        {
            if (s[i] != '$') { r += s[i++]; continue; }
            size_t j = i + 1;
            while (j < s.size() && isIdent (s[j])) ++j;
            // 정의된 이름 중 가장 긴 앞부분과 맞춘다
            bool done = false;
            for (size_t k = j; k > i + 1; --k)
            {
                auto it = defines.find (s.substr (i, k - i));
                if (it != defines.end()) { r += it->second; i = k; done = true; break; }
            }
            if (! done) { r += s[i++]; }
        }
        return r;
    }

    void file (const fs::path& p)
    {
        if (depth > 32) { inst->warnings.push_back ("#include too deep: " + pathToU8 (p)); return; }
        std::string text;
        if (! readFileText (p, text)) { inst->warnings.push_back ("cannot read " + pathToU8 (p)); return; }
        ++depth;
        bool inBlock = false;
        size_t ls = 0;
        while (ls <= text.size())
        {
            size_t le = text.find ('\n', ls);
            if (le == std::string::npos) le = text.size();
            std::string line = text.substr (ls, le - ls);
            ls = le + 1;
            if (! line.empty() && line.back() == '\r') line.pop_back();

            // 블록 주석 / 줄 주석
            std::string clean;
            for (size_t i = 0; i < line.size(); ++i)
            {
                if (inBlock)
                {
                    if (line.compare (i, 2, "*/") == 0) { inBlock = false; ++i; }
                    continue;
                }
                if (line.compare (i, 2, "/*") == 0) { inBlock = true; ++i; continue; }
                if (line.compare (i, 2, "//") == 0) break;
                clean += line[i];
            }
            processLine (clean);
            out += '\n';
            if (le == text.size()) break;
        }
        --depth;
    }

    void processLine (const std::string& line)
    {
        size_t pos = 0;
        while (pos < line.size())
        {
            size_t h = line.find ('#', pos);
            while (h != std::string::npos && line.compare (h, 7, "#define") != 0 && line.compare (h, 8, "#include") != 0)
                h = line.find ('#', h + 1);

            if (h == std::string::npos) { out += substitute (line.substr (pos)); return; }

            out += substitute (line.substr (pos, h - pos));
            out += '\n';

            if (line.compare (h, 7, "#define") == 0)
            {
                size_t i = h + 7;
                auto skipWs = [&] { while (i < line.size() && std::isspace ((unsigned char) line[i])) ++i; };
                skipWs();
                size_t ns = i;
                while (i < line.size() && ! std::isspace ((unsigned char) line[i])) ++i;
                std::string name = line.substr (ns, i - ns);
                skipWs();
                size_t vs = i;
                while (i < line.size() && ! std::isspace ((unsigned char) line[i])) ++i;
                std::string value = substitute (line.substr (vs, i - vs));
                if (! name.empty()) defines[name] = value;
                pos = i;
            }
            else
            {
                size_t i = h + 8;
                while (i < line.size() && std::isspace ((unsigned char) line[i])) ++i;
                std::string inc;
                if (i < line.size() && line[i] == '"')
                {
                    size_t e = line.find ('"', i + 1);
                    if (e == std::string::npos) e = line.size();
                    inc = line.substr (i + 1, e - i - 1);
                    pos = e + 1;
                }
                else
                {
                    size_t s = i;
                    while (i < line.size() && ! std::isspace ((unsigned char) line[i])) ++i;
                    inc = line.substr (s, i - s);
                    pos = i;
                }
                inc = substitute (inc);
                std::replace (inc.begin(), inc.end(), '\\', '/');
                file (rootDir / u8path (inc));
                out += '\n';
            }
        }
    }
};

//==============================================================================
struct Op { std::string name, value; };

void tokenize (const std::string& text, std::vector<std::pair<std::string, std::vector<Op>>>& sections)
{
    // sections: (헤더 이름, opcodes) — 첫 헤더 앞의 opcode 는 "" 헤더로
    sections.emplace_back ("", std::vector<Op>());
    size_t i = 0, n = text.size();
    while (i < n)
    {
        char c = text[i];
        if (std::isspace ((unsigned char) c)) { ++i; continue; }
        if (c == '<')
        {
            size_t e = text.find ('>', i);
            if (e == std::string::npos) break;
            std::string h = text.substr (i + 1, e - i - 1);
            for (auto& ch : h) ch = (char) std::tolower ((unsigned char) ch);
            sections.emplace_back (h, std::vector<Op>());
            i = e + 1;
            continue;
        }
        // opcode 이름
        size_t ns = i;
        while (i < n && (isIdent (text[i]) || text[i] == '$')) ++i;
        if (i >= n || text[i] != '=' || i == ns)
        {
            // 알 수 없는 조각: 다음 공백까지 건너뜀
            while (i < n && ! std::isspace ((unsigned char) text[i])) ++i;
            continue;
        }
        std::string name = text.substr (ns, i - ns);
        ++i;   // '='
        // 값: 줄 끝, '<', 또는 ' 다음opcode=' 직전까지
        size_t vs = i, ve = i;
        while (i < n && text[i] != '\n' && text[i] != '\r' && text[i] != '<')
        {
            if (std::isspace ((unsigned char) text[i]))
            {
                size_t j = i;
                while (j < n && (text[j] == ' ' || text[j] == '\t')) ++j;
                size_t k = j;
                while (k < n && isIdent (text[k])) ++k;
                if (k > j && k < n && text[k] == '=') { break; }
                i = j;
                continue;
            }
            ++i;
            ve = i;
        }
        std::string value = text.substr (vs, ve - vs);
        while (! value.empty() && std::isspace ((unsigned char) value.back())) value.pop_back();
        sections.back().second.push_back ({ name, value });
    }
}

//==============================================================================
struct Builder
{
    Instrument& inst;
    fs::path rootDir;
    std::string defaultPath;
    std::map<std::pair<int, int>, int> curveAssign;     // (target, cc) → curve, 리전마다 다시 채움

    explicit Builder (Instrument& i) : inst (i) {}

    void unsupported (const std::string& name)
    {
        inst.unsupported[genericName (name)]++;
    }

    static bool modTargetFor (const std::string& base, ModTarget& t)
    {
        static const std::pair<const char*, ModTarget> table[] = {
            { "amplitude", ModTarget::Amplitude }, { "volume", ModTarget::Volume }, { "gain", ModTarget::Volume },
            { "pan", ModTarget::Pan }, { "tune", ModTarget::Pitch }, { "pitch", ModTarget::Pitch },
            { "offset", ModTarget::Offset }, { "delay", ModTarget::Delay },
            { "ampeg_delay", ModTarget::EgDelay }, { "ampeg_attack", ModTarget::EgAttack },
            { "ampeg_hold", ModTarget::EgHold }, { "ampeg_decay", ModTarget::EgDecay },
            { "ampeg_sustain", ModTarget::EgSustain }, { "ampeg_release", ModTarget::EgRelease },
            { "amp_veltrack", ModTarget::AmpVeltrack },
            { "cutoff", ModTarget::Cutoff1 }, { "cutoff1", ModTarget::Cutoff1 }, { "cutoff2", ModTarget::Cutoff2 },
            { "resonance", ModTarget::Resonance1 }, { "resonance1", ModTarget::Resonance1 }, { "resonance2", ModTarget::Resonance2 },
            { "eq1_gain", ModTarget::Eq1Gain }, { "eq2_gain", ModTarget::Eq2Gain }, { "eq3_gain", ModTarget::Eq3Gain },
            { "eq1_freq", ModTarget::Eq1Freq }, { "eq2_freq", ModTarget::Eq2Freq }, { "eq3_freq", ModTarget::Eq3Freq },
        };
        for (auto& e : table)
            if (base == e.first) { t = e.second; return t != ModTarget::Count; }
        return false;
    }

    /** 'X_onccN' / 'X_ccN' / 'XccN'(v1, ampeg_releasecc) / 'X_curveccN' 를 해석한다. 처리했으면 true. */
    bool modOpcode (Region& r, const std::string& name, const std::string& value)
    {
        std::string base; int cc;
        if (! splitTrailingNumber (name, base, cc)) return false;
        auto ends = [&] (const char* suf) { size_t L = std::strlen (suf); return base.size() > L && base.compare (base.size() - L, L, suf) == 0; };
        auto stem = [&] (size_t L) { std::string s = base.substr (0, base.size() - L); if (! s.empty() && s.back() == '_') s.pop_back(); return s; };

        if (ends ("_curvecc"))
        {
            ModTarget t;
            if (modTargetFor (stem (8), t)) { curveAssign[{ (int) t, cc }] = (int) toF (value); return true; }
            return false;
        }
        if (ends ("_smoothcc") || ends ("_stepcc")) { unsupported (name); return true; }

        std::string s;
        if (ends ("_oncc")) s = stem (5);
        else if (ends ("oncc")) s = stem (4);
        else if (ends ("_cc")) s = stem (3);
        else if (ends ("cc")) s = stem (2);
        else return false;

        ModTarget t;
        if (! modTargetFor (s, t)) return false;
        r.mods.push_back ({ t, cc, (float) toF (value), -1 });
        return true;
    }

    FilterType filterType (const std::string& v)
    {
        if (v == "lpf_1p") return FilterType::Lpf1p;
        if (v == "hpf_1p") return FilterType::Hpf1p;
        if (v == "lpf_2p" || v == "lpf_2p_sv") return FilterType::Lpf2p;
        if (v == "hpf_2p" || v == "hpf_2p_sv") return FilterType::Hpf2p;
        if (v == "bpf_2p" || v == "bpf_2p_sv" || v == "bpf_1p") return FilterType::Bpf2p;
        if (v == "brf_2p" || v == "brf_2p_sv" || v == "brf_1p") return FilterType::Brf2p;
        if (v == "lpf_4p") return FilterType::Lpf4p;
        if (v == "hpf_4p") return FilterType::Hpf4p;
        if (v == "lpf_6p") return FilterType::Lpf6p;
        if (v == "hpf_6p") return FilterType::Hpf6p;
        unsupported ("fil_type=" + v);
        return FilterType::Lpf2p;
    }

    int note (const std::string& v) { int k = parseNoteOrNumber (v); return k == -1000 ? 0 : k; }

    void apply (Region& r, const std::string& name, const std::string& value)
    {
        const std::string& n = name;
        auto F = [&] { return (float) toF (value); };
        auto I = [&] { return (int) std::lround (toF (value)); };

        if (n == "sample")
        {
            std::string v = value;
            std::replace (v.begin(), v.end(), '\\', '/');
            if (! v.empty() && v[0] == '*') { r.silence = true; r.sample.clear(); if (v != "*silence") unsupported ("sample=" + v); return; }
            r.silence = false;
            fs::path p = u8path (defaultPath + v);
            if (p.is_relative()) p = rootDir / p;
            r.sample = pathToU8 (p.lexically_normal());
            return;
        }
        if (n == "key") { int k = note (value); r.lokey = r.hikey = r.keycenter = k; return; }
        if (n == "lokey") { r.lokey = note (value); return; }
        if (n == "hikey") { r.hikey = note (value); return; }
        if (n == "pitch_keycenter") { if (value != "sample") r.keycenter = note (value); return; }
        if (n == "lovel") { r.lovel = I(); return; }
        if (n == "hivel") { r.hivel = I(); return; }
        if (n == "lorand") { r.lorand = F(); return; }
        if (n == "hirand") { r.hirand = F(); return; }
        if (n == "seq_length") { r.seqLength = std::max (1, I()); return; }
        if (n == "seq_position") { r.seqPosition = std::max (1, I()); return; }
        if (n == "trigger")
        {
            if (value == "release") r.trigger = Trigger::Release;
            else if (value == "first") r.trigger = Trigger::First;
            else if (value == "legato") r.trigger = Trigger::Legato;
            else if (value == "release_key") r.trigger = Trigger::ReleaseKey;
            else r.trigger = Trigger::Attack;
            return;
        }
        if (n == "group" || n == "polyphony_group") { r.group = (int64_t) toF (value); return; }
        if (n == "off_by") { r.hasOffBy = true; r.offBy = (int64_t) toF (value); return; }
        if (n == "off_mode") { r.offMode = value == "normal" ? OffMode::Normal : value == "time" ? OffMode::Time : OffMode::Fast; return; }
        if (n == "off_time") { r.offTime = F(); r.offMode = OffMode::Time; return; }
        if (n == "delay") { r.delay = F(); return; }
        if (n == "volume" || n == "gain") { r.volume = F(); return; }
        if (n == "group_volume") { r.groupVolume = F(); return; }
        if (n == "master_volume") { r.masterVolume = F(); return; }
        if (n == "global_volume") { r.globalVolume = F(); return; }
        if (n == "amplitude") { r.amplitude = F(); return; }
        if (n == "pan") { r.pan = F(); return; }
        if (n == "width") { r.width = F(); return; }
        if (n == "tune" || n == "pitch") { r.tune = F(); return; }
        if (n == "transpose") { r.transpose = I(); return; }
        if (n == "pitch_keytrack") { r.pitchKeytrack = F(); return; }
        if (n == "bend_up" || n == "bendup") { r.bendUp = F(); return; }
        if (n == "bend_down" || n == "benddown") { r.bendDown = F(); return; }
        if (n == "offset") { r.offset = (int64_t) toF (value); return; }
        if (n == "end") { r.end = (int64_t) toF (value); return; }
        if (n == "loop_mode" || n == "loopmode")
        {
            if (value == "one_shot") r.loopMode = LoopMode::OneShot;
            else if (value == "loop_continuous") r.loopMode = LoopMode::Continuous;
            else if (value == "loop_sustain") r.loopMode = LoopMode::Sustain;
            else r.loopMode = LoopMode::NoLoop;
            return;
        }
        if (n == "loop_start" || n == "loopstart") { r.loopStart = (int64_t) toF (value); return; }
        if (n == "loop_end" || n == "loopend") { r.loopEnd = (int64_t) toF (value); return; }
        if (n == "ampeg_delay") { r.egDelay = F(); return; }
        if (n == "ampeg_attack") { r.egAttack = F(); return; }
        if (n == "ampeg_hold") { r.egHold = F(); return; }
        if (n == "ampeg_decay") { r.egDecay = F(); return; }
        if (n == "ampeg_sustain") { r.egSustain = F(); return; }
        if (n == "ampeg_release") { r.egRelease = F(); return; }
        if (n == "amp_veltrack") { r.ampVeltrack = F(); return; }
        if (n == "amp_keytrack") { r.ampKeytrack = F(); return; }
        if (n == "amp_keycenter") { r.ampKeycenter = note (value); return; }
        if (n == "xfin_lovel") { r.xfinLovel = I(); return; }
        if (n == "xfin_hivel") { r.xfinHivel = I(); return; }
        if (n == "xfout_lovel") { r.xfoutLovel = I(); return; }
        if (n == "xfout_hivel") { r.xfoutHivel = I(); return; }
        if (n == "xfin_lokey") { r.xfinLokey = note (value); return; }
        if (n == "xfin_hikey") { r.xfinHikey = note (value); return; }
        if (n == "xfout_lokey") { r.xfoutLokey = note (value); return; }
        if (n == "xfout_hikey") { r.xfoutHikey = note (value); return; }
        if (n == "xf_velcurve") { r.xfVelPower = value != "gain"; return; }
        if (n == "xf_keycurve") { r.xfKeyPower = value != "gain"; return; }
        if (n == "xf_cccurve") { r.xfCcPower = value != "gain"; return; }
        if (n == "sw_last") { r.swLast = note (value); return; }
        if (n == "sw_down") { r.swDown = note (value); return; }
        if (n == "sw_up") { r.swUp = note (value); return; }
        if (n == "sw_lokey") { inst.swLokey = note (value); return; }
        if (n == "sw_hikey") { inst.swHikey = note (value); return; }
        if (n == "sw_default") { inst.swDefault = note (value); return; }
        if (n == "rt_decay") { r.rtDecay = F(); return; }
        if (n == "polyphony") { r.polyphony = I(); return; }
        if (n == "note_polyphony") { r.notePolyphony = I(); return; }
        if (n == "fil_type" || n == "fil1_type" || n == "filtype") { r.fil[0].type = filterType (value); r.fil[0].typeSet = true; return; }
        if (n == "fil2_type") { r.fil[1].type = filterType (value); r.fil[1].typeSet = true; return; }
        if (n == "cutoff" || n == "cutoff1") { r.fil[0].cutoff = F(); return; }
        if (n == "cutoff2") { r.fil[1].cutoff = F(); return; }
        if (n == "resonance" || n == "resonance1") { r.fil[0].resonance = F(); return; }
        if (n == "resonance2") { r.fil[1].resonance = F(); return; }
        if (n == "fil_keytrack" || n == "fil1_keytrack") { r.fil[0].keytrack = F(); return; }
        if (n == "fil2_keytrack") { r.fil[1].keytrack = F(); return; }
        if (n == "fil_keycenter" || n == "fil1_keycenter") { r.fil[0].keycenter = note (value); return; }
        if (n == "fil2_keycenter") { r.fil[1].keycenter = note (value); return; }
        if (n == "fil_veltrack" || n == "fil1_veltrack") { r.fil[0].veltrack = F(); return; }
        if (n == "fil2_veltrack") { r.fil[1].veltrack = F(); return; }
        if (n.size() >= 6 && n[0] == 'e' && n[1] == 'q' && n[2] >= '1' && n[2] <= '3' && n[3] == '_')
        {
            auto& eq = r.eq[n[2] - '1'];
            std::string what = n.substr (4);
            if (what == "freq") { eq.freq = F(); return; }
            if (what == "bw") { eq.bw = F(); return; }
            if (what == "gain") { eq.gain = F(); return; }
        }

        std::string base; int num;
        if (splitTrailingNumber (n, base, num))
        {
            if (base == "amp_velcurve_") { r.velPoints.emplace_back (num, F()); return; }
            if ((base == "set_cc" || base == "set_hdcc") && num >= 0 && num < 128)
            { inst.defaultCc[(size_t) num] = base == "set_cc" ? F() / 127.0f : F(); return; }
            if (base == "locc" || base == "hicc" || base == "lohdcc" || base == "hihdcc")
            {
                bool lo = base[0] == 'l';
                float v = base.find ("hd") != std::string::npos ? F() * 127.0f : F();
                auto it = std::find_if (r.ccConditions.begin(), r.ccConditions.end(), [&] (const CcRange& c) { return c.cc == num; });
                if (it == r.ccConditions.end()) { r.ccConditions.push_back ({ num, 0.0f, 127.0f }); it = r.ccConditions.end() - 1; }
                (lo ? it->lo : it->hi) = v;
                return;
            }
            if (base == "on_locc" || base == "on_hicc" || base == "start_locc" || base == "start_hicc")
            {
                bool lo = base.find ("locc") != std::string::npos;
                auto it = std::find_if (r.ccTriggers.begin(), r.ccTriggers.end(), [&] (const CcRange& c) { return c.cc == num; });
                if (it == r.ccTriggers.end()) { r.ccTriggers.push_back ({ num, -1.0f, -1.0f }); it = r.ccTriggers.end() - 1; }
                (lo ? it->lo : it->hi) = F();
                return;
            }
            if (base == "xfin_locc" || base == "xfin_hicc" || base == "xfout_locc" || base == "xfout_hicc")
            {
                auto& list = base.compare (0, 4, "xfin") == 0 ? r.xfinCc : r.xfoutCc;
                bool lo = base.find ("locc") != std::string::npos;
                auto it = std::find_if (list.begin(), list.end(), [&] (const CcRange& c) { return c.cc == num; });
                if (it == list.end()) { list.push_back ({ num, 0.0f, 0.0f }); it = list.end() - 1; }
                (lo ? it->lo : it->hi) = F();
                return;
            }
        }

        if (modOpcode (r, n, value)) return;

        // 소리에 영향 없는 표시용 opcode 는 조용히 넘긴다
        static const char* quiet[] = { "region_label", "group_label", "master_label", "global_label", "sw_label", "label_cc",
                                       "lochan", "hichan", "count" };
        for (auto q : quiet)
            if (n.compare (0, std::strlen (q), q) == 0) return;

        unsupported (n);
    }

    void finalize (Region& r)
    {
        // 곡선 지정을 CC 모듈레이션에 붙인다
        for (auto& m : r.mods)
        {
            auto it = curveAssign.find ({ (int) m.target, m.cc });
            m.curve = it != curveAssign.end() ? it->second : 0;
        }
        std::sort (r.velPoints.begin(), r.velPoints.end());
        // 필터: cutoff 만 있고 형식이 없으면 SFZ 기본 lpf_2p
        for (auto& f : r.fil)
            if (f.cutoff > 0 && ! f.typeSet) f.type = FilterType::Lpf2p;
    }
};

void builtinCurves (Instrument& inst)
{
    for (int c = 0; c <= 6; ++c)
    {
        Curve cv;
        for (int i = 0; i < 128; ++i)
        {
            float x = (float) i / 127.0f;
            float y = 0;
            switch (c)
            {
                case 0: y = x; break;
                case 1: y = 2 * x - 1; break;
                case 2: y = 1 - x; break;
                case 3: y = 1 - 2 * x; break;
                case 4: y = x * x; break;
                case 5: y = std::sqrt (x); break;
                case 6: y = std::sqrt (1 - x); break;
            }
            cv.v[(size_t) i] = y;
        }
        inst.curves[c] = cv;
    }
}

void buildCurve (Instrument& inst, const std::vector<Op>& ops)
{
    int index = -1;
    std::vector<std::pair<int, float>> pts;
    for (auto& op : ops)
    {
        if (op.name == "curve_index") index = (int) toF (op.value);
        else if (op.name.size() > 1 && op.name[0] == 'v' && std::isdigit ((unsigned char) op.name[1]))
            pts.emplace_back (std::atoi (op.name.c_str() + 1), (float) toF (op.value));
    }
    if (index < 0) return;
    // 지정 안 된 끝점: v000 = 0, v127 = 1
    std::map<int, float> m (pts.begin(), pts.end());
    if (! m.count (0)) m[0] = 0.0f;
    if (! m.count (127)) m[127] = 1.0f;
    Curve cv;
    auto it = m.begin();
    for (int i = 0; i < 128; ++i)
    {
        while (std::next (it) != m.end() && std::next (it)->first <= i) ++it;
        auto nx = std::next (it);
        if (nx == m.end() || it->first == i) { cv.v[(size_t) i] = it->second; continue; }
        float t = (float) (i - it->first) / (float) (nx->first - it->first);
        cv.v[(size_t) i] = it->second + (nx->second - it->second) * t;
    }
    inst.curves[index] = cv;
}

} // namespace

//==============================================================================
std::shared_ptr<Instrument> loadSfz (const std::string& path, std::string& err)
{
    auto inst = std::make_shared<Instrument>();
    inst->path = path;
    builtinCurves (*inst);
    inst->defaultCc.fill (0.0f);
    // 흔한 기본값 (MIDI 관례): 볼륨 100, 팬 가운데, 익스프레션 최대
    inst->defaultCc[7] = 100.0f / 127.0f;
    inst->defaultCc[10] = 64.0f / 127.0f;
    inst->defaultCc[11] = 1.0f;

    fs::path p = u8path (path);
    if (! fs::exists (p)) { err = "SFZ not found: " + path; return nullptr; }

    Pre pre;
    pre.rootDir = p.parent_path();
    pre.inst = inst.get();
    pre.file (p);

    std::vector<std::pair<std::string, std::vector<Op>>> sections;
    tokenize (pre.out, sections);

    Builder b (*inst);
    b.rootDir = p.parent_path();

    std::vector<Op> global, master, group;
    std::string current;

    auto emitRegion = [&] (const std::vector<Op>& own)
    {
        Region r;
        b.curveAssign.clear();
        const std::vector<Op>* lists[] = { &global, &master, &group, &own };
        for (auto* list : lists)
            for (auto& op : *list)
                b.apply (r, op.name, op.value);
        b.finalize (r);
        r.index = (int) inst->regions.size();
        if (! r.silence && r.sample.empty()) { inst->warnings.push_back ("region without sample"); return; }
        inst->regions.push_back (std::move (r));
    };

    for (auto& [header, ops] : sections)
    {
        if (header == "control" || (header.empty() && ! ops.empty()))
        {
            for (auto& op : ops)
            {
                std::string base; int num;
                if (op.name == "default_path")
                {
                    b.defaultPath = op.value;
                    std::replace (b.defaultPath.begin(), b.defaultPath.end(), '\\', '/');
                }
                else if (op.name == "note_offset") inst->noteOffset += (int) toF (op.value);
                else if (op.name == "octave_offset") inst->noteOffset += 12 * (int) toF (op.value);
                else if (splitTrailingNumber (op.name, base, num) && num >= 0 && num < 128 && (base == "set_cc" || base == "set_hdcc"))
                    inst->defaultCc[(size_t) num] = base == "set_cc" ? (float) toF (op.value) / 127.0f : (float) toF (op.value);
                else if (op.name.compare (0, 8, "label_cc") == 0 || op.name.compare (0, 10, "label_key") == 0) {}
                else if (splitTrailingNumber (op.name, base, num) && (base == "set_cc" || base == "set_hdcc")) {}
                else b.unsupported (op.name);
            }
        }
        else if (header == "global") { global = ops; master.clear(); group.clear(); }
        else if (header == "master") { master = ops; group.clear(); }
        else if (header == "group") { group = ops; }
        else if (header == "region") { emitRegion (ops); }
        else if (header == "curve") { buildCurve (*inst, ops); }
        else if (header.empty()) {}
        else { inst->unsupported["<" + header + ">"]++; }
        current = header;
    }

    if (inst->regions.empty()) { err = "SFZ has no regions: " + path; return nullptr; }
    return inst;
}

} // namespace mc
