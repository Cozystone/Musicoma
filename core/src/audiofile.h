// Musicoma Core — 오디오 파일 읽기/쓰기 (WAV 8/16/24/32/32f/64f, FLAC 자체 디코더)
#pragma once
#include <cstdint>
#include <string>
#include <vector>
#include "util.h"

namespace mc {

struct AudioData
{
    int channels = 0;
    double sampleRate = 0;
    int64_t frames = 0;
    std::vector<std::vector<float>> ch;   // 채널별 (planar)
    int64_t loopStart = -1, loopEnd = -1; // WAV smpl 청크 (끝 포함)
};

/** 매직 바이트로 형식을 골라 읽는다. 실패하면 false + err */
bool readAudioFile (const fs::path& p, AudioData& out, std::string& err);

bool decodeWav (const uint8_t* d, size_t n, AudioData& out, std::string& err);
bool decodeFlac (const uint8_t* d, size_t n, AudioData& out, std::string& err);

/** 24비트(또는 16/32f) PCM WAV 로 쓴다. 입력은 채널별 float. */
bool writeWav (const fs::path& p, const std::vector<std::vector<float>>& ch, int64_t frames,
               int sampleRate, int bits, std::string& err);

} // namespace mc
