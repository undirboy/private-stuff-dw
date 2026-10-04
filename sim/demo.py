#!/usr/bin/env python3
"""A scripted shift, printed as a timeline.

This is the laptop demo. It runs the whole dispatcher against the example
terminal and narrates what the fleet does, including the four things that are
hard to show with a model chair on a table:

- a passenger scans a boarding pass and says nothing else at all;
- their gate is not announced yet, so they are taken to the lounge and a chair
  comes back for them when it is;
- the airline moves a gate while a chair is already carrying someone;
- a corridor is closed under a chair that is part way along it.

    python3 -m sim.demo
"""

from __future__ import annotations

import sys

from saarthi import Fleet, FlightBoard, FlightStatus, ScanRejected, build_example_terminal
from saarthi.boardingpass import encode


def banner(text: str) -> None:
    print()
    print(f"--- {text} " + "-" * max(0, 66 - len(text)))


def boarding_pass(family: str, given: str, title: str, pnr: str, carrier: str, number: str) -> str:
    return encode(
        family_name=family,
        given_name=given,
        title=title,
        pnr=pnr,
        origin="GOI",
        destination="BOM",
        carrier=carrier,
        flight_number=number,
        day_of_year=280,
        seat="012A",
        sequence_number="0043",
    )


def main() -> int:
    tmap = build_example_terminal()

    problems = tmap.validate()
    if problems:
        print("Map validation failed:")
        for problem in problems:
            print(f"  ! {problem}")
        return 1
    print(f"Map: {tmap.name} — {len(tmap.nodes)} nodes, {len(tmap.segments)} segments, validated.")

    board = FlightBoard()
    board.upsert("AI612", status=FlightStatus.GATE_ASSIGNED, gate="g4")
    board.upsert("6E204", status=FlightStatus.GATE_ASSIGNED, gate="g1")
    board.upsert("SG118", status=FlightStatus.SCHEDULED)  # gate not announced yet
    board.upsert("UK880", status=FlightStatus.GATE_ASSIGNED, gate="g5")

    fleet = Fleet(tmap, board=board, holding_area="lounge")
    fleet.add_chair("CH-01", "dock_w")
    fleet.add_chair("CH-02", "dock_w")
    # A chair held back for frail passengers, capped to a gentler walking pace.
    fleet.add_chair("CH-03", "dock_e", speed_cap_mps=0.8)

    banner("Two passengers scan at the kerb. They say nothing and type nothing")
    fleet.scan_boarding_pass(
        boarding_pass("PEREIRA", "MARIA", "MRS", "ABC123", "AI", "612"), pickup="kerb"
    )
    fleet.scan_boarding_pass(
        boarding_pass("NAIK", "SURESH", "MR", "XYZ789", "6E", "204"), pickup="kerb"
    )
    fleet.run(duration_s=120)

    banner("A third scans, but her gate has not been announced yet")
    fleet.scan_boarding_pass(
        boarding_pass("FERNANDES", "ANA", "MS", "QQQ111", "SG", "118"), pickup="kerb"
    )

    banner("Someone scans a pass for a flight that is not on today's board")
    try:
        fleet.scan_boarding_pass(
            boarding_pass("KHAN", "IMRAN", "MR", "ZZZ000", "AI", "999"), pickup="kerb"
        )
    except ScanRejected as rejected:
        print(f"  chair screen: {rejected.message}")
        print(f"  logged as:    {rejected.reason}")

    banner("The airline moves a gate while a chair is already carrying someone")
    fleet.run(duration_s=180)  # Mrs Pereira is now out on the spine, bound for g4
    board.assign_gate("AI612", "g2")
    fleet.run(duration_s=420)

    banner("SG118 finally gets a gate. A chair goes back to the lounge for her")
    board.assign_gate("SG118", "g5")
    fleet.run(duration_s=600)

    banner("A spill closes the spine under a chair that is already carrying someone")
    fleet.scan_boarding_pass(
        boarding_pass("SHAIKH", "FARID", "MR", "PPP222", "UK", "880"), pickup="sec_q"
    )
    fleet.run(duration_s=200)
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
    print(f"  journeys served     {summary['delivered']}/{summary['requests']}")
    print(f"  mean wait for chair {summary['mean_wait_s']:.0f} s")
    print(f"  worst wait          {summary['worst_wait_s']:.0f} s")
    print(f"  attendant call-outs {summary['escalations']}")
    print()
    for chair in fleet.chairs.values():
        print(
            f"  {chair.id}  {chair.state.value:<10} at {chair.node:<8} "
            f"battery {chair.battery_fraction:.0%}"
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
