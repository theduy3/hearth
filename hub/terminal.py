"""Authenticated Note4C device API and private, single-use calendar approvals."""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import hmac
import json
import logging
import os
import re
import threading
import tempfile
import time
from collections import deque
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from hub.approval_html import message_page, proposal_page, shell_page
from hub.approvals import ApprovalStore
from hub.calendar import FamilyCalendar
from hub.frames import Renderer
from hub.gateway import Gateway, GatewayError
from hub.household import Household, PACIFIC
from hub.httpserver import BoundedHTTPServer, read_body
from hub.journal import Journal, QueueFull, RequestConflict
from hub.wavutil import parse_wav


class RateLimited(RuntimeError):
    pass


class TerminalState:
    def __init__(self, journal, approvals, household, gateway, speech, *, token, origin, notify=None):
        if not isinstance(token, str) or len(token) < 32:
            raise ValueError("a dedicated device credential of at least 32 characters is required")
        parsed = urlsplit(origin)
        if parsed.scheme != "https" or not parsed.hostname or parsed.path not in ("", "/"):
            raise ValueError("the public approval origin must be HTTPS")
        self.journal, self.approvals, self.household = journal, approvals, household
        self.gateway, self.speech = gateway, speech
        self.token, self.origin, self.notify = token, origin.rstrip("/"), notify
        self.device = "note4c"
        self.lock = threading.RLock()
        self.submission_lock = threading.Lock()
        self.notification_lock = threading.Lock()
        self.submissions = deque()
        self.cache = {"events": [], "tasks": [], "notes": []}
        self.errors = {"calendar": True, "vault": True}
        self.generated_at = ""
        self.cache_path = journal.path.with_name("household-view.json")
        self._load_cached_view()
        self.renderer = Renderer()
        self.stop = threading.Event()
        self.wake = threading.Event()
        self.journal.recover()
        self.approvals.recover()
        self.worker = threading.Thread(target=self._work, daemon=True, name="catthew-device-requests")
        self.poller = threading.Thread(target=self._poll, daemon=True, name="catthew-household-view")
        self.worker.start()
        self.poller.start()

    def close(self):
        self.stop.set()
        self.wake.set()
        self.worker.join(timeout=5)
        self.poller.join(timeout=5)

    def _load_cached_view(self):
        try:
            if self.cache_path.stat().st_size > 8 * 1024 * 1024:
                return
            saved = json.loads(self.cache_path.read_text())
            cache = saved["cache"]
            if set(cache) == {"events", "tasks", "notes"} and all(isinstance(x, list) for x in cache.values()):
                self.cache = cache
                self.generated_at = str(saved["generated_at"])
        except (OSError, ValueError, KeyError, TypeError):
            pass  # A derived cache can be rebuilt; it is never authoritative.

    def _save_cached_view(self):
        candidate = None
        try:
            encoded = json.dumps({"cache": self.cache, "generated_at": self.generated_at}, ensure_ascii=False)
            if len(encoded.encode()) > 8 * 1024 * 1024:
                raise ValueError("projection exceeds cache capacity")
            with tempfile.NamedTemporaryFile("w", dir=self.cache_path.parent, prefix=".view-", delete=False, encoding="utf-8") as handle:
                candidate = Path(handle.name)
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(candidate, self.cache_path)
        except (OSError, ValueError, TypeError):
            logging.getLogger(__name__).warning("Household projection cache unavailable; using the in-memory view")
        finally:
            if candidate is not None:
                try:
                    candidate.unlink(missing_ok=True)
                except OSError:
                    pass

    def refresh(self):
        start = datetime.now(PACIFIC).replace(hour=0, minute=0, second=0, microsecond=0)
        try:
            events = self.household.calendar.list_events(start.isoformat(), (start + timedelta(days=7)).isoformat())
            with self.lock:
                self.cache["events"] = [{k: x.get(k) for k in ("id", "summary", "start", "end", "etag", "location")} for x in events]
                self.errors["calendar"] = False
        except Exception:
            with self.lock:
                self.errors["calendar"] = True
        try:
            tasks = [x for x in self.household.tasks() if x["status"] not in ("completed", "done", "cancelled")]
            notes = self.household.reference_notes()
            with self.lock:
                self.cache["tasks"], self.cache["notes"] = tasks, notes
                self.errors["vault"] = False
        except Exception:
            with self.lock:
                self.errors["vault"] = True
        with self.lock:
            self.generated_at = datetime.now(PACIFIC).isoformat(timespec="seconds")
            self._save_cached_view()

    def view(self):
        with self.lock:
            payload = {"generated_at": self.generated_at, "timezone": "America/Vancouver",
                       "stale": any(self.errors.values()), "source_errors": dict(self.errors), **self.cache}
        latest = self.journal.latest(self.device)
        completed = self.journal.latest(self.device, completed=True)
        payload["request"] = latest
        payload["reply"] = completed["reply"] if completed else "Hold the front button to speak to Catthew."
        payload["reply_speech_status"] = completed["speech_status"] if completed else ""
        payload["approval_pending"] = len(self.approvals.pending())
        return payload

    def device_status(self):
        record = self.journal.latest(self.device)
        request = {k: record[k] for k in ("id", "client_id", "status", "speech_status", "error", "created")} if record else None
        return {"request": request, "reply_page": "reply:0"}

    def poster(self, offsets=None):
        offsets = offsets or {}
        payload = self.view()
        for name in ("events", "tasks", "notes"):
            items, offset = payload[name], offsets.get(name, 0)
            payload[name] = items[offset:offset + 8]
            payload[name + "_total"] = len(items)
            payload[name + "_offset"] = offset
        visible = {k: v for k, v in payload.items() if k != "generated_at"}
        payload["revision"] = hashlib.sha256(json.dumps(visible, sort_keys=True, default=str).encode()).hexdigest()[:16]
        return payload

    def enqueue(self, client_id, wav):
        with self.submission_lock:
            existing = self.journal.by_upload(self.device, client_id)
            if not existing:
                now = time.monotonic()
                while self.submissions and self.submissions[0] < now - 60:
                    self.submissions.popleft()
                if len(self.submissions) >= 12:
                    raise RateLimited("device request limit reached")
            record = self.journal.accept(self.device, client_id, wav)
            if not existing:
                self.submissions.append(time.monotonic())
            self.wake.set()
            return record

    def _work(self):
        while not self.stop.is_set():
            self.journal.expire()
            job = self.journal.claim()
            if job is None:
                self.wake.wait(0.25)
                self.wake.clear()
                continue
            agent_started = False
            try:
                text = self.speech.transcribe(job["wav"]).strip()
                del job["wav"]
                if not text:
                    raise ValueError("no speech")
                self.journal.begin_agent(job["id"], text)
                agent_started = True
                prompt = ("Family Note4C terminal: give a concise English reply suitable for display and speech. "
                          f"Household timezone America/Vancouver; local time {datetime.now(PACIFIC).isoformat(timespec='seconds')}. "
                          f"Request reference {job['id']}. Use this reference in operation IDs; calendar changes need private approval.\n\n" + text)
                reply = self.gateway.turn(prompt, self.journal.session(self.device), self.device,
                                          on_run=lambda run: self.journal.set_run(job["id"], run))
                self.journal.complete(job["id"], reply)
                try:
                    self.journal.set_audio(job["id"], self.speech.synthesize(reply))
                except Exception:
                    self.journal.speech_failed(job["id"])
                self.refresh()
            except GatewayError as error:
                self.journal.fail(job["id"], str(error), uncertain=error.uncertain)
            except Exception:
                self.journal.fail(job["id"], "Request could not be completed; verify current records before repeating it.", uncertain=agent_started)

    def _poll(self):
        while not self.stop.is_set():
            self.refresh()
            self.approvals.expire()
            self.dispatch_notifications()
            self.stop.wait(30)

    def dispatch_notifications(self):
        if self.notify is None:
            return
        with self.notification_lock:
            for proposal in self.approvals.pending():
                if proposal["notified"] or proposal["attempts"] >= 3:
                    continue
                capability = self.approvals.mint(proposal["id"])
                try:
                    self.notify(self.origin + "/approval/#" + capability)
                    self.approvals.mark_notified(proposal["id"])
                except Exception:
                    self.approvals.notification_failed(proposal["id"])

    def apply_approval(self, capability, decision):
        record = self.approvals.consume(capability, decision)
        if record is None:
            return None
        if decision == "deny":
            return "Change denied. The calendar was not changed."
        try:
            if record["kind"] == "edit":
                self.household.calendar.edit_event(**record["payload"])
            else:
                self.household.calendar.delete_event(**record["payload"])
        except Exception:
            self.approvals.finish(record["id"], succeeded=False)
            return "The change could not be confirmed. Check the calendar before requesting it again."
        self.approvals.finish(record["id"], succeeded=True)
        self.refresh()
        return "Calendar change confirmed."


