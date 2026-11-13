"""Shared groceries and explicit event lifecycle use real temporary vault notes."""
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from zoneinfo import ZoneInfo

import yaml

from hub.household import Household, ScopeError, _exchange, _parse

NOW = datetime(2026, 11, 12, 12, tzinfo=ZoneInfo("America/Vancouver"))


class GroceryEventTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.vault = Path(self.tmp.name) / "vault"
        (self.vault / "Tasks/tasks").mkdir(parents=True)
        self.calendar_calls = []
        calendar = SimpleNamespace(create_event=lambda *a: self.calendar_calls.append(a))
        self.h = Household(self.vault, calendar, Path(self.tmp.name) / "state")

    def tearDown(self):
        self.tmp.cleanup()

    def note(self, name, meta):
        path = self.vault / "Tasks/tasks" / name
        path.write_text("---\n" + yaml.safe_dump({"tags": ["catthew"], "type": "task", "status": "pending", **meta}) + "---\n# " + name + "\n\n- [ ] " + name + "\n")
        return path

    def test_only_explicit_finished_one_time_events_are_completed(self):
        event = self.note("closure.md", {"kind": "event", "due_date": "2026-11-11", "allDay": True})
        ordinary = self.note("ordinary.md", {"due_date": "2026-11-11", "allDay": True, "google_event_id": "linked-calendar-task"})
        recurring = self.note("recurring.md", {"kind": "event", "due_date": "2026-11-11", "allDay": True, "recurrence": "weekly"})
        today = self.note("today.md", {"kind": "event", "due_date": "2026-11-12", "allDay": True})
        invalid = self.note("invalid.md", {"kind": "event", "due_date": "2026-02-30", "allDay": True})
        before = {p: p.read_bytes() for p in (ordinary, recurring, today, invalid)}
        self.h.complete_past_events(now=NOW)
        meta, body = _parse(event.read_bytes())
        self.assertEqual(meta["status"], "completed")
        self.assertIn("- [x] closure.md", body)
        self.assertTrue(all(p.read_bytes() == raw for p, raw in before.items()))
        self.assertEqual(self.calendar_calls, [])
        completed = event.read_bytes()
        self.h.complete_past_events(now=NOW)
        self.assertEqual(event.read_bytes(), completed)

    def test_timed_event_waits_for_explicit_end_and_preserves_type_and_due_date(self):
        finished = self.note("finished.md", {"kind": "event", "due_date": "2026-11-12", "event_end": NOW.replace(hour=11, minute=59).isoformat()})
        ongoing = self.note("ongoing.md", {"kind": "event", "due_date": "2026-11-12", "event_end": NOW.replace(hour=13).isoformat()})
        unknown = self.note("unknown.md", {"kind": "event", "due_date": "2026-11-11"})
        invalid_end = self.note("date-only-end.md", {"kind": "event", "due_date": "2026-11-12", "event_end": "2026-11-12"})
        self.h.complete_past_events(now=NOW)
        meta, _ = _parse(finished.read_bytes())
        self.assertEqual((meta["type"], meta["due_date"], meta["status"]), ("task", "2026-11-12", "completed"))
        self.assertEqual(_parse(ongoing.read_bytes())[0]["status"], "pending")
        self.assertEqual(_parse(unknown.read_bytes())[0]["status"], "pending")
        self.assertEqual(_parse(invalid_end.read_bytes())[0]["status"], "pending")

    def test_groceries_share_one_checklist_and_never_resurrect_cancelled_old_list(self):
        old = self.note("grocery-list.md", {"tags": ["catthew", "grocery"], "status": "cancelled"})
        before = old.read_bytes()
        self.assertEqual(self.h.groceries()["items"], [])
        first = self.h.add_grocery("voice-1", "Milk (2 litres)")
        again = self.h.add_grocery("voice-1", "Milk (2 litres)")
        self.assertEqual(first["item"]["id"], again["item"]["id"])
        self.assertEqual(first["revision"], again["revision"])
        self.assertEqual(len(self.h.groceries()["items"]), 1)
        self.assertEqual(old.read_bytes(), before)
        self.assertFalse(any(t["title"] == "Grocery Shopping" for t in self.h.tasks()))
        self.assertEqual(self.calendar_calls, [])

    def test_grocery_update_checks_revision_and_retry_does_not_reopen_purchase(self):
        added = self.h.add_grocery("voice-1", "Milk")
        changed = self.h.update_grocery(added["item"]["id"], added["revision"], item="Milk (2 litres)")
        with self.assertRaises(ScopeError):
            self.h.update_grocery(added["item"]["id"], added["revision"], state="purchased")
        bought = self.h.update_grocery(changed["item"]["id"], changed["revision"], state="purchased")
        self.assertEqual(bought["item"]["state"], "purchased")
        # Reusing an operation after its text was edited must not create/reopen it.
        with self.assertRaises(ScopeError):
            self.h.add_grocery("voice-1", "Milk")
        self.assertEqual(self.h.groceries()["items"][0]["state"], "purchased")

    def test_retry_of_unchanged_purchased_item_stays_purchased(self):
        added = self.h.add_grocery("voice-1", "Eggs")
        self.h.update_grocery(added["item"]["id"], added["revision"], state="purchased")
        result = self.h.add_grocery("voice-1", "Eggs")
        self.assertEqual(result["item"]["state"], "purchased")
        self.assertEqual(len(self.h.groceries()["items"]), 1)

    def test_grocery_paths_and_text_cannot_expand_write_scope(self):
        for text in ("", "Milk\n- [ ] Surprise", "Milk <!-- catthew-grocery:123 -->"):
            with self.assertRaises(ValueError):
                self.h.add_grocery("voice-1", text)
        outside = Path(self.tmp.name) / "outside.md"
        outside.write_text("private")
        (self.vault / "Tasks/tasks/grocery-shopping.md").symlink_to(outside)
        with self.assertRaises(ScopeError):
            self.h.add_grocery("voice-1", "Milk")
        self.assertEqual(outside.read_text(), "private")

    def test_grocery_mcp_add_read_and_check_use_the_same_file(self):
        from hub.approvals import ApprovalStore
        from hub.household_mcp import HouseholdTools
        from hub.journal import Journal
        journal = Journal(Path(self.tmp.name) / "requests.sqlite3")
        approvals = ApprovalStore(Path(self.tmp.name) / "approvals.sqlite3")
        try:
            tools = HouseholdTools(self.h, approvals, journal)
            names = {tool["name"] for tool in tools.handle({"id": 1, "method": "tools/list"})["result"]["tools"]}
            self.assertTrue({"household_grocery_read", "household_grocery_add", "household_grocery_update"} <= names)
            added = tools.call("household_grocery_add", {"operation_id": "spoken-milk", "item": "Milk (2 litres)"})
            read = tools.call("household_grocery_read", {})
            self.assertEqual(read["items"], [added["item"]])
            bought = tools.call("household_grocery_update", {"id": added["item"]["id"], "revision": read["revision"], "state": "purchased"})
            self.assertEqual(bought["item"]["state"], "purchased")
            self.assertEqual(self.h.groceries()["items"][0]["state"], "purchased")
            for arguments in ({"operation_id": "other", "item": "Eggs", "path": "/private"},
                              {"operation_id": "other", "item": 12}):
                with self.assertRaises(ValueError):
                    tools.call("household_grocery_add", arguments)
        finally:
            approvals.close()
            journal.close()

    def test_duplicate_grocery_ids_fail_without_discarding_items(self):
        added = self.h.add_grocery("one", "Milk")
        path = self.vault / "Tasks/tasks/grocery-shopping.md"
        raw = path.read_bytes()
        path.write_bytes(raw + raw.split(b"---", 2)[-1])
        with self.assertRaises(ScopeError):
            self.h.groceries()
        self.assertEqual(path.read_bytes(), raw + raw.split(b"---", 2)[-1])

    def test_full_list_refuses_an_extra_item_without_truncation(self):
        for i in range(100):
            self.h.add_grocery(f"item-{i}", f"Grocery {i}")
        path = self.vault / "Tasks/tasks/grocery-shopping.md"
        before = path.read_bytes()
        with self.assertRaises(ScopeError):
            self.h.add_grocery("item-101", "Extra item")
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(len(self.h.groceries()["items"]), 100)

    def test_markdown_examples_and_comments_are_not_grocery_items(self):
        self.h.add_grocery("real", "Real milk")
        path = self.vault / "Tasks/tasks/grocery-shopping.md"
        path.write_text(path.read_text() + "\n<!-- archived example\n- [ ] Hidden milk\n-->\n\n```markdown\n- [ ] Example eggs\n```\n")
        self.assertEqual([item["item"] for item in self.h.groceries()["items"]], ["Real milk"])

    def test_unclosed_markdown_boundaries_cannot_hide_a_successful_addition(self):
        self.h.add_grocery("real", "Milk")
        path = self.vault / "Tasks/tasks/grocery-shopping.md"
        original = path.read_bytes()
        for tail in (b"\n<!-- open comment\n", b"\n```markdown\n"):
            with self.subTest(tail=tail):
                path.write_bytes(original + tail)
                before = path.read_bytes()
                with self.assertRaises(ScopeError):
                    self.h.add_grocery("new-item", "Eggs")
                self.assertEqual(path.read_bytes(), before)

    def test_grocery_body_tags_do_not_authorize_a_mismatched_header(self):
        self.h.add_grocery("real", "Milk")
        path = self.vault / "Tasks/tasks/grocery-shopping.md"
        meta, body = _parse(path.read_bytes())
        meta["tags"] = ["other-workflow"]
        path.write_text("---\n" + yaml.safe_dump(meta) + "---\n" + body + "\n#catthew #grocery\n")
        with self.assertRaises(ScopeError):
            self.h.add_grocery("new-item", "Eggs")

    def test_grocery_growth_never_publishes_an_unreadable_oversized_note(self):
        self.h.add_grocery("real", "Milk")
        path = self.vault / "Tasks/tasks/grocery-shopping.md"
        before = path.read_bytes()
        path.write_bytes(before + b"\n" + b"a" * (256 * 1024 - len(before) - 12))
        original = path.read_bytes()
        with self.assertRaises(ScopeError):
            self.h.add_grocery("new-item", "Eggs")
        self.assertEqual(path.read_bytes(), original)

    def test_racing_grocery_writer_is_preserved_and_update_conflicts(self):
        item = self.h.add_grocery("voice-1", "Milk")
        path = self.vault / "Tasks/tasks/grocery-shopping.md"
        original = path.read_bytes()
        calls = []

        def race(first, second):
            if not calls:
                path.write_bytes(original + b"\nHuman shopping note\n")
            calls.append(True)
            _exchange(first, second)

        with patch("hub.household._exchange", side_effect=race):
            with self.assertRaises(ScopeError):
                self.h.update_grocery(item["item"]["id"], item["revision"], state="purchased")
        self.assertIn("Human shopping note", path.read_text())
        self.assertEqual(self.h.groceries()["items"][0]["state"], "needed")


if __name__ == "__main__":
    unittest.main()
