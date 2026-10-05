#!/usr/bin/env python3
"""Generate the printable chassis parts for one chair.

    python3 hardware/chassis/generate_chassis.py

Writes STL files next to this script, ready to upload to a printing service.

## The design principle: tolerate what we have not measured

Component dimensions here are from catalogue figures, not from calipers on the
actual parts. A chassis with exact holes for a motor that turns out to be two
millimetres different is scrap. So almost nothing is a precise fit:

- the motors are held by **zip ties through slots**, not by bolts through holes,
  which does not care about the motor's exact size;
- the deck carries a **grid of M3 clearance holes** so every board — ESP32,
  driver, RFID reader, battery — bolts down wherever it happens to fit;
- the sensor bracket uses **vertical slots**, so the line sensor's height above
  the floor is set by sliding it, which is the one dimension that has to be right
  and the one nobody gets right first time.

Measure the three figures under CHECK BEFORE PRINTING below, change them here,
and re-run. Everything is parametric.

## Coordinates

X is across the chair, Y is along it with +Y forward, Z is up. The origin is the
centre of the deck's top face.
"""

from __future__ import annotations

import pathlib

import numpy as np
import trimesh

# =============================================================== CHECK BEFORE PRINTING
# These three decide whether the parts fit. Measure them; do not trust the list.

#: Wheel outside diameter. Sets the whole ride height.
WHEEL_DIA = 65.0
#: BO motor gearbox body: length (along its own shaft axis), width, height.
MOTOR_BODY = (48.0, 23.0, 19.0)
#: Height of the motor's shaft axis above the bottom of its body.
MOTOR_AXIS_FROM_BASE = 9.5
# ====================================================================================

DECK_W = 110.0           # across the chair
DECK_L = 160.0           # along the chair
DECK_T = 4.0             # 4 mm so it does not flex between the wheels and castor

M3_CLEAR = 3.4           # clearance for an M3 screw
GRID_PITCH = 15.0        # hole grid spacing
GRID_MARGIN = 12.0       # keep the grid this far from the edges

AXLE_Y = -20.0           # drive axle, behind centre so the castor carries little
ZIP_SLOT = (14.0, 4.0)   # zip-tie slot: long across the motor, narrow along it

CASTOR_Y = 44.0          # castor mounting centre, kept clear of the bracket foot
CASTOR_HOLE_PITCH = 20.0 # square pattern of M3 holes — CHECK YOUR CASTOR

WIRE_PORT = (34.0, 22.0) # cable pass-through, width x depth
WIRE_PORT_Y = 15.0

BRACKET_T = 4.0
BRACKET_FOOT_L = 22.0    # how far the bracket's foot reaches back over the deck
BRACKET_DROP = 46.0      # how far the arm hangs below the deck's top face
SENSOR_SLOT_Z = -30.0    # centre of the line-sensor slots, relative to the deck top
SENSOR_SLOT_H = 16.0     # vertical adjustment range for the line sensor
ULTRASONIC_Z = -10.0     # centre of the ultrasonic bores
HCSR04_BORE = 16.4       # ultrasonic transducer can diameter, plus clearance
HCSR04_PITCH = 26.0      # centre to centre of the two cans

#: Where the sensor bracket bolts to the deck, measured from the deck centre.
BRACKET_BOLT_Y = DECK_L / 2 - 6.0
BRACKET_BOLT_X = (-40.0, -20.0, 0.0, 20.0, 40.0)

OUT = pathlib.Path(__file__).resolve().parent


def ride_height() -> float:
    """Height of the deck's underside above the floor."""
    return WHEEL_DIA / 2 - MOTOR_AXIS_FROM_BASE + MOTOR_BODY[2]


def peg(diameter: float, length: float, at, axis="z") -> trimesh.Trimesh:
    """A cylinder used as a cutting tool."""
    body = trimesh.creation.cylinder(radius=diameter / 2, height=length, sections=32)
    if axis == "y":
        body.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [1, 0, 0]))
    body.apply_translation(at)
    return body


def slab(size, at) -> trimesh.Trimesh:
    body = trimesh.creation.box(extents=size)
    body.apply_translation(at)
    return body


def cut(solid: trimesh.Trimesh, tools: list[trimesh.Trimesh]) -> trimesh.Trimesh:
    """Subtract everything in one operation — far quicker than one at a time."""
    if not tools:
        return solid
    return solid.difference(trimesh.util.concatenate(tools))


