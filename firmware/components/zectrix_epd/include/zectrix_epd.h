#ifndef ZECTRIX_EPD_H_
#define ZECTRIX_EPD_H_

#include <stddef.h>
#include <stdint.h>
#include "driver/gpio.h"
#include "driver/spi_master.h"
#include "esp_err.h"

#ifdef __cplusplus
extern "C" {
#endif

#define ZECTRIX_EPD_PANEL_WIDTH 400
#define ZECTRIX_EPD_PANEL_HEIGHT 300
#define ZECTRIX_EPD_2BPP_FRAME_BYTES 30000

typedef struct zectrix_epd_t* zectrix_epd_handle_t;
typedef struct {
    spi_host_device_t spi_host;
    gpio_num_t pin_cs, pin_dc, pin_reset, pin_busy, pin_mosi, pin_sclk, pin_power;
    int spi_clock_hz;
    uint32_t busy_timeout_ms;
} zectrix_epd_config_t;

void zectrix_epd_get_default_config(zectrix_epd_config_t* config);
esp_err_t zectrix_epd_new(const zectrix_epd_config_t* config, zectrix_epd_handle_t* out_handle);
esp_err_t zectrix_epd_del(zectrix_epd_handle_t handle);

/** NOTE4C only. One display task exclusively owns the handle.
 * Complete power/reset/refresh/sleep cycle; rail is removed on every return.
 * 400x300, row-major, four pixels/byte, leftmost in bits7-6.
 * Black00, white01, yellow10, red11. No partial or grayscale refresh.
 */
esp_err_t zectrix_epd_refresh_full_2bpp(zectrix_epd_handle_t handle,
                                      const uint8_t* framebuffer, size_t size);

#ifdef __cplusplus
}
#endif
#endif
