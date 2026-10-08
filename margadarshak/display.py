"""Turning a screen message into pixels, so the chair never sees a character.

Devanagari needs a shaping engine: dependent vowel signs attach above, below and
around the consonants they modify, and consonants join into conjunct ligatures.
The bitmap-font libraries a microcontroller runs index glyphs by byte and have no
notion of any of that, so a Marathi string passed to one comes out as
disconnected marks and empty boxes. Putting a shaping stack on the ESP32 is the
wrong place to spend the RAM.

So the chair is sent pixels. It blits them and has no opinion about what they
say — the same split as the rest of the system, where the chair follows and the
dispatcher decides.

The shaping already happened, once, in ``tools/render_display.py``, under a
developer's eye and with Pillow and libraqm. What this module does is assemble
those pre-shaped runs into a frame, and it does so with the standard library and
nothing else, because "imports nothing but the standard library, verifiable in
one grep" is a claim this project can afford to keep and would rather not trade
for the convenience of shaping text at the moment it is needed.

That constraint pays for itself in a second way. The atlas holds the fixed parts
of twenty-two messages, digits in both scripts, and the ASCII a boarding pass can
contain. It holds nothing else — so there is no mechanism by which arbitrary text
reaches the panel. A chair cannot display what it has no glyphs for.
"""

from __future__ import annotations

import base64
import json
import pathlib
import re
from dataclasses import dataclass

from .announce import CATALOGUE, format_number

ATLAS_PATH = pathlib.Path(__file__).resolve().parent / "display_atlas.json"
PLACEHOLDER = re.compile(r"\{(\w+)\}")


class Unrenderable(Exception):
    """Something was asked for that the atlas has no pixels for.

    Raised rather than skipped. A screen that quietly drops the characters it
    cannot draw shows a passenger a gate number with a digit missing, which is
    worse than showing nothing and saying so.
    """


@dataclass(frozen=True)
class Run:
    """One pre-shaped piece of text, as a 1-bit bitmap."""

    text: str
    width: int
    height: int
    bits: bytes

    @property
    def stride(self) -> int:
        return (self.width + 7) // 8

    def pixel(self, x: int, y: int) -> int:
        if not (0 <= x < self.width and 0 <= y < self.height):
            return 0
        return (self.bits[y * self.stride + (x >> 3)] >> (7 - (x & 7))) & 1


class Frame:
    """A 1-bit panel image, built left to right and top to bottom."""

    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
        self.stride = (width + 7) // 8
        self.bits = bytearray(self.stride * height)

    def blit(self, run: Run, x: int, y: int) -> int:
        """Draw a run at ``x, y``. Returns the x to carry on from.

        Clipped rather than wrapped: a line too long for the panel is cut off at
        the edge, and :meth:`Screen.compose` is what decides whether that is
        acceptable or whether the text should have been shorter.
        """
        for row in range(run.height):
            target_y = y + row
            if not 0 <= target_y < self.height:
                continue
            for column in range(run.width):
                target_x = x + column
                if not 0 <= target_x < self.width:
                    continue
                if run.pixel(column, row):
                    self.bits[target_y * self.stride + (target_x >> 3)] |= (
                        0x80 >> (target_x & 7)
                    )
        return x + run.width

    def packed(self) -> bytes:
        """The frame as the chair receives it: rows of bits, MSB leftmost."""
        return bytes(self.bits)

    def as_text(self) -> str:
        """The frame as characters, for a test or a terminal. Not for a chair."""
        rows = []
        for y in range(self.height):
            rows.append("".join(
                "#" if (self.bits[y * self.stride + (x >> 3)] >> (7 - (x & 7))) & 1
                else "."
                for x in range(self.width)
            ))
        return "\n".join(rows)


