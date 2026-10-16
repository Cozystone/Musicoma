// 개발용 대역: 내장 이펙트 모듈이 아직 없을 때(musicoma-engine-dev). 출시 빌드에는 안 들어감.
#include "device.h"
namespace mc {
std::unique_ptr<Device> createBuiltinFx (const std::string&) { return nullptr; }
std::vector<std::string> builtinFxNames() { return {}; }
}
