"""Chairs, the dispatcher, and the rules that keep two chairs out of one corridor.

One guided chair is a gadget. What makes it worth an airport's attention is the
fleet behaviour: a passenger asks for help, the nearest chair with enough charge
comes to them, takes them to the right gate even if the gate changes on the way,
and then puts itself back on charge without anyone fetching it.

The chair itself stays deliberately stupid. It follows a line, reads a floor tag,
obeys a speed limit and stops when something is in front of it. Everything in
this module is the dispatcher's job, which means it can be changed, tested and
audited without touching anything that moves.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .boardingpass import BoardingPass, BoardingPassError
from .boardingpass import parse as parse_boarding_pass
from .flights import FlightBoard
from .graph import NodeKind, TerminalMap
from .router import Route, plan

#: Usable battery capacity, watt-hours.
BATTERY_WH = 240.0
#: Drive energy per metre travelled, watt-hours. ~150 W at 1 m/s.
WH_PER_M = 0.045
#: Standing drain: controller, sensors, screen.
IDLE_W = 5.0
#: Refuse a job unless the chair can finish it and still reach a dock, with this
#: much margin on top.
BATTERY_MARGIN = 1.35
#: Below this fraction a chair takes no new work and returns to charge.
BATTERY_RESERVE_FRACTION = 0.20
#: Dock charging rate, watts.
CHARGE_W = 300.0
#: Charge at which a docked chair is announced as ready for a full day's work.
READY_FRACTION = 0.95

#: Seconds spent stationary while the passenger gets on, with the attendant.
BOARDING_DWELL_S = 45.0
#: Seconds spent stationary at the gate while the passenger gets off.
ALIGHTING_DWELL_S = 30.0

#: How long a chair waits for a held corridor before looking for another way round.
WAIT_BEFORE_REPLAN_S = 8.0
#: How long before we call it a deadlock and ask for a human.
WAIT_BEFORE_ESCALATION_S = 90.0


class ChairState(Enum):
    CHARGING = "charging"
    IDLE = "idle"
    TO_PICKUP = "to_pickup"
    BOARDING = "boarding"
    CARRYING = "carrying"
    ALIGHTING = "alighting"
    RETURNING = "returning"
    BLOCKED = "blocked"
    ESTOP = "estop"


#: States in which a passenger is aboard. Used wherever the rules have to be
#: stricter because a person would be the one thrown about.
OCCUPIED_STATES = frozenset({ChairState.BOARDING, ChairState.CARRYING, ChairState.ALIGHTING})


@dataclass
class Request:
    """One passenger's journey."""

    id: str
    passenger: str
    flight: str
    pickup: str
    gate: str
    created_s: float
    assigned_to: str | None = None
    picked_up_s: float | None = None
    delivered_s: float | None = None
    #: True while the passenger is bound for a holding area because the airport
    #: has not announced a gate yet. Cleared when the gate appears.
    awaiting_gate: bool = False
    #: Keyed digest of the booking reference, kept so that a second scan of the
    #: same pass is recognised. The reference itself is never stored.
    pnr_digest: str | None = None
    #: Set on the second leg of a journey that began before the gate was known.
    follow_on_of: str | None = None

    @property
    def waiting(self) -> bool:
        return self.assigned_to is None

    @property
    def active(self) -> bool:
        return self.delivered_s is None

    def wait_time_s(self, now: float) -> float:
        """How long the passenger waited, or has been waiting, for a chair."""
        return (self.picked_up_s if self.picked_up_s is not None else now) - self.created_s


@dataclass
class Event:
    t: float
    chair: str | None
    kind: str
    detail: str

    def __str__(self) -> str:
        mins, secs = divmod(int(self.t), 60)
        who = self.chair or "fleet"
        return f"[{mins:02d}:{secs:02d}] {who:<8} {self.kind:<18} {self.detail}"


class ScanRejected(Exception):
    """A boarding pass was scanned but cannot be acted on.

    ``message`` is written to be shown to the passenger on the chair's screen, so
    it says what to do next rather than what went wrong internally.
    """

    def __init__(self, reason: str, message: str) -> None:
        super().__init__(reason)
        self.reason = reason
        self.message = message


