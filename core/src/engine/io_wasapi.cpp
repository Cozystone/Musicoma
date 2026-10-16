// Musicoma Engine — 실시간 오디오 출력. WASAPI 공유 모드 · 이벤트 구동 · 전용 렌더 스레드(MMCSS "Pro Audio").
// 장치 열기부터 해제까지 모든 COM 객체는 렌더 스레드 안에서 만들고 버린다(아파트 문제 회피).
#include "audioio.h"
#include "io_common.h"

#include <mmdeviceapi.h>
#include <audioclient.h>
#include <avrt.h>
#include <propsys.h>

#include <algorithm>
#include <atomic>
#include <cmath>
#include <cstring>
#include <future>
#include <thread>

namespace mc {

using namespace mc::io;

namespace {

// PKEY_Device_FriendlyName — INITGUID 없이 쓰려고 직접 정의
const PROPERTYKEY kFriendlyName = { { 0xa45c254e, 0xdf1c, 0x4efd, { 0x80, 0x20, 0x67, 0xd1, 0x46, 0xa8, 0x50, 0xe0 } }, 14 };

template <typename T> void safeRelease (T*& p) { if (p) { p->Release(); p = nullptr; } }

std::wstring deviceId (IMMDevice* d)
{
    std::wstring s;
    LPWSTR id = nullptr;
    if (SUCCEEDED (d->GetId (&id)) && id) { s = id; CoTaskMemFree (id); }
    return s;
}

std::wstring friendlyName (IMMDevice* d)
{
    std::wstring s;
    IPropertyStore* ps = nullptr;
    if (SUCCEEDED (d->OpenPropertyStore (STGM_READ, &ps)))
    {
        PROPVARIANT v; PropVariantInit (&v);
        if (SUCCEEDED (ps->GetValue (kFriendlyName, &v)) && v.vt == VT_LPWSTR && v.pwszVal) s = v.pwszVal;
        PropVariantClear (&v);
        ps->Release();
    }
    return s;
}

struct EndpointW { std::wstring name, id; bool isDefault = false; };

std::vector<EndpointW> enumerate (IMMDeviceEnumerator* en)
{
    std::vector<EndpointW> out;
    std::wstring defId;
    IMMDevice* def = nullptr;
    if (SUCCEEDED (en->GetDefaultAudioEndpoint (eRender, eConsole, &def))) { defId = deviceId (def); def->Release(); }

    IMMDeviceCollection* col = nullptr;
    if (FAILED (en->EnumAudioEndpoints (eRender, DEVICE_STATE_ACTIVE, &col))) return out;
    UINT cnt = 0; col->GetCount (&cnt);
    for (UINT i = 0; i < cnt; ++i)
    {
        IMMDevice* d = nullptr;
        if (FAILED (col->Item (i, &d))) continue;
        EndpointW e; e.id = deviceId (d); e.name = friendlyName (d); e.isDefault = (! defId.empty() && e.id == defId);
        out.push_back (std::move (e));
        d->Release();
    }
    col->Release();
    return out;
}

// 장치 샘플 형식
enum class Fmt { F32, I16, I24, I32, I24in32, Unknown };

Fmt classify (const WAVEFORMATEX* wf)
{
    WORD tag = wf->wFormatTag;
    int valid = wf->wBitsPerSample;
    if (tag == WAVE_FORMAT_EXTENSIBLE && wf->cbSize >= 22)
    {
        auto* ex = (const WAVEFORMATEXTENSIBLE*) wf;
        tag = (WORD) ex->SubFormat.Data1;                       // KSDATAFORMAT_SUBTYPE_* 의 Data1 = 형식 태그
        if (ex->Samples.wValidBitsPerSample) valid = ex->Samples.wValidBitsPerSample;
    }
    if (tag == WAVE_FORMAT_IEEE_FLOAT && wf->wBitsPerSample == 32) return Fmt::F32;
    if (tag == WAVE_FORMAT_PCM)
    {
        switch (wf->wBitsPerSample)
        {
            case 16: return Fmt::I16;
            case 24: return Fmt::I24;
            case 32: return valid == 24 ? Fmt::I24in32 : Fmt::I32;   // 24비트 유효값은 상위 비트에 정렬
            default: break;
        }
    }
    return Fmt::Unknown;
}

inline float clip1 (float x) { return x > 1.f ? 1.f : (x < -1.f ? -1.f : x); }

} // namespace

//==============================================================================
struct AudioOutput::Impl
{
    std::thread th;
    HANDLE stopEv = nullptr;
    std::atomic<bool> running { false };   // 렌더 루프가 살아 있는 동안 true (장치 무효화 시 false)

