"""Moving idle chairs to where the work is about to be.

A chair parked on its charger at the far end of the building is not much use to
somebody arriving at the kerb in four minutes. The flight schedule says roughly
when people will arrive and roughly how many will need help, so chairs can be
waiting rather than summoned.

This attacks the number that actually matters. Everything else in the system
shortens the journey; this shortens the wait before it starts, which is the part
passengers complain about and the part an airport is measured on.

How many people a flight brings is the one number this depends on, and for a
long time it was a constant: 1.5 requests per departure, every flight, which is
plainly wrong for a board carrying both a business shuttle and a Gulf labour
route. :mod:`margadarshak.demand` now estimates it per flight from departures
already flown, and :func:`forecast_demand` takes that estimator as
``rate_model``.

The default is still the constant, and deliberately so. With no history there is
nothing to learn from, and the honest cold start is a documented guess rather
than a model fitted to somebody else's airport. Pass a fitted
:class:`~margadarshak.demand.LearnedRate` once a pilot has produced real numbers;
``sim/backtest.py`` is the harness that says whether doing so actually shortens
the wait.

The arithmetic from the schedule to a staging move stays simple and stays
inspectable: an operator can follow every step from "these flights depart soon"
to "so that chair moves there", and :meth:`StagingMove` says what it saves.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .demand import PRIOR_RATE, RateModel
from .flights import FlightBoard

#: Assistance requests expected per departing flight when nothing has been
#: measured yet. It varies enormously by route — a pilgrimage or a
#: hospital-corridor route runs far higher than a business shuttle — so a single
#: number is a cold start and nothing more. Pass ``rate_model`` to replace it
#: with a rate learned per flight; see :mod:`margadarshak.demand`.
DEFAULT_ASSISTANCE_RATE = PRIOR_RATE

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

#: Never strand more than this share of the resting fleet away from a charger.
#: Chargers are the one thing an airport cannot improvise at two in the
#: afternoon, and a fleet that is entirely out on the floor at eleven is a fleet
#: that is entirely flat by three. Staging is a bet on a forecast; this is the
#: size of the bet.
MAX_STAGED_FRACTION = 0.5


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
    rate_model: RateModel | None = None,
    pickup_weights: dict[str, float] | None = None,
) -> list[DemandPoint]:
    """Expected assistance requests per pickup point over the next ``horizon_s``.

    A flight departing at T brings its assistance passengers to the kerb at
    roughly ``T - arrival_lead_s``. Take the flights whose passengers are due to
    arrive inside the horizon, add up how many chairs each is expected to need,
    and spread the total across the pickup points.

    ``rate_model`` supplies that per-flight number — a fitted
    :class:`~margadarshak.demand.LearnedRate`, or anything else answering
    ``rate_for(flight)``. Without one every flight is assumed to need
    ``assistance_rate`` chairs, which is a documented guess and should be
    replaced as soon as a pilot has flown enough departures to measure it.
    """
    weights = pickup_weights if pickup_weights is not None else DEFAULT_PICKUP_WEIGHTS

    total = 0.0
    for flight in board.flights():
        if flight.scheduled_departure_s is None:
            continue
        if not flight.status.accepts_passengers:
            continue
        arrive_at = flight.scheduled_departure_s - arrival_lead_s
        if now_s <= arrive_at < now_s + horizon_s:
            total += rate_model.rate_for(flight) if rate_model else assistance_rate

    if total <= 0:
        return []

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
    max_staged_fraction: float = MAX_STAGED_FRACTION,
) -> list[StagingMove]:
    """Work out which idle chairs to move, and where.

    Three decisions, in order, each of which an operator can follow:

    1. *How many chairs to send out at all.* At most ``max_staged_fraction`` of
       the chairs currently resting with enough charge. The rest stay on the
       chargers.
    2. *How to divide them between the demand points.* Every point with demand
       gets one chair before any point gets two, and the remainder is split in
       proportion to expected requests. A point is never sent more chairs than
       it expects passengers.
    3. *Which chair goes where.* Busiest point first, nearest free staging spot,
       and the chair that can reach that spot soonest.

    Step 2 is where the forecast earns its keep: with one flat rate for every
    flight the split is the same whatever the board says, and improving the
    forecast changes nothing. With a per-flight rate from
    :mod:`margadarshak.demand` the busy end of the building gets the chairs.

    Returns recommendations rather than acting, so an operator can see them, a
    test can assert on them, and a dashboard can show what the system is about
    to do before it does it.
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
    if not resting:
        return []

    # How many chairs to send out. Three limits, and the tightest one wins:
    # somewhere to put them, enough left on charge, and — the one that makes the
    # forecast matter at all — no more chairs than passengers expected. Without
    # that third limit the fleet sends out the same number of chairs whatever the
    # board says, and improving the forecast changes nothing on the floor.
    expected_total = sum(point.expected_requests for point in demand)
    budget = min(
        len(staging_nodes),
        max(1, int(len(resting) * max_staged_fraction)),
        max(1, math.ceil(expected_total)),
    )
    quota = _share_out(demand, budget)

    moves: list[StagingMove] = []
    spare_staging = list(staging_nodes)

    for point in demand:
        for _ in range(quota.get(point.node, 0)):
            if not resting or not spare_staging:
                break

            # The best place left to wait for this demand point.
            staged_times = [
                (fleet.travel_time(node, point.node), node)
                for node in spare_staging
                if fleet.travel_time(node, point.node) is not None
            ]
            if not staged_times:
                break
            staged_time, staging_node = min(staged_times)

            # The chair that can get to that waiting place soonest.
            reachable = [
                (fleet.travel_time(chair.node, staging_node), chair)
                for chair in resting
                if fleet.travel_time(chair.node, staging_node) is not None
            ]
            if not reachable:
                break
            _, chair = min(reachable, key=lambda item: (item[0], item[1].id))

            # Would moving it actually help?
            current_time = fleet.travel_time(chair.node, point.node)
            if current_time is None:
                break
            saving = current_time - staged_time
            if saving < min_saving_s:
                break

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


def _share_out(demand: list[DemandPoint], budget: int) -> dict[str, int]:
    """Divide ``budget`` chairs between demand points. Largest remainder.

    One each first, so a quiet pickup point is never abandoned entirely because
    a busy one exists; then the rest in proportion; then never more chairs than
    a point expects passengers, because a chair waiting for a passenger who is
    not coming is a chair not on its charger.
    """
    wanted = {
        point.node: max(1, int(point.expected_requests + 0.5))
        for point in demand
        if point.expected_requests > 0
    }
    if not wanted or budget <= 0:
        return {}

    quota = {node: 0 for node in wanted}
    remaining = budget

    # One each, in the order given — which is busiest first.
    for point in demand:
        if remaining <= 0:
            break
        if point.node in quota and quota[point.node] < wanted[point.node]:
            quota[point.node] += 1
            remaining -= 1

    if remaining <= 0:
        return {node: n for node, n in quota.items() if n}

    # The rest in proportion to expected requests, largest remainder first.
    total = sum(point.expected_requests for point in demand if point.node in quota)
    shares = []
    for point in demand:
        if point.node not in quota:
            continue
        exact = remaining * point.expected_requests / total if total else 0.0
        whole = int(exact)
        headroom = wanted[point.node] - quota[point.node]
        whole = min(whole, headroom)
        quota[point.node] += whole
        shares.append((exact - int(exact), point.node))

    left = budget - sum(quota.values())
    for _, node in sorted(shares, reverse=True):
        if left <= 0:
            break
        if quota[node] < wanted[node]:
            quota[node] += 1
            left -= 1

    return {node: n for node, n in quota.items() if n}
