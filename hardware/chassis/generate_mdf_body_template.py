#!/usr/bin/env python3
"""Generate a 1:1 cutting template for the wheelchair body, in 4 mm MDF.

    python3 hardware/chassis/generate_mdf_body_template.py

The drive platform underneath is a box with wheels. This is what makes it read as
a wheelchair across a room, which matters more than it sounds: a judge who has to
be told what they are looking at has already stopped being impressed.

Four shapes, six pieces, all flat, all cut with a coping saw and a straight edge.
They bolt to the deck's existing hole grid, so nothing about the drive platform
changes.

## Scale

The deck is 110 mm wide. A wheelchair is about 650 mm across, so this is
**roughly 1:6**, and every dimension below is a real one divided by six. That is
worth keeping true even where nobody would measure it: a model whose proportions
are right looks right, and nobody can say why.

    seat height      500 mm real  ->   83 mm
    seat width       450 mm       ->   75 mm
    backrest top     900 mm       ->  150 mm
    armrest height   700 mm       ->  117 mm
    footplate        150 mm       ->   25 mm
"""

from __future__ import annotations

import pathlib

import generate_chassis as C
from generate_mdf_template import FAINT, INK, MARGIN, PAGE_H, PAGE_W, Sheet

SCALE_NOTE = "1:6"

MDF_T = 4.0

#: Body sits on the deck, so heights here are measured from the deck's top face.
DECK_TOP = C.ride_height() + C.DECK_T  # 46 mm above the floor

SIDE_L = 120.0           # front-to-back length of a side panel
SIDE_SEAT_H = 40.0       # height of the seat step above the deck
SIDE_ARM_H = 70.0        # height of the armrest top above the deck
SIDE_ARM_L = 70.0        # how far forward the raised armrest section runs

SEAT_W, SEAT_D = 100.0, 70.0
BACK_W, BACK_H = 100.0, 66.0
FOOT_W, FOOT_D = 90.0, 25.0
GUSSET = 20.0

OUT = pathlib.Path(__file__).resolve().parent


def side_panel_points(x: float, y: float) -> list[tuple[float, float]]:
    """Stepped profile: low at the front, raised at the back to form an armrest.

    One piece instead of a panel plus a separate armrest, which is two fewer
    glued joints and two fewer chances to get it out of square.
    """
    return [
        (x, y + SIDE_ARM_H),                      # bottom rear
        (x, y),                                   # top rear
        (x + SIDE_ARM_L, y),                      # top front of the armrest
        (x + SIDE_ARM_L, y + SIDE_ARM_H - SIDE_SEAT_H),  # down the step
        (x + SIDE_L, y + SIDE_ARM_H - SIDE_SEAT_H),      # forward along the seat line
        (x + SIDE_L, y + SIDE_ARM_H),             # bottom front
    ]


