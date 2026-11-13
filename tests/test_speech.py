import socket
import threading
import time
import unittest
from types import SimpleNamespace
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from hub.speech import SpeechClient
from hub.speech_server import make_server
from hub.wavutil import wrap_pcm16


class SpeechTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        engine = SimpleNamespace(transcribe=lambda wav: self.calls.append("stt") or "Add milk",
                                 synthesize=lambda text: self.calls.append("tts") or wrap_pcm16(b"\0\0" * 800))
        self.server = make_server("127.0.0.1", 0, engine)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.client = SpeechClient()
        self.client.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def test_stt_and_tts_roundtrip_use_bounded_pcm16_mono(self):
        self.assertEqual(self.client.transcribe(wrap_pcm16(b"\0\0" * 1600)), "Add milk")
        self.assertEqual(self.client.synthesize("Task added.")[:4], b"RIFF")
        self.assertEqual(self.calls, ["stt", "tts"])

    def test_invalid_audio_is_rejected_before_model_execution(self):
        request = Request(self.client.base + "/v1/transcribe", data=b"invalid", headers={"Content-Type": "audio/wav"})
        with self.assertRaises(HTTPError) as caught:
            urlopen(request, timeout=2)
        self.assertEqual(caught.exception.code, 400)
        caught.exception.close()
        self.assertEqual(self.calls, [])

    def test_slow_body_does_not_hold_the_engine_and_has_an_absolute_deadline(self):
        from unittest.mock import patch
        with patch("hub.speech_server.BODY_TIMEOUT", 0.1):
            slow = socket.create_connection(("127.0.0.1", self.server.server_port), timeout=1)
            try:
                slow.sendall(b"POST /v1/speech HTTP/1.1\r\nHost: localhost\r\nContent-Type: application/json\r\nContent-Length: 20\r\n\r\n{")
                started = time.monotonic()
                self.assertEqual(self.client.synthesize("Hello")[:4], b"RIFF")
                self.assertEqual(slow.recv(512), b"")
                self.assertLess(time.monotonic() - started, 0.7)
            finally:
                slow.close()

    def test_speech_engine_busy_rejects_extra_work(self):
        self.server.busy.acquire()
        try:
            with self.assertRaises(HTTPError) as caught:
                self.client.synthesize("Hello")
            self.assertEqual(caught.exception.code, 429)
            caught.exception.close()
        finally:
            self.server.busy.release()
        self.assertEqual(self.calls, [])


if __name__ == "__main__":
    unittest.main()
