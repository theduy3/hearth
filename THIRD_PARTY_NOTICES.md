# Third-party notices

Hearth's project code is MIT licensed. Dependencies and vendored material retain their own licenses.

## Zectrix board support

`firmware/components/zectrix_board` and the original display-driver foundation derive from [zectrix-note4-epd-demo](https://github.com/itopinion/zectrix-note4-epd-demo), MIT, Copyright (c) 2026 Zectrix Lab. The complete text is in `licenses/ZECTRIX_MIT_LICENSE`. Component `ORIGIN.md` files describe local changes.

The replacement native BWRY panel sequence was checked against [youn-ink-fourcolor-firmware](https://github.com/LazyYoun/youn-ink-fourcolor-firmware), commit `8907e59300fde3b77a385dba9f3070b0de17b4c8`. Its root project and underlying firmware are MIT licensed; their notices are retained in `licenses/NOTE4C_REFERENCE_MIT_LICENSE`. Its application, networking and agent code are not vendored.

The obsolete monochrome canvas and TRMNL bitmap font have been removed.

## DejaVu fonts

The VPS renderer uses unmodified DejaVu Sans fonts. Their complete license, source and attribution are shipped in `assets/fonts/`; see `assets/fonts/ORIGIN.md`. Fonts are not embedded into device firmware.

## Espressif and cJSON

ESP-IDF 6.1 is a build dependency, pinned by container digest. `espressif/esp_codec_dev` and `espressif/cjson` are obtained through its Component Manager. Their licenses accompany the downloaded managed components. CI publishes `firmware/dependencies.lock` with the build to record resolved versions.

## VPS speech dependencies and models

Speech dependencies are installed separately from Hermes and device firmware. The Piper engine is GPLv3 and is not vendored into this repository or linked into device firmware. The selected `en_US-joe-medium` male voice uses the CC0 OHF-Voice Joe dataset. Its pinned model card and artifact checksums are retained with the VPS candidate installation. Piper1.5 or newer is required; the active runtime is1.8. Review the model card/license when redistributing artifacts. Faster Whisper/CTranslate2 and other Python dependencies retain their package licenses.

The model preparation tool records pinned revisions, checksums and available license/model-card material beside the private VPS model installation. No speech model weights or voices are committed or included in firmware artifacts.

The optional, currently inactive Parakeet Unified English Q8 candidate is converted by handy-computer from NVIDIA's model and governed by the NVIDIA Open Model License. Its pinned LICENSE, NOTICE, model card and SHA256 manifest are retained at `/opt/catthew-speech/parakeet-q8`. The transcribe.cpp0.4.2 Python/native runtime wheels retain their bundled licenses and are installed separately with the hashes in `deploy/requirements-parakeet.txt`. See `docs/PARAKEET-BENCHMARK.md` for provenance, measured behavior and the activation hold.
