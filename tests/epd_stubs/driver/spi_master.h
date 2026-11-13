#pragma once
#include <cstddef>
#include <cstdint>
#include "esp_err.h"
using spi_host_device_t=int;using spi_device_handle_t=void*;
constexpr int SPI3_HOST=3,SPI_DMA_CH_AUTO=3,SPI_TRANS_USE_TXDATA=1;
struct spi_bus_config_t{int miso_io_num=0,mosi_io_num=0,sclk_io_num=0,quadwp_io_num=0,quadhd_io_num=0,max_transfer_sz=0;};
struct spi_device_interface_config_t{int spics_io_num=0,clock_speed_hz=0,mode=0,queue_size=0;};
struct spi_transaction_t{size_t length=0;int flags=0;uint8_t tx_data[4]{};const void* tx_buffer=nullptr;};
esp_err_t spi_bus_initialize(int,const spi_bus_config_t*,int);esp_err_t spi_bus_free(int);esp_err_t spi_bus_add_device(int,const spi_device_interface_config_t*,void**);esp_err_t spi_bus_remove_device(void*);esp_err_t spi_device_polling_transmit(void*,spi_transaction_t*);
