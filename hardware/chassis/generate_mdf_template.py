#!/usr/bin/env python3
"""Generate a 1:1 drilling template for building the chassis out of MDF.

    python3 hardware/chassis/generate_mdf_template.py

Writes ``mdf_template.svg`` — an A4 sheet drawn at true size. Print it with
scaling **off**, check the ruler on the sheet with a real ruler, glue it to 4 mm
MDF with a stick of pritt, and drill through the crosses.

## What changes against the printed version

The 3D-printed deck uses slots to pass zip ties around the motors. A slot is
awkward to make by hand, so here each slot becomes **a pair of round holes** —
the tie goes down one and up the other, around the motor, and the result is
identical.

The printed bracket is one L-shaped piece. In MDF it is two flat pieces joined at
a right angle, because MDF cannot be bent and its edges will not hold a screw.

Dimensions come from ``generate_chassis.py``, so the two versions cannot drift
apart.
"""

from __future__ import annotations

import pathlib

import generate_chassis as C

MM = 1.0
PAGE_W, PAGE_H = 210.0, 297.0  # A4 portrait
MARGIN = 12.0

#: Hole for a zip tie to pass through 4 mm MDF.
ZIP_HOLE = 4.0
#: How far apart the two holes of a zip-tie pair sit, across the motor.
ZIP_PAIR_SPAN = 10.0

INK = "#1c5cab"
FAINT = "#9ec5f4"

OUT = pathlib.Path(__file__).resolve().parent


class Sheet:
    """A tiny SVG writer. True millimetres, no transforms, nothing clever."""

    def __init__(self) -> None:
        self.parts: list[str] = []

    def outline(self, x: float, y: float, w: float, h: float, label: str) -> None:
        self.parts.append(
            f'<rect x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" height="{h:.2f}" '
            f'fill="none" stroke="{INK}" stroke-width="0.4"/>'
        )
        self.parts.append(
            f'<text x="{x + 2:.2f}" y="{y - 2:.2f}" font-family="sans-serif" '
            f'font-size="3.5" fill="{INK}">{label}</text>'
        )

    def hole(self, x: float, y: float, diameter: float) -> None:
        """A circle at true size, with a cross through the centre to punch."""
        r = diameter / 2
        self.parts.append(
            f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{r:.2f}" fill="none" '
            f'stroke="{INK}" stroke-width="0.25"/>'
        )
        arm = r + 1.2
        self.parts.append(
            f'<path d="M{x - arm:.2f},{y:.2f} H{x + arm:.2f} M{x:.2f},{y - arm:.2f} '
            f'V{y + arm:.2f}" stroke="{INK}" stroke-width="0.18"/>'
        )

    def window(self, x: float, y: float, w: float, h: float) -> None:
        """A rectangular opening to cut out, drawn dashed."""
        self.parts.append(
            f'<rect x="{x - w / 2:.2f}" y="{y - h / 2:.2f}" width="{w:.2f}" height="{h:.2f}" '
            f'fill="none" stroke="{INK}" stroke-width="0.35" stroke-dasharray="2,1.5"/>'
        )

    def note(self, x: float, y: float, text: str, size: float = 3.0) -> None:
        self.parts.append(
            f'<text x="{x:.2f}" y="{y:.2f}" font-family="sans-serif" font-size="{size}" '
            f'fill="{INK}">{text}</text>'
        )

    def ruler(self, x: float, y: float) -> None:
        """A 100 mm scale bar. If this does not measure 100 mm, the print is wrong."""
        self.parts.append(
            f'<path d="M{x:.2f},{y:.2f} h100 M{x:.2f},{y - 2:.2f} v4 '
            f'M{x + 100:.2f},{y - 2:.2f} v4 M{x + 50:.2f},{y - 1.5:.2f} v3" '
            f'stroke="{INK}" stroke-width="0.4"/>'
        )
        for i in range(1, 10):
            self.parts.append(
                f'<path d="M{x + i * 10:.2f},{y - 1:.2f} v2" stroke="{FAINT}" stroke-width="0.3"/>'
            )
        self.note(x, y - 3.5, "Check this measures exactly 100 mm — print at 100%, no page scaling")

    def render(self) -> str:
        body = "\n  ".join(self.parts)
        return (
            f'<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{PAGE_W}mm" height="{PAGE_H}mm" '
            f'viewBox="0 0 {PAGE_W} {PAGE_H}">\n'
            f'  <rect width="{PAGE_W}" height="{PAGE_H}" fill="white"/>\n'
            f'  {body}\n</svg>\n'
        )


