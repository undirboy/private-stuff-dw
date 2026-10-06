#!/usr/bin/env python3
"""Generate the poster: one idea, big, square, for a phone screen or a stall board.

    python3 explainer/generate_ad.py

The explainer sheet is a document — five sections, read standing still. This is
the other thing: one claim, one picture, read in two seconds while scrolling or
walking past. Square, because that is what survives being sent on WhatsApp and
posted anywhere else.

It carries a status line in the footer, small but legible. An image that implies
a working product where none exists is a lie told quickly, and the project's
whole argument with judges rests on not doing that.
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from generate_explainer import BLUE, FAINT, INK, MID, RULE, TINT, Sheet, draw_chair  # noqa: E402

SIDE = 200.0  # mm square; exports square, so 1080 x 1080 drops straight out
OUT = pathlib.Path(__file__).resolve().parent


class Square(Sheet):
    def render(self) -> str:
        return (
            f'<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{SIDE}mm" height="{SIDE}mm" '
            f'viewBox="0 0 {SIDE} {SIDE}">\n'
            f'  <rect width="{SIDE}" height="{SIDE}" fill="#ffffff"/>\n  '
            + "\n  ".join(self.p)
            + "\n</svg>\n"
        )


def main() -> int:
    s = Square()
    M = 16.0

    # ---- the claim ----------------------------------------------------
    s.text(M, 33, "Scan. Sit.", 11.5, INK, "bold")
    s.text(M, 46, "It takes you to your gate.", 11.5, INK, "bold")
    s.text(M, 57, "And when the gate changes, it already knows.", 5.0, BLUE)

    # ---- the chair, large, standing on its guide line ------------------
    draw_chair(s, ox=96, floor_y=156, k=0.52, guide=False)

    # The guide line again, edge to edge, because it is the whole idea and it is
    # the one mark on the page nobody else's wheelchair has.
    s.line(0, 157.5, SIDE, 157.5, BLUE, 1.6, "3,2")

    # ---- the name -----------------------------------------------------
    s.text(M, 174, "MARGADARSHAK", 9.0, INK, "bold", spacing="0.5")
    s.text(M, 181, "मार्गदर्शक — the one who shows the way", 4.2, MID)

    s.line(M, 186.5, SIDE - M, 186.5, RULE, 0.35)
    s.text(M, 192, "A guided wheelchair for Indian airports, built for ₹4,759.", 4.2, INK)
    s.text(M, 197, "Prototype — nothing here has carried a passenger yet.", 3.4, MID)

    path = OUT / "ad.svg"
    path.write_text(s.render(), encoding="utf-8")
    print(f"Wrote {path}  ({SIDE:.0f} x {SIDE:.0f} mm square)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
