#include <atomic>
#include <cstdio>
#include <cstring>
#include <mutex>
#include <new>
#include "driver/gpio.h"
#include "esp_heap_caps.h"
#include "esp_random.h"
#include "esp_sleep.h"
#include "esp_system.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/task.h"
#include "hearth_audio.h"
#include "hearth_config.h"
#include "hearth_net.h"
#include "hearth_protocol.h"
#include "hearth_wifi.h"
#include "nvs_flash.h"
#include "zectrix_board.h"
#include "zectrix_board_config.h"
#include "zectrix_epd.h"

extern const uint8_t setup_frame[] asm("_binary_setup_frame_bin_start");
extern const uint8_t offline_badge[] asm("_binary_offline_badge_bin_start");

namespace {
constexpr uint32_t kCacheMagic=0x43504631;
struct Frame { uint32_t magic=kCacheMagic;HearthFrameInfo info{};uint8_t pixels[kHearthFrameBytes]{}; };
struct Upload { HearthClip clip{};char client[33]{};uint32_t generation=0;int64_t created=0; };
struct AudioCommand { char id[33]{};uint32_t generation=0,attempt=0; };
struct AudioPacket { uint32_t generation=0,attempt=0;uint16_t count=0;bool end=false,good=false;char id[33]{};int16_t samples[512]{}; };

ZectrixBoard g_board;
HearthConfig g_config{};
std::mutex g_mutex,g_audio_flash;
Frame* g_pending_frame=nullptr;
uint32_t g_pending_nav=0,g_nav=0;
Upload* g_upload=nullptr;
HearthFrameInfo g_displayed{},g_navigation{};
int g_steps=0;
char g_desired[33]="today",g_client[129]{},g_played[33]{},g_dismissed[33]{},g_scheduled[33]{},g_page_applied[33]{},g_ack[33]{};
bool g_have_frame=false,g_suppress_audio=false;
char g_audio_target[33]{};
unsigned g_audio_attempts=0;
uint32_t g_audio_sequence=0;
int64_t g_audio_retry_after=0;
std::atomic<bool> g_audio_stopped{false},g_display_stopped{false},g_sleep_requested{false};
std::atomic<uint32_t> g_audio_generation{0};
std::atomic<bool> g_record{false},g_capture_ready{false},g_audio_busy{false},g_display_busy{false},g_online{false},g_clock_ready{false},g_processing{false},g_shutdown{false},g_cache_safe{false};
std::atomic<int64_t> g_error_until{0};
std::atomic<unsigned> g_capture_count{0},g_capture_ms{0},g_upload_count{0},g_frame_count{0};
std::atomic<int> g_capture_result{-1},g_upload_result{-1},g_frame_result{-1};
uint32_t g_capture_generation=0;
QueueHandle_t g_audio_commands=nullptr,g_pcm=nullptr;

void Error() { g_error_until.store(esp_timer_get_time()+4000000); }
void Copy(char* target,size_t capacity,const char* value) {
    size_t size=std::strlen(value);
    if (size>=capacity) { Error();return; }
    std::memcpy(target,value,size+1);
}
Frame* AllocateFrame() {
    void* storage=heap_caps_malloc(sizeof(Frame),MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT);
    return storage ? new(storage) Frame{} : nullptr;
}
void FreeFrame(Frame* frame) { if(frame) heap_caps_free(frame); }
void Navigate(bool backwards) {
    std::lock_guard<std::mutex> lock(g_mutex);
    int next=g_steps+(backwards?-1:1);
    if(next>=-16 && next<=16) g_steps=next;
}
bool Held() {
    return gpio_get_level(ZECTRIX_BUTTON_OK)==0 && !g_shutdown.load() && g_capture_generation==g_audio_generation.load();
}
void CaptureReady() { g_capture_ready.store(true); }
void NewId(char (&out)[33]) {
    uint8_t random[16]{};esp_fill_random(random,sizeof(random));
    for(size_t i=0;i<16;++i) std::snprintf(out+i*2,3,"%02x",random[i]);
}

void DisplayTask(void*) {
    zectrix_epd_config_t config{};zectrix_epd_get_default_config(&config);
    zectrix_epd_handle_t epd=nullptr;
    ESP_ERROR_CHECK(zectrix_epd_new(&config,&epd));
    Frame* current=AllocateFrame();
    if (!current || HearthLoadBlob("frame",current,sizeof(Frame))!=ESP_OK || current->magic!=kCacheMagic || !HearthFrameInfoValid(current->info)) {
        FreeFrame(current);current=nullptr;
    } else {
        std::lock_guard<std::mutex> lock(g_mutex);
        g_displayed=current->info;g_navigation=current->info;g_have_frame=true;
        Copy(g_desired,sizeof(g_desired),current->info.page);
    }
    if (!HearthConfigComplete(g_config)) {
        g_display_busy=true;
        if (zectrix_epd_refresh_full_2bpp(epd,setup_frame,kHearthFrameBytes)!=ESP_OK) Error();
        g_display_busy=false;g_cache_safe=true;
        while(!g_shutdown.load()) vTaskDelay(pdMS_TO_TICKS(100));
        g_display_stopped=true;vTaskDelete(nullptr);return;
    }
    auto* paint=static_cast<uint8_t*>(heap_caps_malloc(kHearthFrameBytes,MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT));
    if (!paint) { Error();esp_restart(); }
    bool painted=false,offline=false,dirty=false;
    int64_t began=esp_timer_get_time();
    for (;;) {
        Frame* next=nullptr;uint32_t nav=0,wanted=0;bool more_steps=false;
        { std::lock_guard<std::mutex> lock(g_mutex);next=g_pending_frame;nav=g_pending_nav;g_pending_frame=nullptr;wanted=g_nav;more_steps=g_steps!=0; }
        if(next && (nav!=wanted || more_steps)) {FreeFrame(next);next=nullptr;}
        bool now_offline=!g_online.load();
        Frame* target=next?next:current;
        bool different=next && (!current || std::strcmp(next->info.etag,current->info.etag) || std::strcmp(next->info.page,current->info.page));
        bool should_paint=!g_shutdown.load() && target && (different || !painted || offline!=now_offline);
        // Give the first authenticated fetch a chance to replace the boot cache.
        if(!next && !painted && esp_timer_get_time()-began<5000000) should_paint=false;
        if (should_paint) {
            g_display_busy=true;g_cache_safe=false;
            std::memcpy(paint,target->pixels,kHearthFrameBytes);
            if(now_offline) for(size_t row=0;row<16;++row) std::memcpy(paint+(280+row)*100+76,offline_badge+row*20,20);
            esp_err_t result=zectrix_epd_refresh_full_2bpp(epd,paint,kHearthFrameBytes);
            g_display_busy=false;
            if(result==ESP_OK) {
                if(next) {FreeFrame(current);current=next;next=nullptr;}
                {std::lock_guard<std::mutex> lock(g_mutex);g_displayed=current->info;g_have_frame=true;}
                painted=true;offline=now_offline;dirty=true;
            } else {
                Error();
                if(next) {
                    std::lock_guard<std::mutex> lock(g_mutex);
                    if(!g_pending_frame && nav==g_nav) {g_pending_frame=next;g_pending_nav=nav;next=nullptr;}
                }
                vTaskDelay(pdMS_TO_TICKS(3000));
            }
        }
        FreeFrame(next);
        {
            std::unique_lock<std::mutex> flash_guard(g_audio_flash,std::defer_lock);
            if(dirty && flash_guard.try_lock() && !g_audio_busy.load()) {
                if(HearthStoreBlob("frame",current,sizeof(Frame))==ESP_OK) dirty=false;
                else Error();
            }
        }
        g_cache_safe.store(!dirty && !g_display_busy.load());
        if(g_shutdown.load() && !g_audio_busy.load()) {g_display_stopped=true;vTaskDelete(nullptr);return;}
        vTaskDelay(pdMS_TO_TICKS(100));
    }
}

bool Cancelled(void* context) {
    auto* command=static_cast<AudioCommand*>(context);
    return command->generation!=g_audio_generation.load() || g_shutdown.load();
}
bool Consume(const int16_t* data,size_t count,void* context) {
    auto* command=static_cast<AudioCommand*>(context);
    AudioPacket packet{};packet.generation=command->generation;packet.attempt=command->attempt;packet.count=static_cast<uint16_t>(count);Copy(packet.id,sizeof(packet.id),command->id);
    std::memcpy(packet.samples,data,count*sizeof(int16_t));
    while(!Cancelled(context)) if(xQueueSend(g_pcm,&packet,pdMS_TO_TICKS(20))==pdTRUE) return true;
    return false;
}
void AudioReader(void*) {
    AudioCommand command{};
    for (;;) {
        if(xQueueReceive(g_audio_commands,&command,portMAX_DELAY)!=pdTRUE) continue;
        if(Cancelled(&command)) continue;
        esp_err_t result=g_clock_ready.load()?HearthFetchAudio(g_config,command.id,Consume,&command,Cancelled):ESP_ERR_INVALID_STATE;
        AudioPacket end{};end.generation=command.generation;end.attempt=command.attempt;end.end=true;end.good=result==ESP_OK;Copy(end.id,sizeof(end.id),command.id);
        while(!Cancelled(&command)) if(xQueueSend(g_pcm,&end,pdMS_TO_TICKS(20))==pdTRUE) break;
    }
}

void AudioTask(void*) {
    HearthSpeaker speaker(&g_board);
    bool playing=false;
    uint32_t playing_generation=0,rejected_attempt=UINT32_MAX;
    char playing_id[33]{};
    std::unique_lock<std::mutex> audio_guard(g_audio_flash,std::defer_lock);
    auto stop_playback=[&](bool dismiss) {
        if(!playing) return;
        speaker.End(false);playing=false;g_audio_busy=false;
        if(audio_guard.owns_lock()) audio_guard.unlock();
        if(dismiss) {
            {std::lock_guard<std::mutex> lock(g_mutex);Copy(g_dismissed,sizeof(g_dismissed),playing_id);}
            HearthStoreId("dismissed",playing_id);
        }
    };
    auto failed=[&](const AudioPacket& packet) {
        rejected_attempt=packet.attempt;
        {std::lock_guard<std::mutex> lock(g_mutex);if(!std::strcmp(g_scheduled,packet.id)) g_scheduled[0]=0;g_audio_retry_after=esp_timer_get_time()+5000000;}
        Error();
    };
    for (;;) {
        if(playing && (playing_generation!=g_audio_generation.load() || g_shutdown.load())) stop_playback(true);
        if(g_shutdown.load()) {
            stop_playback(true);g_record=false;g_capture_ready=false;
            audio_guard.lock();g_board.ReleaseAudio();audio_guard.unlock();
            g_audio_busy=false;g_audio_stopped=true;vTaskDelete(nullptr);return;
        }
        if(g_record.exchange(false)) {
            // A hold can be published after the cancellation check above.
            // Always release playback ownership here before locking capture.
            stop_playback(true);
            g_audio_busy=true;g_capture_ready=false;audio_guard.lock();
            g_capture_generation=g_audio_generation.load();
            xQueueReset(g_pcm);
            HearthClip clip{};
            ++g_capture_count;
            esp_err_t result=HearthRecordWhile(&g_board,Held,30000,&clip,CaptureReady);
            g_capture_result=result;g_capture_ms=clip.ms;
            g_capture_ready=false;g_audio_busy=false;audio_guard.unlock();
            if(result==ESP_OK && !g_shutdown.load() && g_capture_generation==g_audio_generation.load()) {
                auto* upload=new(std::nothrow) Upload;
                if(upload) {
                    upload->clip=clip;upload->generation=g_capture_generation;upload->created=esp_timer_get_time();NewId(upload->client);
                    if(HearthStoreId("upload",upload->client)==ESP_OK) {
                        std::lock_guard<std::mutex> lock(g_mutex);
                        if(!g_upload) {g_upload=upload;Copy(g_client,sizeof(g_client),upload->client);upload=nullptr;g_processing=true;}
                    }
                    if(upload) {HearthClipFree(&upload->clip);delete upload;Error();}
                } else {HearthClipFree(&clip);Error();}
            } else {HearthClipFree(&clip);if(result!=ESP_ERR_INVALID_SIZE && !g_shutdown.load()) Error();}
        }
        AudioPacket packet{};
        if(xQueueReceive(g_pcm,&packet,pdMS_TO_TICKS(20))!=pdTRUE) continue;
        if(packet.generation!=g_audio_generation.load() || packet.attempt==rejected_attempt || g_shutdown.load()) continue;
        if(!playing && !packet.end) {
            g_audio_busy=true;audio_guard.lock();
            Copy(playing_id,sizeof(playing_id),packet.id);
            playing=speaker.Begin();playing_generation=packet.generation;
            if(!playing) {g_audio_busy=false;audio_guard.unlock();failed(packet);continue;}
        }
        if(packet.end) {
            bool delivered=playing && packet.good;
            if(playing) delivered=speaker.End(delivered) && delivered;
            playing=false;g_audio_busy=false;
            if(audio_guard.owns_lock()) audio_guard.unlock();
            if(delivered && packet.generation==g_audio_generation.load()) {
                char id[33]{};Copy(id,sizeof(id),playing_id);
                if(HearthStoreId("played",id)==ESP_OK) {
                    std::lock_guard<std::mutex> lock(g_mutex);Copy(g_played,sizeof(g_played),id);Copy(g_ack,sizeof(g_ack),id);
                } else Error();
            } else if(packet.generation!=g_audio_generation.load()) {
                {std::lock_guard<std::mutex> lock(g_mutex);Copy(g_dismissed,sizeof(g_dismissed),packet.id);}
                HearthStoreId("dismissed",packet.id);
            } else failed(packet);
        } else if(playing && !speaker.Write(packet.samples,packet.count)) {
            stop_playback(false);failed(packet);
        }
    }
}

void NetworkTask(void*) {
    bool first=true;
    uint32_t fetched_nav=0;
    int64_t next_frame=0,next_status=0;
    unsigned failures=0;
    while(!g_shutdown.load()) {
        if(!HearthWifiConnected() || (!g_clock_ready.load() && !HearthWifiSyncTime())) {
            g_clock_ready=false;g_online=false;
            {std::lock_guard<std::mutex> lock(g_mutex);if(g_upload && esp_timer_get_time()-g_upload->created>120000000) {HearthClipFree(&g_upload->clip);delete g_upload;g_upload=nullptr;g_processing=false;Error();}}
            vTaskDelay(pdMS_TO_TICKS(1000));continue;
        }
        g_clock_ready=true;
        Upload* upload=nullptr;
        {std::lock_guard<std::mutex> lock(g_mutex);upload=g_upload;g_upload=nullptr;}
        if(upload) {
            char request[33]{};bool accepted=false;
            for(int attempt=0;attempt<3 && !g_shutdown.load() && esp_timer_get_time()-upload->created<120000000;++attempt) {
                HearthDeviceStatus existing{};
                if(HearthFetchDevice(g_config,&existing)==ESP_OK && existing.present && !std::strcmp(existing.client,upload->client)) {Copy(request,sizeof(request),existing.id);accepted=true;break;}
                ++g_upload_count;
                esp_err_t sent=HearthUpload(g_config,upload->clip,upload->client,request);
                g_upload_result=sent;
                if(sent==ESP_OK) {accepted=true;break;}
                vTaskDelay(pdMS_TO_TICKS(1000*(attempt+1)));
            }
            if(accepted) {
                std::lock_guard<std::mutex> lock(g_mutex);
                if(upload->generation==g_audio_generation.load()) g_suppress_audio=false;
            } else {Error();g_processing=false;}
            HearthClipFree(&upload->clip);delete upload;next_status=0;
        }
        char ack[33]{};
        {std::lock_guard<std::mutex> lock(g_mutex);Copy(ack,sizeof(ack),g_ack);}
        if(*ack && HearthAck(g_config,ack)==ESP_OK) {std::lock_guard<std::mutex> lock(g_mutex);if(!std::strcmp(ack,g_ack)) g_ack[0]=0;}
        int64_t now=esp_timer_get_time();
        if(now>=next_status) {
            uint32_t poll_ms=g_processing.load()?1000:5000;
            HearthDeviceStatus status{};
            if(HearthFetchDevice(g_config,&status)==ESP_OK) {
                failures=0;g_online=true;
                std::lock_guard<std::mutex> lock(g_mutex);
                if(status.present && !std::strcmp(status.client,g_client)) {
                    poll_ms=HearthStatusPollMs(status.status,status.speech);
                    bool completed=!std::strcmp(status.status,"completed");
                    bool failed=!std::strcmp(status.status,"failed") || !std::strcmp(status.status,"uncertain");
                    bool speech_ready=!std::strcmp(status.speech,"ready");
                    bool speech_failed=!std::strcmp(status.speech,"failed");
                    if(failed || completed) {
                        g_processing=false;
                        if(failed || speech_failed) Error();
                    }
                    if(completed && status.page[0] && std::strcmp(g_page_applied,status.id)) {
                        Copy(g_desired,sizeof(g_desired),status.page);g_steps=0;++g_nav;
                        Copy(g_page_applied,sizeof(g_page_applied),status.id);
                    }
                    if(std::strcmp(g_audio_target,status.id)) {Copy(g_audio_target,sizeof(g_audio_target),status.id);g_audio_attempts=0;g_audio_retry_after=0;}
                    if(completed && speech_ready && !g_suppress_audio && !g_audio_busy.load() && !g_record.load() && g_audio_attempts<3 && now>=g_audio_retry_after && std::strcmp(status.id,g_played) && std::strcmp(status.id,g_dismissed) && std::strcmp(status.id,g_scheduled)) {
                        AudioCommand command{};Copy(command.id,sizeof(command.id),status.id);command.generation=g_audio_generation.load();command.attempt=++g_audio_sequence;
                        ++g_audio_attempts;Copy(g_scheduled,sizeof(g_scheduled),status.id);xQueueOverwrite(g_audio_commands,&command);
                    }
                    if(completed && speech_ready && !std::strcmp(status.id,g_played)) Copy(g_ack,sizeof(g_ack),status.id);
                }
            } else if(++failures>=3) g_online=false;
            next_status=now+static_cast<int64_t>(poll_ms)*1000;
        }
        char desired[33]{},etag[67]{};uint32_t nav=0;
        {
            std::lock_guard<std::mutex> lock(g_mutex);
            if(g_steps && !std::strcmp(g_navigation.page,g_desired)) {
                Copy(g_desired,sizeof(g_desired),g_steps<0?g_navigation.previous:g_navigation.next);
                g_steps+=g_steps<0?1:-1;++g_nav;
            }
            Copy(desired,sizeof(desired),g_desired);nav=g_nav;
            if(!first && g_have_frame && !std::strcmp(g_displayed.page,desired)) Copy(etag,sizeof(etag),g_displayed.etag);
        }
        if(first || nav!=fetched_nav || now>=next_frame) {
            Frame* frame=AllocateFrame();bool unchanged=false;
            esp_err_t fetched=ESP_ERR_NO_MEM;
            if(frame) {++g_frame_count;fetched=HearthFetchFrame(g_config,desired,etag,frame->pixels,&frame->info,&unchanged);g_frame_result=fetched;}
            if(frame && fetched==ESP_OK) {
                g_online=true;failures=0;
                {
                    std::lock_guard<std::mutex> lock(g_mutex);
                    if(nav==g_nav) {
                        g_navigation=frame->info;Copy(g_desired,sizeof(g_desired),frame->info.page);
                        if(!unchanged) {FreeFrame(g_pending_frame);g_pending_frame=frame;g_pending_nav=nav;frame=nullptr;}
                    }
                }
                fetched_nav=nav;first=false;
            } else if(++failures>=3) g_online=false;
            FreeFrame(frame);next_frame=now+15000000;
        }
        vTaskDelay(pdMS_TO_TICKS(50));
    }
    vTaskDelete(nullptr);
}
void PrintStatus() {
    bool queued;int steps;
    {std::lock_guard<std::mutex> lock(g_mutex);queued=g_upload!=nullptr;steps=g_steps;}
    std::printf("CATTHEW_RESULT {\"ok\":true,\"wifi\":%d,\"wifi_reason\":%d,\"clock\":%d,\"online\":%d,\"capture_ready\":%d,\"audio_busy\":%d,\"display_busy\":%d,\"processing\":%d,\"queued_upload\":%d,\"nav_steps\":%d,\"capture_count\":%u,\"capture_ms\":%u,\"capture_result\":%d,\"upload_count\":%u,\"upload_result\":%d,\"frame_count\":%u,\"frame_result\":%d,\"http_status\":%d}\n",
        int(HearthWifiConnected()),HearthWifiDisconnectReason(),int(g_clock_ready.load()),int(g_online.load()),int(g_capture_ready.load()),int(g_audio_busy.load()),int(g_display_busy.load()),int(g_processing.load()),int(queued),steps,
        g_capture_count.load(),g_capture_ms.load(),g_capture_result.load(),g_upload_count.load(),g_upload_result.load(),g_frame_count.load(),g_frame_result.load(),HearthNetLastStatus());
    std::fflush(stdout);
}
void Quiesce() {
    g_shutdown=true;g_record=false;++g_audio_generation;
    HearthNetStop();
}
esp_err_t ApplyConfig(const HearthConfig& staged) {
    Quiesce();
    int64_t deadline=esp_timer_get_time()+135000000;
    while(!g_audio_stopped.load() || !g_display_stopped.load()) {
        if(esp_timer_get_time()>deadline) return ESP_ERR_TIMEOUT;
        vTaskDelay(pdMS_TO_TICKS(20));
    }
    std::lock_guard<std::mutex> gate(g_audio_flash);
    return HearthConfigSave(staged);
}
void StartTask(TaskFunction_t function,const char* name,uint32_t stack,UBaseType_t priority) {
    if(xTaskCreate(function,name,stack,nullptr,priority,nullptr)!=pdPASS) {Error();esp_restart();}
}
}

