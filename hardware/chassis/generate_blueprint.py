#!/usr/bin/env python3
"""Generate the assembly blueprint: dimensioned elevations of the whole chair.

    python3 hardware/chassis/generate_blueprint.py

The cutting templates say what to make. This says what it becomes, with the
dimensions that decide whether it works. It is the drawing to put in front of
somebody, and the one to check your build against when something fouls.

A3 landscape at 1:1. Printing it smaller is fine — every figure that matters is
written on, so the drawing does not depend on its own scale.

Everything is computed from the same constants as the parts, so a changed
dimension cannot leave the drawing saying something the parts do not do.
"""

from __future__ import annotations

import pathlib

import generate_chassis as C
import generate_mdf_body_template as B

PAGE_W, PAGE_H = 420.0, 297.0  # A3 landscape
FRAME = 8.0

INK = "#1c5cab"
THIN = "#86b6ef"
GHOST = "#cde2fb"

OUT = pathlib.Path(__file__).resolve().parent

# ---------------------------------------------------------------- geometry
# All heights are above the floor, so the drawing reads the way the chair sits.

FLOOR = 0.0
WHEEL_R = C.WHEEL_DIA / 2
AXLE_Z = WHEEL_R
DECK_BOTTOM = C.ride_height()
DECK_TOP = DECK_BOTTOM + C.DECK_T

#: Body placement along the chair. The side panels run from the rear edge
#: forward; the raised armrest section sits over the seat.
PANEL_REAR_Y = -70.0
PANEL_FRONT_Y = PANEL_REAR_Y + B.SIDE_L
ARM_STEP_Y = PANEL_REAR_Y + B.SIDE_ARM_L

ARM_TOP_Z = DECK_TOP + B.SIDE_ARM_H
FRONT_FRAME_Z = DECK_TOP + B.SIDE_SEAT_H
SEAT_TOP_Z = FRONT_FRAME_Z + B.MDF_T
BACK_TOP_Z = SEAT_TOP_Z + B.BACK_H

FOOT_Z = 28.0
FOOT_Y0, FOOT_Y1 = PANEL_FRONT_Y, PANEL_FRONT_Y + B.FOOT_D

BRACKET_FRONT_Y = C.DECK_L / 2
BRACKET_ARM_Y = BRACKET_FRONT_Y - C.BRACKET_T
ARM_BOTTOM_Z = DECK_TOP - C.BRACKET_DROP + C.BRACKET_T
SENSOR_Z = DECK_TOP + C.SENSOR_SLOT_Z
ULTRASONIC_Z = DECK_TOP + C.ULTRASONIC_Z

WHEEL_X = C.DECK_W / 2 + 5.0
WHEEL_W = 26.0
PANEL_X = C.DECK_W / 2 - 2.0


