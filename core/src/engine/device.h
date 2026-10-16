// Musicoma Engine — 디바이스(악기·이펙트) 공통 인터페이스.
// 클린룸: Tracktion·JUCE 코드를 보지 않고 우리 프로토콜(tests/golden/protocol.json)과 측정(scratch/golden/fx)만 기준으로 만든다.
//
// 스레드: process() 는 오디오 스레드(또는 오프라인 렌더 스레드)에서, 나머지는 명령 스레드에서 불린다.
//         엔진이 그래프 잠금(Engine::graphMutex)으로 둘을 겹치지 않게 하므로 디바이스 안에서 따로 잠글 필요는 없다.
#pragma once
#include <cstdint>
#include <memory>
#include <string>
#include <vector>
#include "../json.h"
#include "../sampler.h"   // MidiEv (frame, kind, a, v)

namespace mc {

/** 파라미터 하나 — device.params 응답 한 줄. value/min/max 는 '사람 단위'(dB, Hz, ms, 반음 …).
    VST3 는 정규화값(0..1)을 value 로, 플러그인이 준 표시 문자열을 text 로. */
struct ParamInfo
{
    std::string id;          // device.set 키 (예: "Low-pass freq", "threshold", VST3 는 파라미터 ID 숫자 문자열)
    std::string name;        // 화면 표시 이름 (예: "Low-shelf freq")
    double value = 0, min = 0, max = 1, def = 0;
    std::string text;        // "110 Hz", "-6.00 dB", "2.00 : 1" …
    bool automatable = true;
};

/** 블록 처리 정보 */
struct ProcessInfo
{
    double sampleRate = 48000;
    double bpm = 120;
    double beat = 0;          // 블록 첫 샘플의 곡 위치(박)
    bool playing = false;     // 재생/렌더 중
    int64_t frame = 0;        // 블록 첫 샘플의 곡 위치(샘플)
};

class Device
{
public:
    virtual ~Device() = default;

    /** 프로토콜의 type 문자열: "musicomaSfz", "4bandEq", "compressor", "reverb", "delay", "chorus", "phaser",
        "lowpass", "pitchShifter", "auxsend", "auxreturn", "vst" … (골든 edit.info 참고) */
    virtual std::string type() const = 0;
    /** 표시 이름: "SFZ Sampler", "4-Band Equaliser", "Compressor", "Surge XT" … */
    virtual std::string name() const = 0;
    virtual bool isInstrument() const { return false; }

    /** 샘플레이트·최대 블록이 바뀔 때마다. 내부 버퍼 할당은 여기서(process 안에서 할당 금지). */
    virtual void prepare (double sampleRate, int maxBlock) = 0;
    /** 재생 시작·탐색 때 꼬리·보이스를 지운다. */
    virtual void reset() {}

    /** 스테레오 제자리 처리. 악기는 L/R 에 '더한다'(들어온 신호는 보통 0). events 의 frame 은 블록 안 위치(0..n-1), 정렬됨. */
    virtual void process (float* L, float* R, int n, const std::vector<MidiEv>& events, const ProcessInfo& info) = 0;

    /** 파라미터 목록(사람 단위). 순서 = index. */
    virtual std::vector<ParamInfo> params() = 0;
    /** id 또는 name(대소문자 무시)으로 찾아 사람 단위 값 설정. 범위 밖이면 자른다. 찾으면 true. */
    virtual bool setParam (const std::string& idOrName, double value) = 0;
    /** "3.5 kHz", "-6 dB" 같은 문자열로 설정(선택). */
    virtual bool setParamText (const std::string& idOrName, const std::string& text) { (void) idOrName; (void) text; return false; }

    /** 저장·되돌리기용 상태(파라미터 값 + 내부 상태). VST3 는 컴포넌트·컨트롤러 상태를 base64 로. */
    virtual Json getState() = 0;
    virtual void setState (const Json& state) = 0;

    /** 소리가 남는 시간(초) — 렌더 꼬리 계산용 */
    virtual double tailSeconds() const { return 0; }
    /** 처리 지연(샘플) */
    virtual int latency() const { return 0; }

    // ── 플러그인 전용(내장은 기본값) ──
    /** 패치 파일(.fxp: CcnK/FPCh 60바이트 헤더 뒤가 상태, 아니면 파일 전체가 상태)을 불러온다. 실패 시 error 채우고 false. */
    virtual bool loadFile (const std::string& path, std::string& error) { (void) path; error = "not a plugin"; return false; }
    /** 플러그인 내장 프로그램 이름들 */
    virtual std::vector<std::string> programs() { return {}; }
    virtual bool setProgram (int index) { (void) index; return false; }
    virtual std::string currentProgramName() { return {}; }
    /** 플러그인 창 열기(사람이 직접 만질 때). 메인(창) 스레드에서 불린다. */
    virtual bool showEditor() { return false; }

    /** 엔진이 관리: 꺼진 디바이스는 process 를 건너뛴다(통과). */
    bool enabled = true;
};

/** 내장 이펙트 만들기 — 이름: "eq", "compressor", "reverb", "delay", "chorus", "phaser", "lowpass" ("filter"), "pitchshift".
    모르는 이름이면 nullptr. (core/src/engine/fx_*.cpp) */
std::unique_ptr<Device> createBuiltinFx (const std::string& name);

/** 내장 이펙트 이름 목록(device.available 의 built_in 에 들어감) */
std::vector<std::string> builtinFxNames();

} // namespace mc
