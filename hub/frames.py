"""Render the family board on the VPS; the Note4C projects four-color pixels."""
from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT = 400, 300
BLACK, WHITE, YELLOW, RED = 0, 1, 2, 3
PALETTE = [0, 0, 0, 255, 255, 255, 245, 205, 20, 195, 30, 35]
FONTS = Path(__file__).resolve().parent.parent / "assets/fonts"


@lru_cache(maxsize=12)
def _font(size, bold=False):
    return ImageFont.truetype(str(FONTS / ("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf")), size)


def _plain(text):
    text = unicodedata.normalize("NFC", str(text or ""))
    text = "".join(c for c in text if c == "\n" or not unicodedata.category(c).startswith("C"))
    text = re.sub(r"(?m)^#{1,6}\s+", "", text)
    return re.sub(r"\*\*(.*?)\*\*", r"\1", text)


def _lines(text, font, width):
    lines = []
    for paragraph in _plain(text).splitlines() or [""]:
        line = ""
        for word in paragraph.split():
            candidate = (line + " " + word).strip()
            if font.getlength(candidate) <= width:
                line = candidate
                continue
            if line:
                lines.append(line)
                line = ""
            while font.getlength(word) > width:
                end = 1
                while end < len(word) and font.getlength(word[:end + 1]) <= width:
                    end += 1
                lines.append(word[:end])
                word = word[end:]
            line = word
        lines.append(line)
    return lines


def _text(draw, x, y, text, *, size=16, bold=False, width=368, rows=1, color=BLACK):
    font = _font(size, bold)
    lines = _lines(text, font, width)
    if len(lines) > rows:
        lines = lines[:rows]
        last = lines[-1]
        while last and font.getlength(last + "…") > width:
            last = last[:-1]
        lines[-1] = last + "…"
    for index, line in enumerate(lines):
        draw.text((x, y + index * (size + 4)), line, font=font, fill=color, anchor="lt")


def _image():
    image = Image.new("P", (WIDTH, HEIGHT), WHITE)
    image.putpalette(PALETTE)
    return image


def pack_pixels(pixels):
    if len(pixels) % 4 or any(value > 3 for value in pixels):
        raise ValueError("pixels must be groups of four BWRY indices")
    return bytes((pixels[i] << 6) | (pixels[i + 1] << 4) | (pixels[i + 2] << 2) | pixels[i + 3]
                 for i in range(0, len(pixels), 4))


def pack_frame(image):
    if image.mode != "P" or image.size != (WIDTH, HEIGHT):
        raise ValueError("frame must be indexed 400x300")
    return pack_pixels(image.tobytes())


def unpack_frame(packed):
    if len(packed) != 30000:
        raise ValueError("frame must contain 30000 bytes")
    pixels = bytearray()
    for value in packed:
        pixels.extend((value >> 6, (value >> 4) & 3, (value >> 2) & 3, value & 3))
    image = Image.frombytes("P", (WIDTH, HEIGHT), bytes(pixels))
    image.putpalette(PALETTE)
    return image


@dataclass(frozen=True)
class Frame:
    pixels: bytes
    etag: str
    page: str
    next_page: str
    previous_page: str
    pages: int


def _chunks(items, count):
    return [items[i:i + count] for i in range(0, len(items), count)] or [[]]


def _due(task):
    try:
        return date.fromisoformat(task.get("due") or "")
    except (ValueError, TypeError):
        return None


def _event_time(event, now):
    value = event.get("start") or {}
    if value.get("date"):
        return date.fromisoformat(value["date"]).strftime("%a, %b %-d") + " · All day"
    try:
        when = datetime.fromisoformat(value["dateTime"]).astimezone(now.tzinfo)
        return when.strftime("%a, %b %-d · %-I:%M %p")
    except (KeyError, ValueError, TypeError):
        return "Time to be confirmed"


def _today(event, now):
    start, end = event.get("start") or {}, event.get("end") or {}
    try:
        if start.get("date"):
            return date.fromisoformat(start["date"]) <= now.date() < date.fromisoformat(end["date"])
        first = datetime.fromisoformat(start["dateTime"]).astimezone(now.tzinfo)
        last = datetime.fromisoformat(end["dateTime"]).astimezone(now.tzinfo)
        midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return first.date() == now.date() or first < midnight < last
    except (ValueError, KeyError, TypeError):
        return False


