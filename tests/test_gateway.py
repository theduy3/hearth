"""Exercise the installed Hermes gateway wire contract with a loopback server."""
from __future__ import annotations

import json
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from hub.gateway import Gateway, GatewayError


def frame(payload, event=None):
    data = payload if isinstance(payload, str) else json.dumps(payload)
    return ((f"event: {event}\n" if event else "") + f"data: {data}\n\n").encode()


def chunk(content=None, finish=None):
    return {"id": "chatcmpl-test", "choices": [{"delta": {"content": content} if content else {}, "finish_reason": finish}]}


class GatewayTests(unittest.TestCase):
    def setUp(self):
        self.requests = []
        self.frames = frame(chunk("Catthew says hello.")) + frame(chunk(finish="stop")) + frame("[DONE]")
        self.status = 200
        self.redirect = False
        self.drip = 0
        self.policy = {"data": [{"name": "stt", "enabled": True, "tools": []}]}
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                if self.path.endswith("/v1/toolsets"):
                    payload = json.dumps(owner.policy).encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)
                    return
                owner.requests.append((self.path, dict(self.headers), None))
                self.send_response(200)
                self.end_headers()

            def do_POST(self):
                body = self.rfile.read(int(self.headers["Content-Length"]))
                owner.requests.append((self.path, dict(self.headers), json.loads(body)))
                self.send_response(owner.status)
                if owner.redirect:
                    self.send_header("Location", f"http://localhost:{owner.server.server_port}/stolen")
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Content-Length", str(len(owner.frames)))
                self.end_headers()
                try:
                    if owner.drip:
                        for value in owner.frames:
                            self.wfile.write(bytes([value]))
                            self.wfile.flush()
                            time.sleep(owner.drip)
                    else:
                        self.wfile.write(owner.frames)
                except (BrokenPipeError, ConnectionResetError):
                    pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.client = Gateway(f"http://127.0.0.1:{self.server.server_port}", "secret-for-test-only")

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def test_routes_to_catthew_without_replacing_soul_and_preserves_session(self):
        runs = []
        reply = self.client.turn("hello", "hearth-session", "kitchen", on_run=runs.append)
        self.assertEqual(reply, "Catthew says hello.")
        path, raw_headers, body = self.requests[0]
        headers = {key.lower(): value for key, value in raw_headers.items()}
        self.assertEqual(path, "/p/catthew/v1/chat/completions")
        self.assertEqual(headers["authorization"], "Bearer secret-for-test-only")
        self.assertEqual(headers["x-hermes-session-id"], "hearth-session")
        self.assertEqual(headers["x-hermes-session-key"], "hearth:note4c:kitchen")
        self.assertEqual(body, {"messages": [{"role": "user", "content": "hello"}], "stream": True})
        self.assertEqual(runs, ["chatcmpl-test"])

    def test_lost_stream_is_uncertain_and_never_retried(self):
        self.frames = frame(chunk("Task added"))
        with self.assertRaises(GatewayError) as caught:
            self.client.turn("add task", "session", "kitchen")
        self.assertTrue(caught.exception.uncertain)
        self.assertEqual(len(self.requests), 1)

    def test_partial_finish_does_not_claim_success(self):
        self.frames = frame(chunk("Maybe")) + frame(chunk(finish="error")) + frame("[DONE]")
        with self.assertRaises(GatewayError) as caught:
            self.client.turn("add task", "session", "kitchen")
        self.assertTrue(caught.exception.uncertain)

    def test_http_rejection_does_not_leak_body_or_credentials_or_retry(self):
        self.status = 429
        self.frames = b"secret provider diagnostics"
        with self.assertRaises(GatewayError) as caught:
            self.client.turn("hello", "session", "kitchen")
        self.assertFalse(caught.exception.uncertain)
        self.assertNotIn("secret", str(caught.exception))
        self.assertEqual(len(self.requests), 1)

    def test_redirect_is_rejected_without_forwarding_profile_credential(self):
        self.status = 302
        self.redirect = True
        with self.assertRaises(GatewayError):
            self.client.turn("hello", "session", "kitchen")
        self.assertEqual(len(self.requests), 1)

    def test_success_requires_a_gateway_run_identity(self):
        no_id = chunk("hello", finish="stop")
        del no_id["id"]
        self.frames = frame(no_id) + frame("[DONE]")
        with self.assertRaises(GatewayError):
            self.client.turn("hello", "session", "kitchen")

    def test_native_tool_leak_blocks_agent_turn_before_submission(self):
        self.policy = {"data": [{"name": "homeassistant", "enabled": True, "tools": ["ha_call_service"]}]}
        with self.assertRaises(GatewayError) as caught:
            self.client.turn("hello", "session", "kitchen")
        self.assertFalse(caught.exception.uncertain)
        self.assertEqual(self.requests, [])

    def test_zero_tool_stt_marker_is_allowed_but_future_native_stt_tool_is_blocked(self):
        self.policy = {"data": [{"name": "stt", "enabled": True, "tools": []}]}
        self.assertEqual(self.client.turn("hello", "session", "kitchen"), "Catthew says hello.")
        self.policy["data"][0]["tools"] = ["new_native_tool"]
        with self.assertRaises(GatewayError):
            self.client.turn("hello", "session", "kitchen")
        self.assertEqual(len(self.requests), 1)

    def test_error_completion_sentinel_is_still_an_error(self):
        self.frames = frame(chunk("Done", finish="stop")) + frame("[DONE]", "error")
        with self.assertRaises(GatewayError):
            self.client.turn("hello", "session", "kitchen")

    def test_gateway_requires_private_numeric_address_without_dns(self):
        from unittest.mock import patch
        with self.assertRaises(ValueError):
            Gateway("http://gateway.example", "secret-for-test-only")
        with patch("socket.getaddrinfo", side_effect=AssertionError("DNS must not be called")):
            self.assertEqual(self.client.turn("hello", "session", "kitchen"), "Catthew says hello.")

    def test_slow_drip_cannot_extend_the_total_turn_deadline(self):
        self.drip = 0.01
        self.client.timeout = 0.08
        started = time.monotonic()
        with self.assertRaises(GatewayError) as caught:
            self.client.turn("hello", "session", "kitchen")
        self.assertTrue(caught.exception.uncertain)
        self.assertLess(time.monotonic() - started, 0.5)

    def test_error_events_and_error_envelopes_cannot_follow_a_successful_stop(self):
        for error in [frame({"message": "failure"}, "error"), frame({"error": {"message": "failure"}})]:
            self.frames = frame(chunk("Task added", finish="stop")) + error + frame("[DONE]")
            with self.assertRaises(GatewayError) as caught:
                self.client.turn("add task", "session", "kitchen")
            self.assertTrue(caught.exception.uncertain)

    def test_approval_is_surfaced_and_never_automatically_accepted(self):
        approval = {"request_id": "approval-1", "choices": ["allow_once", "deny"]}
        self.frames = frame(chunk()) + frame(approval, "approval.request") + frame(chunk("Cancelled")) + frame(chunk(finish="stop")) + frame("[DONE]")
        seen = []
        self.client.turn("delete event", "session", "kitchen", on_approval=lambda run, event: seen.append((run, event)))
        self.assertEqual(seen, [("chatcmpl-test", approval)])
        self.assertEqual(len(self.requests), 1)

    def test_approval_without_handler_aborts_instead_of_hanging(self):
        self.frames = frame(chunk()) + frame({"request_id": "approval-1"}, "approval.request")
        with self.assertRaises(GatewayError) as caught:
            self.client.turn("delete", "session", "kitchen")
        self.assertTrue(caught.exception.uncertain)


if __name__ == "__main__":
    unittest.main()
