#!/usr/bin/env python3
"""Render every screen message to a bitmap atlas, once, at build time.

    python3 tools/render_display.py

Writes ``margadarshak/display_atlas.json``.

**Why this exists.** Devanagari is an abugida: dependent vowel signs attach above,
below and either side of the consonant they modify, and consonants join into
conjunct ligatures. Turning a string of code points into the right pixels needs a
shaping engine — HarfBuzz, or FreeType with one. The display libraries a
microcontroller actually runs (``U8g2``, ``Adafruit_GFX``) carry static bitmap
glyphs indexed by byte, so passing them Marathi produces disconnected marks and
missing-glyph boxes. Porting a shaping stack onto an ESP32 is not a weekend; it
is the wrong place to spend the RAM.

So the chair never sees a character. It receives pixels and draws them, which is
the same split the rest of the system already uses: the dispatcher decides, the
chair obeys.

**Why the atlas is built here rather than rendered live.** The obvious version of
this has the dispatcher shape text with Pillow at the moment it is needed. That
would make Pillow a runtime dependency of ``margadarshak``, and the claim that
the package imports nothing but the standard library — checkable in one grep — is
load-bearing for this project. An airport's security review can verify "no third
party code, no network" in a minute, and that is worth more than the convenience.

The screen's vocabulary is closed anyway: twenty-two messages in four languages,
split at their placeholders, plus digits in both scripts and the ASCII a flight
code or a name off a boarding pass can contain. It all fits in a few tens of
kilobytes, and nothing about it changes between one departure and the next.

So shaping happens here, with Pillow and libraqm, under a developer's eye. What
ships is pixels. ``margadarshak/display.py`` composes them with the standard
library and nothing else.
"""

from __future__ import annotations

import base64
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from margadarshak.announce import CATALOGUE, DISPLAY_ORDER  # noqa: E402

try:
    from PIL import Image, ImageDraw, ImageFont, features
except ImportError:  # pragma: no cover - a build-time tool, not a runtime one
    raise SystemExit(
        "This build tool needs Pillow: pip install Pillow\n"
        "It is not needed to run the dispatcher — see the module docstring."
    )

#: The panel the demonstrator carries. Four lines of sixteen pixels.
#:
#: 128x64 rather than the cheaper 128x32, and the reason is measured rather than
#: guessed: at 13 px, 15 of the 88 message-and-language combinations need three
#: lines and one needs four. Two lines would clip them. A 128x64 module costs
#: much the same, so this is the panel.
PANEL_W, PANEL_H = 128, 64
LINE_H = 16
#: Type size that fills a 16-pixel line without clipping a Devanagari matra,
#: which sits above the headline and is the first thing to be cut off.
FONT_PX = 13

FONT = "/usr/share/fonts/truetype/freefont/FreeSans.ttf"
OUT = pathlib.Path(__file__).resolve().parent.parent / "margadarshak" / "display_atlas.json"

PLACEHOLDER = re.compile(r"\{(\w+)\}")

#: Characters that can appear at runtime inside a placeholder. Boarding passes
#: are ASCII by the IATA standard, so a name or a flight code off a scan is
#: covered by the Latin set; the Devanagari digits are for numbers shown in the
#: local scripts.
RUNTIME_CHARS = (
    "0123456789"
    "०१२३४५६७८९"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "abcdefghijklmnopqrstuvwxyz"
    " .,:-/'"
)


def shaped_font() -> "ImageFont.FreeTypeFont":
    if not features.check("raqm"):
        raise SystemExit(
            "Pillow here has no libraqm, so it cannot shape Devanagari: matras and\n"
            "conjuncts would come out wrong and the atlas would ship broken glyphs.\n"
            "Install libraqm (e.g. apt-get install libraqm0) and reinstall Pillow."
        )
    return ImageFont.truetype(FONT, FONT_PX, layout_engine=ImageFont.Layout.RAQM)


def render(text: str, font) -> tuple[int, int, bytes]:
    """One run of text as a 1-bit bitmap: width, height, packed rows.

    The width is the font's **advance** for the run, not the bounding box of the
    ink. That difference matters: these runs are composed side by side at
    runtime, and a run trimmed to its ink loses the space before and after it, so
    "Gate {gate}, Terminal {terminal}" comes back as "Gate4,Terminal1". Keeping
    the advance keeps the spacing the typographer intended.

    Drawn on an oversized canvas and cropped from a known origin, because a matra
    sits above the headline and a vowel sign below the baseline — both outside
    the box a naive text-size call reports.
    """
    advance = max(1, round(font.getlength(text)))
    pad = FONT_PX * 3
    canvas = Image.new("1", (advance + pad * 2, FONT_PX * 4), 0)
    top = pad // 2
    ImageDraw.Draw(canvas).text((pad, top), text, font=font, fill=1)

    # Crop horizontally from the origin for exactly the advance, so runs sit
    # beside each other at the spacing the font specifies. Vertically, take a
    # line-height strip around the baseline so every run shares one baseline.
    strip_top = max(0, top - (LINE_H - FONT_PX) // 2 - 2)
    strip = canvas.crop((pad, strip_top, pad + advance, strip_top + LINE_H))

    width, height = strip.width, strip.height
    stride = (width + 7) // 8
    packed = bytearray(stride * height)
    pixels = strip.load()
    for y in range(height):
        for x in range(width):
            if pixels[x, y]:
                packed[y * stride + (x >> 3)] |= 0x80 >> (x & 7)
    return width, height, bytes(packed)


def main() -> int:
    font = shaped_font()
    runs: dict[str, dict] = {}

    def add(key: str, text: str) -> None:
        if key in runs:
            return
        width, height, packed = render(text, font)
        runs[key] = {
            "text": text,
            "w": width,
            "h": height,
            "bits": base64.b64encode(packed).decode("ascii"),
        }

    # Every fixed part of every message, per language, split at the placeholders
    # and then again at spaces. Words are the unit because a line that does not
    # fit has to wrap somewhere, and a space is the only place in Devanagari
    # where breaking is safe: no conjunct spans one, and no matra attaches
    # across one. Splitting anywhere else would come apart on the panel.
    for message_id, by_language in CATALOGUE.items():
        for language in DISPLAY_ORDER:
            template = by_language[language]
            for index, part in enumerate(PLACEHOLDER.split(template)[::2]):
                for word_index, word in enumerate(part.split(" ")):
                    if word:
                        add(f"{message_id}|{language}|{index}|{word_index}", word)
    add("space", " ")

    # And every character a placeholder can be filled with at runtime.
    for character in RUNTIME_CHARS:
        add(f"char|{character}", character)

    atlas = {
        "panel": {"w": PANEL_W, "h": PANEL_H, "line_h": LINE_H},
        "font": {"file": FONT, "px": FONT_PX, "shaped_with": "libraqm"},
        "runs": runs,
    }
    OUT.write_text(json.dumps(atlas, ensure_ascii=False, indent=1), encoding="utf-8")

    size_kb = OUT.stat().st_size / 1024
    print(f"Wrote {OUT}")
    print(f"  {len(runs)} runs, {size_kb:.0f} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
