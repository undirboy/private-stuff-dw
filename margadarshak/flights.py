"""The flight information board — where the gate actually comes from.

The boarding pass gives us a flight. This gives us the gate, and tells us when it
moves. In a deployment this is a read-only feed from the airport's operational
database; here it is an in-memory stand-in with the same shape, so the dispatcher
can be written and tested against it now and pointed at the real feed later.

Two cases drive the design:

- **The gate is not assigned yet.** Common for a passenger who arrives early,
  which describes most passengers who need assistance, because they are told to
  come early. The chair cannot take them to a gate that does not exist, so it
  takes them to the assistance lounge and comes back when the gate appears.
- **The gate moves.** Routine, and the thing the current service handles worst.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable


class FlightStatus(Enum):
    SCHEDULED = "scheduled"       # no gate yet
    GATE_ASSIGNED = "gate_assigned"
    BOARDING = "boarding"
    FINAL_CALL = "final_call"
    CLOSED = "closed"             # too late to take anybody there
    DEPARTED = "departed"
    CANCELLED = "cancelled"

    @property
    def accepts_passengers(self) -> bool:
        """Is it still worth putting somebody in a chair for this flight?"""
        return self in {
            FlightStatus.SCHEDULED,
            FlightStatus.GATE_ASSIGNED,
            FlightStatus.BOARDING,
            FlightStatus.FINAL_CALL,
        }


@dataclass
class Flight:
    designator: str
    status: FlightStatus = FlightStatus.SCHEDULED
    #: Map node of the gate, or None while the gate is unassigned.
    gate: str | None = None
    scheduled_departure_s: float | None = None
    #: IATA code of where the aircraft is going. Carried because the rate at
    #: which a flight needs wheelchairs depends enormously on the route, and
    #: :mod:`margadarshak.demand` learns that rate per route. Optional: the
    #: dispatcher never needs it, only the forecast does.
    destination: str | None = None
    #: Aircraft type, for the same reason — a widebody draws more requests than
    #: a turboprop, and not only in proportion to its seats.
    aircraft_type: str | None = None

    @property
    def has_gate(self) -> bool:
        return self.gate is not None


#: Called as ``callback(flight_designator, new_gate)`` whenever a gate is set or moved.
GateListener = Callable[[str, str], None]


class FlightBoard:
    """Live flight status, and a way to be told when a gate changes."""

    def __init__(self) -> None:
        self._flights: dict[str, Flight] = {}
        self._listeners: list[GateListener] = []

    def subscribe(self, listener: GateListener) -> None:
        self._listeners.append(listener)

    # -- the feed --------------------------------------------------------

    def upsert(
        self,
        designator: str,
        *,
        status: FlightStatus = FlightStatus.SCHEDULED,
        gate: str | None = None,
        scheduled_departure_s: float | None = None,
        destination: str | None = None,
        aircraft_type: str | None = None,
    ) -> Flight:
        flight = Flight(
            designator=designator.upper(),
            status=status,
            gate=gate,
            scheduled_departure_s=scheduled_departure_s,
            destination=destination.upper() if destination else None,
            aircraft_type=aircraft_type,
        )
        self._flights[flight.designator] = flight
        return flight

    def get(self, designator: str) -> Flight | None:
        return self._flights.get(designator.upper())

    def flights(self) -> list[Flight]:
        """Everything on the board, for forecasting."""
        return list(self._flights.values())

    def assign_gate(self, designator: str, gate: str) -> None:
        """The airport has assigned, or moved, a gate.

        Fires listeners only on an actual change, so that a feed which repeats
        itself — and they all do — does not reroute a chair every few seconds.
        """
        flight = self._flights.get(designator.upper())
        if flight is None:
            raise KeyError(f"{designator} is not on the board")

        if flight.gate == gate:
            return

        flight.gate = gate
        if flight.status is FlightStatus.SCHEDULED:
            flight.status = FlightStatus.GATE_ASSIGNED

        for listener in self._listeners:
            listener(flight.designator, gate)

    def set_status(self, designator: str, status: FlightStatus) -> None:
        flight = self._flights.get(designator.upper())
        if flight is None:
            raise KeyError(f"{designator} is not on the board")
        flight.status = status

    def __contains__(self, designator: str) -> bool:
        return designator.upper() in self._flights

    def __len__(self) -> int:
        return len(self._flights)
