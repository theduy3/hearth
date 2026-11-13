#ifndef HEARTH_WIFI_H_
#define HEARTH_WIFI_H_
#include "esp_err.h"
#include "hearth_config.h"
esp_err_t HearthWifiStart(const HearthConfig& config);
bool HearthWifiConnected();
bool HearthWifiSyncTime();
#endif
