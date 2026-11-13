#ifndef HEARTH_AUDIO_H_
#define HEARTH_AUDIO_H_
#include <cstddef>
#include <cstdint>
#include <vector>
#include "esp_err.h"
#include "zectrix_board.h"
class AudioCodec;
struct HearthClip { uint8_t* wav=nullptr; size_t bytes=0; uint32_t samples=0,ms=0; };
void HearthClipFree(HearthClip* clip);
esp_err_t HearthRecordWhile(ZectrixBoard* board, bool (*held)(), uint32_t max_ms,
                            HearthClip* out, void (*ready)());
// Only the audio task may construct/use this codec owner or capture audio.
class HearthSpeaker {
public:
    explicit HearthSpeaker(ZectrixBoard* board): board_(board) {}
    bool Begin();
    bool Write(const int16_t* samples, size_t count);
    bool End(bool drain);
private:
    ZectrixBoard* board_;
    AudioCodec* codec_=nullptr;
    std::vector<int16_t> buffer_;
};
#endif
