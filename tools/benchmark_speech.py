"""Measure loopback speech on reusable public synthetic fixtures, never family audio."""
import argparse
import http.client
import json
import os
import statistics
import time
from pathlib import Path
from urllib.parse import urlsplit

from hub.wavutil import parse_wav, wrap_pcm16

FIXTURES = {
    "short": ("This is a connection check. Please greet me briefly.", ("connection", "check")),
    "long": ("This is a speech recognition benchmark. The yellow notebook sits beside the red cup on the white table. The black clock shows seven thirty. Please repeat the sentence clearly.", ("yellow", "notebook", "red", "clock")),
    "maximum": ("The yellow notebook was beside the red cup when the black clock struck seven thirty. I put on my coat and walked down the quiet street to the bakery. A friendly dog waited outside while its owner bought fresh bread. Later that morning the clouds cleared and sunlight filled the garden. I opened the window, watered the plants, and read a chapter of my favorite book. In the afternoon I called a friend to discuss our plans for the weekend. We decided to visit the museum before having dinner near the harbor.", ("yellow", "notebook", "red", "clock")),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixtures", type=Path, required=True)
    parser.add_argument("--label", required=True, choices=("whisper", "parakeet"))
    parser.add_argument("--base", default="http://127.0.0.1:8791")
    args = parser.parse_args()
    base = urlsplit(args.base)
    if base.scheme != "http" or base.hostname != "127.0.0.1" or base.path:
        parser.error("benchmark requires a loopback HTTP speech service")
    os.umask(0o077)
    args.fixtures.mkdir(parents=True, exist_ok=True, mode=0o700)

    def post(path, data, content_type):
        connection = http.client.HTTPConnection(base.hostname, base.port or 80, timeout=90)
        try:
            connection.request("POST", path, body=data, headers={"Content-Type": content_type})
            response = connection.getresponse()
            value = response.read(4 * 1024 * 1024 + 1)
            if response.status != 200 or len(value) > 4 * 1024 * 1024:
                raise RuntimeError("speech benchmark failed: HTTP " + str(response.status))
            return value
        finally:
            connection.close()

    results = {}
    for name, (sentence, words) in FIXTURES.items():
        path = args.fixtures / (name + ".wav")
        if not path.exists():
            audio = post("/v1/speech", json.dumps({"text": sentence}).encode(), "application/json")
            pcm, rate = parse_wav(audio)
            if rate != 16000:
                raise RuntimeError("unexpected benchmark sample rate")
            # Exercise almost the entire supported30s recording bound.
            path.write_bytes(wrap_pcm16(pcm[:29 * 16000 * 2]))
        audio = path.read_bytes()
        pcm, rate = parse_wav(audio)
        samples = []
        correct = True
        for _ in range(3):
            started = time.monotonic()
            value = json.loads(post("/v1/transcribe", audio, "audio/wav"))
            samples.append(round(time.monotonic() - started, 3))
            correct = correct and all(word in value["text"].lower() for word in words)
        results[name] = {"audio_seconds": round(len(pcm) / (rate * 2), 3), "stt_seconds": samples,
                         "warm_median_seconds": statistics.median(samples[1:]), "synthetic_words_present": correct}
        print(json.dumps({"label": args.label, "fixture": name, **results[name]}), flush=True)
    passed = all(result["synthetic_words_present"] for result in results.values())
    (args.fixtures / (args.label + ".json")).write_text(json.dumps(results, indent=2) + "\n")
    if not passed:
        raise SystemExit("synthetic transcription mismatch")
    print("SPEECH_BENCHMARK_VERIFIED", flush=True)


if __name__ == "__main__":
    main()
