#!/usr/bin/env python3
"""Private USB provisioning and credential-free device readiness checks."""
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
STATUS_FIELDS = {"ok", "wifi", "wifi_reason", "clock", "online", "capture_ready", "audio_busy", "display_busy", "processing", "queued_upload", "nav_steps", "capture_count", "capture_ms", "capture_result", "upload_count", "upload_result", "frame_count", "frame_result", "http_status"}


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


class UsbDevice:
    """One connection for identity and commands: opening USB resets this board."""
    def __init__(self, port):
        import serial
        self.connection = serial.Serial(port=None, baudrate=115200, timeout=0.25, write_timeout=5, exclusive=True)
        self.connection.dtr = False
        self.connection.rts = False
        self.connection.port = port

    def __enter__(self):
        self.connection.open()
        return self

    def __exit__(self, *args):
        self.connection.close()

    def exchange(self, line, timeout=12):
        self.connection.reset_input_buffer()
        self.connection.write(line.encode("utf-8") + b"\n")
        self.connection.flush()
        deadline = time.monotonic() + timeout
        pending = bytearray()
        while time.monotonic() < deadline:
            pending.extend(self.connection.read(256))
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


def public_status(status):
    if not status.get("ok") or not {"wifi", "clock", "frame_count"} <= status.keys():
        raise RuntimeError("device status is unavailable")
    return {key: value for key, value in status.items() if key in STATUS_FIELDS and type(value) in (int, bool)}


def wait_ready(device, timeout):
    deadline = time.monotonic() + timeout
    last = {}
    while time.monotonic() < deadline:
        last = public_status(device.exchange("CATTHEW_STATUS"))
        if (last.get("wifi") == 1 and last.get("clock") == 1 and last.get("online") == 1
                and last.get("frame_count", 0) > 0 and last.get("frame_result") == 0):
            return last
        time.sleep(2)
    raise DeviceNotReady(last)


class DeviceNotReady(RuntimeError):
    def __init__(self, status):
        self.status = status


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("info", "status", "wait-online", "pair"))
    parser.add_argument("--port", default="/dev/cu.usbmodem101")
    parser.add_argument("--timeout", type=int, default=90)
    args = parser.parse_args()
    if not 1 <= args.timeout <= 180:
        raise RuntimeError("readiness timeout is outside limits")
    with UsbDevice(args.port) as device:
        info = device.exchange("CATTHEW_INFO")
        if info.get("mac") != expected_mac() or not info["ok"]:
            raise RuntimeError("the attached device does not match the verified backup")
        if args.mode == "info":
            print(json.dumps({"ok": True, "configured": info.get("configured") is True}))
            return
        if args.mode in ("status", "wait-online"):
            status = wait_ready(device, args.timeout) if args.mode == "wait-online" else public_status(device.exchange("CATTHEW_STATUS"))
            print(json.dumps(status))
            if args.mode == "wait-online":
                print("DEVICE_NETWORK_VERIFIED")
            return
        fields = sys.stdin.buffer.read(2048).split(b"\0")
        if len(fields) != 3 or fields[-1] != b"":
            raise RuntimeError("private Wi-Fi input is incomplete")
        ssid, password = (value.decode("utf-8") for value in fields[:2])
        if not 1 <= len(ssid.encode()) <= 32 or len(password.encode()) > 64:
            raise RuntimeError("Wi-Fi input exceeds the device limits")
        document = {"ssid": ssid, "password": password, "hub": "https://zectrix.theduy.cloud", "token": credential()}
        result = device.exchange("CATTHEW_CONFIG " + json.dumps(document, ensure_ascii=False, separators=(",", ":")), timeout=140)
        if not result["ok"]:
            raise RuntimeError("device could not confirm provisioning")
        print("Private Wi-Fi and device credential saved to Note4C NVS; rebooting.")


if __name__ == "__main__":
    try:
        main()
    except DeviceNotReady as error:
        print("Device network is not ready: " + json.dumps(error.status), file=sys.stderr)
        if error.status.get("wifi_reason") == 201:
            print("Wi-Fi network not found (201). Check the exact 2.4 GHz network name and range; re-enter it privately with tools/setup-note4c.sh --wifi-only.", file=sys.stderr)
        raise SystemExit(1)
    except Exception as error:
        # Neither an echoed serial line nor SSH credential stdout belongs in logs.
        print("Note4C setup failed (" + type(error).__name__ + "). Check the USB connection and rerun the wizard.", file=sys.stderr)
        raise SystemExit(1)
