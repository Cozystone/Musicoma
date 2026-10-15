#include "audiofile.h"
#include <algorithm>
#include <bit>
#include <cstring>
#include <fstream>

namespace mc {

namespace {

inline uint16_t rd16 (const uint8_t* p) { return (uint16_t) (p[0] | (p[1] << 8)); }
inline uint32_t rd32 (const uint8_t* p) { return (uint32_t) p[0] | ((uint32_t) p[1] << 8) | ((uint32_t) p[2] << 16) | ((uint32_t) p[3] << 24); }

} // namespace

//==============================================================================
// WAV
bool decodeWav (const uint8_t* d, size_t n, AudioData& out, std::string& err)
{
    if (n < 12 || std::memcmp (d, "RIFF", 4) != 0 || std::memcmp (d + 8, "WAVE", 4) != 0)
    { err = "not a RIFF/WAVE file"; return false; }

    int fmtTag = 0, channels = 0, bits = 0, blockAlign = 0;
    uint32_t rate = 0;
    const uint8_t* data = nullptr;
    size_t dataLen = 0;
    size_t pos = 12;

    while (pos + 8 <= n)
    {
        const uint8_t* c = d + pos;
        uint32_t len = rd32 (c + 4);
        size_t body = pos + 8;
        size_t avail = std::min<size_t> (len, n - body);

        if (std::memcmp (c, "fmt ", 4) == 0 && avail >= 16)
        {
            fmtTag = rd16 (d + body);
            channels = rd16 (d + body + 2);
            rate = rd32 (d + body + 4);
            blockAlign = rd16 (d + body + 12);
            bits = rd16 (d + body + 14);
            if (fmtTag == 0xFFFE && avail >= 26)
                fmtTag = rd16 (d + body + 24);   // WAVE_FORMAT_EXTENSIBLE → 하위 형식
        }
        else if (std::memcmp (c, "data", 4) == 0)
        {
            data = d + body;
            dataLen = avail;
        }
        else if (std::memcmp (c, "smpl", 4) == 0 && avail >= 36)
        {
            uint32_t loops = rd32 (d + body + 28);
            if (loops > 0 && avail >= 36 + 24)
            {
                const uint8_t* L = d + body + 36;
                out.loopStart = rd32 (L + 8);
                out.loopEnd = rd32 (L + 12);
            }
        }
        pos = body + len + (len & 1);
    }

    if (data == nullptr || channels <= 0 || rate == 0 || blockAlign <= 0)
    { err = "WAV missing fmt/data"; return false; }

    const bool isFloat = fmtTag == 3;
    if (! (fmtTag == 1 || isFloat)) { err = "WAV format tag " + std::to_string (fmtTag) + " not supported"; return false; }

    int64_t frames = (int64_t) (dataLen / (size_t) blockAlign);
    out.channels = channels;
    out.sampleRate = rate;
    out.frames = frames;
    out.ch.assign ((size_t) channels, std::vector<float> ((size_t) frames));
    const int bytes = bits / 8;

    for (int64_t f = 0; f < frames; ++f)
    {
        const uint8_t* fr = data + (size_t) f * (size_t) blockAlign;
        for (int c = 0; c < channels; ++c)
        {
            const uint8_t* s = fr + c * bytes;
            float v = 0;
            if (isFloat)
            {
                if (bits == 32) { float x; std::memcpy (&x, s, 4); v = x; }
                else if (bits == 64) { double x; std::memcpy (&x, s, 8); v = (float) x; }
            }
            else switch (bits)
            {
                case 8:  v = ((int) s[0] - 128) / 128.0f; break;
                case 16: v = (int16_t) rd16 (s) / 32768.0f; break;
                case 24: { int32_t x = (int32_t) ((uint32_t) s[0] << 8 | (uint32_t) s[1] << 16 | (uint32_t) s[2] << 24) >> 8; v = x / 8388608.0f; break; }
                case 32: v = (float) ((int32_t) rd32 (s) / 2147483648.0); break;
                default: err = "WAV bit depth " + std::to_string (bits) + " not supported"; return false;
            }
            out.ch[(size_t) c][(size_t) f] = v;
        }
    }
    return true;
}

//==============================================================================
// FLAC (RFC 9639 기반 자체 구현)
namespace {

struct BitReader
{
    // 64비트 캐시: 위쪽(MSB)부터 꺼낸다
    const uint8_t* d;
    size_t n;
    size_t bytePos = 0;   // 다음에 캐시로 넣을 바이트
    uint64_t cache = 0;
    int bits = 0;         // 캐시에 든 비트 수

    BitReader (const uint8_t* data, size_t len) : d (data), n (len) {}

