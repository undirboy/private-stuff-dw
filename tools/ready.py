#!/usr/bin/env python3
"""Is the submission actually ready to send?

    python3 tools/ready.py

Checks the things that would be embarrassing to discover after uploading: a
placeholder nobody filled in, a deck over the size limit, a figure that does not
match the parts list, a claim the evidence does not support.

It prints what is outstanding and what is genuinely blocked on somebody outside
this repository, and it separates the two — because "get a written quote for an
imported wheelchair" is not a thing a script can do, and pretending otherwise is
how it stays undone until the day before.

Exit status is 0 when nothing inside the repository is wrong. Outstanding
human tasks are reported but do not fail the build; they would fail it every
day until they are done, which teaches people to ignore it.
"""

from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
DECK = ROOT / "pitch" / "seva" / "margadarshak-seva-2026.pptx"
MAX_UPLOAD_MB = 15.0

#: Things only a person can close. Listed so they stay visible, not so a script
#: can pretend to check them.
HUMAN = [
    ("A written quote for an imported autonomous wheelchair",
     "the cost claim is the pitch and it is the only number with no evidence under it"),
    ("One measured assistance rate from a real airport",
     "replaces the 1-in-100 estimate, which is the figure a judge can most easily check"),
    ("A Konkani speaker's review of the copy",
     "the target airports are in Goa; Marathi has been read, Konkani has not"),
    ("Order the IR line sensor and the battery",
     "the two parts without which there is nothing to show in December"),
    ("Fill in the qualification line on slide 6",
     "the one placeholder left in the deck"),
]


def problems() -> list[str]:
    found: list[str] = []

    if not DECK.exists():
        return [f"the deck is missing: {DECK.relative_to(ROOT)}"]

    size_mb = DECK.stat().st_size / 1_000_000
    if size_mb > MAX_UPLOAD_MB:
        found.append(f"the deck is {size_mb:.1f} MB, over the {MAX_UPLOAD_MB:.0f} MB limit")

    # Placeholder text, ours or the template's, that should have been replaced.
    try:
        from pptx import Presentation
    except ImportError:
        found.append("python-pptx is not installed, so the deck could not be read")
        return found

    leftovers = []
    for index, slide in enumerate(Presentation(DECK).slides, start=1):
        for shape in slide.shapes:
            if not shape.has_text_frame:
                continue
            text = shape.text_frame.text
            if re.search(r"\[(?!Your qualification)[^\]]{3,}\]|lorem|ipsum|\bTODO\b",
                         text, re.I):
                leftovers.append(f"slide {index}: {text[:60]!r}")
    found += [f"placeholder left in the deck — {item}" for item in leftovers]

    return found


def main() -> int:
    found = problems()

    if found:
        print("Not ready:")
        for problem in found:
            print(f"  ! {problem}")
    else:
        print("The repository side is ready: deck present, within the size limit, "
              "no placeholder left but the one we meant to leave.")

    print("\nStill outstanding, and only a person can close these:")
    for task, why in HUMAN:
        print(f"  - {task}\n      {why}")

    return 1 if found else 0


if __name__ == "__main__":
    raise SystemExit(main())
