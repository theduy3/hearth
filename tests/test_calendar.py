from __future__ import annotations

import unittest
from types import SimpleNamespace

from hub.calendar import CalendarConflict, FamilyCalendar


class Request:
    def __init__(self, result=None, error=None):
        self.headers = {}
        self.result = result
        self.error = error

    def execute(self):
        if self.error:
            raise self.error
        return self.result


class Service:
    def __init__(self):
        self.calls = []
        self.items = {}
        self.last_request = None

    def events(self):
        return self

    def insert(self, **kwargs):
        self.calls.append(("insert", kwargs))
        body = kwargs["body"]
        if body["id"] in self.items:
            error = RuntimeError("duplicate")
            error.resp = SimpleNamespace(status=409)
            return Request(error=error)
        self.items[body["id"]] = body
        return Request(body)

    def get(self, **kwargs):
        self.calls.append(("get", kwargs))
        return Request(self.items[kwargs["eventId"]])

    def patch(self, **kwargs):
        self.calls.append(("patch", kwargs))
        self.last_request = Request({"id": kwargs["eventId"]})
        return self.last_request

    def delete(self, **kwargs):
        self.calls.append(("delete", kwargs))
        self.last_request = Request({})
        return self.last_request

    def list(self, **kwargs):
        self.calls.append(("list", kwargs))
        return Request({"items": list(self.items.values())})


class CalendarTests(unittest.TestCase):
    def setUp(self):
        self.service = Service()
        self.calendar = FamilyCalendar("fixed-family-calendar", self.service)

    def test_every_operation_uses_only_the_configured_calendar(self):
        self.calendar.create_event("abcde12345", "Family event", "2026-11-13", "2026-11-14")
        self.calendar.list_events("2026-11-13T00:00:00-08:00", "2026-11-14T00:00:00-08:00")
        self.calendar.edit_event("abcde12345", '"rev1"', "Updated", "2026-11-13", "2026-11-14")
        self.assertEqual(self.service.last_request.headers["If-Match"], '"rev1"')
        self.calendar.delete_event("abcde12345", '"rev2"')
        self.assertEqual(self.service.last_request.headers["If-Match"], '"rev2"')
        self.assertTrue(all(args["calendarId"] == "fixed-family-calendar" for _, args in self.service.calls))

    def test_duplicate_creation_reconciles_instead_of_creating_another_event(self):
        first = self.calendar.create_event("abcde12345", "Family", "2026-11-13", "2026-11-14")
        again = self.calendar.create_event("abcde12345", "Family", "2026-11-13", "2026-11-14")
        self.assertEqual(first, again)
        self.assertEqual(len(self.service.items), 1)
        with self.assertRaises(CalendarConflict):
            self.calendar.create_event("abcde12345", "Different", "2026-11-13", "2026-11-14")

    def test_cancelled_event_is_never_silently_recreated(self):
        self.calendar.create_event("abcde12345", "Family", "2026-11-13", "2026-11-14")
        self.service.items["abcde12345"]["status"] = "cancelled"
        with self.assertRaises(CalendarConflict):
            self.calendar.create_event("abcde12345", "Family", "2026-11-13", "2026-11-14")

    def test_primary_calendar_naive_times_and_mixed_time_types_are_rejected(self):
        with self.assertRaises(ValueError):
            FamilyCalendar("primary", self.service)
        for start, end in [("2026-11-13", "2026-11-13"),
                           ("2026-11-13", "2026-11-14T00:00:00-08:00"),
                           ("2026-11-13T08:00:00", "2026-11-13T09:00:00")]:
            with self.assertRaises(ValueError):
                self.calendar.create_event("abcde12345", "Family", start, end)

    def test_wildcard_and_etag_lists_cannot_bypass_reviewed_revision(self):
        for etag in ("*", '"one", "two"', "not-quoted"):
            with self.assertRaises(ValueError):
                self.calendar.delete_event("abcde12345", etag)
            with self.assertRaises(ValueError):
                self.calendar.edit_event("abcde12345", etag, "Family", "2026-11-13", "2026-11-14")

    def test_explicit_event_id_must_fit_google_base32hex_rules(self):
        with self.assertRaises(ValueError):
            self.calendar.create_event("../../other", "Family", "2026-11-13", "2026-11-14")


if __name__ == "__main__":
    unittest.main()
