// test-io — 오디오 출력(WASAPI)·MIDI 입력(WinMM) 시험. 소리는 내지 않는다(콜백은 무음만 쓴다).
#include "audioio.h"
#include <windows.h>
#include <atomic>
#include <chrono>
#include <cstdio>
#include <string>
#include <thread>

using namespace mc;

namespace {

double nowSec()
{
    static LARGE_INTEGER f = [] { LARGE_INTEGER x; QueryPerformanceFrequency (&x); return x; }();
    LARGE_INTEGER c; QueryPerformanceCounter (&c);
    return (double) c.QuadPart / (double) f.QuadPart;
}

std::string esc (const std::string& s)
{
    std::string o;
    for (char c : s) { if (c == '"' || c == '\\') o += '\\'; o += c; }
    return o;
}

struct Stats
{
    std::atomic<long long> frames { 0 };
    std::atomic<long> calls { 0 };
    std::atomic<int> minN { 1 << 30 }, maxN { 0 };
    double first = 0, last = 0, maxGap = 0;
    int firstN = 0;
    long late = 0;          // 직전 콜백과의 간격이 주기의 2배를 넘은 횟수
    double periodSec = 0;
};

int failures = 0;
#define CHECK(c, msg) do { if (! (c)) { std::printf ("  FAIL: %s\n", msg); ++failures; } } while (0)

bool runOutput (const std::string& name, int frames, double seconds, int cycle)
{
    AudioOutput out;
    Stats st;
    std::string err;
    auto cb = [&st] (float* L, float* R, int n)
    {
        // 무음: L/R 은 이미 0 이지만 확실히 0 으로 둔다
        for (int i = 0; i < n; ++i) { L[i] = 0.f; R[i] = 0.f; }
        const double t = nowSec();
        if (st.calls.load() == 0) { st.first = t; st.firstN = n; }
        else
        {
            const double g = t - st.last;
            if (g > st.maxGap) st.maxGap = g;
            if (st.periodSec > 0 && g > 2.0 * st.periodSec) ++st.late;
        }
        st.last = t;
        st.frames += n;
        ++st.calls;
        if (n < st.minN) st.minN = n;
        if (n > st.maxN) st.maxN = n;
    };
    // periodSec 는 open 뒤에 알 수 있으므로 먼저 대략값(10ms)
    st.periodSec = 0.010;
    const double t0 = nowSec();
    if (! out.open (name, frames, cb, err))
    {
        std::printf ("{\"cycle\":%d,\"open\":false,\"error\":\"%s\"}\n", cycle, esc (err).c_str());
        return false;
    }
    const double tOpen = nowSec() - t0;
    std::printf ("{\"cycle\":%d,\"open\":true,\"device\":\"%s\",\"sampleRate\":%.0f,\"periodFrames\":%d,\"openMs\":%.1f}\n",
                 cycle, esc (out.deviceName()).c_str(), out.sampleRate(), out.bufferFrames(), tOpen * 1000.0);

    const auto tEnd = std::chrono::steady_clock::now() + std::chrono::duration<double> (seconds);
    while (std::chrono::steady_clock::now() < tEnd && out.isOpen())
        std::this_thread::sleep_for (std::chrono::milliseconds (20));
    const bool stillOpen = out.isOpen();

    const double tc = nowSec();
    out.close();
    const double tClose = nowSec() - tc;

    const long calls = st.calls.load();
    const long long fr = st.frames.load();
    const double span = st.last - st.first;
    // 실효 레이트 = 첫 콜백 이후 넘긴 프레임 / 첫~마지막 콜백 간격 (첫 콜백 분량은 구간 시작 전 것이라 뺀다)
    const double effRate = span > 0 ? (double) (fr - st.firstN) / span : 0;
    std::printf ("{\"cycle\":%d,\"callbacks\":%ld,\"frames\":%lld,\"spanSec\":%.3f,\"effectiveRate\":%.1f,"
                 "\"avgPeriodMs\":%.3f,\"maxGapMs\":%.3f,\"lateCallbacks\":%ld,\"nMin\":%d,\"nMax\":%d,\"stillOpen\":%s,\"closeMs\":%.1f}\n",
                 cycle, calls, fr, span, effRate,
                 calls > 1 ? span / (calls - 1) * 1000.0 : 0.0, st.maxGap * 1000.0, st.late,
                 st.minN.load(), st.maxN.load(), stillOpen ? "true" : "false", tClose * 1000.0);
    CHECK (calls > 10, "콜백이 거의 오지 않음");
    CHECK (stillOpen, "재생 도중 장치가 닫힘");
    CHECK (! out.isOpen(), "close 뒤에도 isOpen");
    if (span > 0)
    {
        const double ratio = effRate / out.sampleRate();
        CHECK (ratio > 0.97 && ratio < 1.03, "실효 샘플레이트가 장치 값과 3% 넘게 다름");
    }
    return true;
}

} // namespace

