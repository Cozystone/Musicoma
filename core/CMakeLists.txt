cmake_minimum_required(VERSION 3.20)

# Musicoma Core — 자체 오디오 엔진. 표준 라이브러리 + Windows API (+ VST3 SDK, MIT) 만 쓴다. Tracktion·JUCE 없음.
#   musicoma-core     오프라인 렌더러(C1, 렌더 계획 JSON → WAV)
#   musicoma-engine   엔진 서버(127.0.0.1:47800, 기존 프로토콜) — 실시간 재생·VST3·내장 이펙트·녹음
#   test-fx / test-vst3 / test-io   모듈별 시험 프로그램(core/tests/)
project(MusicomaCore LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>")

set(CORE_COMMON
    src/json.cpp
    src/util.cpp
    src/audiofile.cpp
    src/samplepool.cpp
    src/sfz.cpp
    src/dsp.cpp
    src/sampler.cpp
    src/render.cpp)

file(GLOB FX_SRC  CONFIGURE_DEPENDS src/engine/fx_*.cpp)
file(GLOB VST_SRC CONFIGURE_DEPENDS src/engine/vst3_*.cpp)
file(GLOB IO_SRC  CONFIGURE_DEPENDS src/engine/io_*.cpp)
file(GLOB ENG_SRC CONFIGURE_DEPENDS src/engine/eng_*.cpp)

# VST3 SDK(third_party/vst3sdk) 소스 목록·포함 경로 — VST3_SDK_SOURCES / VST3_SDK_INCLUDES / VST3_SDK_DEFINITIONS
include(cmake/vst3sdk.cmake OPTIONAL)

function(mc_options tgt)
    if (MSVC)
        target_compile_options(${tgt} PRIVATE /W3 /utf-8 /O2 /fp:fast /EHsc /permissive- /bigobj)
        target_compile_definitions(${tgt} PRIVATE _CRT_SECURE_NO_WARNINGS UNICODE _UNICODE NOMINMAX WIN32_LEAN_AND_MEAN)
    endif()
    target_include_directories(${tgt} PRIVATE src src/engine)
    if (WIN32)
        target_link_libraries(${tgt} PRIVATE shell32 ws2_32 ole32 oleaut32 uuid avrt winmm user32 gdi32)
    endif()
endfunction()

function(mc_vst3 tgt)
    if (VST3_SDK_SOURCES)
        target_sources(${tgt} PRIVATE ${VST3_SDK_SOURCES})
        target_include_directories(${tgt} PRIVATE ${VST3_SDK_INCLUDES})
        target_compile_definitions(${tgt} PRIVATE ${VST3_SDK_DEFINITIONS})
    endif()
endfunction()

add_executable(musicoma-core src/main.cpp ${CORE_COMMON})
mc_options(musicoma-core)

if (FX_SRC AND EXISTS ${CMAKE_CURRENT_SOURCE_DIR}/tests/test_fx.cpp)
    add_executable(test-fx tests/test_fx.cpp ${FX_SRC} ${CORE_COMMON})
    mc_options(test-fx)
endif()

if (VST_SRC AND EXISTS ${CMAKE_CURRENT_SOURCE_DIR}/tests/test_vst3.cpp)
    add_executable(test-vst3 tests/test_vst3.cpp ${VST_SRC} ${CORE_COMMON})
    mc_options(test-vst3)
    mc_vst3(test-vst3)
endif()

if (IO_SRC AND EXISTS ${CMAKE_CURRENT_SOURCE_DIR}/tests/test_io.cpp)
    add_executable(test-io tests/test_io.cpp ${IO_SRC} ${CORE_COMMON})
    mc_options(test-io)
endif()

if (ENG_SRC)
    add_executable(musicoma-engine ${ENG_SRC} ${FX_SRC} ${VST_SRC} ${IO_SRC} ${CORE_COMMON})
    mc_options(musicoma-engine)
    mc_vst3(musicoma-engine)
endif()

# 개발용: 엔진 뼈대 + I/O 만(내장 이펙트·VST3 는 대역) — 모듈이 준비되기 전 시험
if (ENG_SRC)
    if (VST_SRC)
        add_executable(musicoma-engine-dev ${ENG_SRC} ${IO_SRC} ${VST_SRC} src/engine/stub_fx.cpp ${CORE_COMMON})
        mc_vst3(musicoma-engine-dev)
    else()
        add_executable(musicoma-engine-dev ${ENG_SRC} ${IO_SRC} src/engine/stub_modules.cpp ${CORE_COMMON})
    endif()
    mc_options(musicoma-engine-dev)
endif()
