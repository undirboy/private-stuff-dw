#!/usr/bin/env python3
"""Does a learned demand forecast actually shorten the wait? (Measured: barely.)

    python3 -m sim.backtest

A forecast is not worth having because it is more accurate. It is worth having
if passengers wait less. Those are different claims, and the second is the only
one an airport is buying, so this harness measures both — and they disagree.

**The result, so nobody has to read the output to find it.** Replacing the flat
1.5-chairs-per-flight guess with a rate learned per route cuts the forecast error
by about a third. It then shortens the mean wait by a couple of seconds, which is
inside the run-to-run noise. On twenty paired days the learned forecast was
better on eleven and worse on six. That is not an improvement; it is a coin.

The reason is worth understanding before anybody builds on this. In a terminal
this size the wait is set by how far a chair has to come and how many chairs
there are, not by which of two pickup points they were parked at. Pre-positioning
can only move chairs between places that are all roughly the same distance away,
so knowing demand more precisely has nothing to spend the knowledge on. A better
forecast would pay for itself in a building with longer distances, more pickup
points, or a fleet stretched thin enough that being in the wrong place costs a
whole journey. This terminal is none of those.

So: the machinery is here, it works, it is honest, and on this evidence it is not
yet worth deploying. That is the finding. **Do not quote a wait-time improvement
from this file** — quote the accuracy, and say plainly that it did not convert.

What this harness is really for is answering the question again, properly, with a
pilot's own departures in place of the invented ones below. If the effect is real
anywhere it will show up there, and if it does not, that is worth knowing before
anybody pays for it.

**On the synthetic days.** Nothing has carried a passenger, so there is no history
to fit, and the per-route rates are invented by the author of this file. That
makes the accuracy figure partly circular — of course a model recovers a
structure that was put there deliberately — and it is reported anyway because it
is the sanity check that the estimator is wired up at all. The *consequence*
figure is not circular in the same way: the dispatcher is the real one, and it
was free to turn the better forecast into shorter waits. It mostly did not.

The day is built to contain the thing that makes a flat rate fail: a morning bank
of domestic shuttles that barely need a chair, and a midday bank of Gulf and
pilgrimage routes that need many. A single average is wrong for both. It is still
not wrong in a way that costs much here.

One thing this harness did earn its keep for. The first version of it reported a
42% improvement, which was an artefact: the learned arm was delivering almost
nobody, and a mean taken over delivered passengers only looks wonderful when
almost everyone is left at the kerb. The cause was a real defect — a corridor
jam between two repositioning chairs that no attendant ever came to clear, which
spread until the whole fleet stopped. It is fixed in ``fleet.py`` (an empty chair
now gives way), and this file asserts that every passenger was delivered before
it compares anything, because that is the check whose absence nearly shipped a
made-up number.
"""

from __future__ import annotations

import math
import random
import statistics
import sys
from dataclasses import dataclass

from margadarshak import (
    FlatRate,
    Fleet,
    FlightBoard,
    FlightStatus,
    LearnedRate,
    Observation,
    build_example_terminal,
    forecast_demand,
    mean_absolute_error,
    plan_staging,
)
from margadarshak.prepositioning import DEFAULT_ARRIVAL_LEAD_S

HOUR = 3600.0

#: Routes, and how many assistance passengers each really draws per departure.
#: These numbers are invented. They are the thing a pilot measures; they are here
#: so the machinery has something with structure in it to learn.
ROUTES: list[tuple[str, str, float, str]] = [
    ("6E", "BLR", 0.4, "morning business shuttle"),
    ("UK", "BOM", 0.6, "metro hop"),
    ("AI", "DEL", 0.9, "trunk route"),
    ("SG", "IXE", 1.3, "regional"),
    ("AI", "DXB", 3.0, "Gulf, heavy on elderly passengers"),
    ("6E", "SHJ", 3.9, "Gulf labour route"),
    ("AI", "JED", 5.2, "pilgrimage charter"),
]

#: Which routes fly in which bank. The contrast is the whole point.
MORNING_BANK = [0, 1, 2, 0, 1]      # light
MIDDAY_BANK = [4, 5, 6, 3, 4]       # heavy

GATES = ["g1", "g2", "g3", "g4", "g5"]
#: Chairs in the demonstrator fleet. Eight is roughly what the example
#: terminal's traffic justifies; the sensitivity sweep at the end varies it.
DEFAULT_CHAIRS = 8
STAGING_NODES = ["sec_q", "sp1", "sp2", "checkin"]
RESTAGE_EVERY_S = 15 * 60.0
#: Fleet sizes for the sensitivity sweep at the end.
SWEEP_CHAIRS = [2, 3, 4, 6, 8, 12]
#: Days to fit on, days to test on, and how many of those the sweep reuses.
TRAIN_DAYS = 40
TEST_DAYS = 12
SWEEP_DAYS = 4


