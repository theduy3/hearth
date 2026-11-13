#ifndef HEARTH_CONFIG_H_
#define HEARTH_CONFIG_H_
#include <cstddef>
#include <cstdint>
#include "esp_err.h"

struct HearthConfig {
    char ssid[33]{};
    char password[65]{};
    char hub[96]{};
    char token[97]{};
};

esp_err_t HearthConfigLoad(HearthConfig* config);
esp_err_t HearthConfigSave(const HearthConfig& config);
bool HearthConfigComplete(const HearthConfig& config);
// Raw stdin protocol, no REPL/input echo; saved settings apply on reboot only.
void HearthConfigStartConsole(const HearthConfig& config);
esp_err_t HearthStoreBlob(const char* key, const void* data, size_t size);
esp_err_t HearthLoadBlob(const char* key, void* data, size_t size);
esp_err_t HearthStoreId(const char* key, const char* value);
void HearthLoadId(const char* key, char* value, size_t capacity);
#endif
