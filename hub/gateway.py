"""Profile-scoped Hermes gateway client; a disconnected turn is never resubmitted."""
from __future__ import annotations

import http.client
import ipaddress
import json
import socket
import ssl
import threading
import time
from contextlib import contextmanager
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import Request


class _Reply:
    def __init__(self, response, sock, deadline):
        self.response = response
        self.sock = sock
        self.deadline = deadline
        self.headers = response.headers

    def chunks(self):
        while True:
            if self.response.isclosed():
                return
            remaining = self.deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("gateway deadline exceeded")
            self.sock.settimeout(remaining)
            chunk = self.response.read1(4096)
            if not chunk:
                return
            yield chunk

    def lines(self):
        pending = b""
        total = 0
        for chunk in self.chunks():
            total += len(chunk)
            if total > 8 * 1024 * 1024:
                raise ValueError("oversized gateway stream")
            pending += chunk
            while b"\n" in pending:
                line, pending = pending.split(b"\n", 1)
                if len(line) > 65536:
                    raise ValueError("oversized gateway line")
                yield line + b"\n"
            if len(pending) > 65536:
                raise ValueError("oversized gateway line")
        if pending:
            yield pending

    def read(self, maximum):
        data = bytearray()
        for chunk in self.chunks():
            data.extend(chunk)
            if len(data) >= maximum:
                break
        return bytes(data)


@contextmanager
def _open_request(request, *, timeout):
    """Own the socket so read deadlines cover slow-drip data, not just idle time.

    http.client never follows redirects and never uses environment proxy settings.
    """
    parsed = urlsplit(request.full_url)
    address = ipaddress.ip_address(parsed.hostname)
    connection_type = http.client.HTTPSConnection if parsed.scheme == "https" else http.client.HTTPConnection
    connection = connection_type(parsed.hostname, parsed.port, timeout=timeout)
    deadline = time.monotonic() + timeout
    sock = socket.socket(socket.AF_INET6 if address.version == 6 else socket.AF_INET, socket.SOCK_STREAM)
    timer = None
    response = None
    try:
        sock.settimeout(timeout)

        def interrupt():
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass

        # The owned socket also bounds slow status/header parsing in getresponse().
        timer = threading.Timer(max(0, deadline - time.monotonic()), interrupt)
        timer.daemon = True
        timer.start()
        # A single literal address avoids blocking DNS and per-address timeout retries.
        sock.connect((str(address), parsed.port or (443 if parsed.scheme == "https" else 80)))
        if parsed.scheme == "https":
            sock = ssl.create_default_context().wrap_socket(sock, server_hostname=parsed.hostname,
                                                           do_handshake_on_connect=False)
            sock.settimeout(max(0.001, deadline - time.monotonic()))
            sock.do_handshake()
        connection.sock = sock
        connection.request(request.get_method(), parsed.path, body=request.data,
                           headers=dict(request.header_items()))
        sock.settimeout(max(0.001, deadline - time.monotonic()))
        response = connection.getresponse()
        if response.status != 200:
            response.close()
            raise HTTPError(request.full_url, response.status, "gateway rejected request", response.headers, None)
        yield _Reply(response, sock, deadline)
    finally:
        if timer is not None:
            timer.cancel()
        if response is not None:
            response.close()
        connection.close()
        sock.close()



class GatewayError(RuntimeError):
    def __init__(self, message: str, *, uncertain: bool):
        super().__init__(message)
        self.uncertain = uncertain


