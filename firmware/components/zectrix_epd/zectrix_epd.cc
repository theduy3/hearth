#include "zectrix_epd.h"

#include <cstring>
#include <new>
#include "esp_heap_caps.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

namespace {
constexpr size_t kRowBytes = ZECTRIX_EPD_PANEL_WIDTH / 4;
}

struct zectrix_epd_t {
    zectrix_epd_config_t config{};
    spi_device_handle_t spi = nullptr;
    uint8_t* dma = nullptr;
    bool owns_bus = false;
    int64_t deadline = 0;

    esp_err_t CutPower() {
        gpio_hold_dis(config.pin_power);
        esp_err_t result = gpio_set_level(config.pin_power, 0);
        gpio_hold_en(config.pin_power);
        return result;
    }

    esp_err_t Ready() {
        for (;;) {
            if (esp_timer_get_time() >= deadline) return ESP_ERR_TIMEOUT;
            if (gpio_get_level(config.pin_busy) != 0) return ESP_OK;
            vTaskDelay(pdMS_TO_TICKS(50));
        }
    }

    esp_err_t Send(bool data_mode, const uint8_t* bytes, size_t size) {
        if (size == 0 || size > kRowBytes || bytes == nullptr) return ESP_ERR_INVALID_ARG;
        if (esp_timer_get_time() >= deadline) return ESP_ERR_TIMEOUT;
        gpio_set_level(config.pin_dc, data_mode ? 1 : 0);
        gpio_set_level(config.pin_cs, 0);
        spi_transaction_t tx{};
        tx.length = size * 8;
        if (size <= sizeof(tx.tx_data)) {
            tx.flags = SPI_TRANS_USE_TXDATA;
            std::memcpy(tx.tx_data, bytes, size);
        } else {
            std::memcpy(dma, bytes, size);
            tx.tx_buffer = dma;
        }
        esp_err_t result = spi_device_polling_transmit(spi, &tx);
        gpio_set_level(config.pin_cs, 1);
        return result;
    }

    esp_err_t Command(uint8_t value) { return Send(false, &value, 1); }
    esp_err_t Data(uint8_t value) { return Send(true, &value, 1); }

    esp_err_t Refresh(const uint8_t* frame) {
        deadline = esp_timer_get_time() + static_cast<int64_t>(config.busy_timeout_ms) * 1000;
        gpio_hold_dis(config.pin_power);
        esp_err_t result = gpio_set_level(config.pin_power, 1);
        gpio_hold_en(config.pin_power);
        if (result != ESP_OK) return result;
        vTaskDelay(pdMS_TO_TICKS(10));
        gpio_set_level(config.pin_reset, 1);
        vTaskDelay(pdMS_TO_TICKS(10));
        gpio_set_level(config.pin_reset, 0);
        vTaskDelay(pdMS_TO_TICKS(20));
        gpio_set_level(config.pin_reset, 1);
        vTaskDelay(pdMS_TO_TICKS(10));
        result = Ready();
        // Native four-color reference path: deliberately no monochrome 00:2F,0E
        // OTP selection, temperature commands, external LUT or pixel conversion.
        if (result == ESP_OK) result = Command(0xE9);
        if (result == ESP_OK) result = Data(0x01);
        if (result == ESP_OK) result = Command(0x10);
        if (result == ESP_OK) result = Ready();
        for (int row = 0; result == ESP_OK && row < ZECTRIX_EPD_PANEL_HEIGHT; ++row) {
            result = Send(true, frame + static_cast<size_t>(row) * kRowBytes, kRowBytes);
            if ((row & 15) == 15) vTaskDelay(1);
        }
        if (result == ESP_OK) result = Command(0x04);
        if (result == ESP_OK) result = Ready();
        if (result == ESP_OK) vTaskDelay(pdMS_TO_TICKS(10));
        if (result == ESP_OK) result = Command(0x12);
        if (result == ESP_OK) result = Data(0x00);
        if (result == ESP_OK) vTaskDelay(pdMS_TO_TICKS(10));
        if (result == ESP_OK) result = Ready();
        if (result == ESP_OK) result = Command(0x02);
        if (result == ESP_OK) result = Data(0x00);
        if (result == ESP_OK) result = Ready();
        if (result == ESP_OK) vTaskDelay(pdMS_TO_TICKS(20));
        if (result == ESP_OK) result = Command(0x07);
        if (result == ESP_OK) result = Data(0xA5);
        return result;
    }
};

