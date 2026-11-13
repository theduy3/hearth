#include "hearth_net.h"
#include <algorithm>
#include <cstdio>
#include <cstring>
#include <strings.h>
#include <string>
#include "cJSON.h"
#include "esp_crt_bundle.h"
#include "esp_http_client.h"

namespace {
struct ResponseHeaders {
    HearthFrameInfo frame{};
    char type[80]{};
    bool invalid=false;
};
void HeaderCopy(char* out,size_t cap,const char* value,ResponseHeaders* headers) {
    if (!value || std::strlen(value)>=cap) { headers->invalid=true;return; }
    std::memcpy(out,value,std::strlen(value)+1);
}
esp_err_t Event(esp_http_client_event_t* event) {
    if (event->event_id!=HTTP_EVENT_ON_HEADER || !event->header_key) return ESP_OK;
    auto* h=static_cast<ResponseHeaders*>(event->user_data);
    const char* key=event->header_key;
    if (!strcasecmp(key,"Content-Type")) HeaderCopy(h->type,sizeof(h->type),event->header_value,h);
    if (!strcasecmp(key,"ETag")) HeaderCopy(h->frame.etag,sizeof(h->frame.etag),event->header_value,h);
    if (!strcasecmp(key,"X-Hearth-Page")) HeaderCopy(h->frame.page,sizeof(h->frame.page),event->header_value,h);
    if (!strcasecmp(key,"X-Hearth-Next")) HeaderCopy(h->frame.next,sizeof(h->frame.next),event->header_value,h);
    if (!strcasecmp(key,"X-Hearth-Previous")) HeaderCopy(h->frame.previous,sizeof(h->frame.previous),event->header_value,h);
    return ESP_OK;
}
class Http {
public:
    ResponseHeaders headers{};
    esp_http_client_handle_t client=nullptr;
    Http(const HearthConfig& config,const std::string& path) {
        if (!HearthConfigComplete(config)) return;
        std::string url=std::string(config.hub)+path;
        esp_http_client_config_t options{};
        options.url=url.c_str(); options.timeout_ms=10000;
        options.crt_bundle_attach=esp_crt_bundle_attach;
        options.disable_auto_redirect=true; options.event_handler=Event;
        options.user_data=&headers; options.buffer_size=2048;
        client=esp_http_client_init(&options);
        if (client) {
            char auth[112]{};
            std::snprintf(auth,sizeof(auth),"Bearer %s",config.token);
            if (esp_http_client_set_header(client,"Authorization",auth)!=ESP_OK) {
                esp_http_client_cleanup(client);client=nullptr;
            }
        }
    }
    ~Http() { if (client) { esp_http_client_close(client);esp_http_client_cleanup(client); } }
    esp_err_t Open(const uint8_t* data=nullptr,size_t size=0,const char* type=nullptr,const char* upload=nullptr,const char* etag=nullptr) {
        if (!client) return ESP_ERR_NO_MEM;
        if (data) esp_http_client_set_method(client,HTTP_METHOD_POST);
        if (type) esp_http_client_set_header(client,"Content-Type",type);
        if (upload) esp_http_client_set_header(client,"X-Hearth-Request-Id",upload);
        if (etag && *etag) esp_http_client_set_header(client,"If-None-Match",etag);
        esp_err_t result=esp_http_client_open(client,static_cast<int>(size));
        if (result!=ESP_OK) return result;
        size_t sent=0;
        while (sent<size) {
            int n=esp_http_client_write(client,reinterpret_cast<const char*>(data+sent),std::min<size_t>(4096,size-sent));
            if (n<=0) return ESP_FAIL;
            sent+=static_cast<size_t>(n);
        }
        if (esp_http_client_fetch_headers(client)<0 || headers.invalid) return ESP_ERR_INVALID_RESPONSE;
        return ESP_OK;
    }
    int Status() const { return esp_http_client_get_status_code(client); }
    int64_t Length() const { return esp_http_client_get_content_length(client); }
    bool Read(uint8_t* data,size_t size) {
        size_t have=0;
        while (have<size) {
            int n=esp_http_client_read(client,reinterpret_cast<char*>(data+have),std::min<size_t>(2048,size-have));
            if (n<=0) return false;
            have+=static_cast<size_t>(n);
        }
        return esp_http_client_is_complete_data_received(client);
    }
    cJSON* Json() {
        int64_t size=Length();
        if (size<=0 || size>2048) return nullptr;
        char data[2049]{};
        if (!Read(reinterpret_cast<uint8_t*>(data),static_cast<size_t>(size))) return nullptr;
        return cJSON_ParseWithLength(data,static_cast<size_t>(size));
    }
};

bool String(cJSON* object,const char* key,char* target,size_t capacity) {
    cJSON* value=cJSON_GetObjectItemCaseSensitive(object,key);
    if (!cJSON_IsString(value) || !value->valuestring || std::strlen(value->valuestring)>=capacity) return false;
    std::strcpy(target,value->valuestring);
    return true;
}
}

