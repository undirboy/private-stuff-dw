#!/usr/bin/env python3
"""A scripted shift, printed as a timeline and written out as a dashboard.

This is the laptop demo. It runs the whole dispatcher against the example
terminal and narrates what the fleet does, covering the things that are hard to
show with a model chair on a table:

- a passenger scans a boarding pass and says nothing else at all;
- their gate is not announced yet, so they are taken to the lounge and a chair
  comes back for them when it is;
- the airline moves a gate while a chair is already carrying someone;
- a family travels together as one caravan rather than three separate rides;
- somebody presses a call button at a gate and is collected;
- idle chairs move towards the kerb before the rush, from the flight schedule;
- a corridor is closed under a chair that is part way along it.

    python3 -m sim.demo

Writes ``shift.html`` next to the repository root: open it to see the shift the
way an airport operator would want to.
"""

from __future__ import annotations

import pathlib
import sys

from saarthi import (
    Fleet,
    FlightBoard,
    FlightStatus,
    ScanRejected,
    build_example_terminal,
    forecast_demand,
    plan_staging,
    render_dashboard,
)
from saarthi.announce import DISPLAY_ORDER
from saarthi.boardingpass import encode
from saarthi.screen import screen_for

HOUR = 60 * 60


def banner(text: str) -> None:
    print()
    print(f"--- {text} " + "-" * max(0, 68 - len(text)))


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
    board.upsert("AI612", status=FlightStatus.GATE_ASSIGNED, gate="g4",
                 scheduled_departure_s=2 * HOUR + 15 * 60)
    board.upsert("6E204", status=FlightStatus.GATE_ASSIGNED, gate="g1",
                 scheduled_departure_s=2 * HOUR + 20 * 60)
    board.upsert("SG118", status=FlightStatus.SCHEDULED,
                 scheduled_departure_s=2 * HOUR + 40 * 60)
    board.upsert("UK880", status=FlightStatus.GATE_ASSIGNED, gate="g5",
                 scheduled_departure_s=3 * HOUR)

    fleet = Fleet(tmap, board=board, holding_area="lounge")
    for chair_id in ("CH-01", "CH-02", "CH-03", "CH-04"):
        fleet.add_chair(chair_id, "dock_e")
    # One chair capped to a gentler pace, held back for frail passengers.
    fleet.chairs["CH-04"].speed_cap_mps = 0.8

    fleet.register_call_point("g3", label="Gate 3", default_destination=None)
    fleet.register_call_point("lounge", label="Assistance lounge", default_destination="kerb")

    banner("Before the rush: chairs move towards where the work will be")
    demand = forecast_demand(board, fleet.now, horizon_s=45 * 60)
    for point in demand:
        print(f"  forecast {point.expected_requests:.1f} requests at {point.node}")
    moves = plan_staging(fleet, demand, staging_nodes=["sec_q", "sp1"])
    for move in moves:
        print(f"  {move}")
    fleet.apply_staging(moves)
    fleet.run(duration_s=420)

    banner("Two passengers scan at the kerb. They say nothing and type nothing")
    fleet.scan_boarding_pass(
        boarding_pass("PEREIRA", "MARIA", "MRS", "ABC123", "AI", "612"), pickup="kerb"
    )
    fleet.scan_boarding_pass(
        boarding_pass("NAIK", "SURESH", "MR", "XYZ789", "6E", "204"), pickup="kerb"
    )

    banner("What the chair's screen shows after a scan")
    fleet.run(duration_s=170)  # Mrs Pereira is aboard and under way
    content = screen_for(fleet, fleet.chairs["CH-01"])
    for language in DISPLAY_ORDER:
        print(f"  [{language:3}] " + "  /  ".join(content.lines(language)))

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
    board.assign_gate("AI612", "g2")
    print("  screen now reads: " + screen_for(fleet, fleet.chairs["CH-01"]).primary["en"])
    fleet.run(duration_s=480)

    banner("SG118 finally gets a gate. A chair goes back to the lounge for her")
    board.assign_gate("SG118", "g5")
    fleet.run(duration_s=900)

    banner("A family of three travels together, as one caravan")
    fleet.request_group(
        ["Mr Shaikh", "Mrs Shaikh", "Master Shaikh"], "UK880", pickup="kerb", gate="g5"
    )
    fleet.run(duration_s=240)

    banner("A spill closes the spine under a chair that is already carrying someone")
    fleet.block_segment("sp2~sp3", "cleaning in progress")
    fleet.run(duration_s=600)
    fleet.clear_segment("sp2~sp3")
    fleet.run(duration_s=600)

    banner("Someone at Gate 3 presses the call button")
    stranded = fleet.press_call_button("g3", passenger="Mr Dias")
    fleet.run(duration_s=600)
    print("  chair is here, waiting to be told where to go:")
    print(f"  {announce('welcome', name='Mr Dias')['kok']}")
    fleet.set_destination(stranded, "kerb")
    fleet.run(duration_s=1200)

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
            f"  {chair.id}  {chair.state.value:<12} at {chair.node:<8} "
            f"battery {chair.battery_fraction:.0%}"
        )

    out = render_dashboard(
        fleet,
        pathlib.Path(__file__).resolve().parent.parent / "shift.html",
        title="Morning shift — example terminal",
    )
    print(f"\nDashboard written to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
