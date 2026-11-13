import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from hub.approvals import ApprovalStore
from hub.journal import Journal
from hub.terminal import TerminalState, make_server
from hub.wavutil import wrap_pcm16


class TerminalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        state_path = Path(self.tmp.name)
        self.journal = Journal(state_path / "requests.sqlite3")
        self.approvals = ApprovalStore(state_path / "approvals.sqlite3")
        self.agent_calls = []
        self.deletions = []
        self.notifications = []

        def turn(text, session, device, **kwargs):
            self.agent_calls.append(text)
            kwargs["on_run"]("run-1")
            return "Task added."

        self.household = SimpleNamespace(
            tasks=lambda: [{"id": "task", "title": "Family task", "status": "open"}],
            reference_notes=lambda: [],
            complete_past_events=lambda **kw: [],
            groceries=lambda: {"items": [], "revision": ""},
            calendar=SimpleNamespace(list_events=lambda *a: [], delete_event=lambda **kw: self.deletions.append(kw), edit_event=lambda **kw: self.deletions.append(kw)))
        self.speech = SimpleNamespace(transcribe=lambda data: "Add milk", synthesize=lambda text: wrap_pcm16(b"\0\0" * 800))
        self.state = TerminalState(self.journal, self.approvals, self.household, SimpleNamespace(turn=turn), self.speech,
                                   token="d" * 48, origin="https://zectrix.theduy.cloud", notify=self.notifications.append)
        self.httpd = make_server("127.0.0.1", 0, self.state)
        self.base = f"http://127.0.0.1:{self.httpd.server_port}"
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.state.close()
        self.journal.close()
        self.approvals.close()
        self.tmp.cleanup()

    def request(self, path, *, data=None, headers=None, authenticated=True):
        h = {"Authorization": "Bearer " + "d" * 48} if authenticated else {}
        h.update(headers or {})
        return urlopen(Request(self.base + path, data=data, headers=h), timeout=3)

    def test_unauthorized_clients_cannot_read_or_submit_household_data(self):
        for path, data in [("/v1/poster", None), ("/v1/frame", None), ("/v1/device", None), ("/v1/utterance", b"bad")]:
            with self.assertRaises(HTTPError) as caught:
                self.request(path, data=data, authenticated=False)
            self.assertEqual(caught.exception.code, 401)
            caught.exception.close()
        self.assertEqual(self.agent_calls, [])

    def test_frame_transport_is_exact_and_unchanged_frames_have_no_body(self):
        with self.request("/v1/frame?page=today") as response:
            self.assertEqual(len(response.read()), 30000)
            self.assertEqual(response.headers["Content-Type"], "application/vnd.catthew.bwry2")
            self.assertEqual(response.headers["X-Hearth-Page"], "today")
            self.assertEqual(response.headers["X-Hearth-Next"], "groceries")
            self.assertEqual(response.headers["X-Hearth-Previous"], "groceries")
            self.assertEqual(response.headers["X-Hearth-Pages"], "2")
            etag = response.headers["ETag"]
        with self.request("/v1/frame?page=groceries") as response:
            self.assertEqual(response.headers["X-Hearth-Page"], "groceries")
            self.assertEqual(response.headers["X-Hearth-Next"], "today")
            self.assertEqual(response.headers["X-Hearth-Previous"], "today")
            self.assertEqual(response.headers["X-Hearth-Pages"], "2")
        with self.assertRaises(HTTPError) as caught:
            self.request("/v1/frame?page=today", headers={"If-None-Match": etag})
        self.assertEqual(caught.exception.code, 304)
        self.assertEqual(caught.exception.read(), b"")
        caught.exception.close()
        with self.request("/v1/device") as response:
            status = json.load(response)
        self.assertEqual(status, {"request": None})
        self.assertEqual(self.agent_calls, [])

    def test_projection_cache_survives_restart_during_calendar_outage(self):
        self.household.calendar.list_events = lambda *a: [{"id": "saved", "summary": "Family event"}]
        self.state.refresh()
        self.httpd.shutdown()
        self.state.close()
        self.household.calendar.list_events = lambda *a: (_ for _ in ()).throw(RuntimeError("unavailable"))
        restarted = TerminalState(self.journal, self.approvals, self.household, self.state.gateway, self.speech,
                                  token="d" * 48, origin=self.state.origin)
        try:
            self.assertEqual(restarted.poster()["events"][0]["summary"], "Family event")
            self.assertTrue(restarted.poster()["stale"])
            self.assertEqual(restarted.cache_path.stat().st_mode & 0o077, 0)
        finally:
            restarted.close()

    def test_voice_request_deduplication_reply_audio_and_delivery_ack(self):
        headers = {"Content-Type": "audio/wav", "X-Hearth-Request-Id": "upload-1"}
        body = wrap_pcm16(b"\0\0" * 1600)
        with self.request("/v1/utterance", data=body, headers=headers) as response:
            accepted = json.load(response)
        with self.request("/v1/utterance", data=body, headers=headers) as response:
            self.assertEqual(json.load(response)["request_id"], accepted["request_id"])
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            result = self.journal.get("note4c", accepted["request_id"])
            if result["speech_status"] == "ready":
                break
            time.sleep(0.01)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(len(self.agent_calls), 1)
        self.assertEqual(result["reply"], "Task added.")
        with self.request(f"/v1/requests/{result['id']}/audio") as response:
            self.assertEqual(response.read()[:4], b"RIFF")
        with self.request(f"/v1/requests/{result['id']}/audio-ack", data=b"{}") as response:
            self.assertTrue(json.load(response)["ok"])
        self.assertIsNone(self.journal.audio("note4c", result["id"]))

    def test_approval_link_get_has_no_effect_and_post_is_scoped_single_use(self):
        proposal = self.approvals.propose("proposal", "delete", {"event_id": "event-1", "etag": '"v1"'}, {"summary": "Family event"})
        self.state.dispatch_notifications()
        capability = self.notifications[0].rsplit("#", 1)[1]
        headers = {"Origin": self.state.origin}
        with self.request("/approval/", authenticated=False) as response:
            self.assertNotIn(capability, response.read().decode())
            self.assertEqual(response.headers["Referrer-Policy"], "no-referrer")
        with self.request("/approval/view", data=("capability=" + capability).encode(), authenticated=False, headers=headers) as response:
            self.assertIn("Family event", response.read().decode())
        self.assertEqual(self.deletions, [])
        body = ("capability=" + capability + "&decision=allow").encode()
        with self.assertRaises(HTTPError) as caught:
            self.request("/approval/confirm", data=body, authenticated=False, headers={"Origin": "https://other.example"})
        self.assertEqual(caught.exception.code, 403)
        caught.exception.close()
        with self.request("/approval/confirm", data=body, authenticated=False, headers=headers) as response:
            self.assertEqual(response.status, 200)
        self.assertEqual(self.deletions, [{"event_id": "event-1", "etag": '"v1"'}])
        with self.assertRaises(HTTPError) as caught:
            self.request("/approval/confirm", data=body, authenticated=False, headers=headers)
        self.assertEqual(caught.exception.code, 410)
        caught.exception.close()

    def test_calendar_failure_preserves_last_good_projection_and_marks_stale(self):
        self.state.refresh()
        self.household.calendar.list_events = lambda *a: (_ for _ in ()).throw(RuntimeError("private provider error"))
        self.state.refresh()
        with self.request("/v1/poster") as response:
            poster = json.load(response)
        self.assertTrue(poster["stale"])
        self.assertEqual(poster["tasks"][0]["title"], "Family task")
        self.assertNotIn("private provider error", str(poster))


if __name__ == "__main__":
    unittest.main()