    AudioCallback cb;
    std::wstring wantName;
    int wantFrames = 0;

    // 열린 뒤 고정되는 값(open 반환 전에 렌더 스레드가 기록)
    double sr = 0;
    int period = 0;
    std::string devName;
    std::string lastError;

    void threadMain (std::promise<std::string>* initResult);
    int runOnce (std::promise<std::string>*& initResult);   // 0 = 끝(멈춤·첫 열기 실패), 1 = 다시 열기
};

// 장치를 연 채로 돌다가, 기본 장치가 바뀌었거나(기본을 따를 때) 장치가 사라지면 다시 연다(10-17: 앱을 켤 때의 기본 장치에
// 계속 묶여 있어서, 그 뒤 Windows 기본을 KEF 로 바꿔도 소리가 Realtek 으로 나가던 것).
void AudioOutput::Impl::threadMain (std::promise<std::string>* initResult)
{
    for (;;)
    {
        if (runOnce (initResult) == 0) break;
        if (WaitForSingleObject (stopEv, 500) == WAIT_OBJECT_0) break;
    }
    if (initResult) initResult->set_value ("알 수 없는 초기화 실패");
}

int AudioOutput::Impl::runOnce (std::promise<std::string>*& initResult)
{
    ComScope com;
    IMMDeviceEnumerator* en = nullptr;
    IMMDevice* dev = nullptr;
    IAudioClient* client = nullptr;
    IAudioRenderClient* render = nullptr;
    WAVEFORMATEX* mix = nullptr;
    HANDLE audioEv = nullptr;
    HANDLE mmcss = nullptr;
    std::vector<float> bufL, bufR;
    UINT32 bufSize = 0;
    Fmt fmt = Fmt::Unknown;
    int ch = 0;
    bool started = false;
    bool reopen = false;          // 기본 장치 바뀜·장치 사라짐 → 다시 열기
    const bool firstOpen = initResult != nullptr;
    std::wstring openedId;

    auto fail = [&] (std::string e)
    {
        if (initResult) { initResult->set_value (std::move (e)); initResult = nullptr; }
    };

    HRESULT hr = S_OK;
    do
    {
        if (! com.ok()) { fail (hrText ("CoInitializeEx", com.hr)); break; }
        hr = CoCreateInstance (__uuidof (MMDeviceEnumerator), nullptr, CLSCTX_ALL, __uuidof (IMMDeviceEnumerator), (void**) &en);
        if (FAILED (hr)) { fail (hrText ("MMDeviceEnumerator 생성", hr)); break; }

        // 장치 고르기: 빈 이름 = 기본, 아니면 대소문자 무시 완전일치 → 부분일치
        if (wantName.empty())
        {
            hr = en->GetDefaultAudioEndpoint (eRender, eConsole, &dev);
            if (FAILED (hr)) { fail (hrText ("기본 출력 장치 조회", hr)); break; }
        }
        else
        {
            auto eps = enumerate (en);
            auto want = lowerW (wantName);
            const EndpointW* pick = nullptr;
            for (auto& e : eps) if (lowerW (e.name) == want) { pick = &e; break; }
            if (! pick) for (auto& e : eps) if (lowerW (e.name).find (want) != std::wstring::npos) { pick = &e; break; }
            if (! pick)
            {
                std::string msg = "출력 장치를 찾을 수 없음: \"" + toUtf8 (wantName.c_str()) + "\" (있는 장치:";
                for (auto& e : eps) msg += " \"" + toUtf8 (e.name.c_str()) + "\"";
                fail (msg + ")");
                break;
            }
            hr = en->GetDevice (pick->id.c_str(), &dev);
            if (FAILED (hr)) { fail (hrText ("장치 열기", hr)); break; }
        }
        devName = toUtf8 (friendlyName (dev).c_str());
        openedId = deviceId (dev);

        hr = dev->Activate (__uuidof (IAudioClient), CLSCTX_ALL, nullptr, (void**) &client);
        if (FAILED (hr)) { fail (hrText ("IAudioClient 활성화", hr)); break; }
        hr = client->GetMixFormat (&mix);
        if (FAILED (hr)) { fail (hrText ("GetMixFormat", hr)); break; }
        fmt = classify (mix);
        ch = mix->nChannels;
        sr = (double) mix->nSamplesPerSec;
        if (fmt == Fmt::Unknown || ch < 1) { fail ("지원하지 않는 장치 형식"); break; }

        const DWORD flags = AUDCLNT_STREAMFLAGS_EVENTCALLBACK | AUDCLNT_STREAMFLAGS_NOPERSIST;

        // 1) 작은 주기를 원하면 IAudioClient3 로 엔진 주기 자체를 바꿔 본다(드라이버가 지원할 때만)
        bool inited = false;
        IAudioClient3* c3 = nullptr;
        if (SUCCEEDED (client->QueryInterface (__uuidof (IAudioClient3), (void**) &c3)))
        {
            UINT32 def = 0, fund = 0, mn = 0, mx = 0;
            if (SUCCEEDED (c3->GetSharedModeEnginePeriod (mix, &def, &fund, &mn, &mx)) && fund > 0)
            {
                UINT32 want = wantFrames > 0 ? (UINT32) wantFrames : def;
                UINT32 p = ((want + fund - 1) / fund) * fund;
                p = std::clamp (p, mn, mx);
                if (p < def && SUCCEEDED (c3->InitializeSharedAudioStream (flags, p, mix, nullptr)))
                    inited = true;
            }
            c3->Release();
        }

        // 2) 일반 초기화: 버퍼 길이 = 희망 프레임(0 이면 시스템 최소). 이벤트는 장치 주기마다 온다.
        if (! inited)
        {
            REFERENCE_TIME hns = wantFrames > 0 ? (REFERENCE_TIME) std::llround (wantFrames * 1.0e7 / sr) : 0;
            hr = client->Initialize (AUDCLNT_SHAREMODE_SHARED, flags, hns, 0, mix, nullptr);
            if (FAILED (hr)) { fail (hrText ("IAudioClient::Initialize", hr)); break; }
        }

        // 실제 주기(프레임)
        {
            UINT32 p = 0;
            IAudioClient3* c = nullptr;
            if (inited && SUCCEEDED (client->QueryInterface (__uuidof (IAudioClient3), (void**) &c)))
            {
                WAVEFORMATEX* cur = nullptr;
                if (SUCCEEDED (c->GetCurrentSharedModeEnginePeriod (&cur, &p)) && cur) CoTaskMemFree (cur);
                c->Release();
            }
            if (p == 0)
            {
                REFERENCE_TIME defP = 0, minP = 0;
                client->GetDevicePeriod (&defP, &minP);
                p = (UINT32) std::llround (defP * sr / 1.0e7);
            }
            period = (int) p;
        }

        hr = client->GetBufferSize (&bufSize);
        if (FAILED (hr)) { fail (hrText ("GetBufferSize", hr)); break; }
        audioEv = CreateEventW (nullptr, FALSE, FALSE, nullptr);
        hr = client->SetEventHandle (audioEv);
        if (FAILED (hr)) { fail (hrText ("SetEventHandle", hr)); break; }
        hr = client->GetService (__uuidof (IAudioRenderClient), (void**) &render);
        if (FAILED (hr)) { fail (hrText ("IAudioRenderClient", hr)); break; }

        // 렌더 루프용 버퍼는 여기서 한 번만 잡는다(최대 = 장치 버퍼 크기)
        bufL.assign (bufSize, 0.f);
        bufR.assign (bufSize, 0.f);

        // 시작 전 무음으로 한 번 채운다
        BYTE* data = nullptr;
        if (SUCCEEDED (render->GetBuffer (bufSize, &data))) render->ReleaseBuffer (bufSize, AUDCLNT_BUFFERFLAGS_SILENT);

        DWORD taskIdx = 0;
        mmcss = AvSetMmThreadCharacteristicsW (L"Pro Audio", &taskIdx);
        if (! mmcss) SetThreadPriority (GetCurrentThread(), THREAD_PRIORITY_TIME_CRITICAL);

        hr = client->Start();
        if (FAILED (hr)) { fail (hrText ("IAudioClient::Start", hr)); break; }
        started = true;
        running = true;
        fail ({});   // 성공(빈 문자열) 알림 — 이 뒤로 open() 이 반환된다
    } while (false);

    // ── 렌더 루프 ──────────────────────────────────────────────
    if (started)
    {
        const HANDLE evs[2] = { stopEv, audioEv };
        const int bytesPerSample = mix->wBitsPerSample / 8;
        const int frameBytes = mix->nBlockAlign;
        ULONGLONG lastCheck = GetTickCount64();
        for (;;)
        {
            DWORD w = WaitForMultipleObjects (2, evs, FALSE, 1000);
            if (w == WAIT_OBJECT_0) break;
            if (wantName.empty() && GetTickCount64() - lastCheck >= 1000)   // 기본을 따르는 중: 1초마다 기본 장치 확인
            {
                lastCheck = GetTickCount64();
                IMMDevice* def = nullptr;
                if (SUCCEEDED (en->GetDefaultAudioEndpoint (eRender, eConsole, &def)))
                {
                    const bool changed = deviceId (def) != openedId;
                    def->Release();
                    if (changed) { lastError = "기본 출력 장치가 바뀜"; reopen = true; break; }
                }
            }
            if (w == WAIT_TIMEOUT) continue;                       // 장치가 잠시 멈춤 — 계속 기다린다
            if (w != WAIT_OBJECT_0 + 1) { lastError = "WaitForMultipleObjects 실패"; break; }

            UINT32 pad = 0;
            hr = client->GetCurrentPadding (&pad);
            if (hr == AUDCLNT_E_DEVICE_INVALIDATED) { lastError = "장치가 사라짐(무효화)"; reopen = true; break; }
            if (FAILED (hr)) { lastError = hrText ("GetCurrentPadding", hr); break; }
            const UINT32 n = bufSize - pad;
            if (n == 0) continue;

            BYTE* data = nullptr;
            hr = render->GetBuffer (n, &data);
            if (hr == AUDCLNT_E_DEVICE_INVALIDATED) { lastError = "장치가 사라짐(무효화)"; reopen = true; break; }
            if (FAILED (hr)) { lastError = hrText ("GetBuffer", hr); break; }

            float* L = bufL.data();
            float* R = bufR.data();
            std::memset (L, 0, n * sizeof (float));
            std::memset (R, 0, n * sizeof (float));
            if (cb) cb (L, R, (int) n);

            // 스테레오 float → 장치 형식. 채널 >2: 앞 둘에 L/R, 나머지 0. 모노: 평균.
            std::memset (data, 0, (size_t) n * frameBytes);
            for (UINT32 i = 0; i < n; ++i)
            {
                BYTE* f = data + (size_t) i * frameBytes;
                float a, b;
                if (ch == 1) { a = 0.5f * (L[i] + R[i]); b = 0; }
                else         { a = L[i]; b = R[i]; }
                const int outCh = ch == 1 ? 1 : 2;
                for (int c = 0; c < outCh; ++c)
                {
                    const float x = c == 0 ? a : b;
                    BYTE* s = f + c * bytesPerSample;
                    switch (fmt)
                    {
                        case Fmt::F32: { float v = x; std::memcpy (s, &v, 4); break; }
                        case Fmt::I16: { int16_t v = (int16_t) std::lrint (clip1 (x) * 32767.f); std::memcpy (s, &v, 2); break; }
                        case Fmt::I24: { int32_t v = (int32_t) std::lrint (clip1 (x) * 8388607.f);
                                         s[0] = (BYTE) v; s[1] = (BYTE) (v >> 8); s[2] = (BYTE) (v >> 16); break; }
                        case Fmt::I24in32: { int32_t v = (int32_t) std::lrint (clip1 (x) * 8388607.f) * 256; std::memcpy (s, &v, 4); break; }
                        case Fmt::I32: { int32_t v = (int32_t) std::llrint ((double) clip1 (x) * 2147483647.0); std::memcpy (s, &v, 4); break; }
                        default: break;
                    }
                }
            }
            hr = render->ReleaseBuffer (n, 0);
            if (FAILED (hr)) { lastError = hrText ("ReleaseBuffer", hr); break; }
        }
        running = false;
        client->Stop();
    }

    if (mmcss) AvRevertMmThreadCharacteristics (mmcss);
    safeRelease (render);
    safeRelease (client);
    safeRelease (dev);
    safeRelease (en);
    if (mix) CoTaskMemFree (mix);
    if (audioEv) CloseHandle (audioEv);
    if (! started) return firstOpen ? 0 : 1;   // 처음 열기 실패는 open() 이 오류로 돌려주고, 다시 열기 실패는 잠시 뒤 또 시도
    return reopen ? 1 : 0;
}

//==============================================================================
AudioOutput::AudioOutput() : impl (std::make_unique<Impl>()) {}
AudioOutput::~AudioOutput() { close(); }

std::vector<AudioOutputInfo> AudioOutput::list()
{
    std::vector<AudioOutputInfo> out;
    ComScope com;
    if (! com.ok()) return out;
    IMMDeviceEnumerator* en = nullptr;
    if (FAILED (CoCreateInstance (__uuidof (MMDeviceEnumerator), nullptr, CLSCTX_ALL, __uuidof (IMMDeviceEnumerator), (void**) &en)))
        return out;
    for (auto& e : enumerate (en))
    {
        AudioOutputInfo i;
        i.name = toUtf8 (e.name.c_str());
        i.id = toUtf8 (e.id.c_str());
        i.isDefault = e.isDefault;
        out.push_back (std::move (i));
    }
    en->Release();
    return out;
}

bool AudioOutput::open (const std::string& name, int bufferFrames, AudioCallback cb, std::string& error)
{
    close();
    auto& d = *impl;
    d.cb = std::move (cb);
    d.wantName = fromUtf8 (name);
    d.wantFrames = bufferFrames;
    d.sr = 0; d.period = 0; d.devName.clear(); d.lastError.clear();
    d.stopEv = CreateEventW (nullptr, TRUE, FALSE, nullptr);

    std::promise<std::string> pr;
    auto fut = pr.get_future();
    d.th = std::thread ([&d, p = std::move (pr)] () mutable { d.threadMain (&p); });   // promise 는 스레드가 소유
    std::string err = fut.get();
    if (! err.empty())
    {
        if (d.th.joinable()) d.th.join();
        CloseHandle (d.stopEv); d.stopEv = nullptr;
        d.cb = nullptr;
        d.lastError = err;
        error = err;
        return false;
    }
    return true;
}

void AudioOutput::close()
{
    auto& d = *impl;
    if (d.th.joinable())
    {
        SetEvent (d.stopEv);
        d.th.join();
    }
    if (d.stopEv) { CloseHandle (d.stopEv); d.stopEv = nullptr; }
    d.running = false;
    d.cb = nullptr;
}

bool AudioOutput::isOpen() const           { return impl->running.load(); }
double AudioOutput::sampleRate() const     { return impl->sr; }
int AudioOutput::bufferFrames() const      { return impl->period; }
std::string AudioOutput::deviceName() const { return impl->devName; }

} // namespace mc