def main() -> int:
    sheet = Sheet()

    def poly(points, label="", label_at=None):
        d = " ".join(
            f"{'M' if i == 0 else 'L'}{px:.2f},{py:.2f}" for i, (px, py) in enumerate(points)
        )
        sheet.parts.append(f'<path d="{d} Z" fill="none" stroke="{INK}" stroke-width="0.4"/>')
        if label:
            lx, ly = label_at if label_at else (points[0][0] + 2, points[0][1] - 2)
            sheet.note(lx, ly, label, 3.2)

    top = MARGIN

    # ---- two side panels, stacked, labelled once ------------------------
    y = top
    for n in (1, 2):
        poly(
            side_panel_points(MARGIN, y),
            "SIDE PANEL — CUT 2.  Armrest at the rear, seat step forward." if n == 1 else "",
            (MARGIN + 2, y - 2),
        )
        for fx in (15.0, 55.0, 100.0):
            sheet.hole(MARGIN + fx, y + SIDE_ARM_H - 6, C.M3_CLEAR)
        y += SIDE_ARM_H + 4

    # ---- footplate and gussets, in the column beside the panels ---------
    cx = MARGIN + SIDE_L + 8
    sheet.outline(cx, top, FOOT_D, FOOT_W, "FOOTPLATE")
    for fy in (20.0, 70.0):
        sheet.hole(cx + FOOT_D / 2, top + fy, C.M3_CLEAR)

    gy = top + FOOT_W + 10
    sheet.note(cx, gy - 2, "GUSSETS × 4", 3.2)
    for i in range(4):
        gx = cx + (i % 2) * (GUSSET + 4)
        gyy = gy + (i // 2) * (GUSSET + 4)
        poly([(gx, gyy), (gx + GUSSET, gyy), (gx, gyy + GUSSET)])
        # One hole per leg: the top edge bolts to the side panel's face, the left
        # edge to the deck. The glue does the work; these just hold it square
        # while it dries, which is the part that goes wrong.
        sheet.hole(gx + GUSSET * 0.45, gyy + 4, C.M3_CLEAR)
        sheet.hole(gx + 4, gyy + GUSSET * 0.45, C.M3_CLEAR)

    # ---- seat and backrest, side by side at the bottom ------------------
    by = y + 6
    sheet.outline(MARGIN, by, SEAT_D, SEAT_W, f"SEAT PAN — {SEAT_W:.0f} × {SEAT_D:.0f}")
    for hx in (14.0, SEAT_D - 14.0):
        for hy in (14.0, SEAT_W / 2, SEAT_W - 14.0):
            sheet.hole(MARGIN + hx, by + hy, C.M3_CLEAR)

    bx = MARGIN + SEAT_D + 14
    sheet.outline(bx, by, BACK_H, BACK_W, f"BACKREST — {BACK_W:.0f} × {BACK_H:.0f}")
    for hx in (14.0, BACK_H - 14.0):
        for hy in (16.0, BACK_W - 16.0):
            sheet.hole(bx + hx, by + hy, C.M3_CLEAR)

    used = by + SEAT_W
    sheet.ruler(MARGIN, PAGE_H - MARGIN - 12)
    sheet.note(
        MARGIN,
        PAGE_H - MARGIN - 6,
        "Glue with the gussets inside the corners. Dry-fit the whole body before any glue.",
        2.8,
    )

    path = OUT / "mdf_body_template.svg"
    path.write_text(sheet.render(), encoding="utf-8")

    print(f"side panels ×2  {SIDE_L:.0f} × {SIDE_ARM_H:.0f} mm, stepped")
    print(f"seat pan        {SEAT_W:.0f} × {SEAT_D:.0f} mm")
    print(f"backrest        {BACK_W:.0f} × {BACK_H:.0f} mm")
    print(f"footplate       {FOOT_W:.0f} × {FOOT_D:.0f} mm")
    print(f"gussets ×4      {GUSSET:.0f} mm right-angle triangles")
    print(f"\nassembled: seat {DECK_TOP + SIDE_SEAT_H + MDF_T:.0f} mm, "
          f"armrests {DECK_TOP + SIDE_ARM_H:.0f} mm, "
          f"backrest top {DECK_TOP + SIDE_SEAT_H + MDF_T + BACK_H:.0f} mm above the floor")
    print(f"  at {SCALE_NOTE} that is "
          f"{(DECK_TOP + SIDE_SEAT_H + MDF_T) * 6:.0f} / "
          f"{(DECK_TOP + SIDE_ARM_H) * 6:.0f} / "
          f"{(DECK_TOP + SIDE_SEAT_H + MDF_T + BACK_H) * 6:.0f} mm real")
    limit = PAGE_H - MARGIN - 16
    print(f"\nsheet content ends at {used:.0f} mm, ruler needs it below {limit:.0f} — "
          f"{'fits A4' if used <= limit else 'OVERLAPS THE RULER'}")
    print(f"Wrote {path}")
    return 0 if used <= limit else 1


if __name__ == "__main__":
    raise SystemExit(main())
