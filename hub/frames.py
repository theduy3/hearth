"""Render tasks and groceries on the VPS; replies are spoken by the Note4C."""
from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from hub.household import PACIFIC, event_elapsed

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
        value = task.get("due") or ""
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            return date.fromisoformat(value)
        due = datetime.fromisoformat(value)
        return due.astimezone(PACIFIC).date() if due.tzinfo is not None else None
    except (ValueError, TypeError, OverflowError):
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
                     and not task.get("grocery") and not event_elapsed(task, now)
                     and _due(task) == now.date()]
            tasks.sort(key=lambda task: task.get("title", ""))
            count = len(tasks)
            label = f"Showing 5 of {count} today's tasks" if count > 5 else f"Today · {count} tasks"
            _text(draw, 16, 57, label, size=12)
            for index, task in enumerate(tasks[:5]):
                self._task(draw, task, 77 + index * 34)
            if not tasks:
                _text(draw, 16, 90, "No tasks today.", size=20)
        elif key == "groceries":
            items = [item for item in view.get("groceries", []) if item.get("state") == "needed"]
            for index, item in enumerate(items[:7]):
                _text(draw, 16, 68 + index * 24, item.get("item"), size=18, width=368)
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
        footer = f"Tap for {label} · {selected + 1}/2"
        if key == "groceries" and len(items) > 7:
            footer += f" · +{len(items) - 7} more"
        _text(draw, 16, 282, footer, size=11, width=285)
        # The device overlays its small OFFLINE badge in this reserved area.
        pixels = pack_frame(image)
        return Frame(pixels, hashlib.sha256(pixels).hexdigest(), key, following, previous, 2)

    @staticmethod
    def _task(draw, task, y):
        draw.rectangle((16, y + 3, 27, y + 14), outline=BLACK)
        _text(draw, 36, y, task.get("title") or "Family task", size=17, width=346)