extern "C" void app_main() {
    esp_err_t result=nvs_flash_init();
    if(result==ESP_ERR_NVS_NO_FREE_PAGES || result==ESP_ERR_NVS_NEW_VERSION_FOUND) {ESP_ERROR_CHECK(nvs_flash_erase());result=nvs_flash_init();}
    ESP_ERROR_CHECK(result);
    ESP_ERROR_CHECK(g_board.Init());
    if(HearthConfigLoad(&g_config)!=ESP_OK) g_config={};
    HearthLoadId("upload",g_client,sizeof(g_client));HearthLoadId("played",g_played,sizeof(g_played));HearthLoadId("dismissed",g_dismissed,sizeof(g_dismissed));
    g_audio_commands=xQueueCreate(1,sizeof(AudioCommand));g_pcm=xQueueCreate(8,sizeof(AudioPacket));
    if(!g_audio_commands || !g_pcm) {Error();esp_restart();}
    StartTask(DisplayTask,"color_display",6144,2);
    StartTask(AudioTask,"codec_owner",8192,5);
    if(HearthConfigComplete(g_config)) {
        ESP_ERROR_CHECK(HearthWifiStart(g_config));
        StartTask(AudioReader,"reply_network",8192,3);
        StartTask(NetworkTask,"device_network",12288,3);
    }
    HearthConfigStartConsole(g_config,ApplyConfig,PrintStatus);
    for(;;) {
        ZectrixButtonEvent event{};
        if(g_board.WaitButton(&event,pdMS_TO_TICKS(20)) && !g_shutdown.load()) {
            if(event.button==ZectrixButton::kOk && event.action==ZectrixButtonAction::kLongPress) {
                if(HearthConfigComplete(g_config)) {
                    ++g_audio_generation;
                    std::lock_guard<std::mutex> lock(g_mutex);g_suppress_audio=true;
                    if(!g_upload) g_record=true;else Error();
                } else Error();
            } else if(event.action==ZectrixButtonAction::kClick) {
                Navigate(event.button==ZectrixButton::kUp);
            } else if(event.button==ZectrixButton::kDown && event.action==ZectrixButtonAction::kLongPress) {
                g_sleep_requested=true;Quiesce();
            }
        }
        int64_t now=esp_timer_get_time();
        bool indicator=g_capture_ready.load();
        if(!indicator && g_error_until.load()>now) indicator=(now/150000)%4==0;
        else if(!indicator && (g_processing.load() || g_audio_busy.load())) indicator=(now/250000)%2==0;
        g_board.SetPowerLed(indicator);
        if(g_sleep_requested.load() && g_audio_stopped.load() && g_display_stopped.load()) {
            g_board.SetPowerLed(false);
            esp_sleep_enable_ext1_wakeup_io(1ULL<<ZECTRIX_BUTTON_OK,ESP_EXT1_WAKEUP_ANY_LOW);
            esp_deep_sleep_start();
        }
    }
}
