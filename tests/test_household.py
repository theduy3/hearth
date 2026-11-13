"""Household source boundaries: exact vault tags, stable IDs, and explicit calendar scope."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import yaml

from hub.household import Household, ScopeError


class FakeCalendar:
    def __init__(self):
        self.created = {}
        self.calendar_id = "family-test-calendar"
        self.reads = 0

    def list_events(self, start, end):
        self.reads += 1
        return [{"id": "event-1", "summary": "Family event", "start": {"date": "2026-11-13"}}]

    def create_event(self, event_id, title, start, end):
        self.created.setdefault(event_id, {"id": event_id, "summary": title, "start": start, "end": end})
        return self.created[event_id]


class HouseholdTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "vault"
        (self.root / "Tasks/tasks").mkdir(parents=True)
        (self.root / "Notes").mkdir()
        self.calendar = FakeCalendar()
        self.household = Household(self.root, self.calendar, Path(self.tmp.name) / "state")

    def tearDown(self):
        self.tmp.cleanup()

    def note(self, path, meta, body=""):
        f = self.root / path
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("---\n" + yaml.safe_dump(meta) + "---\n" + body)
        return f

    def test_only_catthew_tasks_are_projected_with_exact_tags(self):
        self.note("Tasks/tasks/a.md", {"title": "Family task", "tags": ["catthew"], "status": "open"})
        self.note("Tasks/tasks/b.md", {"title": "Other task", "tags": ["catthew-other"]})
        self.note("Tasks/tasks/c.md", {"title": "Unrelated"})
        self.note("Tasks/tasks/d.md", {"title": "Body tag"}, "#catthew\n")
        tasks = self.household.tasks()
        self.assertEqual({x["title"] for x in tasks}, {"Family task", "Body tag"})
        self.assertTrue(all(x["id"] and x["revision"] for x in tasks))

    def test_reference_search_excludes_other_notes_and_symlinks(self):
        self.note("Notes/family.md", {"tags": ["kittyggup"], "title": "Family guide"}, "Pack the raincoat.")
        self.note("Notes/private.md", {"tags": ["private"], "title": "Private"}, "Pack a secret.")
        outside = Path(self.tmp.name) / "outside.md"
        outside.write_text("---\ntags: [kittyggup]\n---\nPack outsider")
        (self.root / "Notes/link.md").symlink_to(outside)
        results = self.household.search_notes("pack")
        self.assertEqual(len(results), 1)
        self.assertIn("raincoat", results[0]["text"])

    def test_task_creation_retry_has_one_note_and_one_linked_event(self):
        first = self.household.create_task("upload-1", "Pack lunch", due="2026-11-13T08:00:00-08:00")
        again = self.household.create_task("upload-1", "Pack lunch", due="2026-11-13T08:00:00-08:00")
        self.assertEqual(first["id"], again["id"])
        self.assertEqual(len(self.household.tasks()), 1)
        self.assertEqual(len(self.calendar.created), 1)
        self.assertEqual(first["calendar_event_id"], again["calendar_event_id"])

    def test_same_operation_with_changed_task_is_rejected(self):
        self.household.create_task("id", "Pack lunch")
        with self.assertRaises(ScopeError):
            self.household.create_task("id", "Different task")

    def test_task_completion_requires_current_revision_and_correct_scope(self):
        task = self.household.create_task("id", "Pack lunch")
        with self.assertRaises(ScopeError):
            self.household.complete_task(task["id"], "stale")
        done = self.household.complete_task(task["id"], task["revision"])
        self.assertEqual(done["status"], "completed")
        with self.assertRaises(ScopeError):
            self.household.complete_task("../../private", "revision")

    def test_partial_calendar_failure_preserves_task_and_retry_reconciles(self):
        original = self.calendar.create_event
        self.calendar.create_event = lambda *args: (_ for _ in ()).throw(RuntimeError("temporary outage"))
        first = self.household.create_task("id", "Pack lunch", due="2026-11-13T08:00:00-08:00")
        self.assertFalse(first["ok"])
        self.assertTrue(first["task_saved"])
        self.assertEqual(len(self.household.tasks()), 1)
        self.calendar.create_event = original
        again = self.household.create_task("id", "Pack lunch", due="2026-11-13T08:00:00-08:00")
        self.assertTrue(again["ok"])
        self.assertEqual(len(self.household.tasks()), 1)
        self.assertEqual(len(self.calendar.created), 1)

    def test_date_only_task_uses_an_all_day_event_and_existing_link_fields(self):
        task = self.household.create_task("all-day", "Pack", due="2026-11-13")
        self.assertTrue(task["ok"])
        event = next(iter(self.calendar.created.values()))
        self.assertEqual(event["start"], "2026-11-13")
        self.assertEqual(event["end"], "2026-11-14")
        path = next((self.root / "Tasks/tasks").glob("*.md"))
        raw = path.read_text()
        self.assertIn("google_event_id:", raw)
        self.assertIn("google_calendar_id:", raw)

    def test_concurrent_task_edit_is_preserved_and_completion_conflicts(self):
        from unittest.mock import patch
        from hub.household import _exchange
        task = self.household.create_task("id", "Pack lunch")
        path = next((self.root / "Tasks/tasks").glob("*.md"))
        original = path.read_bytes()
        calls = []

        def race(first, second):
            if not calls:
                path.write_bytes(original + b"\nConcurrent family edit\n")
            calls.append(True)
            _exchange(first, second)

        with patch("hub.household._exchange", side_effect=race):
            with self.assertRaises(ScopeError):
                self.household.complete_task(task["id"], task["revision"])
        self.assertIn("Concurrent family edit", path.read_text())

    def test_reconciliation_refuses_a_task_changed_after_calendar_failure(self):
        self.calendar.create_event = lambda *a: (_ for _ in ()).throw(RuntimeError("offline"))
        self.household.create_task("id", "Pack", due="2026-11-13")
        path = next((self.root / "Tasks/tasks").glob("*.md"))
        path.write_text(path.read_text().replace("status: open", "status: completed"))
        with self.assertRaises(ScopeError):
            self.household.create_task("id", "Pack", due="2026-11-13")
        self.assertEqual(self.calendar.created, {})

    def test_human_date_typo_does_not_hide_a_tagged_task(self):
        path = self.root / "Tasks/tasks/typo.md"
        path.write_text("---\ntitle: Family task\ntags: [catthew]\ndue_date: 2026-02-30\nallDay: true\n---\nFamily task\n")
        tasks = self.household.tasks()
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["due"], "2026-02-30")
        self.household.complete_task(tasks[0]["id"], tasks[0]["revision"])
        self.assertIs(yaml.safe_load(path.read_text().split("---", 2)[1])["allDay"], True)

    def test_existing_catthew_bugs_and_ideas_remain_in_the_workflow(self):
        for name in ("bugs", "ideas"):
            directory = self.root / "Tasks" / name
            directory.mkdir()
            (directory / "item.md").write_text(f"---\nid: {name}\ntags: [catthew]\nstatus: open\ntype: {name}\n---\n# Family item\n")
        tasks = {task["id"]: task for task in self.household.tasks()}
        self.assertEqual(set(tasks), {"bugs", "ideas"})
        self.household.complete_task("bugs", tasks["bugs"]["revision"])
        self.assertEqual(next(task for task in self.household.tasks() if task["id"] == "bugs")["status"], "completed")

    def test_kittyggup_reference_scope_includes_all_vault_directories(self):
        (self.root / "Tasks/tasks/reference.md").write_text("---\ntitle: Shared reference\ntags: [kittyggup]\n---\nShared family information.\n")
        self.assertEqual(len(self.household.reference_notes()), 1)
        self.assertEqual(self.household.search_notes("information")[0]["title"], "Shared reference")
        self.assertEqual(self.household.tasks(), [])

    def test_due_time_requires_explicit_timezone(self):
        with self.assertRaises(ValueError):
            self.household.create_task("id", "Pack", due="2026-11-13T08:00:00")


if __name__ == "__main__":
    unittest.main()