    inline void refill()
    {
        while (bits <= 56)
        {
            uint64_t b = bytePos < n ? d[bytePos] : 0;
            if (bytePos >= n + 8) throw std::runtime_error ("FLAC: read past end");
            ++bytePos;
            cache |= b << (56 - bits);
            bits += 8;
        }
    }

    /** 지금 읽을 비트의 바이트 위치 */
    size_t pos() const { return (bytePos * 8 - (size_t) bits); }
    void seekBits (size_t bitPos) { bytePos = bitPos >> 3; cache = 0; bits = 0; int skip = (int) (bitPos & 7); if (skip) { refill(); cache <<= skip; bits -= skip; } }

    inline uint64_t read (int k)
    {
        if (k == 0) return 0;
        if (k > 56)
        {
            uint64_t hi = read (k - 32);
            return (hi << 32) | read (32);
        }
        if (bits < k) refill();
        uint64_t v = cache >> (64 - k);
        cache <<= k;
        bits -= k;
        return v;
    }

    inline uint32_t bit() { return (uint32_t) read (1); }
    inline uint64_t bitsN (int k) { return read (k); }

    inline int64_t sbits (int k)
    {
        if (k == 0) return 0;
        uint64_t v = read (k);
        if (v & (1ull << (k - 1)))
            return (int64_t) v - (int64_t) (1ull << k);
        return (int64_t) v;
    }

    inline uint32_t unary()
    {
        uint32_t zeros = 0;
        while (true)
        {
            if (bits == 0) refill();
            if (cache == 0)
            {
                zeros += (uint32_t) bits;
                cache = 0; bits = 0;
                if (bytePos > n + 8) throw std::runtime_error ("FLAC: read past end");
                continue;
            }
            int lz = std::countl_zero (cache);
            if (lz < bits)
            {
                zeros += (uint32_t) lz;
                cache <<= (lz + 1);
                bits -= lz + 1;
                return zeros;
            }
            zeros += (uint32_t) bits;
            cache = 0; bits = 0;
        }
    }