class Gateway:
    def __init__(self, base_url: str, key: str, *, timeout: float = 120):
        parsed = urlsplit(base_url)
        if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ("", "/"):
            raise ValueError("Hermes base URL must be an HTTP(S) origin")
        try:
            address = ipaddress.ip_address(parsed.hostname)
        except ValueError:
            raise ValueError("Hermes gateway must use a private numeric IP address") from None
        if not (address.is_private or address.is_loopback):
            raise ValueError("Hermes gateway must remain on a private network")
        if len(key) < 16 or any(c in key for c in "\r\n"):
            raise ValueError("Hermes API key must contain at least 16 characters")
        self.base = base_url.rstrip("/") + "/p/catthew"
        self.key = key
        self.timeout = timeout
        self._open = _open_request

    def _request(self, path: str, body: dict, *, headers=None):
        return Request(self.base + path, data=json.dumps(body).encode("utf-8"),
                       headers={"Authorization": "Bearer " + self.key,
                                "Content-Type": "application/json", **(headers or {})})

    def _assert_household_policy(self):
        request = Request(self.base + "/v1/toolsets", headers={"Authorization": "Bearer " + self.key})
        try:
            with self._open(request, timeout=min(15, self.timeout)) as response:
                raw = response.read(131073)
                if len(raw) > 131072:
                    raise ValueError("tool policy exceeded its limit")
                data = json.loads(raw)
                entries = data["data"]
                if not isinstance(entries, list) or not entries:
                    raise ValueError("invalid tool catalog")
                for entry in entries:
                    if not isinstance(entry, dict) or not isinstance(entry.get("enabled"), bool):
                        raise ValueError("invalid tool policy")
                    if entry["enabled"] and not (entry.get("name") == "stt" and entry.get("tools") == []):
                        raise ValueError("native tools are enabled on the household channel")
        except Exception:
            raise GatewayError("Household tool policy is unavailable or exposes unexpected capabilities; no agent turn was started.", uncertain=False) from None

    def turn(self, text: str, session: str, device: str, *, on_run=None, on_approval=None):
        if not text.strip() or len(text) > 8000:
            raise ValueError("transcript is empty or too long")
        for value in (session, device):
            if not value or len(value) > 128 or any(c in value for c in "\r\n"):
                raise ValueError("invalid session/device identifier")
        self._assert_household_policy()
        req = self._request("/v1/chat/completions",
                            {"messages": [{"role": "user", "content": text}], "stream": True},
                            headers={"X-Hermes-Session-Id": session,
                                     "X-Hermes-Session-Key": "hearth:note4c:" + device})
        reply = []
        run_id = ""
        finish = None
        done = False
        total = 0
        started = time.monotonic()
        try:
            with self._open(req, timeout=self.timeout) as response:
                if response.headers.get_content_type() != "text/event-stream":
                    raise GatewayError("Hermes returned an invalid stream.", uncertain=True)
                event = "message"
                data = []
                for raw in response.lines():
                    if time.monotonic() - started > self.timeout:
                        raise GatewayError("Hermes turn timed out; verify its outcome.", uncertain=True)
                    total += len(raw)
                    if len(raw) > 65536 or total > 8 * 1024 * 1024:
                        raise GatewayError("Hermes stream exceeded the limit.", uncertain=True)
                    if not raw:
                        break
                    line = raw.decode("utf-8").rstrip("\r\n")
                    if line.startswith(":"):
                        continue
                    if line:
                        field, _, value = line.partition(":")
                        if value.startswith(" "):
                            value = value[1:]
                        if field == "event":
                            event = value
                        elif field == "data":
                            data.append(value)
                        continue
                    if not data:
                        event = "message"
                        continue
                    payload = "\n".join(data)
                    data = []
                    if event == "error":
                        raise GatewayError("Hermes reported a turn error; verify the outcome.", uncertain=True)
                    if payload == "[DONE]" and event == "message":
                        done = True
                        break
                    frame = json.loads(payload)
                    if not isinstance(frame, dict):
                        raise ValueError("stream object required")
                    if event == "error" or "error" in frame:
                        raise GatewayError("Hermes reported a turn error; verify the outcome.", uncertain=True)
                    if event == "approval.request":
                        if not run_id or on_approval is None:
                            raise GatewayError("Action requires approval; no approval channel is available.", uncertain=True)
                        on_approval(run_id, frame)
                    elif event == "message":
                        next_id = frame.get("id")
                        if next_id and (not isinstance(next_id, str) or len(next_id) > 256):
                            raise ValueError("invalid stream run identity")
                        if next_id and next_id != run_id:
                            if run_id:
                                raise ValueError("stream changed run identity")
                            run_id = next_id
                            if on_run:
                                on_run(run_id)
                        choices = frame.get("choices") or []
                        if choices:
                            choice = choices[0]
                            content = (choice.get("delta") or {}).get("content")
                            if content:
                                if not isinstance(content, str):
                                    raise ValueError("reply content must be text")
                                reply.append(content)
                                if sum(map(len, reply)) > 16000:
                                    raise GatewayError("Hermes reply exceeded the limit.", uncertain=True)
                            if choice.get("finish_reason") is not None:
                                finish = choice["finish_reason"]
                    event = "message"
        except HTTPError as exc:
            exc.close()
            # A server error can occur after a tool executed; 4xx rejects the turn.
            raise GatewayError(f"Hermes rejected the request (HTTP {exc.code}).",
                               uncertain=exc.code >= 500) from None
        except GatewayError:
            raise
        except (URLError, OSError, http.client.HTTPException, ValueError, TypeError, KeyError):
            raise GatewayError("Hermes connection ended; verify the outcome before retrying.", uncertain=True) from None
        if not done or finish != "stop" or not run_id:
            raise GatewayError("Hermes did not confirm a complete response; verify the outcome.", uncertain=True)
        result = "".join(reply).strip()
        if not result:
            raise GatewayError("Hermes completed without a reply.", uncertain=True)
        return result

    def approve(self, run_id: str, request_id: str, choice: str):
        """Forward an explicit authenticated decision, never infer approval from speech."""
        req = self._request(f"/v1/runs/{quote(run_id, safe='')}/approval",
                            {"request_id": request_id, "choice": choice})
        try:
            with self._open(req, timeout=12) as response:
                data = response.read(65537)
                if len(data) > 65536:
                    raise ValueError("oversized approval response")
                return json.loads(data)
        except (HTTPError, URLError, OSError, http.client.HTTPException, ValueError):
            raise GatewayError("Approval could not be confirmed.", uncertain=True) from None
