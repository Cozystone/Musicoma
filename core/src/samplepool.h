// Musicoma Core — 샘플 풀: 파일 하나는 한 번만 읽어 모든 트랙이 함께 쓴다.
#pragma once
#include <atomic>
#include <map>
#include <memory>
#include <mutex>
#include <string>
#include "audiofile.h"

namespace mc {

class SamplePool
{
public:
    /** 처음 요청한 스레드가 읽고, 동시에 요청한 다른 스레드는 기다렸다가 같은 것을 받는다. 실패하면 nullptr. */
    std::shared_ptr<const AudioData> get (const std::string& path);

    size_t filesLoaded() const  { return loaded.load(); }
    size_t bytesLoaded() const  { return bytes.load(); }
    size_t filesFailed() const  { return failed.load(); }

private:
    struct Entry
    {
        std::once_flag once;
        std::shared_ptr<const AudioData> data;
    };

    std::mutex mapLock;
    std::map<std::string, std::shared_ptr<Entry>> entries;
    std::atomic<size_t> loaded { 0 }, bytes { 0 }, failed { 0 };
};

} // namespace mc
