cmake_minimum_required(VERSION 3.22)

project(MusicomaEngine VERSION 0.1.0)

set(CMAKE_MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>")

set(TE_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../third_party/tracktion_engine")
add_subdirectory(${TE_DIR}/modules/juce ${CMAKE_BINARY_DIR}/juce)
add_subdirectory(${TE_DIR}/modules ${CMAKE_BINARY_DIR}/tracktion)

juce_add_gui_app(musicoma_engine
    PRODUCT_NAME "musicoma-engine"
    COMPANY_NAME "Musicoma"
    NEEDS_CURL FALSE
    NEEDS_WEB_BROWSER FALSE)

juce_generate_juce_header(musicoma_engine)

# 콘솔 서브시스템: MCP 서버가 띄웠을 때 로그를 stdout 으로 받는다.
set_target_properties(musicoma_engine PROPERTIES WIN32_EXECUTABLE OFF)

target_compile_features(musicoma_engine PRIVATE cxx_std_20)

target_sources(musicoma_engine PRIVATE
    src/Main.cpp
    src/Session.cpp
    src/Server.cpp
    src/SfzPlugin.cpp)

target_include_directories(musicoma_engine PRIVATE src third_party)

target_compile_definitions(musicoma_engine PRIVATE
    _CONSOLE=1
    JUCE_PLUGINHOST_VST3=1
    JUCE_MODAL_LOOPS_PERMITTED=1
    JUCE_STRICT_REFCOUNTEDPOINTER=1
    JUCE_USE_CURL=0
    JUCE_WEB_BROWSER=0
    TRACKTION_ENABLE_TIMESTRETCH_SOUNDTOUCH=1)

target_link_libraries(musicoma_engine PRIVATE
    tracktion::tracktion_core
    tracktion::tracktion_engine
    tracktion::tracktion_graph
    juce::juce_audio_devices
    juce::juce_audio_processors
    juce::juce_audio_utils
    juce::juce_recommended_config_flags)

if (MSVC)
    target_compile_options(musicoma_engine PRIVATE /bigobj /utf-8)
endif()
