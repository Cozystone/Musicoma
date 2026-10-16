// Musicoma Engine — VST3 디바이스(createVst3 가 돌려주는 Device 의 구체형). 엔진·시험이 dynamic_cast 로 추가 기능을 쓴다.
#pragma once
#include <string>
#include "device.h"

namespace mc {

class Vst3DeviceApi : public Device
{
public:
    /** 오프라인(렌더) 모드: setupProcessing 의 processMode 를 kOffline 으로. 다음 prepare() 부터 적용. */
    virtual void setOffline (bool offline) = 0;
    /** 편집 창이 열려 있나 / 닫기(창 스레드에서 처리, 기다림) */
    virtual bool editorOpen() const = 0;
    virtual void closeEditor() = 0;
    /** 진단: 매핑이 없어 버린 CC/벤드 수, 플러그인 예외로 멈췄나 */
    virtual int droppedControllers() const = 0;
    virtual bool crashed() const = 0;
    /** 클래스 ID(16진 32자)·경로 */
    virtual std::string pluginPath() const = 0;
};

/** 창 스레드 메시지 루프를 멈춘다(시험·종료용). runVst3WindowThread() 가 돌아온다. */
void stopVst3WindowThread();

} // namespace mc
