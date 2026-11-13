"""Local CPU English speech service. Raw microphone audio remains in memory."""
from __future__ import annotations

import argparse
import io
import json
import threading
import wave
from http.server import BaseHTTPRequestHandler
from pathlib import Path

from hub.httpserver import BoundedHTTPServer, read_body
from hub.wavutil import parse_wav, wrap_pcm16

BODY_TIMEOUT = 5


class SpeechEngine:
    def __init__(self, whisper_model, voice_model):
        from faster_whisper import WhisperModel
        from piper import PiperVoice
        self.whisper = WhisperModel(str(whisper_model), device="cpu", compute_type="int8", cpu_threads=2, num_workers=1)
        self.voice = PiperVoice.load(str(voice_model))

    def transcribe(self, wav):
        segments, info = self.whisper.transcribe(io.BytesIO(wav), language="en", beam_size=1,
                                               condition_on_previous_text=False, vad_filter=True)
        return " ".join(segment.text.strip() for segment in segments).strip()

    def synthesize(self, text):
        import numpy as np
        import soxr
        output = io.BytesIO()
        with wave.open(output, "wb") as stream:
            self.voice.synthesize_wav(text, stream)
        pcm, rate = parse_wav(output.getvalue())
        if rate != 16000:
            samples = np.frombuffer(pcm, dtype="<i2").astype(np.float32) / 32768
            samples = soxr.resample(samples, rate, 16000)
            pcm = np.rint(np.clip(samples, -1, 32767 / 32768) * 32768).astype("<i2").tobytes()
        return wrap_pcm16(pcm)


class Handler(BaseHTTPRequestHandler):
    server_version = "CatthewSpeech/1.0"

    def setup(self):
        super().setup()
        self.connection.settimeout(15)

    def log_message(self, *args):
        pass

    def send(self, code, data, content_type="application/json"):
        if content_type == "application/json":
            data = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        try:
            self.end_headers()
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_GET(self):
        self.send(200 if self.path == "/health" else 404, {"ok": self.path == "/health", "language": "en", "sample_rate": 16000})

    def do_POST(self):
        try:
            body = read_body(self, 960044, timeout=BODY_TIMEOUT)
            if self.path == "/v1/transcribe":
                if self.headers.get("Content-Type") != "audio/wav":
                    raise ValueError("audio/wav is required")
                pcm, rate = parse_wav(body)
                if rate != 16000 or len(pcm) > 960000:
                    raise ValueError("need at most 30 seconds of PCM16 mono at 16 kHz")
                text = None
            elif self.path == "/v1/speech":
                if self.headers.get("Content-Type") != "application/json":
                    raise ValueError("application/json is required")
                payload = json.loads(body)
                if not isinstance(payload, dict) or set(payload) != {"text"}:
                    raise ValueError("one text field is required")
                text = payload["text"]
                if not isinstance(text, str) or not text.strip() or len(text) > 1200:
                    raise ValueError("speech text is empty or too long")
            else:
                self.send(404, {"error": "unknown speech route"})
                return
        except (ValueError, UnicodeError):
            self.send(400, {"error": "invalid speech request"})
            return
        if not self.server.busy.acquire(blocking=False):
            self.send(429, {"error": "speech engine busy"})
            return
        try:
            if text is None:
                result = self.server.engine.transcribe(body)
                if not isinstance(result, str) or len(result) > 8000:
                    raise ValueError("transcription exceeds its limit")
                self.send(200, {"text": result, "language": "en"})
            else:
                audio = self.server.engine.synthesize(text)
                _, rate = parse_wav(audio)
                if rate != 16000 or len(audio) > 4 * 1024 * 1024:
                    raise ValueError("invalid synthesized audio")
                self.send(200, audio, "audio/wav")
        except Exception:
            self.send(503, {"error": "speech processing failed"})
        finally:
            self.server.busy.release()


def make_server(host, port, engine):
    server = BoundedHTTPServer((host, port), Handler)
    server.busy = threading.Lock()
    server.engine = engine
    return server


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--whisper-model", type=Path, required=True)
    parser.add_argument("--voice-model", type=Path, required=True)
    args = parser.parse_args()
    server = make_server("127.0.0.1", 8791, SpeechEngine(args.whisper_model, args.voice_model))
    print("Catthew English speech ready on loopback", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
