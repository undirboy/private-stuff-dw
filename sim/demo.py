#!/usr/bin/env python3
"""A scripted shift, printed as a timeline.

This is the laptop demo. It runs the whole dispatcher against the example
terminal and narrates what the fleet does, including the three things that are
hard to show with a model chair on a table: a gate change mid-journey, a corridor
closed under a chair's wheels, and two chairs meeting in a single-file corridor.

    python3 -m sim.demo
"""

from __future__ import annotations

import sys

from saarthi import Fleet, build_example_terminal


def banner(text: str) -> None:
    print()
    print(f"--- {text} " + "-" * max(0, 62 - len(text)))


def main() -> int:
    tmap = build_example_terminal()

    problems = tmap.validate()
    if problems:
        print("Map validation failed:")
        for problem in problems:
            print(f"  ! {problem}")
        return 1
    print(f"Map: {tmap.name} — {len(tmap.nodes)} nodes, {len(tmap.segments)} segments, validated.")

    fleet = Fleet(tmap)
    fleet.add_chair("CH-01", "dock_w")
    fleet.add_chair("CH-02", "dock_w")
    # A chair held back for frail passengers, capped to a gentler walking pace.
    fleet.add_chair("CH-03", "dock_e", speed_cap_mps=0.8)

    banner("Morning rush: three passengers, three chairs")
    fleet.request_assistance("Mrs Pereira", "AI-612", pickup="kerb", gate="g4")
    fleet.request_assistance("Mr Naik", "6E-204", pickup="kerb", gate="g1")
    fleet.run(duration_s=120)

    fleet.request_assistance("Ms Fernandes", "SG-118", pickup="lounge", gate="g5")
    fleet.run(duration_s=180)

    banner("The airline moves a gate while a passenger is already on the way")
    fleet.gate_changed("AI-612", "g2")
    fleet.run(duration_s=240)

    banner("A spill closes the spine under a chair that is already carrying someone")
    fleet.request_assistance("Mr Shaikh", "UK-880", pickup="sec_q", gate="g5")
    fleet.run(duration_s=180)  # let him board and get out onto the spine
    fleet.block_segment("sp2~sp3", "cleaning in progress")
    fleet.run(duration_s=420)
    fleet.clear_segment("sp2~sp3")

    banner("Chairs return themselves to the docks")
    fleet.run(duration_s=900)

    banner("Timeline")
    for event in fleet.events:
        print(event)

    banner("Shift summary")
    summary = fleet.summary()
    print(f"  requests served     {summary['delivered']}/{summary['requests']}")
    print(f"  mean wait for chair {summary['mean_wait_s']:.0f} s")
    print(f"  worst wait          {summary['worst_wait_s']:.0f} s")
    print(f"  attendant call-outs {summary['escalations']}")
    print()
    for chair in fleet.chairs.values():
        print(f"  {chair.id}  {chair.state.value:<10} at {chair.node:<8} battery {chair.battery_fraction:.0%}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
