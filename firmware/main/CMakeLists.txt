idf_component_register(
    SRCS "app_main.cc" "hearth_wifi.cc" "hearth_config.cc"
         "hearth_audio.cc" "hearth_net.cc" "hearth_protocol.cc"
    INCLUDE_DIRS "."
    REQUIRES zectrix_epd zectrix_board nvs_flash esp_wifi esp_netif esp_event
             esp_timer esp_http_client mbedtls espressif__cjson esp_driver_gpio heap
    EMBED_FILES "assets/setup_frame.bin" "assets/offline_badge.bin"
)
target_compile_features(${COMPONENT_LIB} PUBLIC cxx_std_17)
