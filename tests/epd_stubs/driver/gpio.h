#pragma once
#include <cstdint>
#include "esp_err.h"
using gpio_num_t=int;
constexpr int GPIO_NUM_6=6,GPIO_NUM_8=8,GPIO_NUM_9=9,GPIO_NUM_10=10,GPIO_NUM_11=11,GPIO_NUM_12=12,GPIO_NUM_13=13;
constexpr int GPIO_MODE_OUTPUT=1,GPIO_MODE_INPUT=0,GPIO_PULLUP_ENABLE=1;
#define GPIO_IS_VALID_GPIO(x) ((x)>=0 && (x)<49)
#define GPIO_IS_VALID_OUTPUT_GPIO(x) GPIO_IS_VALID_GPIO(x)
struct gpio_config_t{uint64_t pin_bit_mask=0;int mode=0,pull_up_en=0;};
esp_err_t gpio_config(const gpio_config_t*);esp_err_t gpio_set_level(int,int);int gpio_get_level(int);esp_err_t gpio_hold_dis(int);esp_err_t gpio_hold_en(int);
