#!/usr/bin/env python3
"""Download pinned public English speech models into the isolated VPS runtime."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    from huggingface_hub import HfApi, hf_hub_download, snapshot_download
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", type=Path, required=True)
    parser.add_argument("--whisper-size", choices=("tiny.en", "base.en"), default="base.en")
    args = parser.parse_args()
    root = args.models.resolve()
    root.mkdir(parents=True, exist_ok=True)
    whisper_repo = "Systran/faster-whisper-" + args.whisper_size
    voice_name = "en_US-joe-medium"
    manifest_file = root / "manifest.json"
    if manifest_file.exists():
        manifest = json.loads(manifest_file.read_text())
        if manifest["whisper_repo"] != whisper_repo or manifest.get("voice") != voice_name:
            raise ValueError("choose a new candidate directory instead of replacing a pinned model")
        for item in manifest["artifacts"]:
            if sha256(Path(item["path"])) != item["sha256"]:
                raise ValueError("speech model checksum mismatch; refusing automatic replacement")
        print("pinned_speech_models=verified")
        return
    api = HfApi(token=False)
    voice_repo = "rhasspy/piper-voices"
    whisper_revision = api.model_info(whisper_repo).sha
    voice_revision = api.model_info(voice_repo).sha
    snapshot_download(whisper_repo, revision=whisper_revision, token=False, local_dir=root / "whisper")
    prefix = "en/en_US/joe/medium/"
    voice = None
    for filename in (voice_name + ".onnx", voice_name + ".onnx.json", "MODEL_CARD"):
        path = hf_hub_download(voice_repo, filename=prefix + filename, revision=voice_revision, token=False, local_dir=root / "voices")
        if filename.endswith(".onnx"):
            voice = Path(path)
    artifacts = [root / "whisper/model.bin", voice, voice.with_suffix(".onnx.json")]
    manifest = {"whisper_repo": whisper_repo, "whisper_revision": whisper_revision,
                "voice_repo": voice_repo, "voice_revision": voice_revision, "voice": voice_name,
                "voice_dataset_license": "CC0 (OHF-Voice joe)",
                "artifacts": [{"path": str(path), "sha256": sha256(path)} for path in artifacts]}
    manifest_file.write_text(json.dumps(manifest, indent=2) + "\n")
    print("pinned_speech_models=downloaded")


if __name__ == "__main__":
    main()
