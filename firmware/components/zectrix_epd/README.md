# Note4C native BWRY display

ESP-IDF 6.1 component for the 400×300 Zectrix Note4C four-color SSD2683 panel. The public API accepts exactly30,000 packed bytes: black00, white01, yellow10, red11; the leftmost pixel occupies bits7–6. Four pixels per byte,100 bytes per row.

Only full refresh is supported. Every refresh owns panel power through reset, native color upload, power-on, display refresh, power-off and deep sleep. An active-low BUSY wait has a120-second whole-cycle deadline; failure removes power and is reported to the caller. The application uses a separate display owner task and commits displayed metadata only after successful refresh. No monochrome LUT, OTP initialization, partial refresh or grayscale mode remains.

Pins: power6, BUSY8, reset9, DC10, CS11, SCLK12, MOSI13. SPI3 mode0,20MHz. See tests/note4c_epd_test.cc for the actual-driver command/power trace tests. Physical colors still require the calibration-card acceptance check.

Derived from Zectrix Lab board support, MIT, Copyright2026 Zectrix Lab. See ORIGIN.md and licenses/ZECTRIX_MIT_LICENSE.