extern "C" void zectrix_epd_get_default_config(zectrix_epd_config_t* config) {
    if (config == nullptr) return;
    *config = {};
    config->spi_host = SPI3_HOST;
    config->pin_dc = GPIO_NUM_10;
    config->pin_cs = GPIO_NUM_11;
    config->pin_sclk = GPIO_NUM_12;
    config->pin_mosi = GPIO_NUM_13;
    config->pin_reset = GPIO_NUM_9;
    config->pin_busy = GPIO_NUM_8;
    config->pin_power = GPIO_NUM_6;
    config->spi_clock_hz = 20000000;
    config->busy_timeout_ms = 120000;
}

extern "C" esp_err_t zectrix_epd_new(const zectrix_epd_config_t* config, zectrix_epd_handle_t* output) {
    if (output != nullptr) *output = nullptr;
    if (config == nullptr || output == nullptr || config->spi_clock_hz <= 0 || config->busy_timeout_ms < 100 ||
        !GPIO_IS_VALID_OUTPUT_GPIO(config->pin_cs) || !GPIO_IS_VALID_OUTPUT_GPIO(config->pin_dc) ||
        !GPIO_IS_VALID_OUTPUT_GPIO(config->pin_reset) || !GPIO_IS_VALID_GPIO(config->pin_busy) ||
        !GPIO_IS_VALID_OUTPUT_GPIO(config->pin_mosi) || !GPIO_IS_VALID_OUTPUT_GPIO(config->pin_sclk) ||
        !GPIO_IS_VALID_OUTPUT_GPIO(config->pin_power)) return ESP_ERR_INVALID_ARG;
    auto* epd = new (std::nothrow) zectrix_epd_t;
    if (epd == nullptr) return ESP_ERR_NO_MEM;
    epd->config = *config;
    epd->dma = static_cast<uint8_t*>(heap_caps_malloc(kRowBytes, MALLOC_CAP_DMA | MALLOC_CAP_INTERNAL));
    if (epd->dma == nullptr) { delete epd; return ESP_ERR_NO_MEM; }
    gpio_hold_dis(config->pin_power);
    gpio_config_t outputs{};
    outputs.pin_bit_mask = (1ULL << config->pin_cs) | (1ULL << config->pin_dc) |
                          (1ULL << config->pin_reset) | (1ULL << config->pin_power);
    outputs.mode = GPIO_MODE_OUTPUT;
    outputs.pull_up_en = GPIO_PULLUP_ENABLE;
    esp_err_t result = gpio_config(&outputs);
    gpio_config_t busy{};
    busy.pin_bit_mask = 1ULL << config->pin_busy;
    busy.mode = GPIO_MODE_INPUT;
    busy.pull_up_en = GPIO_PULLUP_ENABLE;
    if (result == ESP_OK) result = gpio_config(&busy);
    if (result == ESP_OK) {
        gpio_set_level(config->pin_cs, 1);
        gpio_set_level(config->pin_dc, 1);
        gpio_set_level(config->pin_reset, 1);
        result = epd->CutPower();
    }
    spi_bus_config_t bus{};
    bus.miso_io_num = -1;
    bus.mosi_io_num = config->pin_mosi;
    bus.sclk_io_num = config->pin_sclk;
    bus.quadwp_io_num = -1;
    bus.quadhd_io_num = -1;
    bus.max_transfer_sz = kRowBytes;
    if (result == ESP_OK) {
        result = spi_bus_initialize(config->spi_host, &bus, SPI_DMA_CH_AUTO);
        epd->owns_bus = result == ESP_OK;
    }
    spi_device_interface_config_t device{};
    device.spics_io_num = -1;
    device.clock_speed_hz = config->spi_clock_hz;
    device.mode = 0;
    device.queue_size = 1;
    if (result == ESP_OK) result = spi_bus_add_device(config->spi_host, &device, &epd->spi);
    if (result != ESP_OK) {
        epd->CutPower();
        if (epd->owns_bus) spi_bus_free(config->spi_host);
        heap_caps_free(epd->dma);
        delete epd;
        return result;
    }
    *output = epd;
    return ESP_OK;
}

extern "C" esp_err_t zectrix_epd_del(zectrix_epd_handle_t epd) {
    if (epd == nullptr) return ESP_ERR_INVALID_ARG;
    esp_err_t result = epd->CutPower();
    esp_err_t next = spi_bus_remove_device(epd->spi);
    if (result == ESP_OK) result = next;
    next = spi_bus_free(epd->config.spi_host);
    if (result == ESP_OK) result = next;
    heap_caps_free(epd->dma);
    delete epd;
    return result;
}

extern "C" esp_err_t zectrix_epd_refresh_full_2bpp(zectrix_epd_handle_t epd, const uint8_t* frame, size_t size) {
    if (epd == nullptr || frame == nullptr || size != ZECTRIX_EPD_2BPP_FRAME_BYTES) return ESP_ERR_INVALID_ARG;
    esp_err_t result = epd->Refresh(frame);
    esp_err_t off = epd->CutPower();
    return result == ESP_OK ? off : result;
}
