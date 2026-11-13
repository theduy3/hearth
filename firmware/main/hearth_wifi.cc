#include "hearth_wifi.h"
#include <atomic>
#include <cstring>
#include <ctime>
#include "esp_event.h"
#include "esp_netif.h"
#include "esp_netif_sntp.h"
#include "esp_wifi.h"

namespace {
std::atomic<bool> g_connected{false};
bool g_sntp_started = false;
void Event(void*, esp_event_base_t base, int32_t id, void*) {
    if (base == WIFI_EVENT && id == WIFI_EVENT_STA_START) esp_wifi_connect();
    if (base == WIFI_EVENT && id == WIFI_EVENT_STA_DISCONNECTED) {
        g_connected.store(false);
        esp_wifi_connect();
    }
    if (base == IP_EVENT && id == IP_EVENT_STA_GOT_IP) g_connected.store(true);
}
}

esp_err_t HearthWifiStart(const HearthConfig& config) {
    if (!HearthConfigComplete(config)) return ESP_ERR_INVALID_ARG;
    esp_err_t result = esp_netif_init();
    if (result != ESP_OK) return result;
    result = esp_event_loop_create_default();
    if (result != ESP_OK) return result;
    if (esp_netif_create_default_wifi_sta() == nullptr) return ESP_FAIL;
    wifi_init_config_t init = WIFI_INIT_CONFIG_DEFAULT();
    result = esp_wifi_init(&init);
    if (result != ESP_OK) return result;
    result = esp_event_handler_register(WIFI_EVENT, ESP_EVENT_ANY_ID, Event, nullptr);
    if (result == ESP_OK) result = esp_event_handler_register(IP_EVENT, IP_EVENT_STA_GOT_IP, Event, nullptr);
    wifi_config_t wifi{};
    // Native Wi-Fi arrays allow exactly32/64 bytes, without a terminator.
    std::memcpy(wifi.sta.ssid, config.ssid, std::strlen(config.ssid));
    std::memcpy(wifi.sta.password, config.password, std::strlen(config.password));
    wifi.sta.threshold.authmode = config.password[0] ? WIFI_AUTH_WPA2_PSK : WIFI_AUTH_OPEN;
    if (result == ESP_OK) result = esp_wifi_set_mode(WIFI_MODE_STA);
    if (result == ESP_OK) result = esp_wifi_set_config(WIFI_IF_STA, &wifi);
    if (result == ESP_OK) result = esp_wifi_set_ps(WIFI_PS_MIN_MODEM);
    if (result == ESP_OK) result = esp_wifi_start();
    return result;
}

bool HearthWifiConnected() { return g_connected.load(); }

bool HearthWifiSyncTime() {
    if (!HearthWifiConnected()) return false;
    if (!g_sntp_started) {
        esp_sntp_config_t config = ESP_NETIF_SNTP_DEFAULT_CONFIG("pool.ntp.org");
        if (esp_netif_sntp_init(&config) != ESP_OK) return false;
        g_sntp_started = true;
    }
    if (esp_netif_sntp_sync_wait(pdMS_TO_TICKS(10000)) == ESP_OK) return true;
    // A previously synchronized clock survives ordinary network loss/deep sleep.
    return std::time(nullptr) >= 1767225600;  // 2026-01-01; never bypass TLS checks.
}
