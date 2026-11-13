#!/usr/bin/env python3
"""Exercise VPS STT → Catthew → TTS through the authenticated public device API."""
import http.client
import json
import time
import uuid
from pathlib import Path

from hub.settings import setting
from hub.speech import SpeechClient
from hub.wavutil import parse_wav


def main():
    state = Path("/home/hermes/.hermes/catthew-terminal-state")
    token = setting((state / "terminal.env").read_text(), "HEARTH_DEVICE_TOKEN")

    def api(method, path, body=None, headers=None):
        connection = http.client.HTTPSConnection("zectrix.theduy.cloud", timeout=20)
        try:
            connection.request(method, path, body=body, headers={"Authorization": "Bearer " + token, **(headers or {})})
            response = connection.getresponse()
            data = response.read(4 * 1024 * 1024 + 1)
            if response.status not in (200, 202) or len(data) > 4 * 1024 * 1024:
                raise RuntimeError("public voice check failed: HTTP " + str(response.status))
            return data
        finally:
            connection.close()

    clip = SpeechClient().synthesize("This is a connection check only. Please greet me briefly. Do not change any household records.")
    accepted = json.loads(api("POST", "/v1/utterance", clip,
                             {"Content-Type": "audio/wav", "X-Hearth-Request-Id": "smoke-" + uuid.uuid4().hex}))
    path = "/v1/requests/" + accepted["request_id"]
    deadline = time.monotonic() + 55
    while time.monotonic() < deadline:
        result = json.loads(api("GET", path))
        if result["status"] in ("failed", "uncertain") or result["speech_status"] == "failed":
            raise RuntimeError("voice check outcome: " + result["status"] + "/" + result["speech_status"])
        if result["status"] == "completed" and result["speech_status"] == "ready":
            break
        time.sleep(0.5)
    else:
        raise RuntimeError("voice check timed out; inspect this request before repeating")
    pcm, rate = parse_wav(api("GET", path + "/audio"))
    if not result["reply"].strip() or not pcm or rate != 16000:
        raise RuntimeError("voice check returned an incomplete reply")
    evidence = {"request_id": result["id"], "checked_at": time.time(), "text_reply": True,
                "pcm_bytes": len(pcm), "sample_rate": rate, "https_audio_verified": True}
    target = state / "last-voice-check.json"
    target.write_text(json.dumps(evidence))
    target.chmod(0o600)
    print(json.dumps(evidence))
    print("VOICE_PATH_VERIFIED")


if __name__ == "__main__":
    main()
