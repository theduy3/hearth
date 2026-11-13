import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from hub.approvals import ApprovalStore
from hub.household_mcp import HouseholdTools
from hub.journal import Journal


class MCPBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.approvals = ApprovalStore(Path(self.tmp.name) / "approvals.sqlite3")
        self.calls = []
        calendar = SimpleNamespace(
            list_events=lambda *a: [],
            get_event=lambda event_id: {"id": event_id, "etag": '"revision"', "summary": "Family event"},
            create_event=lambda *a: self.calls.append(a) or {"id": "event"},
            edit_event=lambda **kw: self.calls.append(kw) or {"id": "event"},
            delete_event=lambda **kw: self.calls.append(kw) or {"ok": True},
        )
        self.household = SimpleNamespace(calendar=calendar, tasks=lambda: [], search_notes=lambda q: [])
        self.journal = Journal(Path(self.tmp.name) / "requests.sqlite3")
        self.safe = HouseholdTools(self.household, self.approvals, self.journal)

    def tearDown(self):
        self.approvals.close()
        self.journal.close()
        self.tmp.cleanup()

    def test_page_tool_requires_an_active_voice_request_and_does_not_mutate_household(self):
        request = self.journal.accept("note4c", "voice", b"wav")
        self.journal.claim()
        self.journal.begin_agent(request["id"], "show today's tasks")
        result = self.safe.call("note4c_show_page", {"request_id": request["id"], "page": "today"})
        self.assertEqual(result, {"ok": True, "page": "today"})
        self.assertEqual(self.calls, [])
        with self.assertRaises(ValueError):
            self.safe.call("note4c_show_page", {"request_id": request["id"], "page": "reply:0"})
        self.journal.complete(request["id"], "Your tasks are ready.")
        self.assertEqual(self.journal.page(request["id"]), "today")

    def test_model_cannot_directly_edit_delete_or_approve(self):
        for name in ("household_edit_event", "household_delete_event", "household_apply", "approve", "terminal", "read_file"):
            with self.assertRaises(ValueError):
                self.safe.call(name, {})
        self.assertEqual(self.calls, [])

    def test_proposals_preserve_exact_payload_without_changing_the_calendar(self):
        args = {"operation_id": "operation", "event_id": "event", "etag": '"revision"'}
        result = self.safe.call("household_propose_event_delete", args)
        self.assertEqual(result["status"], "pending")
        self.assertEqual(self.calls, [])
        self.assertNotIn("capability", result)
        stored = self.approvals.get(result["proposal_id"])
        self.assertEqual(stored["payload"], {"event_id": "event", "etag": '"revision"'})
        self.assertEqual(stored["preview"]["summary"], "Family event")

    def test_stale_proposals_are_rejected_before_notification(self):
        with self.assertRaises(ValueError):
            self.safe.call("household_propose_event_delete", {"operation_id": "id", "event_id": "event", "etag": '"old"'})
        self.assertEqual(self.approvals.pending(), [])

    def test_model_cannot_supply_calendar_paths_or_approval_flags(self):
        for key in ("calendar_id", "path", "approved"):
            with self.assertRaises(ValueError):
                self.safe.call("household_read", {key: "anything"})
        self.assertEqual(self.calls, [])

    def test_rpc_errors_do_not_leak_exception_content_or_claim_success(self):
        self.household.tasks = lambda: (_ for _ in ()).throw(RuntimeError("private diagnostics"))
        result = self.safe.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "household_read"}})
        self.assertTrue(result["result"]["isError"])
        self.assertNotIn("private diagnostics", str(result))

    def test_rpc_notifications_do_not_generate_responses(self):
        self.assertIsNone(self.safe.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}))


if __name__ == "__main__":
    unittest.main()
