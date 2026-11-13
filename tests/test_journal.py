"""Durable terminal requests must not replay household actions after a crash."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from hub.journal import Journal, RequestConflict, QueueFull


class JournalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "requests.sqlite3"
        self.journal = Journal(self.path, capacity=2)

    def tearDown(self):
        self.journal.close()
        self.tmp.cleanup()

    def test_upload_retry_returns_same_request_after_reopen(self):
        first = self.journal.accept("kitchen", "upload-1", b"wav")
        session = self.journal.session("kitchen")
        self.journal.close()
        self.journal = Journal(self.path, capacity=2)
        again = self.journal.accept("kitchen", "upload-1", b"wav")
        self.assertEqual(first["id"], again["id"])
        self.assertEqual(session, self.journal.session("kitchen"))
        self.assertEqual(self.journal.depth(), 1)

    def test_reusing_upload_id_with_different_content_is_a_conflict(self):
        self.journal.accept("kitchen", "id", b"one")
        with self.assertRaises(RequestConflict):
            self.journal.accept("kitchen", "id", b"two")

    def test_device_boundaries_and_bounded_queue(self):
        first = self.journal.accept("a", "id", b"one")
        self.journal.accept("b", "id", b"two")
        self.assertIsNone(self.journal.get("b", first["id"]))
        with self.assertRaises(QueueFull):
            self.journal.accept("a", "next", b"three")
        # An existing request remains retryable while the queue is full.
        self.assertEqual(first["id"], self.journal.accept("a", "id", b"one")["id"])

    def test_crash_recovery_does_not_replay_agent_turn(self):
        request = self.journal.accept("a", "id", b"wav")
        self.journal.claim()
        self.journal.begin_agent(request["id"], "hello")
        self.journal.set_run(request["id"], "run-123")
        self.journal.close()
        self.journal = Journal(self.path)
        self.journal.recover()
        stored = self.journal.get("a", request["id"])
        self.assertEqual(stored["status"], "uncertain")
        self.assertEqual(stored["run_id"], "run-123")
        self.assertIsNone(self.journal.claim())
        self.assertIsNone(self.journal.audio("a", request["id"]))

    def test_transcription_crash_is_safe_to_resume(self):
        request = self.journal.accept("a", "id", b"wav")
        self.assertEqual(self.journal.claim()["wav"], b"wav")
        self.journal.recover()
        self.assertEqual(self.journal.claim()["id"], request["id"])

    def test_completed_reply_and_audio_survive_tts_failure_without_retry(self):
        request = self.journal.accept("a", "id", b"wav")
        self.journal.claim()
        self.journal.begin_agent(request["id"], "task")
        self.journal.complete(request["id"], "Task added.")
        self.journal.speech_failed(request["id"])
        stored = self.journal.get("a", request["id"])
        self.assertEqual(stored["status"], "completed")
        self.assertEqual(stored["reply"], "Task added.")
        self.assertEqual(stored["speech_status"], "failed")
        self.assertIsNone(self.journal.claim())
        self.journal.set_audio(request["id"], b"reply-wav")
        self.assertEqual(self.journal.audio("a", request["id"]), b"reply-wav")
        self.assertIsNone(self.journal.audio("other", request["id"]))
        # Raw microphone data is deleted before the agent is invoked.
        self.assertIsNone(stored.get("wav"))

    def test_completed_microphone_data_is_erased_from_database_and_sidecars(self):
        marker = b"unique-private-microphone-test-marker"
        request = self.journal.accept("a", "id", marker)
        self.journal.claim()
        self.journal.begin_agent(request["id"], "private-transcript-test-marker")
        self.journal.complete(request["id"], "Done")
        for path in Path(self.tmp.name).glob("requests.sqlite3*"):
            self.assertFalse(marker in path.read_bytes(), path.name)
            self.assertFalse(b"private-transcript-test-marker" in path.read_bytes(), path.name)

    def test_history_capacity_is_bounded_without_forgetting_dedupe(self):
        self.journal.close()
        self.journal = Journal(self.path, history_capacity=2)
        for i in range(2):
            request = self.journal.accept("a", str(i), b"wav")
            self.journal.claim()
            self.journal.begin_agent(request["id"], "hello")
            self.journal.complete(request["id"], "Done")
        self.journal.expire(now=10**12)
        with self.assertRaises(QueueFull):
            self.journal.accept("a", "new", b"wav")
        old = self.journal.accept("a", "0", b"wav")
        self.assertEqual(old["status"], "completed")
        self.assertEqual(old["reply"], "")

    def test_session_registration_is_bounded_but_existing_devices_remain_available(self):
        self.journal.close()
        self.journal = Journal(self.path, device_capacity=1)
        session = self.journal.session("a")
        with self.assertRaises(QueueFull):
            self.journal.session("b")
        self.assertEqual(self.journal.session("a"), session)
        with self.assertRaises(ValueError):
            self.journal.session("x" * 129)

    def test_delivery_cannot_be_acknowledged_early_or_resurrected_after_ack(self):
        request = self.journal.accept("a", "id", b"wav")
        self.journal.claim()
        self.journal.begin_agent(request["id"], "hello")
        self.journal.complete(request["id"], "Done")
        self.assertFalse(self.journal.clear_audio("a", request["id"]))
        self.journal.set_audio(request["id"], b"first")
        self.assertTrue(self.journal.clear_audio("a", request["id"]))
        self.journal.set_audio(request["id"], b"late synthesis")
        self.journal.speech_failed(request["id"])
        self.assertIsNone(self.journal.audio("a", request["id"]))
        self.assertEqual(self.journal.get("a", request["id"])["speech_status"], "delivered")

    def test_audio_cache_is_bounded_without_forgetting_completed_requests(self):
        self.journal.close()
        self.journal = Journal(self.path, reply_audio_capacity=8)
        records = []
        for index in range(2):
            row = self.journal.accept("a", str(index), b"wav")
            self.journal.claim()
            self.journal.begin_agent(row["id"], "hello")
            self.journal.complete(row["id"], "Done")
            self.journal.set_audio(row["id"], b"12345")
            records.append(row)
        old = self.journal.get("a", records[0]["id"])
        self.assertEqual(old["status"], "completed")
        self.assertEqual(old["speech_status"], "expired")
        self.assertEqual(old["reply"], "Done")
        self.assertIsNone(self.journal.audio("a", old["id"]))
        self.assertEqual(self.journal.accept("a", "0", b"wav")["id"], old["id"])

    def test_expired_raw_audio_is_never_processed(self):
        request = self.journal.accept("a", "id", b"wav", now=1)
        self.journal.expire(now=86402)
        self.assertIsNone(self.journal.claim())
        self.assertEqual(self.journal.get("a", request["id"])["status"], "failed")


if __name__ == "__main__":
    unittest.main()
