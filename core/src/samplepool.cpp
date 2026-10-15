#include "samplepool.h"

namespace mc {

std::shared_ptr<const AudioData> SamplePool::get (const std::string& path)
{
    std::shared_ptr<Entry> e;
    {
        std::lock_guard<std::mutex> l (mapLock);
        auto& slot = entries[path];
        if (! slot) slot = std::make_shared<Entry>();
        e = slot;
    }

    std::call_once (e->once, [&]
    {
        auto d = std::make_shared<AudioData>();
        std::string err;
        if (readAudioFile (u8path (path), *d, err))
        {
            e->data = d;
            ++loaded;
            bytes += (size_t) d->frames * (size_t) d->channels * sizeof (float);
        }
        else
        {
            ++failed;
            logWarn ("sample: " + err);
        }
    });

    return e->data;
}

} // namespace mc
