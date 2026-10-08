"""How many people on this flight will need a chair — learned, not assumed.

``prepositioning.py`` decides where idle chairs should wait. To do that it needs
one number per departing flight: how many assistance requests it will generate.
Until now that number was a constant, 1.5, applied to every flight on the board.

That constant is obviously wrong, and wrong in a way that matters. A morning
business shuttle to Bengaluru and a Gulf labour route or a pilgrimage charter do
not generate assistance requests at anything like the same rate. Using one number
for both sends chairs to the wrong end of the building and lengthens exactly the
wait the system exists to shorten.

So this module learns the rate per flight from flights that have already
departed. It is the one place in the project where a model earns its place.

**Why this and not navigation.** The chair follows a line in the floor. There is
no perception stack, no localisation and nothing learned anywhere near the motor
or the brake — that is what makes the build cost four figures instead of six, and
it is a safety argument as much as a cost one. Forecasting is different: it is a
staffing decision, it is made minutes in advance, it is reversible, and being
wrong makes somebody wait longer rather than putting them in danger. See
``docs/ai.md`` for the full line and where it is drawn.

**Why shrinkage and not a neural network.** Three reasons, in order of how much
they matter:

1. *The data is thin.* An airport that has run a pilot for a month has a few
   hundred departures, and a specific route may appear five times. Any method
   with enough capacity to be interesting will fit noise on five samples. This
   one cannot: with five observations it stays close to the broader average, and
   it moves towards the route's own history only as that history accumulates.
2. *The operator has to be able to follow it.* ``explain()`` returns the chain of
   evidence — this route, this carrier, this hour, everything — with the sample
   count at each step. A duty manager can read why chairs went to the kerb. A
   staffing decision nobody can follow is a staffing decision nobody will trust,
   and it will be overridden by hand within a week.
3. *It runs on the standard library.* The whole package does. No wheels to build
   on an airport's locked-down machine, nothing to keep patched, and the model
   fits in milliseconds on the laptop that is already running the dispatcher.

The method is hierarchical empirical-Bayes shrinkage: start at the average over
every flight, then move towards the average for this hour of day, then this
carrier, then this exact route, taking each step only as far as the evidence at
that level supports. It is the standard treatment for small-sample count data and
it is about fifty lines.

**There is no data yet.** Nothing has carried a passenger, so there is nothing to
fit. What is built here is the thing that has to exist *before* a pilot can
produce useful numbers: the schema for the observation, the collector that turns
a running shift into observations, the estimator, and a backtest that says
whether a fitted model would actually have shortened the wait. Fitting it is a
job for the pilot's own data, and a rate fitted to anybody else's airport should
be treated as decoration.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Iterable, Protocol

from .flights import Flight, FlightBoard

#: Used when there is no history at all — the flat rate this module replaces.
#: It is a guess, it is documented as a guess, and the first week of a pilot
#: should overwrite it.
PRIOR_RATE = 1.5

#: How much evidence it takes to move a group's estimate halfway from the
#: broader average to the group's own history, measured in flights. Five is
#: deliberately cautious: a route seen five times gets half its own way, a route
#: seen fifty is trusted almost entirely. Lower it only with a reason.
PRIOR_STRENGTH = 5.0

#: Below this many observations in total, the fit is reported as not ready. The
#: estimator still answers — it just answers with the prior — but a dashboard
#: should say "not enough history yet" rather than imply a forecast exists.
MIN_OBSERVATIONS = 20


@dataclass(frozen=True)
class Observation:
    """One departed flight, and how many assistance requests it actually drew.

    This is the training row, and it is deliberately tiny. It names no
    passenger, carries no booking reference and holds nothing that could
    identify anybody — see ``docs/privacy.md``. A year of these for a busy
    airport is a few megabytes of text.
    """

    designator: str
    requests: int
    destination: str | None = None
    aircraft_type: str | None = None
    #: Scheduled departure, seconds from midnight local. Used for hour of day.
    departure_s: float | None = None

    def __post_init__(self) -> None:
        if self.requests < 0:
            raise ValueError("requests cannot be negative")
        if not self.designator:
            raise ValueError("an observation needs a flight designator")

    @property
    def carrier(self) -> str:
        return carrier_of(self.designator)

    @property
    def hour(self) -> int | None:
        return hour_of(self.departure_s)

    def as_dict(self) -> dict:
        return {
            "designator": self.designator,
            "requests": self.requests,
            "destination": self.destination,
            "aircraft_type": self.aircraft_type,
            "departure_s": self.departure_s,
        }

    @classmethod
    def from_dict(cls, raw: dict) -> "Observation":
        return cls(
            designator=str(raw["designator"]),
            requests=int(raw["requests"]),
            destination=raw.get("destination"),
            aircraft_type=raw.get("aircraft_type"),
            departure_s=raw.get("departure_s"),
        )


def carrier_of(designator: str) -> str:
    """``6E204`` -> ``6E``. The IATA designator is two characters, then digits."""
    text = designator.strip().upper()
    for index, character in enumerate(text):
        if character.isdigit() and index >= 2:
            return text[:index]
    return text[:2] if len(text) >= 2 else text


def hour_of(departure_s: float | None) -> int | None:
    """Hour of day, 0-23, or None when the flight has no scheduled time."""
    if departure_s is None:
        return None
    return int(departure_s // 3600) % 24


class RateModel(Protocol):
    """Anything that can say how many chairs a flight will need."""

    def rate_for(self, flight: Flight) -> float:
        ...


@dataclass(frozen=True)
class FlatRate:
    """One number for every flight — the behaviour this module replaces.

    Kept, named and tested, because it is the baseline the backtest has to beat.
    A forecast that cannot beat a constant is not a forecast.
    """

    rate: float = PRIOR_RATE

    def rate_for(self, flight: Flight) -> float:  # noqa: ARG002 - deliberate
        return self.rate


@dataclass(frozen=True)
class Evidence:
    """One step of the shrinkage chain, for showing an operator the reasoning."""

    level: str
    key: str
    observations: int
    group_mean: float | None
    estimate: float

    def __str__(self) -> str:  # pragma: no cover - reporting aid
        if self.group_mean is None:
            return f"{self.level} {self.key}: no history, stays at {self.estimate:.2f}"
        return (
            f"{self.level} {self.key}: {self.observations} flights averaging "
            f"{self.group_mean:.2f} -> {self.estimate:.2f}"
        )


class LearnedRate:
    """Per-flight assistance rate, fitted by hierarchical shrinkage.

    Fit it from observations, ask it for a rate, and ask it to explain itself::

        model = LearnedRate.fit(log.observations())
        model.rate_for(board.get("6E204"))
        for step in model.explain(board.get("6E204")):
            print(step)
    """

    def __init__(
        self,
        *,
        prior_rate: float = PRIOR_RATE,
        prior_strength: float = PRIOR_STRENGTH,
    ) -> None:
        if prior_strength <= 0:
            raise ValueError("prior_strength must be positive")
        self.prior_rate = prior_rate
        self.prior_strength = prior_strength
        self.n_observations = 0
        self._global: tuple[int, float] = (0, 0.0)
        #: level -> key -> (count, total requests)
        self._groups: dict[str, dict[str, tuple[int, float]]] = {
            "hour": {},
            "carrier": {},
            "route": {},
        }

    # -- fitting ---------------------------------------------------------

    @classmethod
    def fit(
        cls,
        observations: Iterable[Observation],
        *,
        prior_rate: float = PRIOR_RATE,
        prior_strength: float = PRIOR_STRENGTH,
    ) -> "LearnedRate":
        model = cls(prior_rate=prior_rate, prior_strength=prior_strength)
        for observation in observations:
            model.observe(observation)
        return model

    def observe(self, observation: Observation) -> None:
        """Add one departed flight. Incremental, so a pilot can fit as it runs."""
        self.n_observations += 1
        count, total = self._global
        self._global = (count + 1, total + observation.requests)

        for level, key in self._keys(observation.designator, observation.destination,
                                     observation.departure_s):
            if key is None:
                continue
            bucket = self._groups[level]
            count, total = bucket.get(key, (0, 0.0))
            bucket[key] = (count + 1, total + observation.requests)

    @staticmethod
    def _keys(
        designator: str, destination: str | None, departure_s: float | None
    ) -> list[tuple[str, str | None]]:
        """The group keys for a flight, broadest first. Order is the chain."""
        hour = hour_of(departure_s)
        carrier = carrier_of(designator)
        return [
            ("hour", None if hour is None else f"{hour:02d}"),
            ("carrier", carrier or None),
            ("route", f"{carrier}-{destination}" if destination and carrier else None),
        ]

    @property
    def ready(self) -> bool:
        """Enough history to call this a forecast rather than a guess."""
        return self.n_observations >= MIN_OBSERVATIONS

    @property
    def global_mean(self) -> float:
        count, total = self._global
        return total / count if count else self.prior_rate

    # -- using it --------------------------------------------------------

    def rate_for(self, flight: Flight) -> float:
        return self.explain(flight)[-1].estimate

    def explain(self, flight: Flight) -> list[Evidence]:
        """The chain of evidence behind a rate, broadest step first.

        Always at least one step long, so the caller never has to handle an empty
        explanation. The first step is the airport-wide average.
        """
        count, _ = self._global
        estimate = self.global_mean
        chain = [
            Evidence(
                level="airport",
                key="all flights",
                observations=count,
                group_mean=self.global_mean if count else None,
                estimate=estimate,
            )
        ]

        destination = getattr(flight, "destination", None)
        for level, key in self._keys(flight.designator, destination,
                                     flight.scheduled_departure_s):
            if key is None:
                continue
            group_count, group_total = self._groups[level].get(key, (0, 0.0))
            if group_count == 0:
                chain.append(
                    Evidence(level=level, key=key, observations=0,
                             group_mean=None, estimate=estimate)
                )
                continue
            # Shrink the group's own mean towards the estimate carried down from
            # the level above, weighting by how much evidence this group has.
            estimate = (group_total + self.prior_strength * estimate) / (
                group_count + self.prior_strength
            )
            chain.append(
                Evidence(
                    level=level,
                    key=key,
                    observations=group_count,
                    group_mean=group_total / group_count,
                    estimate=estimate,
                )
            )
        return chain

    # -- persistence -----------------------------------------------------

    def to_json(self) -> str:
        """Serialise the fitted model. Small enough to read and to diff."""
        return json.dumps(
            {
                "prior_rate": self.prior_rate,
                "prior_strength": self.prior_strength,
                "n_observations": self.n_observations,
                "global": list(self._global),
                "groups": {
                    level: {key: list(value) for key, value in bucket.items()}
                    for level, bucket in self._groups.items()
                },
            },
            indent=2,
            sort_keys=True,
        )

    @classmethod
    def from_json(cls, text: str) -> "LearnedRate":
        raw = json.loads(text)
        model = cls(
            prior_rate=float(raw["prior_rate"]),
            prior_strength=float(raw["prior_strength"]),
        )
        model.n_observations = int(raw["n_observations"])
        count, total = raw["global"]
        model._global = (int(count), float(total))
        for level, bucket in raw["groups"].items():
            if level not in model._groups:
                raise ValueError(f"unknown grouping level {level}")
            model._groups[level] = {
                key: (int(value[0]), float(value[1])) for key, value in bucket.items()
            }
        return model

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        state = "fitted" if self.ready else "cold"
        return (
            f"<LearnedRate {state}: {self.n_observations} flights, "
            f"mean {self.global_mean:.2f}/flight>"
        )


class AssistanceLog:
    """The observations a pilot collects, and the one thing it must record.

    The dispatcher already knows every request and which flight it was for. This
    turns a finished shift into training rows, so that a month of operation
    produces the data the forecast needs without anybody filling in a form.

    A flight with no requests is as important as one with five, and is the row
    most easily lost: nothing happens, so nothing gets written down, and the
    model learns that every flight needs a chair. ``observe_board`` therefore
    walks the *flight board*, not the request list, and records the zeroes.
    """

    def __init__(self) -> None:
        self._observations: list[Observation] = []

    def record(self, observation: Observation) -> None:
        self._observations.append(observation)

    def observations(self) -> list[Observation]:
        return list(self._observations)

    def __len__(self) -> int:
        return len(self._observations)

    def observe_board(
        self,
        board: FlightBoard,
        counts: dict[str, int],
        *,
        only_departed: bool = True,
    ) -> int:
        """Record every flight on the board, including the ones nobody needed.

        ``counts`` maps flight designator to requests seen, as
        :meth:`Fleet.assistance_counts` returns it. Returns how many rows were
        added. With ``only_departed`` the board is filtered to flights that have
        actually gone, because a flight still boarding may yet draw a request and
        recording it now would teach the model a number that is too low.
        """
        from .flights import FlightStatus  # local: keeps the import graph flat

        added = 0
        for flight in board.flights():
            if only_departed and flight.status is not FlightStatus.DEPARTED:
                continue
            self.record(
                Observation(
                    designator=flight.designator,
                    requests=int(counts.get(flight.designator, 0)),
                    destination=getattr(flight, "destination", None),
                    aircraft_type=getattr(flight, "aircraft_type", None),
                    departure_s=flight.scheduled_departure_s,
                )
            )
            added += 1
        return added

    # -- persistence -----------------------------------------------------

    def to_json(self) -> str:
        return json.dumps(
            [observation.as_dict() for observation in self._observations], indent=2
        )

    @classmethod
    def from_json(cls, text: str) -> "AssistanceLog":
        log = cls()
        for raw in json.loads(text):
            log.record(Observation.from_dict(raw))
        return log


def mean_absolute_error(model: RateModel, observations: Iterable[Observation]) -> float:
    """Average error in chairs per flight. The number a model has to beat.

    Reported in chairs rather than anything statistical, because the question an
    operator asks is "how many chairs is it out by", and the answer to that is
    the only honest way to compare a fitted model against the flat rate.
    """
    total = 0.0
    count = 0
    for observation in observations:
        flight = Flight(
            designator=observation.designator,
            scheduled_departure_s=observation.departure_s,
            destination=observation.destination,
            aircraft_type=observation.aircraft_type,
        )
        total += abs(model.rate_for(flight) - observation.requests)
        count += 1
    return total / count if count else 0.0