class SegmentReservations:
    """Keeps chairs from driving into each other.

    A corridor wide enough for two chairs abreast can hold two. A single-file
    corridor holds exactly one, whichever direction it is going. A chair claims
    the segment before it enters and releases it as it leaves.
    """

    def __init__(self, tmap: TerminalMap) -> None:
        self._tmap = tmap
        self._held: dict[str, set[str]] = {}

    def holders(self, segment_id: str) -> set[str]:
        return self._held.get(segment_id, set())

    def can_enter(self, segment_id: str, chair_id: str) -> bool:
        held = self._held.get(segment_id, set())
        if chair_id in held:
            return True
        return len(held) < self._tmap.segments[segment_id].capacity

    def acquire(self, segment_id: str, chair_id: str) -> bool:
        if not self.can_enter(segment_id, chair_id):
            return False
        self._held.setdefault(segment_id, set()).add(chair_id)
        return True

    def release(self, segment_id: str, chair_id: str) -> None:
        held = self._held.get(segment_id)
        if held:
            held.discard(chair_id)
            if not held:
                del self._held[segment_id]

    def release_all(self, chair_id: str) -> None:
        for segment_id in list(self._held):
            self.release(segment_id, chair_id)


@dataclass
class Chair:
    """One guided chair.

    Position is either "at ``node``" (``route`` is None or finished) or "``progress_m``
    along the segment leaving ``node``".
    """

    id: str
    node: str
    home_dock: str
    state: ChairState = ChairState.CHARGING
    battery_wh: float = BATTERY_WH
    speed_cap_mps: float | None = None

    route: Route | None = None
    leg: int = 0
    progress_m: float = 0.0
    held_segment: str | None = None

    request: Request | None = None
    dwell_remaining_s: float = 0.0
    #: How long this chair has been unable to move. Accumulates across replans,
    #: and is only cleared when the chair actually enters a corridor — otherwise a
    #: chair can swap between two occupied routes forever, resetting its own
    #: patience each time, and never admit that it is stuck.
    blocked_s: float = 0.0
    replan_attempts: int = 0
    escalated: bool = False
    #: Set when the destination changes mid-journey. Applied at the next node,
    #: because a chair on a guide line between two junctions has nowhere to turn.
    pending_goal: str | None = None

    @property
    def battery_fraction(self) -> float:
        return self.battery_wh / BATTERY_WH

    @property
    def occupied(self) -> bool:
        return self.state in OCCUPIED_STATES

    @property
    def available(self) -> bool:
        return (
            self.state in (ChairState.IDLE, ChairState.CHARGING)
            and self.battery_fraction > BATTERY_RESERVE_FRACTION
        )

    @property
    def current_segment(self) -> str | None:
        if self.route is None or self.leg >= len(self.route.segments):
            return None
        return self.route.segments[self.leg]

    @property
    def remaining_segments(self) -> list[str]:
        if self.route is None:
            return []
        return self.route.segments[self.leg :]


