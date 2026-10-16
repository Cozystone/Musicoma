# Steinberg VST3 SDK 3.8.1 (MIT) — 호스팅에 필요한 소스만. vstgui·base 라이브러리는 쓰지 않는다.
# core/CMakeLists.txt 가 include → VST3_SDK_SOURCES / VST3_SDK_INCLUDES / VST3_SDK_DEFINITIONS
set(VST3_SDK_ROOT "${CMAKE_CURRENT_LIST_DIR}/../../third_party/vst3sdk")
get_filename_component(VST3_SDK_ROOT "${VST3_SDK_ROOT}" ABSOLUTE)

if (EXISTS "${VST3_SDK_ROOT}/pluginterfaces/base/funknown.cpp")
    set(VST3_SDK_SOURCES
        # pluginterfaces: FUnknown·IID·문자열
        ${VST3_SDK_ROOT}/pluginterfaces/base/coreiids.cpp
        ${VST3_SDK_ROOT}/pluginterfaces/base/funknown.cpp
        ${VST3_SDK_ROOT}/pluginterfaces/base/ustring.cpp
        ${VST3_SDK_ROOT}/pluginterfaces/base/conststringtable.cpp
        # VST 인터페이스 IID
        ${VST3_SDK_ROOT}/public.sdk/source/vst/vstinitiids.cpp
        ${VST3_SDK_ROOT}/public.sdk/source/common/commoniids.cpp
        # IBStream 메모리 스트림
        ${VST3_SDK_ROOT}/public.sdk/source/common/memorystream.cpp
        # 호스팅 도우미: PluginFactory/ClassInfo, IHostApplication(IMessage·IAttributeList), IPlugInterfaceSupport
        ${VST3_SDK_ROOT}/public.sdk/source/vst/hosting/module.cpp
        ${VST3_SDK_ROOT}/public.sdk/source/vst/hosting/hostclasses.cpp
        ${VST3_SDK_ROOT}/public.sdk/source/vst/hosting/pluginterfacesupport.cpp
        ${VST3_SDK_ROOT}/public.sdk/source/vst/utility/stringconvert.cpp
        ${VST3_SDK_ROOT}/public.sdk/source/common/commonstringconvert.cpp
    )
    set(VST3_SDK_INCLUDES ${VST3_SDK_ROOT})
    set(VST3_SDK_DEFINITIONS RELEASE=1)
    # SDK 소스는 경고가 많다 — 우리 /W3 은 유지하되 C4996(codecvt deprecated)만 끈다
    set_source_files_properties(${VST3_SDK_SOURCES} PROPERTIES COMPILE_OPTIONS "/wd4996;/wd4244;/wd4267")
else()
    message(WARNING "VST3 SDK not found at ${VST3_SDK_ROOT} — VST3 hosting disabled")
endif()
