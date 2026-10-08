#!/usr/bin/env python3
"""Generate the one-page explainer: what this project is, on a single sheet.

    python3 explainer/generate_explainer.py

Writes ``explainer.pdf`` and ``explainer.png`` — A4 landscape, meant to be
printed, projected, pinned to a board or sent to somebody who has thirty seconds.

This is not the blueprint and not the application. Those answer "how is it built"
and "why should it be funded". This one answers "what is it", for a person who
has not heard of it and is not going to read a page of prose to find out.

The chair in it is drawn from the real geometry in ``generate_blueprint.py``, so
the picture is of the thing that was actually designed rather than a sketch of
something like it.
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "hardware" / "chassis"))

import generate_blueprint as B  # noqa: E402

PAGE_W, PAGE_H = 297.0, 210.0  # A4 landscape

INK = "#14161a"
BLUE = "#1c5cab"
MID = "#5b6472"
FAINT = "#c9d4e4"
RULE = "#dfe4ea"
TINT = "#eef4fc"

OUT = pathlib.Path(__file__).resolve().parent


class Sheet:
    def __init__(self) -> None:
        self.p: list[str] = []

    def text(self, x, y, s, size=3.4, fill=INK, weight="normal", anchor="start", spacing=None):
        extra = f' letter-spacing="{spacing}"' if spacing else ""
        self.p.append(
            f'<text x="{x:.2f}" y="{y:.2f}" font-family="FreeSans, DejaVu Sans, sans-serif" '
            f'font-size="{size}" fill="{fill}" font-weight="{weight}" '
            f'text-anchor="{anchor}"{extra}>{s}</text>'
        )

    def lines(self, x, y, rows, size=3.4, fill=MID, leading=4.6):
        for i, row in enumerate(rows):
            self.text(x, y + i * leading, row, size, fill)

    def rect(self, x, y, w, h, fill="none", stroke="none", sw=0.3, rx=0):
        self.p.append(
            f'<rect x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" height="{h:.2f}" rx="{rx}" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>'
        )

    def line(self, x1, y1, x2, y2, stroke=RULE, sw=0.3, dash=None):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        self.p.append(
            f'<path d="M{x1:.2f},{y1:.2f} L{x2:.2f},{y2:.2f}" stroke="{stroke}" '
            f'stroke-width="{sw}" fill="none"{d}/>'
        )

    def circle(self, cx, cy, r, fill="none", stroke=INK, sw=0.4):
        self.p.append(
            f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{r:.2f}" fill="{fill}" '
            f'stroke="{stroke}" stroke-width="{sw}"/>'
        )

    def stroke_path(self, pts, stroke=MID, sw=1.2):
        d = " ".join(f"{'M' if i == 0 else 'L'}{x:.2f},{y:.2f}" for i, (x, y) in enumerate(pts))
        self.p.append(
            f'<path d="{d}" fill="none" stroke="{stroke}" stroke-width="{sw}" '
            f'stroke-linecap="round" stroke-linejoin="round"/>'
        )

    def poly(self, pts, fill="none", stroke=INK, sw=0.4):
        d = " ".join(f"{'M' if i == 0 else 'L'}{x:.2f},{y:.2f}" for i, (x, y) in enumerate(pts))
        self.p.append(f'<path d="{d} Z" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>')

    def render(self) -> str:
        return (
            f'<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{PAGE_W}mm" height="{PAGE_H}mm" '
            f'viewBox="0 0 {PAGE_W} {PAGE_H}">\n'
            f'  <rect width="{PAGE_W}" height="{PAGE_H}" fill="#ffffff"/>\n  '
            + "\n  ".join(self.p)
            + "\n</svg>\n"
        )


def draw_chair(s: Sheet, ox: float, floor_y: float, k: float, guide: bool = True) -> None:
    """The chair, side on, at scale ``k``, drawn from the real design.

    Painted far to near, which is the whole trick: the side panel is a solid, so
    anything drawn before it disappears behind it. The wheel is outboard of the
    panel and so goes on last; the passenger sits between the panels and is drawn
    over them as a cutaway, because a side elevation of a wheelchair with nobody
    in it does not read as a wheelchair.
    """

    def P(y: float, z: float) -> tuple[float, float]:
        return ox + y * k, floor_y - z * k

    if guide:
        s.line(*P(-96, 0), *P(104, 0), FAINT, 0.5)

    # 1. Backrest, furthest back. Widened from the 4 mm board so it reads at this
    #    size; every other dimension here is true to the design.
    bx, by = P(B.PANEL_REAR_Y - 7, B.BACK_TOP_Z)
    s.rect(bx, by, 7 * k, (B.BACK_TOP_Z - B.SEAT_TOP_Z) * k, "#e8eef7", INK, 0.45)

    # 2. Side panel: armrest at the rear, lower frame forward.
    s.poly(
        [
            P(B.PANEL_REAR_Y, B.DECK_TOP),
            P(B.PANEL_REAR_Y, B.ARM_TOP_Z),
            P(B.ARM_STEP_Y, B.ARM_TOP_Z),
            P(B.ARM_STEP_Y, B.FRONT_FRAME_Z),
            P(B.PANEL_FRONT_Y, B.FRONT_FRAME_Z),
            P(B.PANEL_FRONT_Y, B.DECK_TOP),
        ],
        "#f4f7fb",
        INK,
        0.5,
    )
    s.line(*P(B.PANEL_REAR_Y, B.SEAT_TOP_Z), *P(B.ARM_STEP_Y, B.SEAT_TOP_Z), FAINT, 0.5)

    # 3. Deck, and the footplate hung off its front on a strut.
    dx, dy = P(-B.C.DECK_L / 2, B.DECK_TOP)
    s.rect(dx, dy, B.C.DECK_L * k, B.C.DECK_T * k, "#ffffff", INK, 0.45)
    s.line(*P(B.FOOT_Y0 + 3, B.DECK_BOTTOM), *P(B.FOOT_Y0 + 3, B.FOOT_Z), INK, 0.35)
    fx, fy = P(B.FOOT_Y0, B.FOOT_Z)
    s.rect(fx, fy, B.B.FOOT_D * k, B.B.MDF_T * k, "#ffffff", INK, 0.45)

    # 4. The passenger, as a cutaway.
    s.stroke_path([P(-38, 94), P(-47, 148)], MID, 2.4 * k)
    s.stroke_path([P(-38, 94), P(22, 94), P(52, 38)], MID, 2.4 * k)
    s.stroke_path([P(-45, 134), P(-8, 118)], MID, 1.8 * k)
    hx, hy = P(-50, 158)
    s.circle(hx, hy, 9 * k, "#ffffff", MID, 0.5)

    # 5. The drive wheel, outboard of everything. Spokes because nothing else
    #    says "wheelchair" as quickly.
    wx, wy = P(B.C.AXLE_Y, B.AXLE_Z)
    r = B.WHEEL_R * k
    s.circle(wx, wy, r, "#ffffff", INK, 0.6)
    for a in range(0, 180, 30):
        import math

        dxs, dys = math.cos(math.radians(a)) * r * 0.86, math.sin(math.radians(a)) * r * 0.86
        s.line(wx - dxs, wy - dys, wx + dxs, wy + dys, FAINT, 0.3)
    s.circle(wx, wy, r * 0.16, "#ffffff", INK, 0.4)

    cx, cy = P(B.C.CASTOR_Y, 0)
    s.circle(cx, cy - 9 * k, 9 * k, "#ffffff", INK, 0.45)

    # 6. The sensor bracket, and the line it is reading.
    s.rect(*P(B.BRACKET_ARM_Y, B.DECK_TOP + B.C.BRACKET_T), B.C.BRACKET_T * k,
           (B.DECK_TOP + B.C.BRACKET_T - B.ARM_BOTTOM_Z) * k, "#ffffff", BLUE, 0.5)
    if guide:
        gx1, gy1 = P(-96, 0)
        gx2, _ = P(104, 0)
        s.line(gx1, gy1 + 1.5, gx2, gy1 + 1.5, BLUE, 1.2, "2.4,1.6")
        s.text(gx1, gy1 + 6.0, "the guide line it follows, laid into the floor", 2.9, BLUE)


def main() -> int:
    s = Sheet()
    M = 16.0

    # ---- header -------------------------------------------------------
    s.text(M, 24, "MARGADARSHAK", 13, INK, "bold", spacing="0.6")
    s.text(M, 32.5, "मार्गदर्शक — the one who shows the way", 4.0, MID)
    s.text(
        M, 42,
        "A wheelchair that takes airport passengers to their gate by itself, "
        "for a fraction of what the imported ones cost.",
        4.6, INK,
    )
    s.line(M, 48, PAGE_W - M, 48, RULE, 0.4)

    # ---- left: the chair ----------------------------------------------
    draw_chair(s, ox=M + 46, floor_y=146, k=0.56)
    s.text(M, 163, "The demonstrator", 3.6, INK, "bold")
    s.lines(M, 169, [
        "1:6 scale, 4 mm MDF, two chairs for ₹4,759.",
        "Drive wheels double as the wheelchair's own.",
    ], 3.2)

    # ---- right: problem -----------------------------------------------
    cx = 128.0
    s.text(cx, 60, "THE PROBLEM", 3.4, BLUE, "bold", spacing="0.5")
    s.lines(cx, 67.5, [
        "Indian airports must provide wheelchair assistance free, and",
        "do not have the attendants to do it. Passengers wait without",
        "knowing how long. Delivered to a gate, they are stranded there",
        "until somebody remembers them. And when the airline moves",
        "the gate, nobody tells the person pushing the chair.",
    ], 3.4)

    # ---- right: how it works ------------------------------------------
    s.text(cx, 100, "HOW IT WORKS", 3.4, BLUE, "bold", spacing="0.5")
    beats = [
        ("1", "The passenger scans their boarding pass.", "Nothing to type, nothing to read, no app."),
        ("2", "A laptop in the airport finds the gate.", "The pass names the flight; the gate is looked up live."),
        ("3", "The chair follows a line in the floor.", "No map, no cloud. It stops for anything in front of it."),
    ]
    for i, (n, head, body) in enumerate(beats):
        y = 108 + i * 13
        s.circle(cx + 2.4, y - 1.2, 2.6, TINT, BLUE, 0.4)
        s.text(cx + 2.4, y, n, 3.2, BLUE, "bold", anchor="middle")
        s.text(cx + 8, y - 1.6, head, 3.6, INK, "bold")
        s.text(cx + 8, y + 3.0, body, 3.2, MID)

    # ---- the one thing ------------------------------------------------
    s.rect(cx, 150, PAGE_W - M - cx, 20, TINT, BLUE, 0.4, rx=1.5)
    s.text(cx + 5, 157.5, "If the gate changes mid-journey, the chair is simply re-routed.",
           3.9, INK, "bold")
    s.text(cx + 5, 163.5,
           "A person pushing a wheelchair cannot do that. They set off committed, "
           "and nobody tells them.", 3.2, MID)

    # ---- footer strip --------------------------------------------------
    s.line(M, 182, PAGE_W - M, 182, RULE, 0.4)
    facts = [
        ("₹4,759", "two working chairs"),
        ("4 languages", "Konkani first, English last"),
        ("No cloud", "nothing leaves the airport"),
        ("214 tests", "the dispatcher runs today"),
    ]
    step = (PAGE_W - 2 * M) / len(facts)
    for i, (big, small) in enumerate(facts):
        x = M + i * step
        s.text(x, 190, big, 5.0, BLUE, "bold")
        s.text(x, 195, small, 3.0, MID)

    s.text(PAGE_W - M, 203,
           "Nothing here has yet carried a passenger. The hardware is designed and not built.",
           2.9, MID, anchor="end")

    path = OUT / "explainer.svg"
    path.write_text(s.render(), encoding="utf-8")
    print(f"Wrote {path}  ({PAGE_W:.0f} x {PAGE_H:.0f} mm, A4 landscape)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