class Fleet:
    """The dispatcher and the world it drives."""

    def __init__(
        self,
        tmap: TerminalMap,
        *,
        now_s: float = 0.0,
        board: FlightBoard | None = None,
        holding_area: str | None = None,
        scan_secret: bytes = b"saarthi-dev-key-replace-in-deployment",
    ) -> None:
        self.tmap = tmap
        self.now = now_s
        self.chairs: dict[str, Chair] = {}
        self.requests: list[Request] = []
        self.events: list[Event] = []
        self.blocked_segments: set[str] = set()
        self.reservations = SegmentReservations(tmap)
        self._request_seq = 0

        #: Where a passenger goes when their gate has not been announced yet.
        self.holding_area = holding_area
        self._scan_secret = scan_secret
        self.board = board
        if board is not None:
            board.subscribe(self._on_gate_assigned)

    # -- setup -----------------------------------------------------------

    def add_chair(self, chair_id: str, dock: str, **kwargs) -> Chair:
        if self.tmap.nodes[dock].kind is not NodeKind.DOCK:
            raise ValueError(f"{dock} is not a dock")
        chair = Chair(id=chair_id, node=dock, home_dock=dock, **kwargs)
        self.chairs[chair_id] = chair
        return chair

    def log(self, kind: str, detail: str, chair: str | None = None) -> None:
        self.events.append(Event(self.now, chair, kind, detail))

    # -- inputs from the outside world -----------------------------------

    def request_assistance(self, passenger: str, flight: str, pickup: str, gate: str) -> Request:
        """A passenger asks for a chair."""
        self._request_seq += 1
        request = Request(
            id=f"R{self._request_seq:03d}",
            passenger=passenger,
            flight=flight,
            pickup=pickup,
            gate=gate,
            created_s=self.now,
        )
        self.requests.append(request)
        self.log("request", f"{request.id} {passenger} {flight} {pickup} -> {gate}")
        return request

    def scan_boarding_pass(self, scan: str, pickup: str) -> Request:
        """A passenger holds their boarding pass up to the reader.

        This is the whole interaction. No typing, no screen to read, no shared
        language needed. The pass names the flight; the flight board names the
        gate; the dispatcher sends a chair.

        Raises :class:`ScanRejected` when the scan cannot be acted on, with a
        message written for the passenger rather than for a log file.
        """
        try:
            boarding_pass = parse_boarding_pass(scan)
        except BoardingPassError as exc:
            raise ScanRejected(
                str(exc), "That did not scan as a boarding pass. Please try again."
            ) from exc

        designator = boarding_pass.flight_designator
        digest = boarding_pass.pnr_digest(self._scan_secret)

        # Somebody scanning twice is impatient, not a second passenger.
        for existing in self.requests:
            if existing.pnr_digest == digest and existing.active:
                self.log("rescan", f"{designator} already has {existing.id}")
                return existing

        if self.board is None:
            raise ScanRejected(
                "no flight board configured",
                "The flight information system is unavailable. Please ask a member of staff.",
            )

        flight = self.board.get(designator)
        if flight is None:
            raise ScanRejected(
                f"{designator} is not on the board",
                f"We cannot find flight {designator} today. Please check with your airline.",
            )
        if not flight.status.accepts_passengers:
            raise ScanRejected(
                f"{designator} is {flight.status.value}",
                f"Flight {designator} has already {flight.status.value}. "
                "Please speak to a member of staff.",
            )

        destination, awaiting = flight.gate, False
        if destination is None:
            # The gate is genuinely not known yet. This is common for exactly the
            # passengers who need a chair, because they are told to arrive early.
            # Take them somewhere comfortable and come back for them.
            if self.holding_area is None:
                raise ScanRejected(
                    f"{designator} has no gate and no holding area is configured",
                    f"Flight {designator} has no gate yet. Please ask a member of staff.",
                )
            destination, awaiting = self.holding_area, True

        request = self.request_assistance(
            passenger=boarding_pass.display_name,
            flight=designator,
            pickup=pickup,
            gate=destination,
        )
        request.pnr_digest = digest
        request.awaiting_gate = awaiting
        self.log(
            "scanned",
            f"{boarding_pass.display_name} on {designator}"
            + (" — no gate yet, routing to the lounge" if awaiting else f" to {destination}"),
        )
        return request

    def _on_gate_assigned(self, flight: str, gate: str) -> None:
        """The flight board told us a gate was set or moved."""
        self.gate_changed(flight, gate)

    def gate_changed(self, flight: str, new_gate: str) -> None:
        """The airline moved a flight. Chairs already under way are redirected.

        This is the case that a printed sign and a human pushing a wheelchair
        handle badly, and it is the most convincing thing the system does.
        """
        self.log("gate_change", f"{flight} now boarding at {new_gate}")
        for request in list(self.requests):
            if request.flight != flight:
                continue

            if not request.active:
                # Already dropped somewhere. If that somewhere was the holding
                # area, because no gate existed when they scanned, they are still
                # our responsibility: send a chair for the second leg.
                if request.awaiting_gate:
                    request.awaiting_gate = False
                    follow_on = self.request_assistance(
                        passenger=request.passenger,
                        flight=flight,
                        pickup=request.gate,
                        gate=new_gate,
                    )
                    follow_on.pnr_digest = request.pnr_digest
                    follow_on.follow_on_of = request.id
                    self.log(
                        "gate_announced",
                        f"{request.passenger} waiting at {request.gate}, "
                        f"sending a chair on to {new_gate}",
                    )
                continue

            request.awaiting_gate = False
            old_gate, request.gate = request.gate, new_gate
            chair = self.chairs.get(request.assigned_to) if request.assigned_to else None
            if chair is not None and chair.state is ChairState.CARRYING:
                chair.pending_goal = new_gate
                self.log(
                    "rerouting",
                    f"{request.passenger} was bound for {old_gate}, diverting at next junction",
                    chair.id,
                )

    def block_segment(self, segment_id: str, reason: str) -> None:
        """Take a corridor out of service: a spill, a queue barrier, a works area."""
        if segment_id not in self.tmap.segments:
            raise ValueError(f"unknown segment {segment_id}")
        self.blocked_segments.add(segment_id)
        self.log("blocked", f"{segment_id} closed ({reason})")
        for chair in self.chairs.values():
            if segment_id in chair.remaining_segments and chair.route is not None:
                chair.pending_goal = chair.route.destination
                self.log("rerouting", f"route uses closed {segment_id}", chair.id)

    def clear_segment(self, segment_id: str) -> None:
        self.blocked_segments.discard(segment_id)
        self.log("cleared", f"{segment_id} back in service")

    def emergency_stop(self, chair_id: str, reason: str) -> None:
        """Latch a chair stopped. Only an attendant clears it."""
        chair = self.chairs[chair_id]
        chair.state = ChairState.ESTOP
        chair.route = None
        self.reservations.release_all(chair_id)
        chair.held_segment = None
        self.log("estop", reason, chair_id)

    # -- the clock -------------------------------------------------------

    def step(self, dt_s: float = 1.0) -> None:
        self.now += dt_s
        self._dispatch()
        for chair in self.chairs.values():
            self._advance(chair, dt_s)

    def run(self, duration_s: float, dt_s: float = 1.0) -> None:
        end = self.now + duration_s
        while self.now < end:
            self.step(dt_s)

    # -- dispatch --------------------------------------------------------

    def _dispatch(self) -> None:
        """Give every waiting passenger the chair that can reach them soonest."""
        for request in self.requests:
            if not request.waiting:
                continue

            best: tuple[float, Chair, Route] | None = None
            for chair in self.chairs.values():
                if not chair.available:
                    continue
                approach = self._plan_for(chair, chair.node, request.pickup)
                if approach is None:
                    continue
                journey = self._plan_for(chair, request.pickup, request.gate)
                if journey is None:
                    continue
                if not self._has_battery_for(chair, approach, journey):
                    continue
                if best is None or approach.duration_s < best[0]:
                    best = (approach.duration_s, chair, approach)

            if best is None:
                continue

            _, chair, approach = best
            request.assigned_to = chair.id
            chair.request = request
            chair.state = ChairState.TO_PICKUP
            self._set_route(chair, approach)
            self.log(
                "assigned",
                f"{request.id} {request.passenger} -> pickup at {request.pickup} "
                f"(eta {approach.duration_s:.0f}s)",
                chair.id,
            )

    def _has_battery_for(self, chair: Chair, approach: Route, journey: Route) -> bool:
        """Can this chair do the job and still get home to a dock?"""
        home = self._plan_for(chair, journey.destination, self._nearest_dock(journey.destination))
        if home is None:
            return False
        metres = approach.distance_m + journey.distance_m + home.distance_m
        return chair.battery_wh >= metres * WH_PER_M * BATTERY_MARGIN

    def _nearest_dock(self, from_node: str) -> str:
        docks = self.tmap.nodes_of_kind(NodeKind.DOCK)
        return min(docks, key=lambda d: self.tmap.distance(from_node, d.id)).id

    def _plan_for(self, chair: Chair, start: str, goal: str) -> Route | None:
        """Plan, honouring closed corridors and this chair's own speed cap."""
        return plan(
            self.tmap,
            start,
            goal,
            blocked_segments=frozenset(self.blocked_segments),
            speed_cap_mps=chair.speed_cap_mps,
        )

    def _set_route(self, chair: Chair, route: Route) -> None:
        chair.route = route
        chair.leg = 0
        chair.progress_m = 0.0

    # -- motion ----------------------------------------------------------

    def _advance(self, chair: Chair, dt_s: float) -> None:
        chair.battery_wh = max(0.0, chair.battery_wh - IDLE_W * dt_s / 3600.0)

        if chair.state is ChairState.ESTOP:
            return

        if chair.state is ChairState.CHARGING:
            # A docked chair stays docked and stays charging. It is already
            # available for dispatch, so there is nothing to be gained by calling
            # it idle, and an "idle" state that quietly drains a chair sitting on
            # a charger is how a fleet goes flat overnight.
            before = chair.battery_fraction
            chair.battery_wh = min(BATTERY_WH, chair.battery_wh + CHARGE_W * dt_s / 3600.0)
            if before < READY_FRACTION <= chair.battery_fraction:
                self.log("ready", f"charged at {chair.node}", chair.id)
            return

        if chair.dwell_remaining_s > 0:
            chair.dwell_remaining_s -= dt_s
            if chair.dwell_remaining_s <= 0:
                self._dwell_finished(chair)
            return

        if chair.state is ChairState.IDLE or chair.route is None:
            return

        if chair.leg >= len(chair.route.segments):
            self._arrived(chair)
            return

        segment = self.tmap.segments[chair.route.segments[chair.leg]]

        # Claim the corridor before entering it.
        if chair.held_segment != segment.id:
            if not self.reservations.acquire(segment.id, chair.id):
                self._wait_for_corridor(chair, segment.id, dt_s)
                return
            if chair.held_segment is not None:
                self.reservations.release(chair.held_segment, chair.id)
            chair.held_segment = segment.id
            if chair.state is ChairState.BLOCKED:
                chair.state = self._moving_state(chair)
                self.log("resumed", f"entering {segment.id}", chair.id)
            # Moving again: the chair has earned its patience back.
            chair.blocked_s = 0.0
            chair.replan_attempts = 0
            chair.escalated = False

        speed = segment.max_speed_mps
        if chair.speed_cap_mps is not None:
            speed = min(speed, chair.speed_cap_mps)

        travelled = speed * dt_s
        chair.progress_m += travelled
        chair.battery_wh = max(0.0, chair.battery_wh - travelled * WH_PER_M)

        if chair.progress_m >= segment.length_m:
            chair.progress_m = 0.0
            chair.node = segment.other_end(chair.node)
            chair.leg += 1
            self._at_node(chair)

    def _moving_state(self, chair: Chair) -> ChairState:
        if chair.request is None:
            return ChairState.RETURNING
        return ChairState.CARRYING if chair.request.picked_up_s is not None else ChairState.TO_PICKUP

    def _wait_for_corridor(self, chair: Chair, segment_id: str, dt_s: float) -> None:
        """Another chair holds the corridor we want. Wait, then look for a way round."""
        if chair.state is not ChairState.BLOCKED:
            chair.state = ChairState.BLOCKED
            holders = ", ".join(sorted(self.reservations.holders(segment_id)))
            self.log("waiting", f"{segment_id} held by {holders}", chair.id)
        chair.blocked_s += dt_s

        due = WAIT_BEFORE_REPLAN_S * (chair.replan_attempts + 1)
        if chair.blocked_s >= due and chair.route is not None:
            chair.replan_attempts += 1
            # Rule out every corridor that is full right now, not just the one we
            # happen to be nosed up against: diverting into a second occupied
            # corridor is not progress.
            unavailable = {
                sid
                for sid in self.tmap.segments
                if not self.reservations.can_enter(sid, chair.id)
            }
            detour = plan(
                self.tmap,
                chair.node,
                chair.route.destination,
                blocked_segments=frozenset(self.blocked_segments | unavailable),
                speed_cap_mps=chair.speed_cap_mps,
            )
            if detour is not None and detour.segments:
                self.log("detour", f"around {segment_id} via {detour.nodes[1]}", chair.id)
                self._set_route(chair, detour)
                chair.state = self._moving_state(chair)
                return

        if chair.blocked_s >= WAIT_BEFORE_ESCALATION_S and not chair.escalated:
            # No way round and nobody has moved: two chairs are nose to nose in a
            # single-file corridor. The fix is a passing bay in the floor plan;
            # until then an attendant has to intervene, so say so loudly.
            chair.escalated = True
            self.log(
                "escalation",
                f"deadlocked at {chair.node} waiting on {segment_id}; attendant needed",
                chair.id,
            )

    def _at_node(self, chair: Chair) -> None:
        """Reached a junction. The one place a chair may change its mind."""
        if chair.pending_goal is not None and chair.route is not None:
            goal = chair.pending_goal
            chair.pending_goal = None
            replanned = self._plan_for(chair, chair.node, goal)
            if replanned is None:
                self.log("unroutable", f"no way from {chair.node} to {goal}", chair.id)
            else:
                held = chair.held_segment
                self._set_route(chair, replanned)
                chair.held_segment = held
                self.log("replanned", f"{chair.node} -> {goal}", chair.id)

        if chair.route is not None and chair.leg >= len(chair.route.segments):
            self._arrived(chair)

    def _arrived(self, chair: Chair) -> None:
        if chair.held_segment is not None:
            self.reservations.release(chair.held_segment, chair.id)
            chair.held_segment = None
        chair.route = None

        if chair.state is ChairState.TO_PICKUP:
            chair.state = ChairState.BOARDING
            chair.dwell_remaining_s = BOARDING_DWELL_S
            passenger = chair.request.passenger if chair.request else "passenger"
            self.log("at_pickup", f"waiting for {passenger} to board at {chair.node}", chair.id)

        elif chair.state is ChairState.CARRYING:
            chair.state = ChairState.ALIGHTING
            chair.dwell_remaining_s = ALIGHTING_DWELL_S
            if chair.request is not None:
                chair.request.delivered_s = self.now
                self.log(
                    "delivered",
                    f"{chair.request.passenger} at {chair.node} "
                    f"({chair.request.wait_time_s(self.now):.0f}s wait for a chair)",
                    chair.id,
                )

        elif chair.state is ChairState.RETURNING:
            chair.state = ChairState.CHARGING
            self.log("docked", f"on charge at {chair.node} ({chair.battery_fraction:.0%})", chair.id)

    def _dwell_finished(self, chair: Chair) -> None:
        chair.dwell_remaining_s = 0.0

        if chair.state is ChairState.BOARDING and chair.request is not None:
            chair.request.picked_up_s = self.now
            onward = self._plan_for(chair, chair.node, chair.request.gate)
            if onward is None:
                self.log("unroutable", f"no way to {chair.request.gate}", chair.id)
                chair.state = ChairState.IDLE
                return
            chair.state = ChairState.CARRYING
            self._set_route(chair, onward)
            self.log(
                "departing",
                f"{chair.request.passenger} to {chair.request.gate} "
                f"({onward.distance_m:.0f} m, eta {onward.duration_s:.0f}s)",
                chair.id,
            )

        elif chair.state is ChairState.ALIGHTING:
            chair.request = None
            self._send_home(chair)

    def _send_home(self, chair: Chair) -> None:
        """Put the chair back on charge by itself. Nobody comes to fetch it."""
        dock = self._nearest_dock(chair.node)
        home = self._plan_for(chair, chair.node, dock)
        if home is None:
            chair.state = ChairState.IDLE
            self.log("stranded", f"no route to a dock from {chair.node}", chair.id)
            return
        chair.state = ChairState.RETURNING
        self._set_route(chair, home)
        self.log("returning", f"to {dock} unaccompanied ({home.distance_m:.0f} m)", chair.id)

    # -- reporting -------------------------------------------------------

    def summary(self) -> dict[str, float | int]:
        delivered = [r for r in self.requests if r.delivered_s is not None]
        waits = [r.wait_time_s(self.now) for r in delivered]
        return {
            "requests": len(self.requests),
            "delivered": len(delivered),
            "outstanding": len(self.requests) - len(delivered),
            "mean_wait_s": sum(waits) / len(waits) if waits else 0.0,
            "worst_wait_s": max(waits) if waits else 0.0,
            "escalations": sum(1 for e in self.events if e.kind == "escalation"),
        }