class Draw:
    """Minimal SVG with the few things a drawing needs."""

    def __init__(self) -> None:
        self.p: list[str] = []

    def line(self, x1, y1, x2, y2, colour=INK, w=0.35, dash=None):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        self.p.append(
            f'<path d="M{x1:.2f},{y1:.2f} L{x2:.2f},{y2:.2f}" stroke="{colour}" '
            f'stroke-width="{w}" fill="none"{d}/>'
        )

    def rect(self, x, y, w, h, colour=INK, sw=0.35, fill="none"):
        self.p.append(
            f'<rect x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" height="{h:.2f}" '
            f'fill="{fill}" stroke="{colour}" stroke-width="{sw}"/>'
        )

    def circle(self, cx, cy, r, colour=INK, sw=0.35, fill="none"):
        self.p.append(
            f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{r:.2f}" fill="{fill}" '
            f'stroke="{colour}" stroke-width="{sw}"/>'
        )

    def poly(self, pts, colour=INK, sw=0.35, fill="none"):
        d = " ".join(f"{'M' if i == 0 else 'L'}{x:.2f},{y:.2f}" for i, (x, y) in enumerate(pts))
        self.p.append(f'<path d="{d} Z" fill="{fill}" stroke="{colour}" stroke-width="{sw}"/>')

    def text(self, x, y, s, size=3.0, colour=INK, anchor="start", weight="normal"):
        self.p.append(
            f'<text x="{x:.2f}" y="{y:.2f}" font-family="sans-serif" font-size="{size}" '
            f'fill="{colour}" text-anchor="{anchor}" font-weight="{weight}">{s}</text>'
        )

    def arrow(self, x, y, angle):
        """A small filled arrowhead, angle 0 = pointing right."""
        import math

        a = math.radians(angle)
        tip = (x, y)
        back = 2.2
        for sign in (1, -1):
            bx = x - back * math.cos(a) + sign * 0.9 * math.sin(a)
            by = y - back * math.sin(a) - sign * 0.9 * math.cos(a)
            self.line(tip[0], tip[1], bx, by, INK, 0.5)

    def vdim(self, x, y0, y1, label, tick_x0, tick_x1):
        """A vertical dimension at page-x ``x`` between two page-y values."""
        self.line(tick_x0, y0, x + 2, y0, THIN, 0.22)
        self.line(tick_x1, y1, x + 2, y1, THIN, 0.22)
        self.line(x, y0, x, y1, INK, 0.3)
        self.arrow(x, y0, 90 if y0 < y1 else -90)
        self.arrow(x, y1, -90 if y0 < y1 else 90)
        self.text(x + 1.6, (y0 + y1) / 2 + 1, label, 2.8)

    def hdim(self, y, x0, x1, label, tick_y0, tick_y1):
        self.line(x0, tick_y0, x0, y - 2, THIN, 0.22)
        self.line(x1, tick_y1, x1, y - 2, THIN, 0.22)
        self.line(x0, y, x1, y, INK, 0.3)
        self.arrow(x0, y, 180)
        self.arrow(x1, y, 0)
        self.text((x0 + x1) / 2, y - 1.4, label, 2.8, anchor="middle")

    def render(self) -> str:
        return (
            f'<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{PAGE_W}mm" height="{PAGE_H}mm" '
            f'viewBox="0 0 {PAGE_W} {PAGE_H}">\n'
            f'  <rect width="{PAGE_W}" height="{PAGE_H}" fill="white"/>\n  '
            + "\n  ".join(self.p)
            + "\n</svg>\n"
        )