bool HearthFrameInfoValid(const HearthFrameInfo& info) {
    if (!HearthPageValid(info.page) || !HearthPageValid(info.next) || !HearthPageValid(info.previous) || strnlen(info.etag,sizeof(info.etag))!=66 || info.etag[0]!='"' || info.etag[65]!='"') return false;
    for (size_t i=1;i<65;++i) if (!((info.etag[i]>='0'&&info.etag[i]<='9')||(info.etag[i]>='a'&&info.etag[i]<='f'))) return false;
    return true;
}
namespace {
std::string RequestPath(const char* id,const char* suffix) { return std::string("/v1/requests/")+id+suffix; }
}

esp_err_t HearthFetchFrame(const HearthConfig& config,const char* page,const char* etag,uint8_t* pixels,HearthFrameInfo* info,bool* unchanged) {
    if (!HearthPageValid(page) || !pixels || !info || !unchanged) return ESP_ERR_INVALID_ARG;
    Http http(config,std::string("/v1/frame?page=")+page);
    esp_err_t result=http.Open(nullptr,0,nullptr,nullptr,etag);
    if (result!=ESP_OK) return result;
    if (!HearthFrameInfoValid(http.headers.frame)) return ESP_ERR_INVALID_RESPONSE;
    if (http.Status()==304) {
        if (!etag || !*etag || std::strcmp(etag,http.headers.frame.etag)!=0) return ESP_ERR_INVALID_RESPONSE;
        *unchanged=true;*info=http.headers.frame;return ESP_OK;
    }
    if (http.Status()!=200 || http.Length()!=kHearthFrameBytes || std::strcmp(http.headers.type,"application/vnd.catthew.bwry2")) return ESP_ERR_INVALID_RESPONSE;
    if (!http.Read(pixels,kHearthFrameBytes)) return ESP_FAIL;
    *unchanged=false;*info=http.headers.frame;return ESP_OK;
}

esp_err_t HearthFetchDevice(const HearthConfig& config,HearthDeviceStatus* status) {
    if (!status) return ESP_ERR_INVALID_ARG;
    *status={};
    Http http(config,"/v1/device");
    esp_err_t result=http.Open();
    if (result!=ESP_OK) return result;
    if (http.Status()!=200) return ESP_ERR_INVALID_RESPONSE;
    cJSON* body=http.Json();
    if (!cJSON_IsObject(body)) { cJSON_Delete(body);return ESP_ERR_INVALID_RESPONSE; }
    cJSON* request=cJSON_GetObjectItemCaseSensitive(body,"request");
    bool good=cJSON_IsNull(request);
    if (cJSON_IsObject(request)) {
        good=String(request,"id",status->id,sizeof(status->id)) && HearthRequestIdValid(status->id) &&
             String(request,"client_id",status->client,sizeof(status->client)) &&
             String(request,"status",status->status,sizeof(status->status)) &&
             String(request,"speech_status",status->speech,sizeof(status->speech));
        status->present=good;
    }
    cJSON_Delete(body);
    return good ? ESP_OK : ESP_ERR_INVALID_RESPONSE;
}

esp_err_t HearthUpload(const HearthConfig& config,const HearthClip& clip,const char* client_id,char (&id)[33]) {
    Http http(config,"/v1/utterance");
    esp_err_t result=http.Open(clip.wav,clip.bytes,"audio/wav",client_id);
    if (result!=ESP_OK) return result;
    if (http.Status()!=202) return ESP_ERR_INVALID_RESPONSE;
    cJSON* body=http.Json();
    bool good=String(body,"request_id",id,sizeof(id)) && HearthRequestIdValid(id);
    cJSON_Delete(body);
    return good ? ESP_OK : ESP_ERR_INVALID_RESPONSE;
}

esp_err_t HearthAck(const HearthConfig& config,const char* id) {
    if (!HearthRequestIdValid(id)) return ESP_ERR_INVALID_ARG;
    Http http(config,RequestPath(id,"/audio-ack"));
    const uint8_t body[]={'{','}'};
    esp_err_t result=http.Open(body,2,"application/json");
    if (result!=ESP_OK) return result;
    return http.Status()==200 ? ESP_OK : ESP_ERR_INVALID_RESPONSE;
}

esp_err_t HearthFetchAudio(const HearthConfig& config,const char* id,HearthPcmConsumer consume,void* context,bool (*cancelled)(void*)) {
    if (!HearthRequestIdValid(id) || !consume || !cancelled) return ESP_ERR_INVALID_ARG;
    if (cancelled(context)) return ESP_ERR_INVALID_STATE;
    Http http(config,RequestPath(id,"/audio"));
    esp_err_t result=http.Open();
    if (result!=ESP_OK) return result;
    if (http.Status()!=200 || http.Length()<=44 || http.Length()>static_cast<int64_t>(kHearthMaxAudioBytes) || std::strcmp(http.headers.type,"audio/wav")) return ESP_ERR_INVALID_RESPONSE;
    HearthPcmDecoder decoder(static_cast<size_t>(http.Length()),consume,context);
    uint8_t buffer[1024]{};
    for (;;) {
        if (cancelled(context)) return ESP_ERR_INVALID_STATE;
        int n=esp_http_client_read(http.client,reinterpret_cast<char*>(buffer),sizeof(buffer));
        if (n<0) return ESP_FAIL;
        if (n==0) break;
        if (!decoder.Feed(buffer,static_cast<size_t>(n))) return ESP_FAIL;
    }
    return decoder.Complete() && esp_http_client_is_complete_data_received(http.client) ? ESP_OK : ESP_FAIL;
}
