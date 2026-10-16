// Musicoma Engine — MIDI 입력(WinMM). 짧은 메시지(MIM_DATA)만 넘기고 시스템 익스클루시브는 버린다.
// sysex 버퍼(midiInAddBuffer)를 걸지 않으므로 MIM_LONGDATA 는 오지 않고, 새는 메모리도 없다.
#include "audioio.h"
#include "io_common.h"

#include <mmsystem.h>
#include <atomic>

namespace mc {

using namespace mc::io;

struct MidiInput::Impl
{
    HMIDIIN h = nullptr;
    std::function<void (const MidiInMsg&)> cb;
    std::atomic<bool> live { false };   // close 중엔 콜백을 막는다
    std::string devName;

    static void CALLBACK proc (HMIDIIN, UINT msg, DWORD_PTR inst, DWORD_PTR p1, DWORD_PTR p2)
    {
        // WinMM 콜백 스레드 — 여기서 WinMM 함수를 부르면 안 된다. 짧게.
        if (msg != MIM_DATA && msg != MIM_MOREDATA) return;   // MIM_LONGDATA·오류·열기/닫기는 무시
        auto* self = (Impl*) inst;
        if (! self || ! self->live.load (std::memory_order_acquire) || ! self->cb) return;
        const DWORD m = (DWORD) p1;
        MidiInMsg e;
        e.status = (uint8_t) (m & 0xff);
        e.data1  = (uint8_t) ((m >> 8) & 0x7f);
        e.data2  = (uint8_t) ((m >> 16) & 0x7f);
        e.timeSec = (double) (DWORD) p2 / 1000.0;            // midiInStart 기준 ms
        self->cb (e);
    }
};

MidiInput::MidiInput() : impl (std::make_unique<Impl>()) {}
MidiInput::~MidiInput() { close(); }

std::vector<MidiInputInfo> MidiInput::list()
{
    std::vector<MidiInputInfo> out;
    const UINT n = midiInGetNumDevs();
    for (UINT i = 0; i < n; ++i)
    {
        MIDIINCAPSW caps {};
        if (midiInGetDevCapsW (i, &caps, sizeof (caps)) != MMSYSERR_NOERROR) continue;
        MidiInputInfo info;
        info.name = toUtf8 (caps.szPname);
        info.index = (int) i;
        out.push_back (std::move (info));
    }
    return out;
}

bool MidiInput::open (int index, std::function<void (const MidiInMsg&)> cb, std::string& error)
{
    close();
    auto& d = *impl;
    const UINT n = midiInGetNumDevs();
    if (index < 0 || (UINT) index >= n) { error = "MIDI 입력 번호가 범위 밖: " + std::to_string (index); return false; }

    MIDIINCAPSW caps {};
    midiInGetDevCapsW ((UINT) index, &caps, sizeof (caps));
    d.cb = std::move (cb);

    MMRESULT r = midiInOpen (&d.h, (UINT) index, (DWORD_PTR) &Impl::proc, (DWORD_PTR) &d, CALLBACK_FUNCTION);
    if (r != MMSYSERR_NOERROR)
    {
        wchar_t txt[MAXERRORLENGTH] {};
        midiInGetErrorTextW (r, txt, MAXERRORLENGTH);
        error = "midiInOpen 실패: " + toUtf8 (txt);
        d.h = nullptr; d.cb = nullptr;
        return false;
    }
    d.devName = toUtf8 (caps.szPname);
    d.live.store (true, std::memory_order_release);
    r = midiInStart (d.h);
    if (r != MMSYSERR_NOERROR)
    {
        error = "midiInStart 실패";
        close();
        return false;
    }
    return true;
}

void MidiInput::close()
{
    auto& d = *impl;
    d.live.store (false, std::memory_order_release);
    if (d.h)
    {
        midiInStop (d.h);
        midiInReset (d.h);   // 걸린 버퍼가 있으면 돌려받는다(지금은 없음)
        midiInClose (d.h);   // 반환 뒤로는 콜백이 오지 않는다
        d.h = nullptr;
    }
    d.cb = nullptr;
    d.devName.clear();
}

bool MidiInput::isOpen() const    { return impl->h != nullptr; }
std::string MidiInput::name() const { return impl->devName; }

} // namespace mc
