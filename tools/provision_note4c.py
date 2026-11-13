#!/usr/bin/env python3
"""Private USB provisioning and read-only physical voice-check evidence."""
import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path


REMOTE = r'''
import json
from pathlib import Path
values={}
for line in Path('/home/hermes/.hermes/catthew-terminal-state/terminal.env').read_text().splitlines():
 if line.startswith('HEARTH_DEVICE_TOKEN='):
  values['token']=line.split('=',1)[1].strip().strip('"').strip("'")
print(json.dumps(values))
'''


def credential():
    result = subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", "bluehost",
                             "docker", "exec", "-i", "--user", "1500", "hermes",
                             "/home/hermes/.hermes/hermes-agent/venv/bin/python", "-"],
                            input=REMOTE, text=True, capture_output=True, check=True, timeout=20)
    token = json.loads(result.stdout)["token"]
    if not re.fullmatch(r"[A-Za-z0-9_-]{32,96}", token):
        raise RuntimeError("device credential is not valid")
    return token


def expected_mac():
    path = Path.home() / ".local/share/catthew-note4c/active-backup.json"
    mac = json.loads(path.read_text())["expected_mac"]
    if not re.fullmatch(r"(?:[a-f0-9]{2}:){5}[a-f0-9]{2}", mac):
        raise RuntimeError("private device identity is missing")
    return mac


def exchange(port, line, timeout=12):
    import serial
    connection = serial.Serial(port=None, baudrate=115200, timeout=0.25, write_timeout=5, exclusive=True)
    connection.dtr = False
    connection.rts = False
    connection.port = port
    connection.open()
    try:
        connection.reset_input_buffer()
        connection.write(line.encode("utf-8") + b"\n")
        connection.flush()
        deadline = time.monotonic() + timeout
        pending = bytearray()
        while time.monotonic() < deadline:
            data = connection.read(256)
            pending.extend(data)
            if len(pending) > 8192:
                pending.clear()
            while b"\n" in pending:
                raw, _, rest = pending.partition(b"\n")
                pending = bytearray(rest)
                if raw.startswith(b"CATTHEW_RESULT "):
                    result = json.loads(raw[15:])
                    if not isinstance(result, dict) or not isinstance(result.get("ok"), bool):
                        raise RuntimeError("invalid device response")
                    return result
        raise RuntimeError("device did not answer")
    finally:
        connection.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("info", "status", "pair"))
    parser.add_argument("--port", default="/dev/cu.usbmodem101")
    args = parser.parse_args()
    info = exchange(args.port, "CATTHEW_INFO")
    if info.get("mac") != expected_mac() or not info["ok"]:
        raise RuntimeError("the attached device does not match the verified backup")
    if args.mode == "info":
        print(json.dumps({"ok": True, "configured": info.get("configured") is True}))
        return
    if args.mode == "status":
        status = exchange(args.port, "CATTHEW_STATUS")
        fields = {"ok", "wifi", "wifi_reason", "clock", "online", "capture_ready", "audio_busy", "display_busy", "processing", "queued_upload", "nav_steps", "capture_count", "capture_ms", "capture_result", "upload_count", "upload_result", "frame_count", "frame_result", "http_status"}
        if not status["ok"] or not {"wifi", "clock", "frame_count"} <= status.keys():
            raise RuntimeError("device status is unavailable")
        print(json.dumps({key: value for key, value in status.items() if key in fields and type(value) in (int, bool)}))
        return
    fields = sys.stdin.buffer.read(2048).split(b"\0")
    if len(fields) != 3 or fields[-1] != b"":
        raise RuntimeError("private Wi-Fi input is incomplete")
    ssid, password = (value.decode("utf-8") for value in fields[:2])
    if not 1 <= len(ssid.encode()) <= 32 or len(password.encode()) > 64:
        raise RuntimeError("Wi-Fi input exceeds the device limits")
    document = {"ssid": ssid, "password": password, "hub": "https://zectrix.theduy.cloud", "token": credential()}
    result = exchange(args.port, "CATTHEW_CONFIG " + json.dumps(document, ensure_ascii=False, separators=(",", ":")), timeout=140)
    if not result["ok"]:
        raise RuntimeError("device could not confirm provisioning; it may reboot into its previous settings")
    print("Private Wi-Fi and device credential saved to Note4C NVS; rebooting.")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        # Neither an echoed serial line nor SSH credential stdout belongs in logs.
        print("Note4C setup failed (" + type(error).__name__ + "). Check the USB connection and rerun the wizard.", file=sys.stderr)
        raise SystemExit(1)
