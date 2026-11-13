#ifndef HEARTH_PROTOCOL_H_
#define HEARTH_PROTOCOL_H_
#include <cstddef>
#include <cstdint>

constexpr size_t kHearthFrameBytes = 30000;
constexpr size_t kHearthMaxAudioBytes = 4 * 1024 * 1024;
using HearthPcmConsumer = bool (*)(const int16_t*, size_t, void*);

// Our owned audio API emits canonical44-byte mono PCM16/16kHz WAV.
// This is deliberately not a general media/container decoder.
class HearthPcmDecoder {
public:
    HearthPcmDecoder(size_t length, HearthPcmConsumer consumer, void* context);
    bool Feed(const uint8_t* bytes, size_t size);
    bool Complete() const;
private:
    size_t length_, received_ = 0, header_size_ = 0;
    uint8_t header_[44]{};
    uint8_t half_ = 0;
    bool have_half_ = false, valid_ = true;
    HearthPcmConsumer consumer_;
    void* context_;
    bool HeaderValid() const;
};
void HearthWavHeader(uint8_t* header, uint32_t pcm_bytes);
bool HearthPageValid(const char* page);
bool HearthRequestIdValid(const char* id);
#endif
