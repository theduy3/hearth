import copy
import hashlib
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from PIL import Image

from hub.frames import Renderer, pack_frame


NOW = datetime(2026, 11, 12, 10, 0, tzinfo=ZoneInfo("America/Vancouver"))


def fixture():
    return {"events": [], "tasks": [{"id": str(i), "title": "Family task " + str(i), "due": "2026-11-11" if i == 0 else "", "status": "open"} for i in range(9)],
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

    def test_navigation_is_exactly_daily_tasks_and_chat_even_with_overflow(self):
        renderer = Renderer()
        view = fixture()
        view["reply"] = "A long response with useful family details. " * 100
        view["tasks"] *= 20
        daily = renderer.render(view, "today", now=NOW)
        chat = renderer.render(view, daily.next_page, now=NOW)
        self.assertEqual((daily.page, chat.page), ("today", "reply:0"))
        self.assertEqual((daily.next_page, daily.previous_page), ("reply:0", "reply:0"))
        self.assertEqual((chat.next_page, chat.previous_page), ("today", "today"))
        self.assertEqual((daily.pages, chat.pages), (2, 2))
        self.assertEqual(len(daily.pixels), 30000)
        self.assertEqual(len(chat.pixels), 30000)

    def test_daily_tasks_show_due_today_overdue_and_undated_but_not_future(self):
        renderer = Renderer()
        view = fixture()
        view["tasks"] = [{"title": "Overdue", "due": "2026-11-11"},
                         {"title": "Due today", "due": "2026-11-12"},
                         {"title": "Undated", "due": ""},
                         {"title": "Check invalid date", "due": "not-a-date"}]
        original = renderer.render(view, "today", now=NOW).pixels
        view["tasks"].append({"title": "Future task", "due": "2026-11-13"})
        self.assertEqual(renderer.render(view, "today", now=NOW).pixels, original)
        view["tasks"][1]["title"] = "Changed task for today"
        self.assertNotEqual(renderer.render(view, "today", now=NOW).pixels, original)

    def test_hidden_calendar_and_notes_changes_do_not_refresh_either_page(self):
        renderer = Renderer()
        view = fixture()
        before = {key: renderer.render(view, key, now=NOW).etag for key in ("today", "reply:0")}
        view["events"] = [{"summary": "Future family event"}] * 100
        view["notes"] *= 100
        after = {key: renderer.render(view, key, now=NOW).etag for key in before}
        self.assertEqual(before, after)

    def test_source_errors_and_unknown_outcomes_are_visibly_distinct(self):
        renderer = Renderer()
        view = fixture()
        normal = renderer.render(view, "reply:0", now=NOW)
        view["request"] = {"id": "new", "status": "uncertain", "error": "Check current records before repeating this request."}
        uncertain = renderer.render(view, "reply:0", now=NOW)
        self.assertNotEqual(normal.pixels, uncertain.pixels)
        view["source_errors"]["calendar"] = True
        view["stale"] = True
        self.assertNotEqual(renderer.render(fixture(), "today", now=NOW).pixels, renderer.render(view, "today", now=NOW).pixels)

    def test_unicode_and_long_words_render_without_invalid_palette_values(self):
        view = fixture()
        view["reply"] = "Gia đình · Chuẩn bị đồ dùng rất quan trọng " * 80 + "x" * 300
        result = Renderer().render(view, "reply:0", now=NOW)
        self.assertEqual(len(result.pixels), 30000)


if __name__ == "__main__":
    unittest.main()