def side_elevation(d: Draw, ox: float, floor_y: float, dim_x: float) -> None:
    """Looking at the chair from its left. +Y (forward) is to the right."""

    def P(y: float, z: float) -> tuple[float, float]:
        return ox + y, floor_y - z

    d.line(*P(-95, 0), *P(95, 0), INK, 0.6)
    d.text(*P(-94, -5), "FLOOR", 2.6, THIN)

    # Drive wheel, with hub and centre lines.
    wx, wy = P(C.AXLE_Y, AXLE_Z)
    d.circle(wx, wy, WHEEL_R, INK, 0.45)
    d.circle(wx, wy, 5, THIN, 0.3)
    d.line(wx - WHEEL_R - 4, wy, wx + WHEEL_R + 4, wy, THIN, 0.22, "3,2")
    d.line(wx, wy - WHEEL_R - 4, wx, wy + WHEEL_R + 4, THIN, 0.22, "3,2")

    # Castor and its riser.
    cx, cy = P(C.CASTOR_Y, 0)
    d.circle(cx, cy - 9, 9, INK, 0.4)
    d.rect(cx - 10, floor_y - DECK_BOTTOM, 20, DECK_BOTTOM - 18, THIN, 0.3)

    # Deck.
    dx, dy = P(-C.DECK_L / 2, DECK_TOP)
    d.rect(dx, dy, C.DECK_L, C.DECK_T, INK, 0.5)

    # Side panel: raised armrest section at the rear, lower frame forward.
    d.poly(
        [
            P(PANEL_REAR_Y, DECK_TOP),
            P(PANEL_REAR_Y, ARM_TOP_Z),
            P(ARM_STEP_Y, ARM_TOP_Z),
            P(ARM_STEP_Y, FRONT_FRAME_Z),
            P(PANEL_FRONT_Y, FRONT_FRAME_Z),
            P(PANEL_FRONT_Y, DECK_TOP),
        ],
        INK,
        0.5,
    )

    # Seat on its cleats, and the backrest.
    sx, sy = P(PANEL_REAR_Y, SEAT_TOP_Z)
    d.rect(sx, sy, B.SEAT_D, B.MDF_T, INK, 0.45)
    d.rect(sx - 4, sy, B.MDF_T, 4, THIN, 0.3)  # cleat, end on
    bx, by = P(PANEL_REAR_Y - B.MDF_T, BACK_TOP_Z)
    d.rect(bx, by, B.MDF_T, BACK_TOP_Z - SEAT_TOP_Z, INK, 0.45)

    # Footplate.
    fx, fy = P(FOOT_Y0, FOOT_Z)
    d.rect(fx, fy, B.FOOT_D, B.MDF_T, INK, 0.45)
    d.line(*P(PANEL_FRONT_Y, DECK_TOP), *P(FOOT_Y0 + 2, FOOT_Z), THIN, 0.3)

    # Sensor bracket.
    d.rect(*P(BRACKET_FRONT_Y - C.BRACKET_FOOT_L, DECK_TOP + C.BRACKET_T),
           C.BRACKET_FOOT_L, C.BRACKET_T, INK, 0.45)
    d.rect(*P(BRACKET_ARM_Y, DECK_TOP + C.BRACKET_T),
           C.BRACKET_T, DECK_TOP + C.BRACKET_T - ARM_BOTTOM_Z, INK, 0.45)
    ux, uy = P(BRACKET_ARM_Y, ULTRASONIC_Z)
    d.circle(ux - 2, uy, 2.2, THIN, 0.3)
    d.text(ux - 7, uy + 1, "ultrasonic", 2.3, THIN, anchor="end")
    lx, ly = P(BRACKET_ARM_Y, SENSOR_Z)
    d.line(lx - 8, ly, lx, ly, THIN, 0.3)
    d.text(lx - 9, ly + 1, "line sensor", 2.3, THIN, anchor="end")

    # Dimensions, stepped out so they do not cross each other.
    for i, (z, label) in enumerate(
        [
            (FOOT_Z, f"footplate {FOOT_Z:.0f}"),
            (AXLE_Z, f"axle {AXLE_Z:.0f}"),
            (DECK_BOTTOM, f"deck underside {DECK_BOTTOM:.0f}"),
            (SEAT_TOP_Z, f"seat {SEAT_TOP_Z:.0f}"),
            (ARM_TOP_Z, f"armrest {ARM_TOP_Z:.0f}"),
            (BACK_TOP_Z, f"backrest top {BACK_TOP_Z:.0f}"),
        ]
    ):
        x = dim_x + i * 8
        d.vdim(x, floor_y, floor_y - z, label, ox - 80, ox + 76)

    d.hdim(floor_y + 14, *[P(-C.DECK_L / 2, 0)[0], P(C.DECK_L / 2, 0)[0]],
           f"deck {C.DECK_L:.0f}", floor_y, floor_y)
    d.hdim(floor_y + 24, P(PANEL_REAR_Y - B.MDF_T, 0)[0], P(FOOT_Y1, 0)[0],
           f"overall {FOOT_Y1 - PANEL_REAR_Y + B.MDF_T:.0f}", floor_y, floor_y)

    d.text(ox - 80, floor_y + 36, "SIDE ELEVATION", 4.2, INK, weight="bold")
    d.text(ox - 80, floor_y + 41, "looking from the chair's left; forward to the right", 2.6, THIN)


