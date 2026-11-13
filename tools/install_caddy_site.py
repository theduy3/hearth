#!/usr/bin/env python3
"""Append only the approved Catthew hostname to the existing Caddy service."""
import argparse
import hashlib
import json
import os
import subprocess
import tempfile
import uuid
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fragment", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if not args.apply:
        parser.error("pass --apply only for the approved Bluehost delivery path")
    config = Path("/etc/Caddyfile")
    original = config.read_bytes()
    fragment = b"\n# Catthew Note4C household terminal\n" + args.fragment.read_bytes() + b"\n"
    if b"zectrix.theduy.cloud" in original:
        raise SystemExit("Hostname already appears in Caddyfile; inspect instead of adding another route")
    backups = Path("/root/catthew-deploy-backups")
    backups.mkdir(mode=0o700, exist_ok=True)
    os.chmod(backups, 0o700)
    backup = backups / ("Caddyfile-" + uuid.uuid4().hex)
    backup.write_bytes(original)
    os.chmod(backup, 0o600)
    descriptor, candidate = tempfile.mkstemp(dir="/etc", prefix=".Caddyfile-catthew-")
    expected = original + fragment
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(expected)
        validation = subprocess.run(["/usr/local/bin/caddy", "validate", "--config", candidate, "--adapter", "caddyfile"], capture_output=True)
        (backups / "last-validation.log").write_bytes(validation.stdout + validation.stderr)
        os.chmod(backups / "last-validation.log", 0o600)
        if validation.returncode:
            raise RuntimeError("Caddy candidate validation failed; existing configuration was not changed")
        if config.read_bytes() != original:
            raise RuntimeError("Caddy configuration changed during review; refusing to overwrite it")
        with config.open("ab") as handle:
            handle.write(fragment)
            handle.flush()
            os.fsync(handle.fileno())
        if config.read_bytes() != expected:
            raise RuntimeError("Concurrent Caddy edit detected; inspect the preserved backup before reloading")
        reload = subprocess.run(["systemctl", "reload", "caddy-photoframe.service"], capture_output=True)
        (backups / "last-reload.log").write_bytes(reload.stdout + reload.stderr)
        os.chmod(backups / "last-reload.log", 0o600)
        if reload.returncode:
            if config.read_bytes() == expected:
                config.write_bytes(original)
            raise RuntimeError("Caddy reload failed; rollout stopped")
        print(json.dumps({"hostname": "zectrix.theduy.cloud", "validated": True, "reloaded": True,
                          "original_sha256": hashlib.sha256(original).hexdigest(), "backup": str(backup)}))
    finally:
        os.unlink(candidate)


if __name__ == "__main__":
    main()
