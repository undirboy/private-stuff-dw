"""Saarthi: a guided assistive chair for terminals.

*Saarthi* (सारथी) is the charioteer — the one who drives so the passenger does not
have to.

The design bet of this project is that an airport is not an unsolved robotics
problem. It is a building somebody owns, can survey, and can lay a guide path
into. A chair that follows that path needs no map of the world, no localisation
stack and no machine learning, which is what makes it cheap enough to deploy in
the airports that have the longest wheelchair queues and the smallest budgets.

    from saarthi import Fleet, build_example_terminal

    tmap = build_example_terminal()
    fleet = Fleet(tmap)
    fleet.add_chair("CH-01", "dock_w")
    fleet.request_assistance("Mrs Pereira", "AI-612", pickup="kerb", gate="g4")
    fleet.run(duration_s=900)

The map tools live in :mod:`saarthi.mapfile` and are imported from there, so that
``python3 -m saarthi.mapfile map.json --validate`` runs cleanly for somebody who
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
]
