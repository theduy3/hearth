#include <cassert>
#include <cstdint>
#include <cstdio>
#include <vector>
#include "hearth_protocol.h"

bool Collect(const int16_t* samples,size_t count,void* context) {
    auto* output=static_cast<std::vector<int16_t>*>(context);
    output->insert(output->end(),samples,samples+count);
    return true;
}
bool Cancel(const int16_t*,size_t,void*) { return false; }
int main() {
    std::vector<uint8_t> wav(50);
    HearthWavHeader(wav.data(),6);
    wav[44]=0;wav[45]=128;wav[46]=0;wav[47]=0;wav[48]=255;wav[49]=127;
    for(size_t chunk=1;chunk<50;++chunk) {
        std::vector<int16_t> output;
        HearthPcmDecoder decoder(wav.size(),Collect,&output);
        for(size_t offset=0;offset<wav.size();) {
            size_t n=std::min(chunk,wav.size()-offset);
            assert(decoder.Feed(wav.data()+offset,n));offset+=n;
        }
        assert(decoder.Complete());
        assert((output==std::vector<int16_t>{-32768,0,32767}));
    }
    std::vector<int16_t> output;
    HearthPcmDecoder truncated(wav.size(),Collect,&output);
    assert(truncated.Feed(wav.data(),49));assert(!truncated.Complete());
    auto stereo=wav;stereo[22]=2;
    HearthPcmDecoder invalid(stereo.size(),Collect,&output);
    assert(!invalid.Feed(stereo.data(),stereo.size()));assert(!invalid.Complete());
    HearthPcmDecoder cancelled(wav.size(),Cancel,nullptr);
    assert(!cancelled.Feed(wav.data(),wav.size()));assert(!cancelled.Complete());
    assert(HearthPageValid("tasks:3"));assert(!HearthPageValid("today&token=other"));assert(!HearthPageValid(nullptr));
    assert(HearthRequestIdValid("0123456789abcdef0123456789abcdef"));
    assert(!HearthRequestIdValid("../../approval/token"));
    std::puts("NOTE4C_PROTOCOL_OK");
}
