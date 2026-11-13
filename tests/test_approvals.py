import tempfile
import unittest
from pathlib import Path

from hub.approvals import ApprovalStore


class ApprovalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = ApprovalStore(Path(self.tmp.name) / "approvals.sqlite3")
        self.payload = {"event_id": "event", "etag": '"version"'}

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_proposal_has_no_approval_capability_until_private_notification(self):
        proposal = self.store.propose("operation", "delete", self.payload, {"summary": "Family event"})
        self.assertNotIn("capability", proposal)
        self.assertNotIn("nonce", proposal)
        capability = self.store.mint(proposal["id"], now=100)
        shown = self.store.view(capability, now=101)
        self.assertEqual(shown["payload"], self.payload)
        self.assertIsNone(self.store.view("invented", now=101))

    def test_approval_is_single_use_and_cannot_be_replayed(self):
        proposal = self.store.propose("operation", "delete", self.payload, {})
        capability = self.store.mint(proposal["id"], now=100)
        accepted = self.store.consume(capability, "allow", now=101)
        self.assertEqual(accepted["status"], "executing")
        self.assertIsNone(self.store.consume(capability, "allow", now=101))
        self.store.recover()
        self.assertEqual(self.store.get(proposal["id"])["status"], "uncertain")

    def test_expired_or_denied_proposals_never_execute(self):
        proposal = self.store.propose("operation", "delete", self.payload, {})
        capability = self.store.mint(proposal["id"], now=100)
        self.assertIsNone(self.store.consume(capability, "allow", now=701))
        capability = self.store.mint(proposal["id"], now=1000)
        self.assertEqual(self.store.consume(capability, "deny", now=1001)["status"], "denied")
        self.assertIsNone(self.store.consume(capability, "allow", now=1001))

    def test_restart_recovers_an_interrupted_notification_without_reusing_its_link(self):
        proposal = self.store.propose("operation", "delete", self.payload, {})
        unsent = self.store.mint(proposal["id"], now=100)
        self.store.recover()
        self.assertIsNone(self.store.view(unsent, now=101))
        self.assertFalse(self.store.pending()[0]["notified"])
        replacement = self.store.mint(proposal["id"], now=102)
        self.store.mark_notified(proposal["id"])
        self.store.recover()
        self.assertIsNotNone(self.store.view(replacement, now=103))

    def test_failed_notification_retries_without_restart_and_stops_at_limit(self):
        proposal = self.store.propose("operation", "delete", self.payload, {})
        for attempt in range(3):
            capability = self.store.mint(proposal["id"], now=100 + attempt)
            self.store.notification_failed(proposal["id"])
            self.assertIsNone(self.store.view(capability, now=101 + attempt))
            if attempt < 2:
                self.assertEqual(self.store.pending()[0]["id"], proposal["id"])
        self.assertEqual(self.store.get(proposal["id"])["status"], "failed")
        self.assertEqual(self.store.pending(), [])

    def test_operation_id_is_bound_to_exact_payload_and_etag(self):
        first = self.store.propose("operation", "delete", self.payload, {})
        self.assertEqual(first["id"], self.store.propose("operation", "delete", self.payload, {})["id"])
        with self.assertRaises(ValueError):
            self.store.propose("operation", "delete", {**self.payload, "etag": '"new"'}, {})
        with self.assertRaises(ValueError):
            self.store.propose("other", "delete", {**self.payload, "etag": "*"}, {})


if __name__ == "__main__":
    unittest.main()