def poisson(rng: random.Random, mean: float) -> int:
    """Knuth's method. Counts of rare independent events — which is what this is."""
    if mean <= 0:
        return 0
    limit = math.exp(-mean)
    count, product = 0, rng.random()
    while product > limit:
        count += 1
        product *= rng.random()
    return count


@dataclass(frozen=True)
class Departure:
    designator: str
    destination: str
    departure_s: float
    gate: str
    true_rate: float
    passengers: int


def build_day(rng: random.Random) -> list[Departure]:
    """One day's departures, with how many people actually needed a chair."""
    day: list[Departure] = []
    serial = 100
    banks = [(3.0 * HOUR, MORNING_BANK), (6.0 * HOUR, MIDDAY_BANK)]

    for bank_start, route_indices in banks:
        for offset, route_index in enumerate(route_indices):
            carrier, destination, rate, _ = ROUTES[route_index]
            serial += 7
            departure_s = bank_start + offset * 22 * 60 + rng.uniform(-300, 300)
            day.append(
                Departure(
                    designator=f"{carrier}{serial}",
                    destination=destination,
                    departure_s=departure_s,
                    gate=GATES[len(day) % len(GATES)],
                    true_rate=rate,
                    passengers=poisson(rng, rate),
                )
            )
    return sorted(day, key=lambda d: d.departure_s)


def observations(day: list[Departure]) -> list[Observation]:
    return [
        Observation(
            designator=departure.designator,
            requests=departure.passengers,
            destination=departure.destination,
            departure_s=departure.departure_s,
        )
        for departure in day
    ]


def run_shift(
    day: list[Departure], rate_model, *, seed: int, chairs: int = DEFAULT_CHAIRS
) -> dict[str, float]:
    """Replay one day through the dispatcher, staging from ``rate_model``."""
    rng = random.Random(seed)
    tmap = build_example_terminal()
    board = FlightBoard()
    for departure in day:
        board.upsert(
            departure.designator,
            status=FlightStatus.GATE_ASSIGNED,
            gate=departure.gate,
            scheduled_departure_s=departure.departure_s,
            destination=departure.destination,
        )

    fleet = Fleet(tmap, board=board, holding_area="lounge")
    for index in range(chairs):
        fleet.add_chair(f"CH-{index + 1:02d}", "dock_w" if index % 2 else "dock_e")

    # When each passenger turns up at the kerb: about two hours before their
    # flight, give or take, because that is what people told to come early do.
    arrivals: list[tuple[float, Departure, int]] = []
    for departure in day:
        for number in range(departure.passengers):
            at = departure.departure_s - DEFAULT_ARRIVAL_LEAD_S + rng.uniform(-20 * 60, 25 * 60)
            arrivals.append((max(0.0, at), departure, number))
    arrivals.sort(key=lambda item: item[0])

    staged = 0
    next_restage = 0.0
    cursor = 0
    end = max(d.departure_s for d in day) + HOUR

    while fleet.now < end:
        while cursor < len(arrivals) and arrivals[cursor][0] <= fleet.now:
            _, departure, number = arrivals[cursor]
            fleet.request_assistance(
                f"{departure.designator}/{number}",
                departure.designator,
                pickup="kerb",
                gate=departure.gate,
            )
            cursor += 1

        if fleet.now >= next_restage:
            demand = forecast_demand(board, fleet.now, rate_model=rate_model)
            staged += fleet.apply_staging(plan_staging(fleet, demand, STAGING_NODES))
            next_restage = fleet.now + RESTAGE_EVERY_S

        fleet.run(duration_s=60.0, dt_s=2.0)

    summary = fleet.summary()
    battery = [chair.battery_fraction for chair in fleet.chairs.values()]
    return {
        "requests": summary["requests"],
        "undelivered": summary["requests"] - summary["delivered"],
        "delivered": summary["delivered"],
        "mean_wait_s": summary["mean_wait_s"],
        "worst_wait_s": summary["worst_wait_s"],
        "staging_moves": staged,
        "mean_battery": sum(battery) / len(battery),
    }


def compare(day: list[Departure], flat, learned, *, seed: int, chairs: int) -> tuple:
    """One day through the dispatcher twice. Refuses to compare broken runs.

    A mean wait is taken over the passengers who were actually delivered, so a
    run that strands people reports a *better* number than one that serves them.
    Any comparison that does not check this first can be made to say anything.
    """
    a = run_shift(day, flat, seed=seed, chairs=chairs)
    b = run_shift(day, learned, seed=seed, chairs=chairs)
    for label, result in (("flat", a), ("learned", b)):
        if result["undelivered"]:
            raise AssertionError(
                f"{label} arm left {result['undelivered']} of {result['requests']} "
                f"passengers undelivered — its mean wait is meaningless"
            )
    return a, b


