import copy
import hashlib
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from PIL import Image

from hub.frames import Renderer, pack_frame


NOW = datetime(2026, 11, 12, 10, 0, tzinfo=ZoneInfo("America/Vancouver"))


def fixture():
    return {"events": [], "tasks": [{"id": str(i), "title": "Family task " + str(i), "due": "2026-11-11" if i == 0 else "2026-11-12", "status": "open"} for i in range(9)],
            "notes": [{"id": "note", "title": "Gia đình", "text": "Chuẩn bị đồ dùng cho gia đình."}],
            "reply": "Hello. How can I help the family?", "request": {"id": "request", "status": "completed"},
            "stale": False, "source_errors": {"calendar": False, "vault": False}, "generated_at": "2026-11-12T10:00:00-08:00"}


class FrameTests(unittest.TestCase):
    def test_panel_palette_and_pixel_order_match_the_reference(self):
        image = Image.new("P", (400, 300), 1)
        for x, color in enumerate((0, 1, 3, 2)):
            image.putpixel((x, 0), color)
        packed = pack_frame(image)
        self.assertEqual(len(packed), 30000)
        self.assertEqual(packed[0], 0x1E)  # black, white, red, yellow
        self.assertEqual(packed[1:], b"\x55" * 29999)
        image.putpixel((0, 0), 4)
        with self.assertRaises(ValueError):
            pack_frame(image)

    def test_frame_dimensions_are_not_silently_scaled(self):
        with self.assertRaises(ValueError):
            pack_frame(Image.new("P", (300, 400), 1))

    def test_polling_and_normal_voice_progress_do_not_repaint_the_board(self):
        renderer = Renderer()
        view = fixture()
        first = renderer.render(view, "today", now=NOW)
        view["generated_at"] = "2026-11-12T10:00:30-08:00"
        view["request"]["status"] = "processing"
        again = renderer.render(view, "today", now=NOW)
        self.assertEqual(first.pixels, again.pixels)
        self.assertEqual(first.etag, hashlib.sha256(first.pixels).hexdigest())

    def test_navigation_is_exactly_tasks_and_groceries_even_with_overflow(self):
        renderer = Renderer()
        view = fixture()
        view["reply"] = "A long response with useful family details. " * 100
        view["tasks"] *= 20
        view["groceries"] = [{"id": str(i), "item": "Grocery " + str(i), "state": "needed"} for i in range(100)]
        daily = renderer.render(view, "today", now=NOW)
        grocery = renderer.render(view, daily.next_page, now=NOW)
        self.assertEqual((daily.page, grocery.page), ("today", "groceries"))
        self.assertEqual((daily.previous_page, grocery.previous_page), ("groceries", "today"))
        self.assertEqual(grocery.next_page, "today")
        self.assertTrue(all(frame.pages == 2 and len(frame.pixels) == 30000 for frame in (daily, grocery)))

    def test_tasks_show_today_only_and_exclude_groceries(self):
        renderer, view = Renderer(), fixture()
        view["tasks"] = [{"title": "Today's family task", "due": "2026-11-12"}]
        original = renderer.render(view, "today", now=NOW).pixels
        view["tasks"].extend([
            {"title": "Overdue", "due": "2026-11-11"},
            {"title": "Undated", "due": ""},
            {"title": "Invalid date", "due": "not-a-date"},
            {"title": "Future", "due": "2026-11-13"},
            {"title": "Buy groceries", "due": "2026-11-12", "grocery": True},
        ])
        self.assertEqual(renderer.render(view, "today", now=NOW).pixels, original)
        view["tasks"][0]["title"] = "Changed task for today"
        self.assertNotEqual(renderer.render(view, "today", now=NOW).pixels, original)

    def test_timed_task_due_dates_use_the_household_local_day(self):
        renderer, view = Renderer(), fixture()
        view["tasks"] = [{"title": "Today's task", "due": "2026-11-12"}]
        original = renderer.render(view, "today", now=NOW).pixels
        view["tasks"][0]["due"] = "2026-11-13T01:00:00+00:00"
        self.assertEqual(renderer.render(view, "today", now=NOW).pixels, original)
        view["tasks"][0]["due"] = "2026-11-13T20:00:00+00:00"
        self.assertNotEqual(renderer.render(view, "today", now=NOW).pixels, original)

    def test_empty_groceries_do_not_render_an_instruction_or_item_count(self):
        from unittest.mock import patch
        import hub.frames
        view = fixture()
        labels = []
        original = hub.frames._text
        def capture(*args, **kwargs):
            labels.append(str(args[3]))
            return original(*args, **kwargs)
        with patch.object(hub.frames, "_text", side_effect=capture):
            Renderer().render(view, "groceries", now=NOW)
        self.assertNotIn("Ask Catthew to add groceries.", labels)
        self.assertNotIn("0 items to buy", labels)


    def test_hidden_calendar_and_notes_changes_do_not_refresh_either_page(self):
        renderer = Renderer()
        view = fixture()
        before = {key: renderer.render(view, key, now=NOW).etag for key in ("today", "groceries")}
        view["reply"] = "A spoken response that must never create a chat screen. " * 100
        view["reply_speech_status"] = "ready"
        view["events"] = [{"summary": "Future family event"}] * 100
        view["notes"] *= 100
        after = {key: renderer.render(view, key, now=NOW).etag for key in before}
        self.assertEqual(before, after)

    def test_elapsed_events_and_ordinary_overdue_tasks_are_not_shown(self):
        renderer, view = Renderer(), fixture()
        original = renderer.render(view, "today", now=NOW).pixels
        view["tasks"].append({"id": "past-event", "title": "Closure has passed", "due": "2026-11-11", "kind": "event", "all_day": True})
        self.assertEqual(renderer.render(view, "today", now=NOW).pixels, original)
        view["tasks"][0]["title"] = "A genuine overdue task remains actionable"
        self.assertEqual(renderer.render(view, "today", now=NOW).pixels, original)

    def test_grocery_changes_update_only_its_screen_and_purchases_disappear(self):
        renderer, view = Renderer(), fixture()
        before = {key: renderer.render(view, key, now=NOW).pixels for key in ("today", "groceries")}
        view["groceries"] = [{"id": "milk", "item": "Milk (2 litres)", "state": "needed"}]
        self.assertNotEqual(renderer.render(view, "groceries", now=NOW).pixels, before["groceries"])
        self.assertEqual(renderer.render(view, "today", now=NOW).pixels, before["today"])
        view["groceries"][0]["state"] = "purchased"
        self.assertEqual(renderer.render(view, "groceries", now=NOW).pixels, before["groceries"])

    def test_source_errors_and_unknown_outcomes_are_visibly_distinct(self):
        renderer = Renderer()
        view = fixture()
        normal = renderer.render(view, "today", now=NOW)
        view["request"] = {"id": "new", "status": "uncertain", "error": "Check current records before repeating this request."}
        uncertain = renderer.render(view, "today", now=NOW)
        self.assertNotEqual(normal.pixels, uncertain.pixels)
        view["source_errors"]["calendar"] = True
        view["stale"] = True
        self.assertNotEqual(renderer.render(fixture(), "today", now=NOW).pixels, renderer.render(view, "today", now=NOW).pixels)

    def test_unconfirmed_requests_remain_visible_during_source_outages(self):
        renderer, view = Renderer(), fixture()
        view["stale"] = True
        before = {page: renderer.render(view, page, now=NOW).pixels for page in ("today", "groceries")}
        view["request"] = {"status": "uncertain"}
        for page in before:
            self.assertNotEqual(renderer.render(view, page, now=NOW).pixels, before[page])

    def test_unicode_and_long_words_render_without_invalid_palette_values(self):
        view = fixture()
        view["groceries"] = [{"item": "Gia đình · Chuẩn bị đồ dùng rất quan trọng " * 80 + "x" * 300, "state": "needed"}]
        result = Renderer().render(view, "groceries", now=NOW)
        self.assertEqual(len(result.pixels), 30000)


if __name__ == "__main__":
    unittest.main()
