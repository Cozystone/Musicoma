// Musicoma Engine — 표준 MIDI 파일(SMF 0/1) 읽기 → MIDI 클립(clip.import_midi)
#include <algorithm>
#include <cmath>
#include <map>
#include "eng_model.h"
#include "util.h"

namespace mc {

namespace {
struct Rd
{
    const std::vector<uint8_t>& d;
    size_t p = 0;
    explicit Rd (const std::vector<uint8_t>& x) : d (x) {}
    bool ok (size_t n) const { return p + n <= d.size(); }
    uint32_t u32() { uint32_t v = (d[p] << 24) | (d[p + 1] << 16) | (d[p + 2] << 8) | d[p + 3]; p += 4; return v; }
    uint16_t u16() { uint16_t v = (uint16_t) ((d[p] << 8) | d[p + 1]); p += 2; return v; }
    uint32_t vlq() { uint32_t v = 0; for (int i = 0; i < 4 && p < d.size(); ++i) { uint8_t b = d[p++]; v = (v << 7) | (b & 0x7F); if (! (b & 0x80)) break; } return v; }
};
}

bool importMidiFile (const std::string& path, int wantTrack, double, Clip& out, std::string& err)
{
    std::vector<uint8_t> d;
    if (! readFileBytes (u8path (path), d)) { err = "cannot read " + path; return false; }
    Rd r (d);
    if (! r.ok (14) || std::string ((const char*) d.data(), 4) != "MThd") { err = "not a MIDI file"; return false; }
    r.p = 4;
    uint32_t hl = r.u32();
    uint16_t fmt = r.u16(), ntr = r.u16(), div = r.u16();
    (void) fmt;
    r.p = 8 + hl;
    if (div & 0x8000) { err = "SMPTE time division not supported"; return false; }
    const double ppq = div ? div : 480;
    out = Clip();
    out.midi = true;
    out.name = fs::path (u8path (path)).stem().string();
    double lastBeat = 0;
    for (int ti = 0; ti < ntr && r.ok (8); ++ti)
    {
        std::string id ((const char*) &d[r.p], 4);
        r.p += 4;
        uint32_t len = r.u32();
        size_t end = r.p + len;
        if (id != "MTrk") { r.p = end; continue; }
        bool use = wantTrack < 0 || wantTrack == ti;
        uint64_t tick = 0;
        uint8_t running = 0;
        std::map<int, std::pair<double, int>> on;   // 음 → (시작 박, 세기)
        while (r.p < end && r.p < d.size())
        {
            tick += r.vlq();
            double beat = tick / ppq;
            uint8_t st = d[r.p];
            if (st & 0x80) ++r.p; else st = running;
            if (st == 0xFF)
            {
                uint8_t type = d[r.p++];
                uint32_t l = r.vlq();
                if (type == 0x03 && use && wantTrack >= 0) out.name = std::string ((const char*) &d[r.p], l);
                r.p += l;
                continue;
            }
            if (st == 0xF0 || st == 0xF7) { uint32_t l = r.vlq(); r.p += l; continue; }
            running = st;
            uint8_t hi = st & 0xF0;
            uint8_t a = d[r.p++];
            uint8_t b = (hi == 0xC0 || hi == 0xD0) ? 0 : d[r.p++];
            if (! use) continue;
            if (hi == 0x90 && b > 0) on[a] = { beat, b };
            else if (hi == 0x80 || (hi == 0x90 && b == 0))
            {
                auto it = on.find (a);
                if (it != on.end())
                {
                    out.notes.push_back ({ a, it->second.first, std::max (1.0 / 64, beat - it->second.first), it->second.second });
                    on.erase (it);
                    lastBeat = std::max (lastBeat, beat);
                }
            }
            else if (hi == 0xB0) out.cc.push_back ({ a, beat, b });
            else if (hi == 0xE0) out.bend.push_back ({ beat, (double) (((b << 7) | a) - 8192) / 8192.0 });
        }
        r.p = end;
    }
    std::sort (out.notes.begin(), out.notes.end(), [] (const Note& x, const Note& y) { return x.start < y.start; });
    out.length = std::max (4.0, std::ceil (lastBeat / 4.0) * 4.0);
    if (out.notes.empty()) { err = "no notes in MIDI file"; return false; }
    return true;
}

} // namespace mc
