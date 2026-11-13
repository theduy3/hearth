"""Measure isolated local speech using public synthetic text, not family recordings."""
import argparse
import json
import resource
import sys
import time
from pathlib import Path

from hub.speech_server import SpeechEngine


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", type=Path, required=True)
    args = parser.parse_args()
    voice = args.models / "voices/en/en_US/ljspeech/medium/en_US-ljspeech-medium.onnx"
    started = time.monotonic()
    engine = SpeechEngine(args.models / "whisper", voice)
    loaded = time.monotonic()
    audio = engine.synthesize("Add milk to the family shopping list.")
    spoken = time.monotonic()
    text = engine.transcribe(audio)
    finished = time.monotonic()
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024 if sys.platform != "darwin" else 1024 * 1024)
    result = {"load_seconds": round(loaded - started, 2), "tts_seconds": round(spoken - loaded, 2),
              "stt_seconds": round(finished - spoken, 2), "peak_rss_mib": round(peak, 1),
              "audio_bytes": len(audio), "synthetic_transcript": text,
              "synthetic_roundtrip_ok": all(word in text.lower() for word in ("milk", "family", "shopping"))}
    print(json.dumps(result), flush=True)
    if not result["synthetic_roundtrip_ok"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
