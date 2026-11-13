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

    input_started = time.monotonic()
    clip = SpeechClient().synthesize("This is a connection check only. Please greet me briefly. Do not change any household records.")
    input_synthesis_seconds = time.monotonic() - input_started
    started = time.monotonic()
    accepted = json.loads(api("POST", "/v1/utterance", clip,
                             {"Content-Type": "audio/wav", "X-Hearth-Request-Id": "smoke-" + uuid.uuid4().hex}))
    upload_seconds = time.monotonic() - started
    transitions = []
    path = "/v1/requests/" + accepted["request_id"]
    deadline = time.monotonic() + 55
    while time.monotonic() < deadline:
        result = json.loads(api("GET", path))
        state_pair = [result["status"], result["speech_status"]]
        if not transitions or transitions[-1]["state"] != state_pair:
            transitions.append({"state": state_pair, "seconds": round(time.monotonic() - started, 3)})
        if result["status"] in ("failed", "uncertain") or result["speech_status"] == "failed":
            raise RuntimeError("voice check outcome: " + result["status"] + "/" + result["speech_status"])
        if result["status"] == "completed" and result["speech_status"] == "ready":
            break
        time.sleep(0.5)
    else:
        raise RuntimeError("voice check timed out; inspect this request before repeating")
    ready_seconds = time.monotonic() - started
    download_started = time.monotonic()
    pcm, rate = parse_wav(api("GET", path + "/audio"))
    download_seconds = time.monotonic() - download_started
    if not result["reply"].strip() or not pcm or rate != 16000:
        raise RuntimeError("voice check returned an incomplete reply")
    evidence = {"request_id": result["id"], "checked_at": time.time(), "text_reply": True,
                "pcm_bytes": len(pcm), "sample_rate": rate, "https_audio_verified": True,
                "timing": {"input_tts_seconds": round(input_synthesis_seconds, 3), "upload_seconds": round(upload_seconds, 3),
                           "audio_ready_seconds": round(ready_seconds, 3), "download_seconds": round(download_seconds, 3), "transitions": transitions}}
    target = state / "last-voice-check.json"
    target.write_text(json.dumps(evidence))
    target.chmod(0o600)
    print(json.dumps(evidence))
    print("VOICE_PATH_VERIFIED")


if __name__ == "__main__":
    main()
