#!/usr/bin/env python3
"""Prepare the pinned public Parakeet Unified English Q8_0 candidate; no inference."""
import argparse
import hashlib
import json
import os
from pathlib import Path
from urllib.request import urlopen

REPO = "handy-computer/parakeet-unified-en-0.6b-gguf"
REVISION = "843b1b175ace04f5a89d379c79e2518c0d065b25"
MODEL = "parakeet-unified-en-0.6b-Q8_0.gguf"
SIZE = 731357568
SHA256 = "4b50b6dd862bf6e346929aaf4f5eaacec003bfa3f56462d6c874b41ef2f38795"


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def prepare(root):
    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=True, mode=0o755)
    artifacts = []
    for name in (MODEL, "LICENSE", "NOTICE", "README.md"):
        path = root / name
        if not path.exists():
            temporary = root / (name + ".part")
            try:
                count = 0
                with urlopen(f"https://huggingface.co/{REPO}/resolve/{REVISION}/{name}", timeout=60) as response, temporary.open("wb") as stream:
                    for chunk in iter(lambda: response.read(1024 * 1024), b""):
                        count += len(chunk)
                        if count > (SIZE if name == MODEL else 1024 * 1024):
                            raise ValueError("public artifact exceeds pinned size limit")
                        stream.write(chunk)
                if name == MODEL and (count != SIZE or sha256(temporary) != SHA256):
                    raise ValueError("Parakeet model checksum/size mismatch")
                os.chmod(temporary, 0o644)
                os.replace(temporary, path)
            finally:
                temporary.unlink(missing_ok=True)
        digest = sha256(path)
        if name == MODEL and (path.stat().st_size != SIZE or digest != SHA256):
            raise ValueError("existing Parakeet model changed; refusing replacement")
        artifacts.append({"name": name, "bytes": path.stat().st_size, "sha256": digest})
    manifest = {"repo": REPO, "revision": REVISION, "runtime": "transcribe-cpp==0.4.2",
                "license": "NVIDIA Open Model License", "artifacts": artifacts}
    manifest_path = root / "manifest.json"
    if manifest_path.exists() and json.loads(manifest_path.read_text()) != manifest:
        raise ValueError("candidate provenance changed; refusing manifest replacement")
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print("PARAKEET_MODEL_VERIFIED", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", type=Path, required=True)
    prepare(parser.parse_args().models)
