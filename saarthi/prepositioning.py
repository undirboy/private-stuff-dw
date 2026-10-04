"""Moving idle chairs to where the work is about to be.

A chair parked on its charger at the far end of the building is not much use to
somebody arriving at the kerb in four minutes. The flight schedule says roughly
when people will arrive and roughly how many will need help, so chairs can be
waiting rather than summoned.

This attacks the number that actually matters. Everything else in the system
shortens the journey; this shortens the wait before it starts, which is the part
passengers complain about and the part an airport is measured on.

The forecast is deliberately simple arithmetic over the flight schedule rather
than anything learned. Two reasons: there is no historic data yet, and a staffing
decision an operator cannot follow the reasoning of is a staffing decision they
will not trust. Once a pilot has produced real numbers, replace
``assistance_rate`` with a per-flight rate measured from them — that is a better
use of data than a model.
"""

from __future__ import annotations

from dataclasses import dataclass

from .flights import FlightBoard

#: Assistance requests expected per departing flight. A placeholder: measure it.
#: It varies enormously by route — a pilgrimage or a hospital-corridor route runs
#: far higher than a business shuttle — so a single number is a starting point
#: and nothing more.
DEFAULT_ASSISTANCE_RATE = 1.5

#: How far ahead of departure assistance passengers turn up. They are told to
#: come early, and they do.
DEFAULT_ARRIVAL_LEAD_S = 2 * 60 * 60

#: Where departing passengers first ask for a chair, as a share of all requests.
DEFAULT_PICKUP_WEIGHTS: dict[str, float] = {"kerb": 0.8, "sec_q": 0.2}

#: Do not strand a chair away from its charger below this.
MIN_STAGING_BATTERY_FRACTION = 0.45

#: Only move a chair if staging it saves at least this much response time.
#: Shuffling chairs around for five seconds of theoretical gain wastes battery
#: and looks, to anybody watching the floor, like the system is malfunctioning.
MIN_SAVING_S = 45.0


@dataclass(frozen=True)
class DemandPoint:
    """Expected requests at one pickup point over the forecast horizon."""

    node: str
    expected_requests: float


@dataclass(frozen=True)
class StagingMove:
    """A recommendation to park an idle chair somewhere more useful."""

    chair_id: str
    to_node: str
    serving: str
    saves_s: float

    def __str__(self) -> str:  # pragma: no cover - reporting aid
        return (
            f"{self.chair_id} -> {self.to_node} for {self.serving} "
            f"(saves {self.saves_s:.0f}s)"
        )


def forecast_demand(
    board: FlightBoard,
    now_s: float,
    *,
    horizon_s: float = 45 * 60,
    arrival_lead_s: float = DEFAULT_ARRIVAL_LEAD_S,
    assistance_rate: float = DEFAULT_ASSISTANCE_RATE,
    pickup_weights: dict[str, float] | None = None,
) -> list[DemandPoint]:
    """Expected assistance requests per pickup point over the next ``horizon_s``.

    A flight departing at T brings its assistance passengers to the kerb at
    roughly ``T - arrival_lead_s``. Count the flights whose passengers are due to
    arrive inside the horizon, and spread the expected requests across the
    pickup points.
    """
    weights = pickup_weights if pickup_weights is not None else DEFAULT_PICKUP_WEIGHTS

    expected_flights = 0.0
    for flight in board.flights():
        if flight.scheduled_departure_s is None:
            continue
        if not flight.status.accepts_passengers:
            continue
        arrive_at = flight.scheduled_departure_s - arrival_lead_s
        if now_s <= arrive_at < now_s + horizon_s:
            expected_flights += 1

    if expected_flights == 0:
        return []

    total = expected_flights * assistance_rate
    points = [
        DemandPoint(node=node, expected_requests=total * share)
        for node, share in weights.items()
        if share > 0
    ]
    points.sort(key=lambda p: (-p.expected_requests, p.node))
    return points


def plan_staging(
    fleet,
    demand: list[DemandPoint],
    staging_nodes: list[str],
    *,
    min_battery_fraction: float = MIN_STAGING_BATTERY_FRACTION,
    min_saving_s: float = MIN_SAVING_S,
) -> list[StagingMove]:
    """Work out which idle chairs to move, and where.

    Greedy, busiest demand point first: the heaviest expected load gets the chair
    that can respond to it quickest. Returns recommendations rather than acting,
    so an operator can see them, a test can assert on them, and a dashboard can
    show what the system is about to do before it does it.
    """
    if not demand:
        return []

    for node in staging_nodes:
        if node not in fleet.tmap.nodes:
            raise ValueError(f"unknown staging node {node}")

    resting = [
        chair
        for chair in fleet.chairs.values()
        if chair.available and chair.battery_fraction >= min_battery_fraction
    ]

    moves: list[StagingMove] = []
    spare_staging = list(staging_nodes)

    for point in demand:
        if not resting or not spare_staging:
            break

        # The best place to wait for this demand point.
        staged_times = [
            (fleet.travel_time(node, point.node), node)
            for node in spare_staging
            if fleet.travel_time(node, point.node) is not None
        ]
        if not staged_times:
            continue
        staged_time, staging_node = min(staged_times)

        # The chair that can get to that waiting place soonest.
        reachable = [
            (fleet.travel_time(chair.node, staging_node), chair)
            for chair in resting
            if fleet.travel_time(chair.node, staging_node) is not None
        ]
        if not reachable:
            continue
        _, chair = min(reachable, key=lambda item: (item[0], item[1].id))

        # Would moving it actually help?
        current_time = fleet.travel_time(chair.node, point.node)
        if current_time is None:
            continue
        saving = current_time - staged_time
        if saving < min_saving_s:
            continue

        moves.append(
            StagingMove(
                chair_id=chair.id,
                to_node=staging_node,
                serving=point.node,
                saves_s=saving,
            )
        )
        resting.remove(chair)
        spare_staging.remove(staging_node)

    return moves
