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
"""

from .boardingpass import BoardingPass, BoardingPassError
from .fleet import Chair, ChairState, Event, Fleet, Request, ScanRejected, SegmentReservations
from .flights import Flight, FlightBoard, FlightStatus
from .graph import Guide, Node, NodeKind, Segment, TerminalMap
from .router import Route, plan
from .terminal import build_example_terminal

__all__ = [
    "BoardingPass",
    "BoardingPassError",
    "Chair",
    "ChairState",
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
    "TerminalMap",
    "build_example_terminal",
    "plan",
]