    void align() { int r = bits & 7; cache <<= r; bits -= r; }
};

void readResidual (BitReader& br, int blockSize, int order, int64_t* out)
{
    int method = (int) br.bitsN (2);
    if (method > 1) throw std::runtime_error ("FLAC: bad residual method");
    int paramBits = method == 0 ? 4 : 5;
    int escape = method == 0 ? 15 : 31;
    int partOrder = (int) br.bitsN (4);
    int parts = 1 << partOrder;
    int idx = 0;

    for (int p = 0; p < parts; ++p)
    {
        int count = (blockSize >> partOrder) - (p == 0 ? order : 0);
        int k = (int) br.bitsN (paramBits);

        if (k == escape)
        {
            int nb = (int) br.bitsN (5);
            for (int i = 0; i < count; ++i)
                out[idx++] = br.sbits (nb);
        }
        else
        {
            for (int i = 0; i < count; ++i)
            {
                uint64_t q = br.unary();
                uint64_t v = (q << k) | br.bitsN (k);
                out[idx++] = (int64_t) (v >> 1) ^ -(int64_t) (v & 1);
            }
        }
    }
}

void readSubframe (BitReader& br, int blockSize, int bps, int64_t* s)
{
    if (br.bit() != 0) throw std::runtime_error ("FLAC: bad subframe padding");
    int type = (int) br.bitsN (6);
    int wasted = 0;
    if (br.bit())
        wasted = (int) br.unary() + 1;
    bps -= wasted;

    if (type == 0)
    {
        int64_t v = br.sbits (bps);
        for (int i = 0; i < blockSize; ++i) s[i] = v;
    }
    else if (type == 1)
    {
        for (int i = 0; i < blockSize; ++i) s[i] = br.sbits (bps);
    }
    else if (type >= 8 && type <= 12)
    {
        int order = type - 8;
        for (int i = 0; i < order; ++i) s[i] = br.sbits (bps);
        readResidual (br, blockSize, order, s + order);
        for (int i = order; i < blockSize; ++i)
        {
            int64_t r = s[i];
            switch (order)
            {
                case 0: s[i] = r; break;
                case 1: s[i] = r + s[i - 1]; break;
                case 2: s[i] = r + 2 * s[i - 1] - s[i - 2]; break;
                case 3: s[i] = r + 3 * s[i - 1] - 3 * s[i - 2] + s[i - 3]; break;
                case 4: s[i] = r + 4 * s[i - 1] - 6 * s[i - 2] + 4 * s[i - 3] - s[i - 4]; break;
            }
        }
    }
    else if (type >= 32)
    {
        int order = type - 31;
        for (int i = 0; i < order; ++i) s[i] = br.sbits (bps);
        int precision = (int) br.bitsN (4) + 1;
        if (precision == 16) throw std::runtime_error ("FLAC: bad LPC precision");
        int shift = (int) br.sbits (5);
        if (shift < 0) shift = 0;
        int64_t coef[32];
        for (int i = 0; i < order; ++i) coef[i] = br.sbits (precision);
        readResidual (br, blockSize, order, s + order);
        for (int i = order; i < blockSize; ++i)
        {
            int64_t acc = 0;
            for (int j = 0; j < order; ++j)
                acc += coef[j] * s[i - 1 - j];
            s[i] += acc >> shift;
        }
    }
    else
        throw std::runtime_error ("FLAC: reserved subframe type");

    if (wasted)
        for (int i = 0; i < blockSize; ++i) s[i] <<= wasted;
}

} // namespace

bool decodeFlac (const uint8_t* d, size_t n, AudioData& out, std::string& err)
{
    try
    {
        size_t pos = 0;
        // ID3v2 태그가 앞에 붙은 파일
        if (n > 10 && std::memcmp (d, "ID3", 3) == 0)
            pos = 10 + (((size_t) d[6] & 0x7f) << 21 | ((size_t) d[7] & 0x7f) << 14 | ((size_t) d[8] & 0x7f) << 7 | ((size_t) d[9] & 0x7f));

        if (pos + 4 > n || std::memcmp (d + pos, "fLaC", 4) != 0) { err = "not a FLAC file"; return false; }
        pos += 4;

        int channels = 0, bps = 0;
        uint32_t rate = 0;
        uint64_t total = 0;
        bool last = false;

        while (! last && pos + 4 <= n)
        {
            last = (d[pos] & 0x80) != 0;
            int type = d[pos] & 0x7f;
            size_t len = (size_t) d[pos + 1] << 16 | (size_t) d[pos + 2] << 8 | d[pos + 3];
            pos += 4;
            if (type == 0 && len >= 34)
            {
                BitReader br (d + pos, len);
                br.bitsN (16); br.bitsN (16); br.bitsN (24); br.bitsN (24);
                rate = (uint32_t) br.bitsN (20);
                channels = (int) br.bitsN (3) + 1;
                bps = (int) br.bitsN (5) + 1;
                total = br.bitsN (36);
            }
            pos += len;
        }

        if (channels == 0) { err = "FLAC: no STREAMINFO"; return false; }

        out.channels = channels;
        out.sampleRate = rate;
        out.ch.assign ((size_t) channels, {});
        for (auto& c : out.ch) c.reserve ((size_t) total);

        std::vector<int64_t> buf[8];
        const float scale = 1.0f / (float) (1u << (bps - 1));

        BitReader br (d, n);
        br.seekBits (pos * 8);

        while ((br.pos() >> 3) + 2 < n)
        {
            // 프레임 동기 찾기 (보통 바로 이어지고, 어긋나면 한 바이트씩)
            size_t at = br.pos();
            size_t byte = at >> 3;
            if (! (d[byte] == 0xFF && (d[byte + 1] & 0xFE) == 0xF8))
            {
                br.seekBits (at + 8);
                continue;
            }
            br.bitsN (16);
            int bsCode = (int) br.bitsN (4);
            int srCode = (int) br.bitsN (4);
            int chAssign = (int) br.bitsN (4);
            int ssCode = (int) br.bitsN (3);
            br.bitsN (1);
            // UTF-8 식 프레임 번호
            uint32_t first = (uint32_t) br.bitsN (8);
            int extra = 0;
            if (first & 0x80) { uint32_t m = 0x40; while (first & m) { ++extra; m >>= 1; } }
            for (int i = 0; i < extra; ++i) br.bitsN (8);

            int blockSize = 0;
            if (bsCode == 1) blockSize = 192;
            else if (bsCode >= 2 && bsCode <= 5) blockSize = 576 << (bsCode - 2);
            else if (bsCode == 6) blockSize = (int) br.bitsN (8) + 1;
            else if (bsCode == 7) blockSize = (int) br.bitsN (16) + 1;
            else if (bsCode >= 8) blockSize = 256 << (bsCode - 8);
            else throw std::runtime_error ("FLAC: reserved block size");

            if (srCode == 12) br.bitsN (8);
            else if (srCode == 13 || srCode == 14) br.bitsN (16);

            int fbps = bps;
            switch (ssCode)
            {
                case 1: fbps = 8; break;  case 2: fbps = 12; break; case 4: fbps = 16; break;
                case 5: fbps = 20; break; case 6: fbps = 24; break; case 7: fbps = 32; break;
                default: break;
            }
            br.bitsN (8);   // CRC-8

            int nch = chAssign < 8 ? chAssign + 1 : 2;
            for (int c = 0; c < nch; ++c)
            {
                buf[c].resize ((size_t) blockSize);
                int sbps = fbps;
                if ((chAssign == 8 && c == 1) || (chAssign == 9 && c == 0) || (chAssign == 10 && c == 1))
                    ++sbps;   // side 채널은 1비트 더
                readSubframe (br, blockSize, sbps, buf[c].data());
            }
            br.align();
            br.bitsN (16);  // CRC-16

            if (chAssign == 8)
                for (int i = 0; i < blockSize; ++i) buf[1][i] = buf[0][i] - buf[1][i];
            else if (chAssign == 9)
                for (int i = 0; i < blockSize; ++i) buf[0][i] = buf[0][i] + buf[1][i];
            else if (chAssign == 10)
                for (int i = 0; i < blockSize; ++i)
                {
                    int64_t mid = buf[0][i] * 2 | (buf[1][i] & 1);
                    int64_t side = buf[1][i];
                    buf[0][i] = (mid + side) >> 1;
                    buf[1][i] = (mid - side) >> 1;
                }

            for (int c = 0; c < std::min (nch, channels); ++c)
                for (int i = 0; i < blockSize; ++i)
                    out.ch[(size_t) c].push_back ((float) buf[c][i] * scale);

            if (total > 0 && out.ch[0].size() >= total)
                break;
        }

        if (total > 0)
            for (auto& c : out.ch) c.resize ((size_t) std::min<uint64_t> (total, c.size()));
        out.frames = (int64_t) out.ch[0].size();
        return out.frames > 0;
    }
    catch (const std::exception& ex)
    {
        err = ex.what();
        return false;
    }
}

//==============================================================================
bool readAudioFile (const fs::path& p, AudioData& out, std::string& err)
{
    std::vector<uint8_t> bytes;
    if (! readFileBytes (p, bytes)) { err = "cannot read " + pathToU8 (p); return false; }
    if (bytes.size() >= 4 && std::memcmp (bytes.data(), "RIFF", 4) == 0)
        return decodeWav (bytes.data(), bytes.size(), out, err);
    if (bytes.size() >= 4 && (std::memcmp (bytes.data(), "fLaC", 4) == 0 || std::memcmp (bytes.data(), "ID3", 3) == 0))
        return decodeFlac (bytes.data(), bytes.size(), out, err);
    err = "unknown audio format: " + pathToU8 (p);
    return false;
}

//==============================================================================
bool writeWav (const fs::path& p, const std::vector<std::vector<float>>& ch, int64_t frames,
               int sampleRate, int bits, std::string& err)
{
    const int channels = (int) ch.size();
    const bool isFloat = bits == 32;
    const int bytes = bits / 8;
    const uint64_t dataLen = (uint64_t) frames * (uint64_t) channels * (uint64_t) bytes;
    if (dataLen > 0xFFFFFFF0ull) { err = "output too large for WAV"; return false; }

    std::vector<uint8_t> o;
    o.reserve ((size_t) dataLen + 64);
    auto w16 = [&] (uint32_t v) { o.push_back ((uint8_t) v); o.push_back ((uint8_t) (v >> 8)); };
    auto w32 = [&] (uint32_t v) { w16 (v & 0xffff); w16 (v >> 16); };
    auto tag = [&] (const char* t) { o.insert (o.end(), t, t + 4); };

    tag ("RIFF"); w32 ((uint32_t) (36 + dataLen)); tag ("WAVE");
    tag ("fmt "); w32 (16); w16 (isFloat ? 3 : 1); w16 ((uint32_t) channels); w32 ((uint32_t) sampleRate);
    w32 ((uint32_t) (sampleRate * channels * bytes)); w16 ((uint32_t) (channels * bytes)); w16 ((uint32_t) bits);
    tag ("data"); w32 ((uint32_t) dataLen);

    for (int64_t f = 0; f < frames; ++f)
        for (int c = 0; c < channels; ++c)
        {
            float v = ch[(size_t) c][(size_t) f];
            if (isFloat) { uint32_t u; std::memcpy (&u, &v, 4); w32 (u); continue; }
            double x = clampv<double> (v, -1.0, 1.0);
            if (bits == 24)
            {
                int32_t s = (int32_t) std::lround (x * 8388607.0);
                o.push_back ((uint8_t) s); o.push_back ((uint8_t) (s >> 8)); o.push_back ((uint8_t) (s >> 16));
            }
            else
            {
                int32_t s = (int32_t) std::lround (x * 32767.0);
                w16 ((uint32_t) (uint16_t) (int16_t) s);
            }
        }

    std::ofstream f (p, std::ios::binary);
    if (! f) { err = "cannot write " + pathToU8 (p); return false; }
    f.write ((const char*) o.data(), (std::streamsize) o.size());
    return (bool) f;
}

} // namespace mc
