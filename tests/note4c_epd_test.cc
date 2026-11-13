#include <cassert>
#include <cstdio>
#include <cstdint>
#include <vector>
#include "zectrix_epd.h"
#include "freertos/task.h"

namespace {
int levels[49]{};
int64_t micros = 0;
int calls = 0, fail_at = 0;
bool stall_refresh = false;
uint8_t command = 0;
std::vector<uint8_t> commands, frame_bytes, parameters;
void Clear() {
    commands.clear(); frame_bytes.clear(); parameters.clear();
    calls = 0; fail_at = 0; stall_refresh = false; levels[8] = 1;
}
}

esp_err_t gpio_config(const gpio_config_t*) { return ESP_OK; }
esp_err_t gpio_set_level(int pin, int value) { levels[pin] = value; return ESP_OK; }
int gpio_get_level(int pin) { return levels[pin]; }
esp_err_t gpio_hold_dis(int) { return ESP_OK; }
esp_err_t gpio_hold_en(int) { return ESP_OK; }
int64_t esp_timer_get_time() { return micros; }
void vTaskDelay(TickType_t ticks) { micros += static_cast<int64_t>(ticks) * 1000; }
esp_err_t spi_bus_initialize(int, const spi_bus_config_t*, int) { return ESP_OK; }
esp_err_t spi_bus_free(int) { return ESP_OK; }
esp_err_t spi_bus_add_device(int, const spi_device_interface_config_t*, void** device) { *device = reinterpret_cast<void*>(1); return ESP_OK; }
esp_err_t spi_bus_remove_device(void*) { return ESP_OK; }
esp_err_t spi_device_polling_transmit(void*, spi_transaction_t* tx) {
    if (++calls == fail_at) return ESP_FAIL;
    const auto* bytes = (tx->flags & SPI_TRANS_USE_TXDATA) ? tx->tx_data : static_cast<const uint8_t*>(tx->tx_buffer);
    size_t size = tx->length / 8;
    if (levels[10] == 0) {
        assert(size == 1);
        command = bytes[0]; commands.push_back(command);
        if (command == 0x12 && stall_refresh) levels[8] = 0;
    } else if (command == 0x10) {
        assert(size == 100);
        frame_bytes.insert(frame_bytes.end(), bytes, bytes + size);
    } else {
        parameters.insert(parameters.end(), bytes, bytes + size);
    }
    return ESP_OK;
}

int main() {
    zectrix_epd_config_t config{};
    zectrix_epd_get_default_config(&config);
    assert(config.busy_timeout_ms == 120000);
    zectrix_epd_handle_t epd = nullptr;
    assert(zectrix_epd_new(&config, &epd) == ESP_OK);
    std::vector<uint8_t> pixels(30000, 0x55);
    pixels[0] = 0x1E;  // black, white, red, yellow: no conversion allowed.
    Clear();
    assert(zectrix_epd_refresh_full_2bpp(epd, pixels.data(), 29999) == ESP_ERR_INVALID_ARG);
    assert(calls == 0 && levels[6] == 0);
    assert(zectrix_epd_refresh_full_2bpp(epd, pixels.data(), pixels.size()) == ESP_OK);
    assert((commands == std::vector<uint8_t>{0xE9, 0x10, 0x04, 0x12, 0x02, 0x07}));
    assert((parameters == std::vector<uint8_t>{0x01, 0x00, 0x00, 0xA5}));
    assert(frame_bytes == pixels && levels[6] == 0);
    Clear(); stall_refresh = true;
    int64_t before = micros;
    assert(zectrix_epd_refresh_full_2bpp(epd, pixels.data(), pixels.size()) == ESP_ERR_TIMEOUT);
    assert(micros - before >= 120000000 && micros - before < 120100000);
    assert((commands == std::vector<uint8_t>{0xE9, 0x10, 0x04, 0x12}));
    assert(levels[6] == 0);  // Never send power-off while the controller is stuck BUSY.
    Clear(); fail_at = 5;
    assert(zectrix_epd_refresh_full_2bpp(epd, pixels.data(), pixels.size()) == ESP_FAIL);
    assert(levels[6] == 0);
    Clear();
    assert(zectrix_epd_refresh_full_2bpp(epd, pixels.data(), pixels.size()) == ESP_OK);
    assert(zectrix_epd_del(epd) == ESP_OK);
    std::puts("NOTE4C_EPD_OK");
}
