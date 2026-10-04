"""Route planning over the guide network.

A* on the path graph, with time as the cost. Time rather than distance because a
chair is slowed to walking pace through a crowded security hall and runs at full
speed down an empty pier, so the shortest route is routinely not the quickest.

Turns carry a penalty. A chair that pivots at a junction has to slow, rotate and
reacquire the line, which costs real seconds and is unpleasant for the passenger.
Without the penalty the planner cheerfully returns zig-zag routes that are a
metre shorter and far worse to ride.
"""

from __future__ import annotations

import heapq
import math
from dataclasses import dataclass, field

from .graph import Segment, TerminalMap

#: Seconds lost to a full stop-rotate-reacquire at a junction.
TURN_PENALTY_S = 4.0

#: A heading change below this is taken at speed and costs nothing.
TURN_DEADBAND_RAD = math.radians(25)


@dataclass(frozen=True)
class Route:
    """A planned journey: the nodes to visit and the segments between them."""

    nodes: list[str]
    segments: list[str]
    distance_m: float
    duration_s: float

    def __len__(self) -> int:
        return len(self.segments)

    @property
    def origin(self) -> str:
        return self.nodes[0]

    @property
    def destination(self) -> str:
        return self.nodes[-1]


@dataclass(order=True)
class _Candidate:
    priority: float
    cost_so_far: float = field(compare=False)
    node: str = field(compare=False)
    came_from: str | None = field(compare=False)
    path: list[str] = field(compare=False, default_factory=list)
    segments: list[str] = field(compare=False, default_factory=list)


def _heading(tmap: TerminalMap, frm: str, to: str) -> float:
    a, b = tmap.nodes[frm], tmap.nodes[to]
    return math.atan2(b.y - a.y, b.x - a.x)


def _turn_cost(tmap: TerminalMap, came_from: str | None, at: str, going_to: str) -> float:
    """Seconds added for the heading change at ``at``."""
    if came_from is None:
        return 0.0
    incoming = _heading(tmap, came_from, at)
    outgoing = _heading(tmap, at, going_to)
    change = abs(math.atan2(math.sin(outgoing - incoming), math.cos(outgoing - incoming)))
    if change <= TURN_DEADBAND_RAD:
        return 0.0
    # Proportional to the angle: a gentle bend costs less than a reversal.
    return TURN_PENALTY_S * (change / math.pi)


def traverse_time(segment: Segment, speed_cap_mps: float | None = None) -> float:
    """Seconds to drive a segment end to end."""
    speed = segment.max_speed_mps
    if speed_cap_mps is not None:
        speed = min(speed, speed_cap_mps)
    return segment.length_m / speed


def plan(
    tmap: TerminalMap,
    start: str,
    goal: str,
    *,
    blocked_segments: frozenset[str] = frozenset(),
    speed_cap_mps: float | None = None,
) -> Route | None:
    """Quickest route from ``start`` to ``goal``, or None if there is no way through.

    ``blocked_segments`` is how a spillage, a queue barrier or another chair's
    reservation is fed back into planning: the corridor is simply not in the
    graph for this call.

    ``speed_cap_mps`` caps the chair's own speed everywhere, used to slow a chair
    carrying a frail passenger without editing the map.
    """
    if start not in tmap.nodes or goal not in tmap.nodes:
        raise ValueError(f"route endpoints must be on the map: {start} -> {goal}")
    if start == goal:
        return Route(nodes=[start], segments=[], distance_m=0.0, duration_s=0.0)

    top_speed = tmap.top_speed_mps
    if speed_cap_mps is not None:
        top_speed = min(top_speed, speed_cap_mps)

    def heuristic(node: str) -> float:
        # Straight-line time at the best speed available: never an overestimate,
        # so A* stays optimal.
        return tmap.distance(node, goal) / top_speed

    open_set: list[_Candidate] = [
        _Candidate(
            priority=heuristic(start),
            cost_so_far=0.0,
            node=start,
            came_from=None,
            path=[start],
            segments=[],
        )
    ]
    # Keyed on (node, arrived-from) because the cheapest way onward depends on
    # the heading we arrive with.
    best: dict[tuple[str, str | None], float] = {(start, None): 0.0}

    while open_set:
        current = heapq.heappop(open_set)

        if current.node == goal:
            distance = sum(tmap.segments[s].length_m for s in current.segments)
            return Route(
                nodes=current.path,
                segments=current.segments,
                distance_m=distance,
                duration_s=current.cost_so_far,
            )

        state = (current.node, current.came_from)
        if current.cost_so_far > best.get(state, math.inf):
            continue

        for neighbour, segment in tmap.exits(current.node):
            if segment.id in blocked_segments:
                continue
            if neighbour == current.came_from:
                continue  # never immediately reverse down the segment just driven

            step = traverse_time(segment, speed_cap_mps)
            step += _turn_cost(tmap, current.came_from, current.node, neighbour)
            cost = current.cost_so_far + step

            next_state = (neighbour, current.node)
            if cost >= best.get(next_state, math.inf):
                continue
            best[next_state] = cost

            heapq.heappush(
                open_set,
                _Candidate(
                    priority=cost + heuristic(neighbour),
                    cost_so_far=cost,
                    node=neighbour,
                    came_from=current.node,
                    path=current.path + [neighbour],
                    segments=current.segments + [segment.id],
                ),
            )

    return None