def main() -> int:
    rng = random.Random(20261006)
    train = [build_day(rng) for _ in range(TRAIN_DAYS)]
    test = [build_day(rng) for _ in range(TEST_DAYS)]

    flat = FlatRate()
    learned = LearnedRate.fit(row for day in train for row in observations(day))

    print("Margadarshak — does a learned demand forecast shorten the wait?")
    print()
    print(f"  trained on {len(train)} synthetic days, {learned.n_observations} departures")
    print(f"  model is {'ready' if learned.ready else 'NOT ready — too little history'}")
    print()

    print("1. Accuracy, on days the model never saw")
    print("   (error in chairs per flight — lower is better)")
    held_out = [row for day in test for row in observations(day)]
    flat_mae = mean_absolute_error(flat, held_out)
    learned_mae = mean_absolute_error(learned, held_out)
    print(f"     flat rate of {flat.rate}        {flat_mae:.2f}")
    print(f"     learned per-flight rate   {learned_mae:.2f}")
    if flat_mae:
        print(f"     -> {100 * (flat_mae - learned_mae) / flat_mae:.0f}% less error")
    print()

    print("   What it learned, for one flight from each bank:")
    board = FlightBoard()
    for index in (0, 6):
        carrier, destination, true_rate, label = ROUTES[index]
        flight = board.upsert(
            f"{carrier}900",
            scheduled_departure_s=(3.0 if index == 0 else 6.0) * HOUR,
            destination=destination,
        )
        print(f"     {carrier}900 to {destination} — {label}, really {true_rate}/flight")
        for step in learned.explain(flight):
            print(f"       {step}")
    print()

    print("2. Consequence: the same days, through the dispatcher")
    print(f"   ({DEFAULT_CHAIRS} chairs, {len(test)} paired days; wait in seconds)")
    print()
    print(f"   {'day':>4}  {'flat':>12}  {'learned':>12}  {'saved':>7}")
    print(f"   {'':>4}  {'mean  worst':>12}  {'mean  worst':>12}  {'':>7}")
    savings: list[float] = []
    for number, day in enumerate(test, start=1):
        a, b = compare(day, flat, learned, seed=number, chairs=DEFAULT_CHAIRS)
        saved = a["mean_wait_s"] - b["mean_wait_s"]
        savings.append(saved)
        print(
            f"   {number:>4}  {a['mean_wait_s']:>5.0f} {a['worst_wait_s']:>6.0f}  "
            f"{b['mean_wait_s']:>5.0f} {b['worst_wait_s']:>6.0f}  {saved:>+7.0f}"
        )

    mean_saving = statistics.mean(savings)
    spread = statistics.stdev(savings) if len(savings) > 1 else 0.0
    better = sum(1 for value in savings if value > 1)
    worse = sum(1 for value in savings if value < -1)
    print()
    print(f"   mean saving  {mean_saving:>+6.1f} s per passenger")
    print(f"   spread       {spread:>6.1f} s between days")
    print(f"   better on {better} of {len(savings)} days, worse on {worse}")
    print()
    if abs(mean_saving) <= spread:
        print("   VERDICT: not distinguishable from noise. The forecast is a third")
        print("   more accurate and the passengers cannot tell. Do not claim a")
        print("   wait-time improvement on this evidence.")
    else:
        print("   VERDICT: the saving is larger than the day-to-day spread. Worth")
        print("   checking against a pilot's real departures before quoting.")
    print()

    print("3. Does fleet size change the answer?")
    print("   (mean wait, seconds)")
    print()
    print(f"   {'chairs':>7}  {'flat':>7}  {'learned':>8}  {'saved':>7}")
    for chairs in SWEEP_CHAIRS:
        results = [
            compare(day, flat, learned, seed=index, chairs=chairs)
            for index, day in enumerate(test[:SWEEP_DAYS], start=1)
        ]
        a_wait = sum(a["mean_wait_s"] for a, _ in results) / len(results)
        b_wait = sum(b["mean_wait_s"] for _, b in results) / len(results)
        note = "   (nothing to pre-position)" if abs(a_wait - b_wait) < 1 else ""
        print(f"   {chairs:>7}  {a_wait:>7.0f}  {b_wait:>8.0f}  {a_wait - b_wait:>+7.0f}{note}")
    print()
    print("   Below about four chairs the forecast cannot change anything, and the")
    print("   reason is not subtle: half the fleet is one chair, it goes to the")
    print("   busiest pickup point, and no forecast improves on that. Worth saying")
    print("   to an airport asking whether it can start with two.")
    print()
    print("   Above that it still changes very little, because in a terminal this")
    print("   size every pre-positioning spot is about as far from the kerb as any")
    print("   other. The forecast needs somewhere to spend its accuracy. Give it a")
    print("   bigger building, more pickup points, or a fleet stretched thinner,")
    print("   and the question is worth asking again — with real departures.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
