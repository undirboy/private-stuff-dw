"""The terminal path network.

The chair does not map the building. The building tells the chair where it may
go, by way of a guide path laid into the floor. This module is the digital twin
of that physical path: nodes are places the chair can stop or turn, segments are
the stretches of guide line between them.

Keeping the map here, rather than in the chair, is deliberate. A chair that only
knows "follow the line, read the tag, obey the next instruction" has very little
that can go wrong, and nothing on board that needs recertifying when a gate is
renumbered.

Terminals have levels. At Dabolim and at Mopa you check in on one floor and board
from another, so a map that is only ever flat cannot describe a real journey.
Nodes therefore carry a ``level``, and the only way between two levels is a
:class:`Lift` — because the two other ways a building offers are stairs and an
escalator, and neither is a thing you put a seated passenger on.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

# A chair plus a passenger is ~0.75 m across. Two of them need clearance to pass
# without either driver flinching, so we call a lane 0.9 m.
LANE_WIDTH_M = 0.9

#: The furthest a chair may travel with no guide line under it, crossing a
#: surveyed break on heading and odometry alone.
#:
#: Short on purpose. Heading drifts and wheels slip, so the error grows with the
#: distance, and a chair that has quietly rotated a few degrees over two metres
#: arrives at the far side pointing past the line rather than at it. Two metres
#: covers an expansion joint, a fire-shutter track and a security threshold,
#: which is what this is for. A longer break is a floor-plan problem to fix with
#: tape, not a number to raise here.
MAX_DEAD_RECKONING_M = 2.0

#: Metres the chair actually drives on a lift segment: into the car, and out of
#: it at the far landing. The vertical travel is not driving and does not go in
#: here — the chair spends no battery being carried and its odometer does not
#: turn. Used for the default length of a lift segment where the survey has not
#: measured the landings.
LIFT_DRIVE_M = 4.0


class Zone(Enum):
    """Which side of security a place is on.

    This is not a routing hint, it is the law. A vehicle that has not been
    screened cannot be airside, and screening a wheelchair means a person
    inspecting it and swabbing it for explosive trace — not something a chair
    does to itself by driving through an archway.

    So the two zones are two fleets. A landside chair works the kerb, the
    check-in hall and the queue; an airside chair works the piers and the gates.
    Neither crosses, and the passenger crosses on foot or in a manual chair
    pushed by staff, which is what happens at every Indian airport today
    whatever is written in a proposal.
    """

    LANDSIDE = "landside"
    AIRSIDE = "airside"


class NodeKind(Enum):
    JUNCTION = "junction"
    GATE = "gate"
    DOCK = "dock"
    PICKUP = "pickup"
    WAYPOINT = "waypoint"
    #: A lift landing: the bit of floor outside the doors, on one level. A lift
    #: is a pair of these joined by a lift segment, not a node of its own, so
    #: that "which floor is the chair on" always has an answer.
    LIFT = "lift"


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

    #: No guide line, because the chair is not driving: it is standing still in a
    #: lift car being carried to another level. Set by the map rather than
    #: surveyed, and only ever on a lift segment.
    CARRIED = "carried_in_lift"


@dataclass(frozen=True)
class Lift:
    """A lift car: the one place in a journey where the chair is a passenger.

    Everything else in this package is about driving. A lift is not driving, and
    the difference matters because none of the usual arithmetic applies — the
    chair covers no ground, spends no battery on traction, and its wait is set by
    where the car happens to be and who else wants it rather than by any corridor
    width.

    ``call_s`` is the honest worst case rather than an average, and it is a
    constant on purpose. Modelling a lift controller properly means knowing where
    the car is, which needs an interface to the lift that an airport may or may
    not give us; until then a pessimistic constant makes the routing decision
    (gate upstairs or gate downstairs) come out on the safe side. A real
    interface would replace exactly this number and nothing else.

    ``capacity_chairs`` is one by default, and that is not timidity: a chair with
    a passenger and their bag fills a small lift car, and a second chair edging
    in is how somebody's foot gets caught in a closing door.
    """

    id: str
    #: Worst case seconds between pressing the call and the doors opening.
    call_s: float = 25.0
    #: Doors open, or doors close. Counted twice per ride.
    door_s: float = 6.0
    #: Seconds of vertical travel per level crossed.
    ride_s_per_level: float = 9.0
    #: How many chairs share a car. One, unless the survey says the car is big.
    capacity_chairs: int = 1


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

    ``level`` is which floor this is on, counting the one you arrive at by road
    as 0. It is an integer and not a height because nothing here needs metres of
    altitude; what it needs is "are these two places on the same floor", and
    getting that wrong is how a route walks a passenger into a stairwell.
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
    #: Which floor, with the road outside as 0. Two nodes on different levels can
    #: share an x and a y — a lift shaft is the obvious case — so ``level`` is
    #: part of a node's position, not a label on it.
    level: int = 0
    #: Which side of security. Defaults to landside, so a map that says nothing
    #: about security describes one zone, which is what it always meant.
    zone: Zone = Zone.LANDSIDE


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
    #: Longest break in the guide line on this segment, in metres.
    #:
    #: Real terminal floors are not continuous. Expansion joints, fire-shutter
    #: tracks and stainless security thresholds interrupt the line, and a chair
    #: that stopped dead at every one would be useless. So a chair is allowed to
    #: coast straight across a gap on heading and odometry alone.
    #:
    #: It is a property of the segment, surveyed, and not a global timeout, which
    #: is the distinction that matters. A blanket "coast two metres whenever the
    #: line disappears" cannot tell a surveyed expansion joint from a chair that
    #: has genuinely wandered off the path — and in the second case it coasts two
    #: metres further into whatever it wandered towards. Here the floor plan says
    #: where a gap is and how long it is, and a chair that loses the line
    #: anywhere else stops.
    gap_m: float = 0.0

    #: True where crossing this means being screened: the metal detector, the
    #: pat-down, the swab of the chair.
    #:
    #: No chair ever drives across one of these. It is in the map so that the two
    #: zones are known to be two ends of one journey, and so that
    #: :func:`margadarshak.router.plan` can refuse to cross it rather than
    #: quietly planning a route through a CISF post.
    screening: bool = False

    #: The lift car this segment is a ride in, or None for ordinary floor.
    #:
    #: A lift segment is a different kind of edge wearing the same shape: the
    #: chair enters it, waits, is carried, and leaves on another level. It is
    #: still an edge of the graph, which is the point — the router, the corridor
    #: reservations and the battery check all keep working, and none of them
    #: needs to know what a lift is.
    lift: Lift | None = None

    #: How many levels this segment crosses. Filled in by
    #: :meth:`TerminalMap.connect` from the two nodes, because a number the
    #: surveyor has to keep in step with the node levels by hand is a number that
    #: will one day disagree with them.
    levels_crossed: int = 0

    @property
    def is_lift(self) -> bool:
        return self.lift is not None

    @property
    def transit_s(self) -> float | None:
        """Seconds from arriving at the doors to leaving at the far landing.

        Call, doors open, the ride itself, doors close. None for floor segments,
        where the time is the length divided by a speed like any other.
        """
        if self.lift is None:
            return None
        return (
            self.lift.call_s
            + 2 * self.lift.door_s
            + self.lift.ride_s_per_level * max(1, self.levels_crossed)
        )

    @property
    def capacity(self) -> int:
        """How many chairs may occupy this segment at once.

        A single-lane segment is exclusive: one chair, one direction, no passing.
        Those are the segments that cause contention, so the width of a corridor
        is a routing input and not just a note on a drawing.

        A lift is set by the car and not by any width: a wide landing does not
        make the car bigger.
        """
        if self.lift is not None:
            return max(1, self.lift.capacity_chairs)
        return max(1, int(self.width_m // LANE_WIDTH_M))

    @property
    def may_dead_reckon(self) -> bool:
        """Is there a surveyed break in the line here at all?"""
        return self.gap_m > 0.0

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
        gap_m: float = 0.0,
        lift: Lift | None = None,
        screening: bool = False,
    ) -> Segment:
        """Lay a guide line between two nodes.

        Length defaults to the straight-line distance between them; pass it
        explicitly for a segment that curves, because the chair travels the line
        and not the chord.

        Pass ``lift`` to make this a ride rather than a drive. The guide is then
        :attr:`Guide.CARRIED` whatever was asked for — there is no line in a lift
        car to choose between — the number of levels crossed is read off the two
        nodes, and the length defaults to the few metres the chair drives getting
        in and out, because the straight-line distance between two landings in
        one shaft is zero and a zero-length segment divides badly.
        """
        for node_id in (a, b):
            if node_id not in self.nodes:
                raise ValueError(f"unknown node {node_id}")
        if a == b:
            raise ValueError(f"segment from {a} to itself")
        if self.segment_between(a, b) is not None:
            raise ValueError(f"segment {a}-{b} already exists")

        if length_m is None:
            length_m = LIFT_DRIVE_M if lift is not None else self.distance(a, b)

        segment = Segment(
            id=f"{a}~{b}",
            a=a,
            b=b,
            length_m=length_m,
            max_speed_mps=max_speed_mps,
            width_m=width_m,
            guide=Guide.CARRIED if lift is not None else guide,
            gap_m=gap_m,
            screening=screening,
            lift=lift,
            levels_crossed=abs(self.nodes[a].level - self.nodes[b].level),
        )
        self.segments[segment.id] = segment
        self._adjacency[a].append(segment.id)
        self._adjacency[b].append(segment.id)
        return segment

    # -- queries ---------------------------------------------------------

    def distance(self, a: str, b: str) -> float:
        """Straight-line distance between two nodes, in metres, along the floor.

        Horizontal only. Two landings in one lift shaft are zero metres apart by
        this measure and several seconds apart in practice, which is exactly the
        distinction :attr:`Segment.transit_s` exists to carry.
        """
        na, nb = self.nodes[a], self.nodes[b]
        return math.hypot(na.x - nb.x, na.y - nb.y)

    def zone_of(self, node_id: str) -> Zone:
        return self.nodes[node_id].zone

    def screening_points(self) -> list[Segment]:
        return [s for s in self.segments.values() if s.screening]

    def levels(self) -> list[int]:
        """Every floor this map describes, lowest first."""
        return sorted({node.level for node in self.nodes.values()})

    def lifts(self) -> list[Segment]:
        return [s for s in self.segments.values() if s.is_lift]

    @property
    def min_ride_s_per_level(self) -> float:
        """The quickest any lift here crosses one level.

        A lower bound, for the route planner's heuristic. Zero when the building
        is flat, which costs the planner nothing because it then never has a
        level to cross.
        """
        return min((s.lift.ride_s_per_level for s in self.lifts()), default=0.0)

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

        for segment in self.segments.values():
            if segment.gap_m <= 0.0:
                continue
            if segment.gap_m > MAX_DEAD_RECKONING_M:
                problems.append(
                    f"segment {segment.id} declares a {segment.gap_m:.1f} m break in the "
                    f"guide line, beyond the {MAX_DEAD_RECKONING_M:.1f} m a chair may "
                    f"cross on heading and odometry alone"
                )
            if segment.gap_m >= segment.length_m:
                problems.append(
                    f"segment {segment.id} is {segment.length_m:.1f} m long and declares a "
                    f"{segment.gap_m:.1f} m break, so there is no line on it to reacquire"
                )
            if segment.guide is Guide.RFID:
                problems.append(
                    f"segment {segment.id} is marked by sparse RFID, which is already "
                    f"dead reckoning between tags; declaring a gap on top of it is "
                    f"double-counting the distance travelled blind"
                )

        problems += self._level_problems()
        problems += self._zone_problems()

        docks = self.nodes_of_kind(NodeKind.DOCK)
        if not docks:
            problems.append("map has no dock, so chairs have nowhere to return to")
        else:
            reachable = self._reachable_from(docks[0].id)
            for node in self.nodes.values():
                if node.id not in reachable:
                    problems.append(f"node {node.id} is unreachable from dock {docks[0].id}")

        return problems

    def _level_problems(self) -> list[str]:
        """Everything that can be wrong about how this map changes floors.

        All of these are survey mistakes rather than software faults, and all of
        them are mistakes somebody will actually make: the drawing shows a ramp
        where there is a flight of stairs, a lift is drawn as a corridor, a
        landing has no tag on the floor.
        """
        problems: list[str] = []

        for segment in self.segments.values():
            a, b = self.nodes[segment.a], self.nodes[segment.b]
            climbs = a.level != b.level

            if climbs and not segment.is_lift:
                problems.append(
                    f"segment {segment.id} joins level {a.level} to level {b.level} "
                    f"without a lift. A guide line cannot climb: if there is a ramp "
                    f"here, survey its top and bottom on the same level; if there "
                    f"are stairs or an escalator, there is no route here at all"
                )
            if segment.is_lift and not climbs:
                problems.append(
                    f"segment {segment.id} is a lift ride that starts and ends on "
                    f"level {a.level}"
                )
            if segment.guide is Guide.CARRIED and not segment.is_lift:
                problems.append(
                    f"segment {segment.id} says the chair is carried along it but "
                    f"declares no lift, so nothing says what carries it"
                )
            if segment.is_lift and segment.gap_m > 0.0:
                problems.append(
                    f"segment {segment.id} is a lift ride and declares a "
                    f"{segment.gap_m:.1f} m break in the guide line, which is a "
                    f"measurement of a line that is not there"
                )
            if segment.is_lift:
                untagged = [n.id for n in (a, b) if n.tag_id is None]
                if untagged:
                    problems.append(
                        f"lift landing(s) {', '.join(untagged)} have no floor tag, so "
                        f"a chair leaving the car cannot confirm which level it is on"
                    )

        # One lift to a level with gates on it is a single point of failure that
        # strands the people least able to walk down. Worth saying out loud at
        # survey time, when adding the second lift to the plan is free.
        for level in self.levels():
            gates = [
                n
                for n in self.nodes_of_kind(NodeKind.GATE)
                if n.level == level
            ]
            if not gates:
                continue
            serving = [
                s
                for s in self.lifts()
                if level in (self.nodes[s.a].level, self.nodes[s.b].level)
            ]
            if not serving:
                continue  # unreachability is reported separately, and more plainly
            cars = {s.lift.id for s in serving}
            if len(cars) == 1:
                problems.append(
                    f"level {level} has {len(gates)} gate(s) and exactly one lift "
                    f"({sorted(cars)[0]}) reaching it, so a single lift out of "
                    f"service strands every passenger on that level"
                )

        return problems

    def _zone_problems(self) -> list[str]:
        """Everything that can be wrong about where security is.

        A survey that leaves security out does not produce a system that skips
        security. It produces a chair that drives at a CISF post.
        """
        problems: list[str] = []

        for segment in self.segments.values():
            a, b = self.nodes[segment.a], self.nodes[segment.b]
            crosses = a.zone is not b.zone
            if crosses and not segment.screening:
                problems.append(
                    f"segment {segment.id} runs from {a.zone.value} to {b.zone.value} "
                    f"and is not marked as a screening point. Nothing crosses that "
                    f"line unscreened: mark the archway, or the map is claiming a "
                    f"chair may drive around security"
                )
            if segment.screening and not crosses:
                problems.append(
                    f"segment {segment.id} is marked as a screening point but both "
                    f"ends are {a.zone.value}"
                )

        for zone in Zone:
            here = [n for n in self.nodes.values() if n.zone is zone]
            if not here:
                continue
            if not any(n.kind is NodeKind.DOCK for n in here):
                problems.append(
                    f"there are {len(here)} {zone.value} node(s) and no {zone.value} "
                    f"dock. Chairs cannot cross security, so each side of it needs "
                    f"its own fleet and somewhere to charge it"
                )

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
