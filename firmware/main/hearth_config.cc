#include "hearth_config.h"
#include <cctype>
#include <cstdio>
#include <cstring>
#include "cJSON.h"
#include "esp_mac.h"
#include "esp_system.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "nvs.h"

namespace {
constexpr const char* kNamespace = "catthew";
constexpr uint32_t kMagic = 0x43415431;
struct Stored { uint32_t magic; HearthConfig config; };
HearthConfig g_boot{};

template<size_t N> bool Bounded(const char (&value)[N]) {
    return strnlen(value, N) < N;
}

bool CopyJson(cJSON* object, const char* key, char* target, size_t capacity) {
    cJSON* item = cJSON_GetObjectItemCaseSensitive(object, key);
    if (!cJSON_IsString(item) || item->valuestring == nullptr) return false;
    size_t size = std::strlen(item->valuestring);
    if (size >= capacity) return false;
    std::memcpy(target, item->valuestring, size + 1);
    return true;
}

void Result(bool ok, const char* message) {
    // Messages are constants; never echo the incoming provisioning document.
    std::printf("CATTHEW_RESULT {\"ok\":%s,\"message\":\"%s\"}\n", ok ? "true" : "false", message);
    std::fflush(stdout);
}

void Console(void*) {
    char line[768]{};
    size_t used = 0;
    bool overflow = false;
    for (;;) {
        int ch = std::getchar();
        if (ch == EOF) { clearerr(stdin); vTaskDelay(pdMS_TO_TICKS(20)); continue; }
        if (ch == '\r') continue;
        if (ch != '\n') {
            if (used + 1 < sizeof(line)) line[used++] = static_cast<char>(ch);
            else overflow = true;
            continue;
        }
        line[used] = 0;
        if (overflow) Result(false, "configuration too long");
        else if (std::strcmp(line, "CATTHEW_INFO") == 0) {
            uint8_t mac[6]{};
            esp_read_mac(mac, ESP_MAC_WIFI_STA);
            std::printf("CATTHEW_RESULT {\"ok\":true,\"configured\":%s,\"mac\":\"%02x:%02x:%02x:%02x:%02x:%02x\"}\n",
                        HearthConfigComplete(g_boot) ? "true" : "false", mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);
            std::fflush(stdout);
        } else if (std::strncmp(line, "CATTHEW_CONFIG ", 15) == 0) {
            cJSON* document = cJSON_Parse(line + 15);
            HearthConfig staged{};
            bool valid = cJSON_IsObject(document) && cJSON_GetArraySize(document) == 4 &&
                CopyJson(document, "ssid", staged.ssid, sizeof(staged.ssid)) &&
                CopyJson(document, "password", staged.password, sizeof(staged.password)) &&
                CopyJson(document, "hub", staged.hub, sizeof(staged.hub)) &&
                CopyJson(document, "token", staged.token, sizeof(staged.token)) && HearthConfigComplete(staged);
            if (valid && HearthConfigSave(staged) == ESP_OK) {
                Result(true, "saved; rebooting");
                cJSON_Delete(document);
                std::memset(line, 0, sizeof(line));
                std::memset(&staged, 0, sizeof(staged));
                vTaskDelay(pdMS_TO_TICKS(250));
                esp_restart();
            } else Result(false, "configuration rejected or could not be saved");
            cJSON_Delete(document);
            std::memset(&staged, 0, sizeof(staged));
        }
        std::memset(line, 0, sizeof(line));
        used = 0; overflow = false;
    }
}
}

bool HearthConfigComplete(const HearthConfig& c) {
    if (!Bounded(c.ssid) || !Bounded(c.password) || !Bounded(c.hub) || !Bounded(c.token) || !c.ssid[0]) return false;
    size_t password = std::strlen(c.password);
    if (password != 0 && (password < 8 || password > 64)) return false;
    if (password == 64) for (char ch : c.password) { if (!ch) break; if (!std::isxdigit(static_cast<unsigned char>(ch))) return false; }
    if (std::strncmp(c.hub, "https://", 8) != 0 || !c.hub[8]) return false;
    for (const char* p = c.hub + 8; *p; ++p) {
        if (!std::isalnum(static_cast<unsigned char>(*p)) && *p != '.' && *p != '-' && *p != ':') return false;
    }
    size_t token = std::strlen(c.token);
    if (token < 32) return false;
    for (const char* p = c.token; *p; ++p) {
        if (!std::isalnum(static_cast<unsigned char>(*p)) && *p != '-' && *p != '_') return false;
    }
    return true;
}

esp_err_t HearthStoreBlob(const char* key, const void* data, size_t size) {
    nvs_handle_t handle;
    esp_err_t result = nvs_open(kNamespace, NVS_READWRITE, &handle);
    if (result != ESP_OK) return result;
    result = nvs_set_blob(handle, key, data, size);
    if (result == ESP_OK) result = nvs_commit(handle);
    nvs_close(handle);
    return result;
}

esp_err_t HearthLoadBlob(const char* key, void* data, size_t size) {
    nvs_handle_t handle;
    esp_err_t result = nvs_open(kNamespace, NVS_READONLY, &handle);
    if (result != ESP_OK) return result;
    size_t actual = size;
    result = nvs_get_blob(handle, key, data, &actual);
    nvs_close(handle);
    return result == ESP_OK && actual != size ? ESP_ERR_INVALID_SIZE : result;
}

esp_err_t HearthConfigSave(const HearthConfig& config) {
    if (!HearthConfigComplete(config)) return ESP_ERR_INVALID_ARG;
    Stored stored{};
    stored.magic = kMagic;
    stored.config = config;
    return HearthStoreBlob("settings", &stored, sizeof(stored));
}

esp_err_t HearthConfigLoad(HearthConfig* config) {
    if (config == nullptr) return ESP_ERR_INVALID_ARG;
    *config = {};
    Stored stored{};
    esp_err_t result = HearthLoadBlob("settings", &stored, sizeof(stored));
    if (result == ESP_ERR_NVS_NOT_FOUND) return ESP_OK;
    if (result != ESP_OK) return result;
    if (stored.magic != kMagic || !HearthConfigComplete(stored.config)) return ESP_ERR_INVALID_STATE;
    *config = stored.config;
    return ESP_OK;
}

esp_err_t HearthStoreId(const char* key, const char* value) {
    if (value == nullptr || std::strlen(value) > 128) return ESP_ERR_INVALID_ARG;
    nvs_handle_t handle;
    esp_err_t result = nvs_open(kNamespace, NVS_READWRITE, &handle);
    if (result != ESP_OK) return result;
    result = nvs_set_str(handle, key, value);
    if (result == ESP_OK) result = nvs_commit(handle);
    nvs_close(handle);
    return result;
}

void HearthLoadId(const char* key, char* value, size_t capacity) {
    value[0] = 0;
    nvs_handle_t handle;
    if (nvs_open(kNamespace, NVS_READONLY, &handle) != ESP_OK) return;
    size_t size = capacity;
    if (nvs_get_str(handle, key, value, &size) != ESP_OK) value[0] = 0;
    nvs_close(handle);
}

void HearthConfigStartConsole(const HearthConfig& config) {
    g_boot = config;
    setvbuf(stdin, nullptr, _IONBF, 0);
    xTaskCreate(Console, "private_usb_setup", 6144, nullptr, 2, nullptr);
}
