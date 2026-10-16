// 개발용 대역: 내장 이펙트·VST3 모듈이 아직 없을 때 엔진 뼈대만 빌드(musicoma-engine-dev). 출시 빌드에는 안 들어감.
#include <windows.h>
#include "device.h"
#include "vst3host.h"
namespace mc {
std::unique_ptr<Device> createBuiltinFx (const std::string&) { return nullptr; }
std::vector<std::string> builtinFxNames() { return {}; }
std::vector<Vst3Desc> scanVst3 (const std::vector<std::string>&, std::vector<std::string>*) { return {}; }
std::unique_ptr<Device> createVst3 (const Vst3Desc&, std::string& error) { error = "VST3 module not built"; return nullptr; }
void runVst3WindowThread() { MSG msg; while (GetMessageW (&msg, nullptr, 0, 0) > 0) { TranslateMessage (&msg); DispatchMessageW (&msg); } }
}