def front_elevation(d: Draw, ox: float, floor_y: float) -> None:
    """Looking at the chair head on."""

    def P(x: float, z: float) -> tuple[float, float]:
        return ox + x, floor_y - z

    d.line(*P(-80, 0), *P(80, 0), INK, 0.6)

    for side in (-1, 1):
        wx = side * WHEEL_X
        d.rect(*P(wx - WHEEL_W / 2, C.WHEEL_DIA), WHEEL_W, C.WHEEL_DIA, INK, 0.45)
        d.line(*P(wx, AXLE_Z + 6), *P(wx, AXLE_Z - 6), THIN, 0.22, "3,2")

    d.rect(*P(-C.DECK_W / 2, DECK_TOP), C.DECK_W, C.DECK_T, INK, 0.5)

    for side in (-1, 1):
        px = side * PANEL_X
        d.rect(*P(px - B.MDF_T / 2, ARM_TOP_Z), B.MDF_T, ARM_TOP_Z - DECK_TOP, INK, 0.45)

    d.rect(*P(-B.SEAT_W / 2, SEAT_TOP_Z), B.SEAT_W, B.MDF_T, INK, 0.45)
    d.rect(*P(-B.BACK_W / 2, BACK_TOP_Z), B.BACK_W, BACK_TOP_Z - SEAT_TOP_Z, THIN, 0.35)
    d.rect(*P(-B.FOOT_W / 2, FOOT_Z), B.FOOT_W, B.MDF_T, INK, 0.45)

    d.line(*P(0, -4), *P(0, BACK_TOP_Z + 6), THIN, 0.22, "4,2,1,2")

    track = 2 * WHEEL_X + WHEEL_W
    d.hdim(floor_y + 14, *[P(-WHEEL_X - WHEEL_W / 2, 0)[0], P(WHEEL_X + WHEEL_W / 2, 0)[0]],
           f"overall width {track:.0f}", floor_y, floor_y)
    d.hdim(floor_y + 24, P(-C.DECK_W / 2, 0)[0], P(C.DECK_W / 2, 0)[0],
           f"deck {C.DECK_W:.0f}", floor_y, floor_y)

    d.text(ox - 80, floor_y + 36, "FRONT ELEVATION", 4.2, INK, weight="bold")
    d.text(ox - 80, floor_y + 41, "backrest shown light, behind the seat", 2.6, THIN)


def title_block(d: Draw, x: float, y: float, w: float, h: float) -> None:
    d.rect(x, y, w, h, INK, 0.5)
    d.line(x, y + 9, x + w, y + 9, INK, 0.35)
    d.text(x + 2, y + 6.5, "MARGADARSHAK — GUIDED ASSISTIVE CHAIR, SCALE DEMONSTRATOR", 3.4,
           weight="bold")

    rows = [
        ("Scale", "1:1 on A3.  The model is 1:6 of a real wheelchair."),
        ("Material", "4 mm MDF throughout, except the wheels and castor."),
        ("Units", "Millimetres. Heights are above the floor."),
        ("Drive", f"2 × BO geared motor, {C.WHEEL_DIA:.0f} mm wheels, differential, castor at the front."),
        ("Mass", "≈ 600 g loaded."),
        ("Drawn from", "generate_chassis.py and generate_mdf_body_template.py"),
    ]
    for i, (k, v) in enumerate(rows):
        yy = y + 15 + i * 5.2
        d.text(x + 2, yy, k, 2.8, THIN)
        d.text(x + 26, yy, v, 2.8)