def build_deck() -> trimesh.Trimesh:
    """The main plate. Motors zip-tied underneath, everything else bolted on top."""
    deck = slab((DECK_W, DECK_L, DECK_T), (0, 0, -DECK_T / 2))
    tools: list[trimesh.Trimesh] = []

    # Zip-tie slots, two stations along each motor, one slot either side of the body.
    motor_half = MOTOR_BODY[1] / 2
    slot_centres = []
    for side in (-1, 1):
        for station in (0.30, 0.78):  # fractions along the motor body, from the centre out
            x = side * (7.0 + MOTOR_BODY[0] * station)
            for edge in (-1, 1):
                y = AXLE_Y + edge * (motor_half + 3.0)
                slot_centres.append((x, y))
                tools.append(slab((ZIP_SLOT[0], ZIP_SLOT[1], DECK_T * 3), (x, y, 0)))

    # Castor mount.
    for dx in (-1, 1):
        for dy in (-1, 1):
            tools.append(
                peg(
                    M3_CLEAR,
                    DECK_T * 3,
                    (dx * CASTOR_HOLE_PITCH / 2, CASTOR_Y + dy * CASTOR_HOLE_PITCH / 2, 0),
                )
            )

    # Cable pass-through.
    tools.append(slab((WIRE_PORT[0], WIRE_PORT[1], DECK_T * 3), (0, WIRE_PORT_Y, 0)))

    # Bolt holes along the front edge for the sensor bracket.
    for x in BRACKET_BOLT_X:
        tools.append(peg(M3_CLEAR, DECK_T * 3, (x, BRACKET_BOLT_Y, 0)))

    # The mounting grid. Skip anything that would land on a feature already cut.
    nx = int((DECK_W - 2 * GRID_MARGIN) // GRID_PITCH)
    ny = int((DECK_L - 2 * GRID_MARGIN) // GRID_PITCH)
    for i in range(nx + 1):
        for j in range(ny + 1):
            x = -(nx * GRID_PITCH) / 2 + i * GRID_PITCH
            y = -(ny * GRID_PITCH) / 2 + j * GRID_PITCH
            # The motors are underneath, so bolting a board above them is fine.
            # Only skip a hole that would break into a zip-tie slot.
            if any(
                abs(x - sx) < ZIP_SLOT[0] / 2 + 4 and abs(y - sy) < ZIP_SLOT[1] / 2 + 4
                for sx, sy in slot_centres
            ):
                continue
            if abs(y - WIRE_PORT_Y) < WIRE_PORT[1] / 2 + 8 and abs(x) < WIRE_PORT[0] / 2 + 8:
                continue  # over the cable port
            if abs(y - CASTOR_Y) < CASTOR_HOLE_PITCH and abs(x) < CASTOR_HOLE_PITCH:
                continue  # over the castor pattern
            if y > BRACKET_BOLT_Y - 10:
                continue  # over the bracket bolts
            tools.append(peg(M3_CLEAR, DECK_T * 3, (x, y, 0)))

    return cut(deck, tools)


def build_sensor_bracket() -> trimesh.Trimesh:
    """Front bracket: line sensor low down, ultrasonic facing forward.

    An L. The foot bolts to the deck's front edge; the arm hangs down to put the
    line sensor near the floor. The arm's slots are vertical so that height can be
    set by sliding, because the right gap between an IR array and the surface is
    found by trying, never by calculating.
    """
    foot = slab((DECK_W, BRACKET_FOOT_L, BRACKET_T), (0, -BRACKET_FOOT_L / 2, BRACKET_T / 2))
    arm = slab((DECK_W, BRACKET_T, BRACKET_DROP), (0, BRACKET_T / 2, -BRACKET_DROP / 2 + BRACKET_T))
    bracket = foot.union(arm)

    tools: list[trimesh.Trimesh] = []

    # Foot: bolts matching the deck's front edge holes. The foot's front face sits
    # on the deck's front edge, so this offset is measured back from there.
    bolt_offset = -(DECK_L / 2 - BRACKET_BOLT_Y)
    for x in BRACKET_BOLT_X:
        tools.append(peg(M3_CLEAR, BRACKET_T * 3, (x, bolt_offset, BRACKET_T / 2)))

    # Arm: vertical slots for the line sensor, as a slot plus rounded ends.
    slot_z = SENSOR_SLOT_Z
    for x in (-34, -12, 12, 34):
        tools.append(slab((M3_CLEAR, BRACKET_T * 4, SENSOR_SLOT_H), (x, BRACKET_T / 2, slot_z)))
        for end in (-1, 1):
            tools.append(
                peg(
                    M3_CLEAR,
                    BRACKET_T * 4,
                    (x, BRACKET_T / 2, slot_z + end * SENSOR_SLOT_H / 2),
                    axis="y",
                )
            )

    # Arm: two bores for the ultrasonic transducers, up near the deck.
    for side in (-1, 1):
        tools.append(
            peg(
                HCSR04_BORE,
                BRACKET_T * 4,
                (side * HCSR04_PITCH / 2, BRACKET_T / 2, ULTRASONIC_Z),
                axis="y",
            )
        )
    # and its board's mounting holes
    for side in (-1, 1):
        tools.append(
            peg(M3_CLEAR, BRACKET_T * 4, (side * 20.0, BRACKET_T / 2, ULTRASONIC_Z), axis="y")
        )

    return cut(bracket, tools)


def build_castor_riser(height: float) -> trimesh.Trimesh:
    """A packer under the castor, so the deck sits level.

    Print it at whatever ``ride_height()`` minus your castor's own height comes to.
    """
    block = slab((40.0, 40.0, height), (0, 0, height / 2))
    tools = []
    for dx in (-1, 1):
        for dy in (-1, 1):
            tools.append(
                peg(
                    M3_CLEAR,
                    height * 3,
                    (dx * CASTOR_HOLE_PITCH / 2, dy * CASTOR_HOLE_PITCH / 2, height / 2),
                )
            )
    # Hollow it out to save plastic and print time.
    tools.append(slab((22.0, 22.0, height * 3), (0, 0, height / 2)))
    return cut(block, tools)


def sensor_height_range() -> tuple[float, float]:
    """How high above the floor the line sensor can be set, in mm."""
    deck_top = ride_height() + DECK_T
    return (
        deck_top + SENSOR_SLOT_Z - SENSOR_SLOT_H / 2,
        deck_top + SENSOR_SLOT_Z + SENSOR_SLOT_H / 2,
    )


def check_geometry() -> list[str]:
    """Catch the clashes that only show up with the parts in your hand.

    The castor one is not hypothetical: an earlier version put the castor's
    mounting holes underneath the sensor bracket's foot, so the screws could not
    be reached once the bracket was on.
    """
    problems = []

    foot_back_edge = DECK_L / 2 - BRACKET_FOOT_L
    castor_front_hole = CASTOR_Y + CASTOR_HOLE_PITCH / 2
    if castor_front_hole > foot_back_edge:
        problems.append(
            f"castor hole at y={castor_front_hole:.1f} is under the bracket foot "
            f"(which starts at y={foot_back_edge:.1f}) — the screw cannot be reached"
        )

    arm_bottom = BRACKET_T - BRACKET_DROP
    floor = -(ride_height() + DECK_T)
    if arm_bottom - floor < 3.0:
        problems.append(
            f"bracket arm clears the floor by only {arm_bottom - floor:.1f} mm — it will scrape"
        )

    slot_bottom = SENSOR_SLOT_Z - SENSOR_SLOT_H / 2
    if slot_bottom - arm_bottom < 3.0:
        problems.append(
            f"only {slot_bottom - arm_bottom:.1f} mm of material below the sensor slots"
        )

    bore_top = ULTRASONIC_Z + HCSR04_BORE / 2
    slot_top = SENSOR_SLOT_Z + SENSOR_SLOT_H / 2
    if slot_top > ULTRASONIC_Z - HCSR04_BORE / 2:
        problems.append("the sensor slots run into the ultrasonic bores")
    if bore_top > BRACKET_T - 2:
        problems.append("the ultrasonic bores break out of the top of the arm")

    return problems


def lay_on_bed(mesh: trimesh.Trimesh, flip: bool = False) -> trimesh.Trimesh:
    """Orient a part the way it should be printed, and sit it on Z=0.

    The bracket is flipped so its foot is on the bed and the arm points upward.
    That way it is a flat base plus a vertical wall, which prints with no support
    at all. Left as modelled, a slicer rests it on the arm's bottom edge and the
    foot becomes a large overhang needing support that then has to be picked out
    of the sensor slots.
    """
    out = mesh.copy()
    if flip:
        out.apply_transform(trimesh.transformations.rotation_matrix(np.pi, [1, 0, 0]))
    out.apply_translation([0, 0, -out.bounds[0][2]])
    return out


def report(name: str, mesh: trimesh.Trimesh) -> None:
    extents = mesh.bounding_box.extents
    print(
        f"  {name:22} {extents[0]:6.1f} x {extents[1]:6.1f} x {extents[2]:5.1f} mm   "
        f"{mesh.volume / 1000:6.1f} cm3   "
        f"{'watertight' if mesh.is_watertight else 'NOT WATERTIGHT'}"
    )


def main() -> int:
    low, high = sensor_height_range()
    print(f"Ride height (deck underside above floor): {ride_height():.1f} mm")
    print(f"Castor riser needed: {ride_height():.1f} mm minus your castor's height")
    print(f"Line sensor adjustable {low:.0f}-{high:.0f} mm above the floor")
    print(f"Ultrasonic sits {ride_height() + DECK_T + ULTRASONIC_Z:.0f} mm up, facing forward\n")

    problems = check_geometry()
    if problems:
        print("Geometry check failed:")
        for problem in problems:
            print(f"  ! {problem}")
        return 1
    print("Geometry check passed: no clashes between the parts.\n")

    parts = {
        "deck": lay_on_bed(build_deck()),
        "sensor_bracket": lay_on_bed(build_sensor_bracket(), flip=True),
        "castor_riser_20mm": lay_on_bed(build_castor_riser(20.0)),
    }

    ok = True
    for name, mesh in parts.items():
        report(name, mesh)
        if not mesh.is_watertight:
            ok = False
        mesh.export(OUT / f"{name}.stl")

    total = sum(m.volume for m in parts.values()) / 1000
    print(f"\n  {'TOTAL':22} {total:33.1f} cm3 solid")
    print(f"  at 20% infill, roughly {total * 0.3 * 1.24:.0f} g of PLA")
    print(f"\nWrote {len(parts)} STL files to {OUT}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
