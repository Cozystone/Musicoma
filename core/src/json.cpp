#include "json.h"
#include <cmath>
#include <cstdio>
#include <cstdlib>

namespace mc {

namespace {

struct Parser
{
    const std::string& t;
    size_t i = 0;

    explicit Parser (const std::string& text) : t (text) {}

    [[noreturn]] void fail (const char* what)
    {
        throw std::runtime_error (std::string ("JSON: ") + what + " at offset " + std::to_string (i));
    }

    void ws()
    {
        while (i < t.size() && (t[i] == ' ' || t[i] == '\n' || t[i] == '\r' || t[i] == '\t'))
            ++i;
    }

    static void putUtf8 (std::string& out, unsigned cp)
    {
        if (cp < 0x80) out += (char) cp;
        else if (cp < 0x800) { out += (char) (0xC0 | (cp >> 6)); out += (char) (0x80 | (cp & 0x3F)); }
        else if (cp < 0x10000) { out += (char) (0xE0 | (cp >> 12)); out += (char) (0x80 | ((cp >> 6) & 0x3F)); out += (char) (0x80 | (cp & 0x3F)); }
        else { out += (char) (0xF0 | (cp >> 18)); out += (char) (0x80 | ((cp >> 12) & 0x3F)); out += (char) (0x80 | ((cp >> 6) & 0x3F)); out += (char) (0x80 | (cp & 0x3F)); }
    }

    unsigned hex4()
    {
        if (i + 4 > t.size()) fail ("bad \\u escape");
        unsigned v = 0;
        for (int k = 0; k < 4; ++k)
        {
            char c = t[i++];
            v <<= 4;
            if (c >= '0' && c <= '9') v |= (unsigned) (c - '0');
            else if (c >= 'a' && c <= 'f') v |= (unsigned) (c - 'a' + 10);
            else if (c >= 'A' && c <= 'F') v |= (unsigned) (c - 'A' + 10);
            else fail ("bad hex digit");
        }
        return v;
    }

    std::string str()
    {
        if (t[i] != '"') fail ("expected string");
        ++i;
        std::string out;
        while (true)
        {
            if (i >= t.size()) fail ("unterminated string");
            char c = t[i++];
            if (c == '"') break;
            if (c != '\\') { out += c; continue; }
            if (i >= t.size()) fail ("bad escape");
            char e = t[i++];
            switch (e)
            {
                case '"': out += '"'; break;
                case '\\': out += '\\'; break;
                case '/': out += '/'; break;
                case 'b': out += '\b'; break;
                case 'f': out += '\f'; break;
                case 'n': out += '\n'; break;
                case 'r': out += '\r'; break;
                case 't': out += '\t'; break;
                case 'u':
                {
                    unsigned cp = hex4();
                    if (cp >= 0xD800 && cp < 0xDC00 && i + 6 <= t.size() && t[i] == '\\' && t[i + 1] == 'u')
                    {
                        i += 2;
                        unsigned lo = hex4();
                        cp = 0x10000 + ((cp - 0xD800) << 10) + (lo - 0xDC00);
                    }
                    putUtf8 (out, cp);
                    break;
                }
                default: fail ("bad escape");
            }
        }
        return out;
    }

    Json value()
    {
        ws();
        if (i >= t.size()) fail ("unexpected end");
        char c = t[i];
        Json j;
        if (c == '{')
        {
            j.type = Json::Object;
            ++i; ws();
            if (i < t.size() && t[i] == '}') { ++i; return j; }
            while (true)
            {
                ws();
                auto k = str();
                ws();
                if (i >= t.size() || t[i] != ':') fail ("expected ':'");
                ++i;
                j.o.emplace_back (std::move (k), value());
                ws();
                if (i < t.size() && t[i] == ',') { ++i; continue; }
                if (i < t.size() && t[i] == '}') { ++i; break; }
                fail ("expected ',' or '}'");
            }
            return j;
        }
        if (c == '[')
        {
            j.type = Json::Array;
            ++i; ws();
            if (i < t.size() && t[i] == ']') { ++i; return j; }
            while (true)
            {
                j.a.push_back (value());
                ws();
                if (i < t.size() && t[i] == ',') { ++i; continue; }
                if (i < t.size() && t[i] == ']') { ++i; break; }
                fail ("expected ',' or ']'");
            }
            return j;
        }
        if (c == '"') { j.type = Json::String; j.s = str(); return j; }
        if (t.compare (i, 4, "true") == 0)  { i += 4; j.type = Json::Bool; j.b = true; return j; }
        if (t.compare (i, 5, "false") == 0) { i += 5; j.type = Json::Bool; j.b = false; return j; }
        if (t.compare (i, 4, "null") == 0)  { i += 4; return j; }
        if (t.compare (i, 3, "NaN") == 0)   { i += 3; j.type = Json::Number; j.n = 0; return j; }
        // 숫자
        const char* start = t.c_str() + i;
        char* end = nullptr;
        double v = std::strtod (start, &end);
        if (end == start) fail ("bad value");
        i += (size_t) (end - start);
        j.type = Json::Number;
        j.n = v;
        return j;
    }
};

void escape (std::string& out, const std::string& s)
{
    out += '"';
    for (unsigned char c : s)
    {
        switch (c)
        {
            case '"': out += "\\\""; break;
            case '\\': out += "\\\\"; break;
            case '\n': out += "\\n"; break;
            case '\r': out += "\\r"; break;
            case '\t': out += "\\t"; break;
            default:
                if (c < 0x20) { char b[8]; std::snprintf (b, sizeof b, "\\u%04x", c); out += b; }
                else out += (char) c;
        }
    }
    out += '"';
}

void dumpTo (std::string& out, const Json& j, int indent, int depth)
{
    auto nl = [&] (int d) { if (indent >= 0) { out += '\n'; out.append ((size_t) (indent * d), ' '); } };
    switch (j.type)
    {
        case Json::Null: out += "null"; break;
        case Json::Bool: out += j.b ? "true" : "false"; break;
        case Json::Number:
        {
            if (! std::isfinite (j.n)) { out += "null"; break; }
            char b[40];
            if (j.n == std::floor (j.n) && std::fabs (j.n) < 1e15) std::snprintf (b, sizeof b, "%.0f", j.n);
            else std::snprintf (b, sizeof b, "%.6g", j.n);
            out += b;
            break;
        }
        case Json::String: escape (out, j.s); break;
        case Json::Array:
            out += '[';
            for (size_t k = 0; k < j.a.size(); ++k) { if (k) out += ','; nl (depth + 1); dumpTo (out, j.a[k], indent, depth + 1); }
            if (! j.a.empty()) nl (depth);
            out += ']';
            break;
        case Json::Object:
            out += '{';
            for (size_t k = 0; k < j.o.size(); ++k)
            {
                if (k) out += ',';
                nl (depth + 1);
                escape (out, j.o[k].first);
                out += indent >= 0 ? ": " : ":";
                dumpTo (out, j.o[k].second, indent, depth + 1);
            }
            if (! j.o.empty()) nl (depth);
            out += '}';
            break;
    }
}

} // namespace

Json Json::parse (const std::string& text)
{
    Parser p (text);
    auto v = p.value();
    return v;
}

std::string Json::dump (int indent) const
{
    std::string out;
    dumpTo (out, *this, indent, 0);
    return out;
}

} // namespace mc
