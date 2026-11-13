#ifndef HEARTH_NET_H_
#define HEARTH_NET_H_
#include "hearth_config.h"
#include "hearth_audio.h"
#include "hearth_protocol.h"

struct HearthFrameInfo {
    char page[33]{}, next[33]{}, previous[33]{}, etag[67]{};
};
bool HearthFrameInfoValid(const HearthFrameInfo&);
struct HearthDeviceStatus {
    bool present=false;
    char id[33]{},client[129]{},status[17]{},speech[17]{};
};
void HearthNetStop();
int HearthNetLastStatus();
esp_err_t HearthFetchFrame(const HearthConfig&, const char* page, const char* etag,
                          uint8_t* pixels, HearthFrameInfo*, bool* unchanged);
esp_err_t HearthFetchDevice(const HearthConfig&, HearthDeviceStatus*);
esp_err_t HearthUpload(const HearthConfig&, const HearthClip&, const char* client_id, char (&request_id)[33]);
esp_err_t HearthAck(const HearthConfig&, const char* request_id);
esp_err_t HearthFetchAudio(const HearthConfig&, const char* request_id, HearthPcmConsumer,
                          void* context, bool (*cancelled)(void*));
#endif
