// Musicoma Core — 작은 JSON 파서/작성기 (표준 라이브러리만)
#pragma once
#include <map>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>

namespace mc {

struct Json
{
    enum Type { Null, Bool, Number, String, Array, Object };
    Type type = Null;
    bool b = false;
    double n = 0.0;
    std::string s;
    std::vector<Json> a;
    std::vector<std::pair<std::string, Json>> o;   // 순서 보존

    bool isNull() const   { return type == Null; }
    bool isNum() const    { return type == Number; }
    bool isStr() const    { return type == String; }
    bool isArr() const    { return type == Array; }
    bool isObj() const    { return type == Object; }

    const Json* find (const std::string& key) const
    {
        for (auto& kv : o)
            if (kv.first == key)
                return &kv.second;
        return nullptr;
    }

    const Json& operator[] (const std::string& key) const
    {
        static const Json nullJson;
        auto* p = find (key);
        return p ? *p : nullJson;
    }

    double num (const std::string& key, double fallback) const
    {
        auto* p = find (key);
        if (p == nullptr) return fallback;
        if (p->type == Number) return p->n;
        if (p->type == Bool) return p->b ? 1.0 : 0.0;
        return fallback;
    }

    bool flag (const std::string& key, bool fallback) const
    {
        auto* p = find (key);
        if (p == nullptr) return fallback;
        if (p->type == Bool) return p->b;
        if (p->type == Number) return p->n != 0.0;
        return fallback;
    }

    std::string str (const std::string& key, const std::string& fallback = {}) const
    {
        auto* p = find (key);
        return (p && p->type == String) ? p->s : fallback;
    }

    static Json parse (const std::string& text);
    std::string dump (int indent = -1) const;

    // 작성 도우미
    static Json object()                    { Json j; j.type = Object; return j; }
    static Json array()                     { Json j; j.type = Array; return j; }
    static Json number (double v)           { Json j; j.type = Number; j.n = v; return j; }
    static Json string (const std::string& v) { Json j; j.type = String; j.s = v; return j; }
    static Json boolean (bool v)            { Json j; j.type = Bool; j.b = v; return j; }
    void set (const std::string& k, Json v) { type = Object; o.emplace_back (k, std::move (v)); }
    void push (Json v)                      { type = Array; a.push_back (std::move (v)); }
};

} // namespace mc
