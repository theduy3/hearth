#!/usr/bin/env python3
"""Produce a checksummed firmware manifest without provisioning data."""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path


def main():
    root = Path(sys.argv[1]).resolve()
    description = json.loads((root / "project_description.json").read_text())
    sdk = json.loads((root / "config/sdkconfig.json").read_text())
    if description.get("target") != "esp32s3":
        raise ValueError("wrong chip target")
    required = ("SPIRAM", "SPIRAM_MODE_OCT", "ESPTOOLPY_FLASHSIZE_16MB", "ESP_HTTP_CLIENT_ENABLE_HTTPS", "MBEDTLS_CERTIFICATE_BUNDLE")
    if not all(sdk.get(key) is True for key in required):
        raise ValueError("required NOTE4C memory/TLS configuration is missing")
    if any(key.startswith("HEARTH_WIFI_") for key in sdk):
        raise ValueError("compiled Wi-Fi settings are forbidden")
    flash = json.loads((root / "flasher_args.json").read_text())
    files = {}
    for offset, name in flash["flash_files"].items():
        path = (root / name).resolve()
        if not path.is_relative_to(root) or path.suffix != ".bin":
            raise ValueError("flash file escapes build directory")
        files[offset] = {"file": name, "bytes": path.stat().st_size,
                         "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    commit = os.environ.get("GITHUB_SHA") or subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    manifest = {"board": "Note4C", "target": "esp32s3", "flash_bytes": 16777216,
                "source_commit": commit, "files": files, "flash_settings": flash["flash_settings"],
                "initial_nvs_erase": {"offset": "0x9000", "bytes": "0x26000"}}
    (root / "note4c-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print("NOTE4C_FIRMWARE_MANIFEST_OK")


if __name__ == "__main__":
    main()
