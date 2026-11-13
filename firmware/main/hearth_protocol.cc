#include "hearth_protocol.h"
#include <cctype>
#include <cstring>

namespace {
uint16_t U16(const uint8_t* p) { return static_cast<uint16_t>(p[0] | (p[1] << 8)); }
uint32_t U32(const uint8_t* p) {
    return static_cast<uint32_t>(p[0]) | (static_cast<uint32_t>(p[1]) << 8) |
           (static_cast<uint32_t>(p[2]) << 16) | (static_cast<uint32_t>(p[3]) << 24);
}
void Put16(uint8_t* p, uint16_t value) { p[0] = value; p[1] = value >> 8; }
void Put32(uint8_t* p, uint32_t value) { for (int i = 0; i < 4; ++i) p[i] = value >> (i * 8); }
}

uint32_t HearthStatusPollMs(const char* state, const char* speech) {
    bool working=state && (!std::strcmp(state,"queued") || !std::strcmp(state,"transcribing") || !std::strcmp(state,"processing"));
    bool waiting_audio=state && speech && !std::strcmp(state,"completed") && !std::strcmp(speech,"pending");
    return working || waiting_audio ? 500 : 5000;
}

HearthPcmDecoder::HearthPcmDecoder(size_t length, HearthPcmConsumer consumer, void* context)
    : length_(length), consumer_(consumer), context_(context) {
    valid_ = length > 44 && length <= kHearthMaxAudioBytes && consumer != nullptr;
}

bool HearthPcmDecoder::HeaderValid() const {
    return std::memcmp(header_, "RIFF", 4) == 0 && std::memcmp(header_ + 8, "WAVEfmt ", 8) == 0 &&
        U32(header_ + 16) == 16 && U16(header_ + 20) == 1 && U16(header_ + 22) == 1 &&
        U32(header_ + 24) == 16000 && U32(header_ + 28) == 32000 && U16(header_ + 32) == 2 &&
        U16(header_ + 34) == 16 && std::memcmp(header_ + 36, "data", 4) == 0 &&
        static_cast<uint64_t>(U32(header_ + 4)) + 8 == length_ &&
        static_cast<uint64_t>(U32(header_ + 40)) + 44 == length_ && (U32(header_ + 40) & 1) == 0;
}

bool HearthPcmDecoder::Feed(const uint8_t* bytes, size_t size) {
    if (!valid_ || bytes == nullptr || size > length_ - received_) return valid_ = false;
    received_ += size;
    int16_t output[512]{};
    size_t count = 0;
    for (size_t i = 0; i < size; ++i) {
        if (header_size_ < sizeof(header_)) {
            header_[header_size_++] = bytes[i];
            if (header_size_ == sizeof(header_) && !HeaderValid()) return valid_ = false;
            continue;
        }
        if (!have_half_) { half_ = bytes[i]; have_half_ = true; continue; }
        uint16_t raw = static_cast<uint16_t>(half_ | (static_cast<uint16_t>(bytes[i]) << 8));
        std::memcpy(&output[count++], &raw, sizeof(raw));
        have_half_ = false;
        if (count == 512) {
            if (!consumer_(output, count, context_)) return valid_ = false;
            count = 0;
        }
    }
    if (count && !consumer_(output, count, context_)) return valid_ = false;
    return true;
}

bool HearthPcmDecoder::Complete() const {
    return valid_ && header_size_ == sizeof(header_) && received_ == length_ && !have_half_;
}

void HearthWavHeader(uint8_t* p, uint32_t bytes) {
    std::memcpy(p, "RIFF", 4); Put32(p + 4, bytes + 36);
    std::memcpy(p + 8, "WAVEfmt ", 8); Put32(p + 16, 16);
    Put16(p + 20, 1); Put16(p + 22, 1); Put32(p + 24, 16000);
    Put32(p + 28, 32000); Put16(p + 32, 2); Put16(p + 34, 16);
    std::memcpy(p + 36, "data", 4); Put32(p + 40, bytes);
}

bool HearthPageValid(const char* page) {
    if (page == nullptr) return false;
    size_t size = strnlen(page, 33);
    if (size == 0 || size > 32) return false;
    for (size_t i = 0; i < size; ++i) {
        unsigned char ch = static_cast<unsigned char>(page[i]);
        if (!(ch >= 'a' && ch <= 'z') && !(ch >= '0' && ch <= '9') && ch != ':') return false;
    }
    return true;
}

bool HearthRequestIdValid(const char* id) {
    if (id == nullptr) return false;
    if (strnlen(id, 33) != 32) return false;
    for (size_t i = 0; i < 32; ++i) if (!((id[i] >= 'a' && id[i] <= 'f') || (id[i] >= '0' && id[i] <= '9'))) return false;
    return true;
}
