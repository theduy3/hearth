"""Local speech transport and existing-profile Telegram approval delivery."""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from urllib.request import Request

from hub.gateway import _open_request
from hub.wavutil import parse_wav
from hub.settings import setting


class SpeechClient:
    def __init__(self):
        self.base = "http://127.0.0.1:8791"

    def transcribe(self, wav):
        request = Request(self.base + "/v1/transcribe", data=wav, headers={"Content-Type": "audio/wav"})
        with _open_request(request, timeout=45) as response:
            data = response.read(32769)
            if len(data) > 32768:
                raise ValueError("transcription response exceeds limit")
            text = json.loads(data).get("text")
            if not isinstance(text, str) or len(text) > 8000:
                raise ValueError("invalid transcription")
            return text

    def synthesize(self, text):
        if not isinstance(text, str) or not text.strip() or len(text) > 1200:
            raise ValueError("reply is empty or too long to speak")
        request = Request(self.base + "/v1/speech", data=json.dumps({"text": text}).encode(),
                          headers={"Content-Type": "application/json"})
        with _open_request(request, timeout=45) as response:
            wav = response.read(4 * 1024 * 1024 + 1)
            if len(wav) > 4 * 1024 * 1024:
                raise ValueError("spoken reply exceeds limit")
            _, rate = parse_wav(wav)
            if rate != 16000:
                raise ValueError("reply must be PCM16 mono at 16 kHz")
            return wav


class TelegramApprovals:
    def __init__(self, profile):
        value = setting((Path(profile) / ".env").read_text(), "TELEGRAM_ALLOWED_USERS") or ""
        # Reuse existing personal Telegram authorization; group IDs and wildcards
        # cannot receive private approval capabilities.
        if re.sub(r"[0-9,\s\[\]'\"]", "", value):
            raise ValueError("explicit private Telegram users are required for approvals")
        self.users = sorted({int(x) for x in re.findall(r"\d+", value) if int(x) > 0})
        if not 1 <= len(self.users) <= 5:
            raise ValueError("configure one to five existing private Telegram approvers")

    def __call__(self, url):
        if not url.startswith("https://zectrix.theduy.cloud/approval/"):
            raise ValueError("invalid private approval link")
        delivered = 0
        for user in self.users:
            try:
                subprocess.run(["/home/hermes/.local/bin/hermes", "-p", "catthew", "send", "--to", f"telegram:{user}", "--quiet", "--file", "-"],
                               input="Catthew has a family calendar change for you to review. No change has been applied.\n\n" + url,
                               text=True, capture_output=True, check=True, timeout=20)
                delivered += 1
            except (OSError, subprocess.SubprocessError):
                pass
        if not delivered:
            raise RuntimeError("private approval delivery failed")
