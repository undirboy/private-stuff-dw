"""Margadarshak: a guided assistive chair for terminals.

*Margadarshak* (मार्गदर्शक) is the one who shows the way — a guide rather than a
driver, which is exactly the distinction this system turns on. The chair does not
decide where to go. The building's guide path and the dispatcher do, and the
chair follows.

The design bet of this project is that an airport is not an unsolved robotics
problem. It is a building somebody owns, can survey, and can lay a guide path
into. A chair that follows that path needs no map of the world, no localisation
stack and no machine learning, which is what makes it cheap enough to deploy in
the airports that have the longest wheelchair queues and the smallest budgets.

    from margadarshak import Fleet, build_example_terminal

    tmap = build_example_terminal()
    fleet = Fleet(tmap)
    fleet.add_chair("CH-01", "dock_w")
    fleet.request_assistance("Mrs Pereira", "AI-612", pickup="kerb", gate="g4")
    fleet.run(duration_s=900)

The map tools live in :mod:`margadarshak.mapfile` and are imported from there, so that
``python3 -m margadarshak.mapfile map.json --validate`` runs cleanly for somebody who
is validating a map rather than writing code.
"""

from .announce import announce, say
from .boardingpass import BoardingPass, BoardingPassError
from .dashboard import render_dashboard
from .fleet import (
    CallPoint,
    Chair,
    ChairState,
    Event,
    Fleet,
    Request,
    ScanRejected,
    SegmentReservations,
)
from .flights import Flight, FlightBoard, FlightStatus
from .graph import Guide, Node, NodeKind, Segment, TerminalMap
from .prepositioning import DemandPoint, StagingMove, forecast_demand, plan_staging
from .router import Route, plan
from .screen import ScreenContent, screen_for
from .terminal import build_example_terminal

__all__ = [
    "BoardingPass",
    "BoardingPassError",
    "CallPoint",
    "Chair",
    "ChairState",
    "DemandPoint",
    "Event",
    "Fleet",
    "Flight",
    "FlightBoard",
    "FlightStatus",
    "Guide",
    "Node",
    "NodeKind",
    "Request",
    "Route",
    "ScanRejected",
    "ScreenContent",
    "Segment",
    "SegmentReservations",
    "StagingMove",
    "TerminalMap",
    "announce",
    "build_example_terminal",
    "forecast_demand",
    "plan",
    "plan_staging",
    "render_dashboard",
    "say",
    "screen_for",
]