def deck_holes() -> tuple[list[tuple[float, float, float]], list[tuple[float, float]]]:
    """Every hole on the deck, in deck coordinates. Returns (holes, zip pairs)."""
    holes: list[tuple[float, float, float]] = []

    motor_half = C.MOTOR_BODY[1] / 2
    slot_centres = []
    for side in (-1, 1):
        for station in (0.30, 0.78):
            x = side * (7.0 + C.MOTOR_BODY[0] * station)
            for edge in (-1, 1):
                y = C.AXLE_Y + edge * (motor_half + 3.0)
                slot_centres.append((x, y))
                # A slot becomes two holes, side by side across the motor.
                for dx in (-ZIP_PAIR_SPAN / 2, ZIP_PAIR_SPAN / 2):
                    holes.append((x + dx, y, ZIP_HOLE))

    for dx in (-1, 1):
        for dy in (-1, 1):
            holes.append(
                (
                    dx * C.CASTOR_HOLE_PITCH / 2,
                    C.CASTOR_Y + dy * C.CASTOR_HOLE_PITCH / 2,
                    C.M3_CLEAR,
                )
            )

    for x in C.BRACKET_BOLT_X:
        holes.append((x, C.BRACKET_BOLT_Y, C.M3_CLEAR))

    nx = int((C.DECK_W - 2 * C.GRID_MARGIN) // C.GRID_PITCH)
    ny = int((C.DECK_L - 2 * C.GRID_MARGIN) // C.GRID_PITCH)
    for i in range(nx + 1):
        for j in range(ny + 1):
            x = -(nx * C.GRID_PITCH) / 2 + i * C.GRID_PITCH
            y = -(ny * C.GRID_PITCH) / 2 + j * C.GRID_PITCH
            if any(
                abs(x - sx) < C.ZIP_SLOT[0] / 2 + 4 and abs(y - sy) < C.ZIP_SLOT[1] / 2 + 4
                for sx, sy in slot_centres
            ):
                continue
            if (
                abs(y - C.WIRE_PORT_Y) < C.WIRE_PORT[1] / 2 + 8
                and abs(x) < C.WIRE_PORT[0] / 2 + 8
            ):
                continue
            if abs(y - C.CASTOR_Y) < C.CASTOR_HOLE_PITCH and abs(x) < C.CASTOR_HOLE_PITCH:
                continue
            if y > C.BRACKET_BOLT_Y - 10:
                continue
            holes.append((x, y, C.M3_CLEAR))

    return holes, slot_centres


def main() -> int:
    sheet = Sheet()

    # ---- deck ----------------------------------------------------------
    dx, dy = MARGIN, MARGIN + 6
    sheet.outline(dx, dy, C.DECK_W, C.DECK_L, f"DECK — {C.DECK_W:.0f} × {C.DECK_L:.0f} × 4 mm MDF")

    def to_page(x: float, y: float) -> tuple[float, float]:
        """Deck coords (+Y forward, origin centre) to page coords (+Y down)."""
        return dx + C.DECK_W / 2 + x, dy + C.DECK_L / 2 - y

    holes, _ = deck_holes()
    for x, y, d in holes:
        sheet.hole(*to_page(x, y), d)

    px, py = to_page(0, C.WIRE_PORT_Y)
    sheet.window(px, py, C.WIRE_PORT[0], C.WIRE_PORT[1])
    sheet.note(px - 14, py + 1, "cut out", 2.6)

    sheet.note(dx + C.DECK_W + 3, dy + 8, "FRONT", 3.2)
    sheet.parts.append(
        f'<path d="M{dx + C.DECK_W + 6:.2f},{dy + 11:.2f} v10 m-2.5,-10 l2.5,-3 l2.5,3" '
        f'fill="none" stroke="{INK}" stroke-width="0.4"/>'
    )

    # ---- bracket arm ---------------------------------------------------
    arm_h = C.BRACKET_DROP
    ax_, ay_ = MARGIN, dy + C.DECK_L + 11
    sheet.outline(ax_, ay_, C.DECK_W, arm_h, f"BRACKET ARM — {C.DECK_W:.0f} × {arm_h:.0f} × 4 mm")

    def arm_page(x: float, z: float) -> tuple[float, float]:
        """Bracket coords (z measured down from the deck's top face)."""
        return ax_ + C.DECK_W / 2 + x, ay_ + (C.BRACKET_T - z)

    for x in (-34, -12, 12, 34):
        for end in (-1, 1):
            sheet.hole(*arm_page(x, C.SENSOR_SLOT_Z + end * C.SENSOR_SLOT_H / 2), C.M3_CLEAR)
    sheet.note(
        ax_ + 2,
        arm_page(0, C.SENSOR_SLOT_Z)[1] + 1,
        "line sensor: drill both, file between them into a slot to adjust height",
        2.5,
    )

    ux, uy = arm_page(0, C.ULTRASONIC_Z)
    sheet.window(ux, uy, *C.MDF_WINDOW)
    sheet.note(ax_ + C.DECK_W / 2 + 26, uy - 1, "cut out —", 2.6)
    sheet.note(ax_ + C.DECK_W / 2 + 26, uy + 3.5, "cable-tie the HC-SR04 in", 2.6)

    # ---- bracket foot --------------------------------------------------
    fx_, fy_ = MARGIN, ay_ + arm_h + 11
    sheet.outline(
        fx_, fy_, C.DECK_W, C.BRACKET_FOOT_L,
        f"BRACKET FOOT — {C.DECK_W:.0f} × {C.BRACKET_FOOT_L:.0f} × 4 mm",
    )
    for x in C.BRACKET_BOLT_X:
        sheet.hole(
            fx_ + C.DECK_W / 2 + x,
            fy_ + C.BRACKET_FOOT_L - (C.DECK_L / 2 - C.BRACKET_BOLT_Y),
            C.M3_CLEAR,
        )

    sheet.ruler(MARGIN, PAGE_H - MARGIN - 6)
    sheet.note(
        MARGIN,
        PAGE_H - MARGIN,
        "Glue the arm to the foot at 90°, with wood glue and two small angle brackets.",
        2.8,
    )

    path = OUT / "mdf_template.svg"
    path.write_text(sheet.render(), encoding="utf-8")

    print(f"deck:         {C.DECK_W:.0f} × {C.DECK_L:.0f} mm, {len(holes)} holes + 1 cut-out")
    print(f"bracket arm:  {C.DECK_W:.0f} × {arm_h:.0f} mm, 8 holes + 1 window")
    print(f"bracket foot: {C.DECK_W:.0f} × {C.BRACKET_FOOT_L:.0f} mm, {len(C.BRACKET_BOLT_X)} holes")
    used_h = fy_ + C.BRACKET_FOOT_L + MARGIN
    print(f"\nsheet uses {used_h:.0f} of {PAGE_H:.0f} mm — {'fits A4' if used_h <= PAGE_H else 'TOO TALL'}")
    print(f"Wrote {path}")
    return 0 if used_h <= PAGE_H else 1


if __name__ == "__main__":
    raise SystemExit(main())
