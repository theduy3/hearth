#!/usr/bin/env python3
"""Generate only the public setup card and offline badge embedded in firmware."""
from pathlib import Path

from PIL import Image, ImageDraw

from hub.frames import BLACK, PALETTE, RED, WHITE, YELLOW, _font, _image, _text, pack_frame, pack_pixels


def main():
    destination = Path(__file__).resolve().parent.parent / "firmware/main/assets"
    destination.mkdir(parents=True, exist_ok=True)
    image = _image()
    draw = ImageDraw.Draw(image)
    draw.fontmode = "1"
    _text(draw, 16, 17, "Catthew", size=30, bold=True)
    _text(draw, 288, 25, "NOTE4C ▲", size=14, width=96)
    draw.rectangle((16, 62, 383, 65), fill=YELLOW)
    _text(draw, 16, 82, "Your family, at a glance.", size=20)
    for y, line in ((122, "1. Connect this Note4C to your Mac."),
                    (150, "2. Run the setup wizard."),
                    (178, "3. Hold the front button to talk.")):
        _text(draw, 16, y, line, size=15)
    _text(draw, 16, 213, "Speak while the indicator stays lit.", size=13)
    for x, color, label in ((16, BLACK, "Black"), (108, WHITE, "White"), (200, RED, "Red"), (292, YELLOW, "Yellow")):
        draw.rectangle((x, 247, x + 87, 281), fill=color, outline=BLACK)
        _text(draw, x + 10, 257, label, size=14, bold=True, width=76, color=WHITE if color in (BLACK, RED) else BLACK)
    (destination / "setup_frame.bin").write_bytes(pack_frame(image))
    badge = Image.new("P", (80, 16), RED)
    badge.putpalette(PALETTE)
    draw = ImageDraw.Draw(badge)
    draw.fontmode = "1"
    draw.text((10, 2), "OFFLINE", font=_font(11, True), fill=WHITE, anchor="lt")
    (destination / "offline_badge.bin").write_bytes(pack_pixels(badge.tobytes()))
    print("Public setup frame: 30000 bytes; offline badge: 320 bytes")


if __name__ == "__main__":
    main()