class Handler(BaseHTTPRequestHandler):
    server_version = "CatthewTerminal/1.0"

    @property
    def state(self):
        return self.server.state

    def setup(self):
        super().setup()
        self.connection.settimeout(20)

    def log_message(self, *args):
        # URLs can contain private single-use approval capabilities.
        pass

    def send(self, code, data, content_type="application/json", headers=None):
        if content_type == "application/json":
            data = json.dumps(data, ensure_ascii=False, default=str).encode()
        elif isinstance(data, str):
            data = data.encode()
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Content-Type-Options", "nosniff")
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.send_header("Content-Security-Policy", "default-src 'none'; script-src 'self'; style-src 'unsafe-inline'; connect-src 'self'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'")
        try:
            self.end_headers()
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def authorized(self):
        value = self.headers.get("Authorization", "")
        if not hmac.compare_digest(value.encode(), ("Bearer " + self.state.token).encode()):
            self.send(401, {"error": "device authentication required"})
            return False
        return True

    def body(self, maximum):
        return read_body(self, maximum, timeout=20)

    def do_GET(self):
        parsed = urlsplit(self.path)
        path = parsed.path
        if path == "/health":
            healthy = self.state.worker.is_alive() and self.state.poller.is_alive()
            self.send(200 if healthy else 503, {"ok": healthy})
            return
        if path == "/approval/":
            self.send(200, shell_page(), "text/html; charset=utf-8")
            return
        if path == "/approval/client.js":
            self.send(200, Path(__file__).with_name("approval.js").read_bytes(), "text/javascript; charset=utf-8")
            return
        if not self.authorized():
            return
        if path == "/v1/device":
            self.send(200, self.state.device_status())
            return
        if path == "/v1/frame":
            query = parse_qs(parsed.query)
            page = query.get("page", ["today"])[0]
            if len(page) > 32:
                self.send(400, {"error": "invalid page"})
                return
            frame = self.state.renderer.render(self.state.view(), page, now=datetime.now(PACIFIC))
            etag = '"' + frame.etag + '"'
            headers = {"ETag": etag, "X-Hearth-Page": frame.page, "X-Hearth-Next": frame.next_page,
                       "X-Hearth-Previous": frame.previous_page, "X-Hearth-Pages": str(frame.pages)}
            unchanged = self.headers.get("If-None-Match") == etag
            self.send(304 if unchanged else 200, b"" if unchanged else frame.pixels,
                      "application/vnd.catthew.bwry2", headers)
            return
        if path == "/v1/poster":
            try:
                query = parse_qs(parsed.query)
                offsets = {name: int(query.get(name + "_offset", ["0"])[0]) for name in ("events", "tasks", "notes")}
                if any(x < 0 or x > 100000 for x in offsets.values()):
                    raise ValueError("invalid offset")
            except ValueError:
                self.send(400, {"error": "invalid page offset"})
                return
            self.send(200, self.state.poster(offsets))
            return
        match = re.fullmatch(r"/v1/requests/([a-f0-9]{32})(/audio)?", path)
        if match:
            record = self.state.journal.get(self.state.device, match[1])
            if record is None:
                self.send(404, {"error": "unknown request"})
            elif match[2]:
                audio = self.state.journal.audio(self.state.device, match[1])
                if audio:
                    self.send(200, audio, "audio/wav")
                else:
                    self.send(404, {"error": "reply audio is unavailable"})
            else:
                self.send(200, record)
            return
        self.send(404, {"error": "unknown route"})

    def do_POST(self):
        path = urlsplit(self.path).path
        if path in ("/approval/view", "/approval/confirm"):
            if self.headers.get("Origin") != self.state.origin:
                self.send(403, message_page("Open your private approval link from Telegram."), "text/html; charset=utf-8")
                return
            try:
                fields = parse_qs(self.body(512).decode(), strict_parsing=True)
                expected = {"capability"} | ({"decision"} if path.endswith("/confirm") else set())
                if set(fields) != expected or any(len(value) != 1 for value in fields.values()):
                    raise ValueError("invalid approval form")
                capability = fields["capability"][0]
                if path.endswith("/view"):
                    record = self.state.approvals.view(capability)
                    self.send(200 if record else 410, proposal_page(record) if record else message_page("This link is expired or already used. Read the current calendar before preparing another change."), "text/html; charset=utf-8")
                    return
                result = self.state.apply_approval(capability, fields["decision"][0])
            except (ValueError, UnicodeError):
                self.send(400, message_page("This approval request is invalid."), "text/html; charset=utf-8")
                return
            self.send(200 if result else 410, message_page(result or "This link is expired or already used. Read the current calendar before preparing another change."), "text/html; charset=utf-8")
            return
        if not self.authorized():
            return
        ack = re.fullmatch(r"/v1/requests/([a-f0-9]{32})/audio-ack", path)
        if ack:
            try:
                if self.body(128) != b"{}":
                    raise ValueError("empty object required")
                cleared = self.state.journal.clear_audio(self.state.device, ack[1])
            except ValueError:
                self.send(400, {"error": "invalid audio acknowledgement"})
                return
            self.send(200 if cleared else 404, {"ok": cleared})
            return
        if path != "/v1/utterance":
            self.send(404, {"error": "unknown route"})
            return
        try:
            if self.headers.get("Content-Type", "").split(";", 1)[0].lower() != "audio/wav":
                raise ValueError("audio/wav is required")
            wav = self.body(16000 * 2 * 30 + 1024)
            pcm, rate = parse_wav(wav)
            if rate != 16000 or len(pcm) < 320 or len(pcm) > 16000 * 2 * 30:
                raise ValueError("need 16 kHz mono speech between 10 ms and 30 seconds")
            record = self.state.enqueue(self.headers.get("X-Hearth-Request-Id", ""), wav)
        except (ValueError, RequestConflict) as error:
            self.send(409 if isinstance(error, RequestConflict) else 400, {"error": str(error)})
            return
        except (QueueFull, RateLimited):
            self.send(429, {"error": "request capacity reached; retry this upload ID later"})
            return
        self.send(202, {"accepted": True, "request_id": record["id"], "status": record["status"]})


