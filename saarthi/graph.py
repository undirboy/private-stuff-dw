"""The terminal path network.

The chair does not map the building. The building tells the chair where it may
go, by way of a guide path laid into the floor. This module is the digital twin
of that physical path: nodes are places the chair can stop or turn, segments are
the stretches of guide line between them.

Keeping the map here, rather than in the chair, is deliberate. A chair that only
knows "follow the line, read the tag, obey the next instruction" has very little
that can go wrong, and nothing on board that needs recertifying when a gate is
renumbered.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

# A chair plus a passenger is ~0.75 m across. Two of them need clearance to pass
# without either driver flinching, so we call a lane 0.9 m.
LANE_WIDTH_M = 0.9


class NodeKind(Enum):
    JUNCTION = "junction"
    GATE = "gate"
    DOCK = "dock"
    PICKUP = "pickup"
    WAYPOINT = "waypoint"


class Guide(Enum):
    """How the path is physically marked on the floor.

    This is the decision that makes or breaks the build, so it is a property of
    each segment rather than a global assumption: a terminal will realistically
    be a mix.
    """

    #: Magnetic tape under the floor covering. Invisible, immune to lighting,
    #: immune to a polished granite finish, survives being walked on. The default
    #: everywhere it can be laid.
    MAGNETIC = "magnetic_tape"

    #: A painted or taped stripe read by a downward camera. Cheapest to lay and
    #: the easiest to demonstrate, but reflective terminal flooring and foot
    #: traffic both degrade it. Acceptable in back-of-house and on carpet.
    PAINTED = "painted_stripe"

    #: Sparse RFID tags with dead reckoning in between. Used where no continuous
    #: line may be laid at all, such as across a security lane or a fire shutter.
    RFID = "rfid_sparse"


@dataclass(frozen=True)
class Node:
    """A place the chair can be addressed to.

    ``tag_id`` is the floor tag physically present at this node. The chair
    confirms arrival by reading it; a node with no tag is dead-reckoned to and is
    therefore never a stopping point for a passenger.

    ``code`` and ``terminal`` are what a passenger is told: "Gate 4, Terminal 1".
    Both are explicit rather than parsed out of ``label`` or ``id``, because a
    cleverly derived gate number that is wrong sends somebody who cannot easily
    walk back to the wrong end of a building.
    """

    id: str
    kind: NodeKind
    x: float  # metres, terminal-local frame
    y: float
    label: str = ""
    tag_id: str | None = None
    #: The public identifier, as the departure board prints it: "4", "12A".
    code: str | None = None
    #: Which terminal this is in, where an airport has more than one.
    terminal: str | None = None


@dataclass(frozen=True)
class Segment:
    """A stretch of guide line between two nodes. Traversable in both directions."""

    id: str
    a: str
    b: str
    length_m: float
    max_speed_mps: float = 1.2
    width_m: float = 1.8
    guide: Guide = Guide.MAGNETIC

    @property
    def capacity(self) -> int:
        """How many chairs may occupy this segment at once.

        A single-lane segment is exclusive: one chair, one direction, no passing.
        Those are the segments that cause contention, so the width of a corridor
        is a routing input and not just a note on a drawing.
        """
        return max(1, int(self.width_m // LANE_WIDTH_M))

    def other_end(self, node_id: str) -> str:
        if node_id == self.a:
            return self.b
        if node_id == self.b:
            return self.a
        raise ValueError(f"segment {self.id} does not touch node {node_id}")


class TerminalMap:
    """The path network for one terminal."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.nodes: dict[str, Node] = {}
        self.segments: dict[str, Segment] = {}
        self._adjacency: dict[str, list[str]] = {}

    # -- construction ----------------------------------------------------

    def add(self, node: Node) -> Node:
        if node.id in self.nodes:
            raise ValueError(f"duplicate node {node.id}")
        self.nodes[node.id] = node
        self._adjacency[node.id] = []
        return node

    def connect(
        self,
        a: str,
        b: str,
        *,
        max_speed_mps: float = 1.2,
        width_m: float = 1.8,
        guide: Guide = Guide.MAGNETIC,
        length_m: float | None = None,
    ) -> Segment:
        """Lay a guide line between two nodes.

        Length defaults to the straight-line distance between them; pass it
        explicitly for a segment that curves, because the chair travels the line
        and not the chord.
        """
        for node_id in (a, b):
            if node_id not in self.nodes:
                raise ValueError(f"unknown node {node_id}")
        if a == b:
            raise ValueError(f"segment from {a} to itself")
        if self.segment_between(a, b) is not None:
            raise ValueError(f"segment {a}-{b} already exists")

        segment = Segment(
            id=f"{a}~{b}",
            a=a,
            b=b,
            length_m=length_m if length_m is not None else self.distance(a, b),
            max_speed_mps=max_speed_mps,
            width_m=width_m,
            guide=guide,
        )
        self.segments[segment.id] = segment
        self._adjacency[a].append(segment.id)
        self._adjacency[b].append(segment.id)
        return segment

    # -- queries ---------------------------------------------------------

    def distance(self, a: str, b: str) -> float:
        """Straight-line distance between two nodes, in metres."""
        na, nb = self.nodes[a], self.nodes[b]
        return math.hypot(na.x - nb.x, na.y - nb.y)

    def exits(self, node_id: str) -> list[tuple[str, Segment]]:
        """Every (neighbour, segment) leaving this node."""
        return [
            (self.segments[sid].other_end(node_id), self.segments[sid])
            for sid in self._adjacency[node_id]
        ]

    def segment_between(self, a: str, b: str) -> Segment | None:
        for sid in self._adjacency.get(a, ()):
            segment = self.segments[sid]
            if segment.other_end(a) == b:
                return segment
        return None

    def nodes_of_kind(self, kind: NodeKind) -> list[Node]:
        return [n for n in self.nodes.values() if n.kind == kind]

    @property
    def top_speed_mps(self) -> float:
        """Fastest any chair may travel anywhere on this map.

        The route planner's heuristic divides by this, so it must be an upper
        bound or the planner stops being optimal.
        """
        return max((s.max_speed_mps for s in self.segments.values()), default=1.0)

    # -- integrity -------------------------------------------------------

    def validate(self) -> list[str]:
        """Check the map for the mistakes that strand a passenger.

        Returns a list of problems, empty if the map is sound. Run this against
        the real terminal survey before anybody is asked to sit in the chair.
        """
        problems: list[str] = []

        orphans = [nid for nid, sids in self._adjacency.items() if not sids]
        problems += [f"node {nid} has no guide line to it" for nid in orphans]

        for node in self.nodes_of_kind(NodeKind.GATE) + self.nodes_of_kind(NodeKind.PICKUP):
            if node.tag_id is None:
                problems.append(
                    f"{node.kind.value} {node.id} has no floor tag, so arrival cannot be confirmed"
                )

        docks = self.nodes_of_kind(NodeKind.DOCK)
        if not docks:
            problems.append("map has no dock, so chairs have nowhere to return to")
        else:
            reachable = self._reachable_from(docks[0].id)
            for node in self.nodes.values():
                if node.id not in reachable:
                    problems.append(f"node {node.id} is unreachable from dock {docks[0].id}")

        return problems

    def _reachable_from(self, start: str) -> set[str]:
        seen = {start}
        frontier = [start]
        while frontier:
            current = frontier.pop()
            for neighbour, _ in self.exits(current):
                if neighbour not in seen:
                    seen.add(neighbour)
                    frontier.append(neighbour)
        return seen

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (
            f"<TerminalMap {self.name!r} "
            f"{len(self.nodes)} nodes, {len(self.segments)} segments>"
        )