class Renderer:
    def __init__(self):
        _font(16)
        _font(24, True)

    def render(self, view, page, *, now):
        tasks = sorted(view.get("tasks", []), key=lambda x: (_due(x) or date.max, x.get("title", "")))
        pages = [("today", "Today", None)]
        for kind, title, items, count in (("agenda", "Family agenda", view.get("events", []), 4),
                                          ("tasks", "Family tasks", tasks, 4),
                                          ("notes", "Family notes", view.get("notes", []), 3)):
            for index, chunk in enumerate(_chunks(items, count)):
                pages.append((f"{kind}:{index}", title, chunk))
        request = view.get("request") or {}
        failed = request.get("status") in ("failed", "uncertain")
        reply = ("This request could not be confirmed. Check the current records before repeating it."
                 if failed else view.get("reply") or "Hold the front button. Speak while the indicator stays lit, then release to send.")
        reply_lines = _lines(reply, _font(16), 368)
        for index, lines in enumerate(_chunks(reply_lines, 9)):
            pages.append((f"reply:{index}", "Catthew", lines))
        selected = next((i for i, item in enumerate(pages) if item[0] == page), 0)
        key, title, data = pages[selected]
        image = _image()
        draw = ImageDraw.Draw(image)
        draw.fontmode = "1"
        _text(draw, 16, 12, title, size=24, bold=True, width=270)
        _text(draw, 292, 17, now.strftime("%a, %b %-d"), size=12, width=94)
        draw.rectangle((16, 44, 383, 46), fill=YELLOW)
        kind = key.split(":", 1)[0]
        if kind == "today":
            upcoming = [event for event in view.get("events", []) if _today(event, now)][:2]
            _text(draw, 16, 59, "ON THE CALENDAR", size=12, bold=True)
            y = 80
            if not upcoming:
                _text(draw, 16, y, "No events today.", size=16)
                y += 30
            for event in upcoming:
                _text(draw, 16, y, event.get("summary") or "Family event", size=16, bold=True)
                _text(draw, 16, y + 21, _event_time(event, now), size=12)
                y += 45
            _text(draw, 16, y + 4, f"TASKS · {len(tasks)}", size=12, bold=True)
            y += 27
            for task in tasks[:(2 if upcoming else 4)]:
                self._task(draw, task, y, now, compact=True)
                y += 32
            if not tasks:
                _text(draw, 16, y, "Nothing on your list.", size=16)
        elif kind == "agenda":
            if not data:
                _text(draw, 16, 86, "No events in the next seven days.", size=18, rows=2)
            for index, event in enumerate(data):
                y = 61 + index * 50
                _text(draw, 16, y, _event_time(event, now), size=12, bold=True)
                _text(draw, 16, y + 19, event.get("summary") or "Family event", size=16)
        elif kind == "tasks":
            if not data:
                _text(draw, 16, 86, "Nothing on your list.", size=20)
            for index, task in enumerate(data):
                self._task(draw, task, 63 + index * 50, now)
        elif kind == "notes":
            if not data:
                _text(draw, 16, 82, "Your shared family notes appear here.", size=19, rows=2)
                _text(draw, 16, 145, "Tag a note kittyggup to share it.", size=14, rows=2)
            for index, note in enumerate(data):
                y = 63 + index * 64
                _text(draw, 16, y, note.get("title"), size=16, bold=True)
                _text(draw, 16, y + 22, note.get("text"), size=13, rows=2)
        else:
            if failed:
                draw.rectangle((16, 54, 383, 80), fill=RED)
                _text(draw, 24, 59, "Please check this request", size=14, bold=True, color=WHITE)
            y = 91 if failed else 66
            for line in data:
                _text(draw, 16, y, line, size=16)
                y += 20
                if y > 252:
                    break
        if view.get("stale"):
            draw.rectangle((16, 249, 383, 269), fill=YELLOW)
            _text(draw, 23, 252, "Some records unavailable · showing saved data", size=11, width=354)
        elif kind == "reply" and view.get("reply_speech_status") == "failed":
            draw.rectangle((16, 249, 383, 269), fill=YELLOW)
            _text(draw, 23, 252, "Spoken reply unavailable · answer shown above", size=11, width=354)
        elif view.get("approval_pending"):
            _text(draw, 16, 252, "Calendar approval waiting in Telegram", size=12, color=RED)
        draw.line((16, 274, 383, 274), fill=BLACK)
        _text(draw, 16, 282, f"Tap for next page · {selected + 1}/{len(pages)}", size=11, width=285)
        # The device overlays its small OFFLINE badge in this reserved area.
        pixels = pack_frame(image)
        return Frame(pixels, hashlib.sha256(pixels).hexdigest(), key,
                     pages[(selected + 1) % len(pages)][0], pages[(selected - 1) % len(pages)][0], len(pages))

    @staticmethod
    def _task(draw, task, y, now, compact=False):
        due = _due(task)
        overdue = due is not None and due < now.date()
        color = RED if overdue else BLACK
        draw.rectangle((16, y + 3, 27, y + 14), outline=color)
        title = ("Overdue · " if compact and overdue else "") + str(task.get("title") or "Family task")
        _text(draw, 36, y, title, size=15, width=346, color=color)
        if not compact:
            label = "OVERDUE · " + due.strftime("%b %-d") if overdue else ("Due " + due.strftime("%a, %b %-d") if due else ("Check due date" if task.get("due") else "No due date"))
            _text(draw, 36, y + 23, label, size=11, bold=overdue, color=color)