class TerminalServer(BoundedHTTPServer):
    def service_actions(self):
        if not self.state.worker.is_alive() or not self.state.poller.is_alive():
            raise RuntimeError("terminal worker stopped; supervisor restart required")


def make_server(host, port, state):
    server = TerminalServer((host, port), Handler)
    server.state = state
    return server


def main():
    from hub.speech import SpeechClient, TelegramApprovals
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8790)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--vault", type=Path, default=Path("/vault"))
    args = parser.parse_args()
    args.state.mkdir(parents=True, exist_ok=True, mode=0o700)
    instance = os.fdopen(os.open(args.state / "terminal.lock", os.O_CREAT | os.O_RDWR, 0o600), "a")
    fcntl.flock(instance, fcntl.LOCK_EX | fcntl.LOCK_NB)
    calendar = FamilyCalendar.from_profile(args.profile)
    journal = Journal(args.state / "requests.sqlite3")
    approvals = ApprovalStore(args.state / "approvals.sqlite3")
    state = TerminalState(journal, approvals, Household(args.vault, calendar, args.state),
                          Gateway(os.environ["HEARTH_HERMES_URL"], os.environ["HEARTH_HERMES_KEY"]),
                          SpeechClient(), token=os.environ["HEARTH_DEVICE_TOKEN"],
                          origin="https://zectrix.theduy.cloud", notify=TelegramApprovals(args.profile))
    server = make_server("127.0.0.1", args.port, state)
    print("Catthew terminal listening on loopback", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        state.close()
        instance.close()


if __name__ == "__main__":
    main()
