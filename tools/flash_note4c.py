#!/usr/bin/env python3
"""Verify a Note4C CI artifact and flash only the device with a verified backup."""
import argparse
import hashlib
import json
from pathlib import Path

from tools.note4_flash import find_esptool, parse_flash_size_ok, parse_mac, run_esptool
from tools.verify_factory_backup import main as verify_backup


def verify_artifact(directory, expected_commit):
    directory = directory.resolve()
    manifest = json.loads((directory / "note4c-manifest.json").read_text())
    if (manifest.get("board"), manifest.get("target"), manifest.get("flash_bytes"), manifest.get("source_commit")) != (
            "Note4C", "esp32s3", 16777216, expected_commit):
        raise ValueError("artifact does not match the expected Note4C source revision")
    if manifest.get("flash_settings") != {"flash_mode": "dio", "flash_size": "16MB", "flash_freq": "80m"}:
        raise ValueError("unexpected flash settings")
    expected_files = {"0x0": "bootloader/bootloader.bin", "0x8000": "partition_table/partition-table.bin", "0x30000": "hearth.bin"}
    if set(manifest["files"]) != set(expected_files):
        raise ValueError("unexpected flash regions")
    files = []
    limits = {"0x0": 0x8000, "0x8000": 0x1000, "0x30000": 0x3D0000}
    for offset, name in expected_files.items():
        item = manifest["files"][offset]
        path = directory / name
        if item["file"] != name or path.is_symlink() or not path.resolve().is_relative_to(directory):
            raise ValueError("artifact path is not contained in the build")
        data = path.read_bytes()
        if not 0 < len(data) <= limits[offset] or len(data) != item["bytes"] or hashlib.sha256(data).hexdigest() != item["sha256"]:
            raise ValueError("artifact checksum or bounds mismatch")
        files.extend([offset, str(path)])
    if manifest.get("initial_nvs_erase") != {"offset": "0x9000", "bytes": "0x26000"}:
        raise ValueError("unexpected NVS region")
    return files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-dir", required=True, type=Path)
    parser.add_argument("--expect-commit", required=True)
    parser.add_argument("--port", default="/dev/cu.usbmodem101")
    parser.add_argument("--write", action="store_true", help="Write verified firmware and erase its initial NVS region")
    parser.add_argument("--initial-provision", action="store_true", help="Erase the new NVS layout on the first installation only")
    args = parser.parse_args()
    verify_backup()
    files = verify_artifact(args.artifact_dir, args.expect_commit)
    print("FIRMWARE_ARTIFACT_VERIFIED")
    if not args.write:
        return
    backup = json.loads((Path.home() / ".local/share/catthew-note4c/active-backup.json").read_text())
    esptool = find_esptool()
    identity = run_esptool(esptool, args.port, 921600, ["flash-id"], after="no-reset")
    if parse_mac(identity) != backup["expected_mac"] or not parse_flash_size_ok(identity):
        raise ValueError("attached device identity or flash size does not match the backup")
    print("DEVICE_IDENTITY_VERIFIED")
    if args.initial_provision:
        print(run_esptool(esptool, args.port, 921600, ["erase-region", "0x9000", "0x26000"], after="no-reset"))
    print(run_esptool(esptool, args.port, 921600,
                      ["write-flash", "--flash-mode", "dio", "--flash-size", "16MB", "--flash-freq", "80m", *files], after="no-reset"))
    print(run_esptool(esptool, args.port, 921600, ["verify-flash", *files], after="hard-reset"))
    print("NOTE4C_FLASH_VERIFIED")


if __name__ == "__main__":
    main()
