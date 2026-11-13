#!/usr/bin/env python3
"""Verify the private factory image and its recorded successful hardware comparison."""
import hashlib
import json
import os
from pathlib import Path


def main():
    root = Path.home() / ".local/share/catthew-note4c"
    record = json.loads((root / "active-backup.json").read_text())
    image = Path(record["image"]).resolve()
    if not image.is_relative_to((root / "backups").resolve()) or image.is_symlink():
        raise ValueError("factory image is outside the private backup directory")
    if record.get("status") != "complete" or record.get("verified") is not True or image.stat().st_size != 16777216:
        raise ValueError("factory backup is incomplete or unverified")
    if image.stat().st_uid != os.getuid() or image.stat().st_mode & 0o077:
        raise ValueError("factory backup must remain private to its owner")
    digest = hashlib.sha256()
    with image.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    if digest.hexdigest() != record["sha256"]:
        raise ValueError("factory backup checksum mismatch")
    print("FACTORY_BACKUP_VERIFIED")


if __name__ == "__main__":
    main()