int main()
{
    SetConsoleOutputCP (CP_UTF8);

    std::printf ("== 출력 장치 ==\n");
    auto outs = AudioOutput::list();
    for (auto& o : outs)
        std::printf ("{\"type\":\"%s\",\"name\":\"%s\",\"id\":\"%s\",\"isDefault\":%s}\n",
                     esc (o.type).c_str(), esc (o.name).c_str(), esc (o.id).c_str(), o.isDefault ? "true" : "false");
    CHECK (! outs.empty(), "출력 장치가 없음");

    std::printf ("== MIDI 입력 ==\n");
    auto mins = MidiInput::list();
    for (auto& m : mins) std::printf ("{\"index\":%d,\"name\":\"%s\"}\n", m.index, esc (m.name).c_str());
    if (mins.empty()) std::printf ("(없음)\n");

    std::printf ("== 기본 출력: 3초 무음 재생 x 2회(열기·닫기 반복) ==\n");
    for (int c = 1; c <= 2; ++c)
        CHECK (runOutput ("", 480, 3.0, c), "기본 출력 열기 실패");

    std::printf ("== 작은 버퍼 희망(128프레임) 1초 ==\n");
    runOutput ("", 128, 1.0, 3);

    std::printf ("== 없는 이름 ==\n");
    {
        AudioOutput out; std::string err;
        bool ok = out.open ("__no_such_device_xyz__", 480, [] (float*, float*, int) {}, err);
        std::printf ("{\"open\":%s,\"error\":\"%s\"}\n", ok ? "true" : "false", esc (err).c_str());
        CHECK (! ok && ! err.empty(), "없는 이름인데 열림 또는 오류 문자열 없음");
        CHECK (! out.isOpen(), "실패 뒤 isOpen");
    }

    if (! outs.empty())
    {
        std::printf ("== 이름으로 열기(첫 장치 이름 일부, 대문자) ==\n");
        // UTF-8 을 글자 단위로 자르려고 넓은 문자로 바꿔 뒤쪽 3글자를 쓴다(완전일치가 아닌 부분일치 확인)
        std::wstring w (outs[0].name.size() + 1, L' ');
        w.resize ((size_t) MultiByteToWideChar (CP_UTF8, 0, outs[0].name.c_str(), (int) outs[0].name.size(), w.data(), (int) w.size()));
        std::wstring wp = w.size() > 3 ? w.substr (w.size() - 3) : w;
        std::string part (wp.size() * 4 + 1, ' ');
        part.resize ((size_t) WideCharToMultiByte (CP_UTF8, 0, wp.c_str(), (int) wp.size(), part.data(), (int) part.size(), nullptr, nullptr));
        for (auto& ch : part) if (ch >= 'a' && ch <= 'z') ch = (char) (ch - 32);
        AudioOutput out; std::string err;
        bool ok = out.open (part, 480, [] (float* L, float* R, int n) { for (int i = 0; i < n; ++i) L[i] = R[i] = 0; }, err);
        std::printf ("{\"query\":\"%s\",\"open\":%s,\"device\":\"%s\",\"error\":\"%s\"}\n",
                     esc (part).c_str(), ok ? "true" : "false", esc (out.deviceName()).c_str(), esc (err).c_str());
        CHECK (ok, "이름 부분일치로 열기 실패");
        std::this_thread::sleep_for (std::chrono::milliseconds (200));
        out.close();
        out.close();   // 두 번 닫아도 안전해야 한다
    }

    std::printf ("== MIDI 1초 듣기 ==\n");
    if (! mins.empty())
    {
        MidiInput mi; std::string err;
        std::atomic<int> count { 0 };
        bool ok = mi.open (0, [&count] (const MidiInMsg& m)
        {
            if (count++ < 50) std::printf ("{\"midi\":[%u,%u,%u],\"t\":%.3f}\n", m.status, m.data1, m.data2, m.timeSec);
        }, err);
        std::printf ("{\"open\":%s,\"name\":\"%s\",\"error\":\"%s\"}\n", ok ? "true" : "false", esc (mi.name()).c_str(), esc (err).c_str());
        if (ok)
        {
            std::this_thread::sleep_for (std::chrono::seconds (1));
            mi.close();
            std::printf ("{\"received\":%d,\"isOpenAfterClose\":%s}\n", count.load(), mi.isOpen() ? "true" : "false");
        }
    }
    else std::printf ("(MIDI 입력 없음 — 건너뜀)\n");
    {
        MidiInput mi; std::string err;
        bool ok = mi.open (9999, [] (const MidiInMsg&) {}, err);
        std::printf ("{\"midiBogusIndex\":%s,\"error\":\"%s\"}\n", ok ? "true" : "false", esc (err).c_str());
        CHECK (! ok, "없는 MIDI 번호인데 열림");
    }

    std::printf ("== 결과: %s (%d 실패) ==\n", failures ? "FAIL" : "OK", failures);
    return failures ? 1 : 0;
}