class Screen:
    """The atlas, and the frames that can be built from it."""

    def __init__(self, atlas_path: pathlib.Path | str = ATLAS_PATH) -> None:
        raw = json.loads(pathlib.Path(atlas_path).read_text(encoding="utf-8"))
        panel = raw["panel"]
        self.width = int(panel["w"])
        self.height = int(panel["h"])
        self.line_h = int(panel["line_h"])
        self.runs: dict[str, Run] = {
            key: Run(
                text=value["text"],
                width=int(value["w"]),
                height=int(value["h"]),
                bits=base64.b64decode(value["bits"]),
            )
            for key, value in raw["runs"].items()
        }

    # -- building a line -------------------------------------------------

    def runs_for(self, message_id: str, language: str, **params: object) -> list[list[Run]]:
        """One message as a list of words, each word a list of runs.

        Words rather than one flat list, because a line that does not fit has to
        wrap, and a space is the only place a Devanagari line may be broken: no
        conjunct spans one and no matra attaches across one. Breaking anywhere
        else comes apart on the panel.

        Fixed words come from the atlas by id. The parts filled in at runtime — a
        gate, a number of minutes, a flight code — are spelled from the atlas's
        own glyphs, so nothing reaches the panel that was not shaped at build
        time.
        """
        template = CATALOGUE[message_id][language]
        words: list[list[Run]] = []
        pending: list[Run] = []

        for index, part in enumerate(PLACEHOLDER.split(template)):
            if index % 2 == 0:
                if not part:
                    continue
                for word_index, word in enumerate(part.split(" ")):
                    if not word:
                        # A space here ends whatever word was being built.
                        if pending:
                            words.append(pending)
                            pending = []
                        continue
                    key = f"{message_id}|{language}|{index // 2}|{word_index}"
                    run = self.runs.get(key)
                    if run is None:
                        raise Unrenderable(
                            f"no pixels for {key!r} — rebuild the atlas with "
                            f"tools/render_display.py after changing a message"
                        )
                    if word_index > 0 and pending:
                        words.append(pending)
                        pending = []
                    pending.append(run)
                if part.endswith(" ") and pending:
                    words.append(pending)
                    pending = []
            else:
                value = params.get(part)
                if value is None:
                    raise Unrenderable(f"{message_id} needs {part!r}")
                pending.extend(self.spell(format_number(value, language)))

        if pending:
            words.append(pending)
        return words

    def flatten(self, words: list[list[Run]]) -> list[Run]:
        """Words back into one line, with the spaces put back between them."""
        space = self.runs["space"]
        line: list[Run] = []
        for index, word in enumerate(words):
            if index:
                line.append(space)
            line.extend(word)
        return line

    def wrap(self, words: list[list[Run]], width: int | None = None) -> list[list[Run]]:
        """Break a message into lines that fit the panel. Greedy, by word."""
        limit = self.width if width is None else width
        space = self.runs["space"]
        lines: list[list[Run]] = []
        current: list[Run] = []
        used = 0

        for word in words:
            size = sum(run.width for run in word)
            gap = space.width if current else 0
            if current and used + gap + size > limit:
                lines.append(current)
                current, used = list(word), size
                continue
            if current:
                current.append(space)
                used += gap
            current.extend(word)
            used += size

        if current:
            lines.append(current)
        return lines

    def spell(self, text: str) -> list[Run]:
        """One glyph per character, from the atlas. Raises on anything missing."""
        pieces = []
        for character in str(text):
            run = self.runs.get(f"char|{character}")
            if run is None:
                raise Unrenderable(
                    f"the panel has no glyph for {character!r}. Boarding passes are "
                    f"ASCII by the IATA standard, so this is either a message that "
                    f"needs rebuilding into the atlas or text that should not be on "
                    f"a screen in a public terminal."
                )
            pieces.append(run)
        return pieces

    def line_width(self, pieces: list[Run]) -> int:
        return sum(run.width for run in pieces)

    @property
    def lines_per_panel(self) -> int:
        return max(1, self.height // self.line_h)

    # -- building a frame ------------------------------------------------

    def compose(self, lines: list[list[Run]]) -> Frame:
        """Stack lines into a frame, each one centred on the panel."""
        frame = Frame(self.width, self.height)
        for index, pieces in enumerate(lines[: self.height // self.line_h]):
            width = self.line_width(pieces)
            x = max(0, (self.width - width) // 2)
            y = index * self.line_h
            for run in pieces:
                x = frame.blit(run, x, y)
        return frame

    def frame_for(self, content, language: str) -> Frame:
        """A :class:`~margadarshak.screen.ScreenContent`, as pixels.

        Takes the finished lines the dispatcher already decided on, so the panel
        shows exactly what ``screen.py`` says it should and the two cannot drift.
        """
        lines: list[list[Run]] = []
        for message in (content.primary, content.secondary):
            if message is None:
                continue
            lines.extend(self.wrap(
                self.runs_for(message.message_id, language, **message.params)
            ))
        return self.compose(lines)

    def lines_needed(self, message_id: str, language: str, **params: object) -> int:
        """How many panel lines this message needs once wrapped."""
        return len(self.wrap(self.runs_for(message_id, language, **params)))

    def overflows(self, message_id: str, language: str, **params: object) -> int:
        """Pixels past the edge of the widest line, after wrapping. 0 if it fits.

        Non-zero means a single word is wider than the panel, which wrapping
        cannot fix — the message has to be reworded or the panel has to be wider.
        """
        lines = self.wrap(self.runs_for(message_id, language, **params))
        return max(0, max(self.line_width(line) for line in lines) - self.width)