def notes(d: Draw, x: float, y: float) -> float:
    lines = [
        ("CRITICAL DIMENSIONS", True),
        (f"Ride height is set by the wheel: {C.WHEEL_DIA:.0f} mm dia gives a "
         f"{DECK_BOTTOM:.0f} mm deck underside.", False),
        ("A different wheel changes everything above it. Edit WHEEL_DIA and re-run both generators.", False),
        (f"Line sensor adjusts {DECK_TOP + C.SENSOR_SLOT_Z - C.SENSOR_SLOT_H / 2:.0f}–"
         f"{DECK_TOP + C.SENSOR_SLOT_Z + C.SENSOR_SLOT_H / 2:.0f} mm above the floor, by sliding in its slots.", False),
        ("Set it on the real track surface, not on the bench.", False),
        ("", False),
        ("ASSEMBLY", True),
        ("1  Castor and riser first. Check the deck sits level on the wheels before anything else.", False),
        ("2  Motors, zip-tied tight. A motor that can rotate in its mount makes the line following", False),
        ("   untunable, and you will blame the PID for a week.", False),
        ("3  Side panels with gussets inside the corners, square to the deck.", False),
        ("4  Seat cleats inside the panels, then the seat pan, then the backrest.", False),
        ("5  Sensor bracket last, screws left loose until the sensor height is set.", False),
        ("", False),
        ("Dry-fit the whole body with tape before any glue. MDF and wood glue give you ten seconds.", False),
    ]
    for i, (text, bold) in enumerate(lines):
        if not text:
            continue
        d.text(x, y + i * 3.9, text, 3.0 if bold else 2.7,
               INK if bold else THIN, weight="bold" if bold else "normal")
    return y + (len(lines) - 1) * 3.9


def main() -> int:
    d = Draw()
    d.rect(FRAME, FRAME, PAGE_W - 2 * FRAME, PAGE_H - 2 * FRAME, INK, 0.5)

    floor_y = 172.0
    side_elevation(d, ox=110.0, floor_y=floor_y, dim_x=190.0)
    front_elevation(d, ox=320.0, floor_y=floor_y)
    notes_bottom = notes(d, x=18.0, y=222.0)
    title_block(d, x=250.0, y=232.0, w=158.0, h=51.0)

    # Nothing may run off the sheet or into the frame.
    import re

    body = "\n".join(d.p)
    xs = [float(v) for v in re.findall(r'(?:x|cx|x1|x2)="(-?[\d.]+)"', body)]
    ys = [float(v) for v in re.findall(r'(?:y|cy|y1|y2)="(-?[\d.]+)"', body)]
    pts = [tuple(map(float, m)) for m in re.findall(r"[ML](-?[\d.]+),(-?[\d.]+)", body)]
    xs += [q[0] for q in pts]
    ys += [q[1] for q in pts]
    problems = []
    if max(xs) > PAGE_W - FRAME or min(xs) < FRAME:
        problems.append(f"drawing runs to x {min(xs):.0f}..{max(xs):.0f}, frame is {FRAME}..{PAGE_W - FRAME}")
    if max(ys) > PAGE_H - FRAME or min(ys) < FRAME:
        problems.append(f"drawing runs to y {min(ys):.0f}..{max(ys):.0f}, frame is {FRAME}..{PAGE_H - FRAME}")
    if notes_bottom > PAGE_H - FRAME - 4:
        problems.append(f"notes end at y {notes_bottom:.0f}, past the frame")
    if problems:
        print("Layout check failed:")
        for problem in problems:
            print(f"  ! {problem}")
        return 1
    print("Layout check passed: everything inside the frame.\n")

    path = OUT / "blueprint.svg"
    path.write_text(d.render(), encoding="utf-8")

    print("Assembled, above the floor:")
    for label, z in [
        ("footplate", FOOT_Z), ("axle", AXLE_Z), ("deck underside", DECK_BOTTOM),
        ("deck top", DECK_TOP), ("seat", SEAT_TOP_Z), ("armrest", ARM_TOP_Z),
        ("backrest top", BACK_TOP_Z),
    ]:
        print(f"  {label:16} {z:6.1f} mm   ({z * 6:4.0f} mm at 1:6)")
    print(f"\n  overall width    {2 * WHEEL_X + WHEEL_W:6.1f} mm")
    print(f"  overall length   {FOOT_Y1 - PANEL_REAR_Y + B.MDF_T:6.1f} mm")
    print(f"\nWrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
