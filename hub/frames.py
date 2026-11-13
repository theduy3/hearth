"""Render tasks and groceries on the VPS; replies are spoken by the Note4C."""
from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from hub.household import event_elapsed

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


def _due(task):
    try:
        return date.fromisoformat(task.get("due") or "")
    except (ValueError, TypeError):
        return None


class Renderer:
    def __init__(self):
        _font(16)
        _font(24, True)

    def render(self, view, page, *, now):
        pages = ("today", "groceries")
        selected = pages.index(page) if page in pages else 0
        key = pages[selected]
        image = _image()
        draw = ImageDraw.Draw(image)
        draw.fontmode = "1"
        titles = {"today": "Tasks", "groceries": "Grocery Shopping"}
        _text(draw, 16, 12, titles[key], size=24, bold=True, width=270)
        _text(draw, 292, 17, now.strftime("%a, %b %-d"), size=12, width=94)
        draw.rectangle((16, 44, 383, 46), fill=YELLOW)
        if key == "today":
            tasks = [task for task in view.get("tasks", [])
                     if task.get("status") not in ("completed", "done", "cancelled")
                     and not event_elapsed(task, now) and (_due(task) is None or _due(task) <= now.date())]
            tasks.sort(key=lambda task: (_due(task) or date.max, task.get("title", "")))
            count = len(tasks)
            label = f"Showing 5 of {count} · ask Catthew for more" if count > 5 else f"Today, overdue & undated · {count}"
            _text(draw, 16, 57, label, size=12)
            for index, task in enumerate(tasks[:5]):
                self._task(draw, task, 77 + index * 34, now)
            if not tasks:
                _text(draw, 16, 90, "Nothing due today.", size=20)
        elif key == "groceries":
            items = [item for item in view.get("groceries", []) if item.get("state") == "needed"]
            label = f"Showing 7 of {len(items)} · ask Catthew for more" if len(items) > 7 else f"{len(items)} items to buy"
            _text(draw, 16, 57, label, size=12)
            for index, item in enumerate(items[:7]):
                y = 79 + index * 24
                draw.rectangle((16, y + 3, 27, y + 14), outline=BLACK)
                _text(draw, 36, y, item.get("item"), size=16, width=346)
            if not items:
                _text(draw, 16, 90, "Ask Catthew to add groceries.", size=18, rows=2)
        if (view.get("request") or {}).get("status") in ("failed", "uncertain"):
            draw.rectangle((16, 249, 383, 269), fill=RED)
            warning = "Request unconfirmed · check before repeating"
            if view.get("stale"):
                warning = "Request unconfirmed · saved data · check records"
            _text(draw, 23, 252, warning, size=11, color=WHITE, width=354)
        elif view.get("reply_speech_status") == "failed":
            draw.rectangle((16, 249, 383, 269), fill=YELLOW)
            warning = ("Spoken reply unavailable · showing saved data" if view.get("stale")
                       else "Spoken reply unavailable · check current records")
            _text(draw, 23, 252, warning, size=11, width=354)
        elif view.get("stale"):
            draw.rectangle((16, 249, 383, 269), fill=YELLOW)
            _text(draw, 23, 252, "Some records unavailable · showing saved data", size=11, width=354)
        elif view.get("approval_pending"):
            _text(draw, 16, 252, "Calendar approval waiting in Telegram", size=12, color=RED)
        draw.line((16, 274, 383, 274), fill=BLACK)
        following, previous = pages[(selected + 1) % len(pages)], pages[(selected - 1) % len(pages)]
        label = {"today": "tasks", "groceries": "groceries"}[following]
        _text(draw, 16, 282, f"Tap for {label} · {selected + 1}/2", size=11, width=285)
        # The device overlays its small OFFLINE badge in this reserved area.
        pixels = pack_frame(image)
        return Frame(pixels, hashlib.sha256(pixels).hexdigest(), key, following, previous, 2)

    @staticmethod
    def _task(draw, task, y, now):
        due = _due(task)
        overdue = due is not None and due < now.date()
        color = RED if overdue else BLACK
        draw.rectangle((16, y + 3, 27, y + 14), outline=color)
        _text(draw, 36, y, task.get("title") or "Family task", size=15, width=346, color=color)
        label = "OVERDUE · " + due.strftime("%b %-d") if overdue else ("Due today" if due else ("Check due date" if task.get("due") else "No due date"))
        _text(draw, 36, y + 20, label, size=11, bold=overdue, color=color)
