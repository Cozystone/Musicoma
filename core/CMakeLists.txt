cmake_minimum_required(VERSION 3.20)

# Musicoma Core — 자체 오디오 엔진 (C1: 오프라인 렌더). 표준 라이브러리 + Windows API 만 쓴다.
project(MusicomaCore LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>")

add_executable(musicoma-core
    src/main.cpp
    src/json.cpp
    src/util.cpp
    src/audiofile.cpp
    src/samplepool.cpp
    src/sfz.cpp
    src/dsp.cpp
    src/sampler.cpp
    src/render.cpp)

if (MSVC)
    target_compile_options(musicoma-core PRIVATE /W3 /utf-8 /O2 /fp:fast /EHsc /permissive-)
    target_compile_definitions(musicoma-core PRIVATE _CRT_SECURE_NO_WARNINGS UNICODE _UNICODE)
endif()

if (WIN32)
    target_link_libraries(musicoma-core PRIVATE shell32)
endif()
