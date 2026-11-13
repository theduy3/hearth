#include "hearth_audio.h"
#include <cstring>
#include "audio_codec.h"
#include "esp_heap_caps.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "hearth_protocol.h"

namespace { constexpr uint32_t kRate=16000,kChunk=1600; }
void HearthClipFree(HearthClip* clip) {
    if (clip == nullptr) return;
    if (clip->wav != nullptr) heap_caps_free(clip->wav);
    *clip = {};
}

esp_err_t HearthRecordWhile(ZectrixBoard* board, bool (*held)(), uint32_t max_ms,
                            HearthClip* out, void (*ready)()) {
    if (!board || !held || !out || max_ms < 200 || max_ms > 30000) return ESP_ERR_INVALID_ARG;
    *out = {};
    if (!held()) return ESP_ERR_INVALID_SIZE;
    uint32_t maximum = kRate * max_ms / 1000;
    auto* wav = static_cast<uint8_t*>(heap_caps_malloc(44 + maximum * 2, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT));
    if (!wav) return ESP_ERR_NO_MEM;
    board->SetAudioPower(true);
    vTaskDelay(pdMS_TO_TICKS(40));
    AudioCodec* codec = board->PrepareAudio();
    if (!codec || !codec->valid()) {
        board->ReleaseAudio(); heap_caps_free(wav); return ESP_FAIL;
    }
    codec->EnableOutput(false);
    codec->EnableInput(true);
    vTaskDelay(pdMS_TO_TICKS(180));
    std::vector<int16_t> chunk(kChunk);
    bool good = codec->InputData(chunk);  // discard codec settling before ready
    uint32_t samples = 0;
    if (good && held() && ready) ready();
    while (good && held() && samples + kChunk <= maximum) {
        good = codec->InputData(chunk);
        if (good) {
            std::memcpy(wav + 44 + samples * 2, chunk.data(), kChunk * sizeof(int16_t));
            samples += kChunk;
        }
    }
    codec->EnableInput(false);
    board->ReleaseAudio();
    if (!good || samples < kRate / 5) {
        heap_caps_free(wav);
        return good ? ESP_ERR_INVALID_SIZE : ESP_FAIL;
    }
    HearthWavHeader(wav, samples * 2);
    out->wav=wav;out->bytes=44+samples*2;out->samples=samples;out->ms=samples*1000/kRate;
    return ESP_OK;
}

bool HearthSpeaker::Begin() {
    if (codec_) return false;
    board_->SetAudioPower(true);
    vTaskDelay(pdMS_TO_TICKS(40));
    codec_ = board_->PrepareAudio();
    if (!codec_ || !codec_->valid()) { board_->ReleaseAudio(); codec_=nullptr; return false; }
    codec_->EnableInput(false);
    codec_->SetOutputVolume(60);
    codec_->EnableOutput(true);
    return true;
}

bool HearthSpeaker::Write(const int16_t* samples, size_t count) {
    if (!codec_ || !samples || count == 0 || count > 512) return false;
    buffer_.assign(samples,samples+count);
    return codec_->OutputData(buffer_);
}

bool HearthSpeaker::End(bool drain) {
    if (!codec_) return false;
    bool good=true;
    if (drain) {
        buffer_.assign(1600,0);
        good=codec_->OutputData(buffer_);
        vTaskDelay(pdMS_TO_TICKS(100));  // drain DMA before reporting delivery
    }
    codec_->EnableOutput(false);
    board_->ReleaseAudio();
    codec_=nullptr;
    return good;
}
