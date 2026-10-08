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
from .manual import (
    Command,
    ControlMode,
    ControlRefused,
    ManualControl,
    PairingBook,
)
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

#: A gate closes before the aircraft departs, and it is the closing time a
#: passenger actually has to beat.
GATE_CLOSES_BEFORE_DEPARTURE_S = 20 * 60
#: Past this, a waiting passenger goes to the front of the queue whatever their
#: flight is doing. No passenger is left behind by a rule meant to help them.
MAX_WAIT_BEFORE_PRIORITY_S = 15 * 60

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
    AWAITING_DESTINATION = "awaiting_destination"
    STAGING = "staging"
    RETURNING = "returning"
    BLOCKED = "blocked"
    MANUAL = "manual"
    ESTOP = "estop"


#: States in which a passenger is aboard. Used wherever the rules have to be
#: stricter because a person would be the one thrown about.
OCCUPIED_STATES = frozenset(
    {
        ChairState.BOARDING,
        ChairState.CARRYING,
        ChairState.ALIGHTING,
        ChairState.AWAITING_DESTINATION,
    }
)


@dataclass
class Request:
    """One passenger's journey."""

    id: str
    passenger: str
    flight: str
    pickup: str
    #: Where the passenger is going. None when a call button was pressed and
    #: nobody has said where yet — the chair collects them first and asks after.
    gate: str | None
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
    #: Raised by a button on a wall rather than by a scan at the kerb.
    from_call_point: bool = False
    #: Shared by passengers travelling together, who are dispatched as one
    #: caravan rather than as unrelated individuals.
    group_id: str | None = None

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


@dataclass(frozen=True)
class CallPoint:
    """A button on a wall that summons a chair.

    The gap this closes: today a passenger delivered to a gate is stranded there
    until somebody remembers them. A button at the gate, the lounge and the
    accessible toilet turns a one-way ride into a service.

    ``default_destination`` is for the places where the answer is always the
    same — an arrivals gate button means "take me to the exit" — and is left
    None where it is not, in which case the chair comes and then asks.
    """

    node: str
    label: str = ""
    default_destination: str | None = None


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
    #: Caravan this chair is travelling in, if any. Members share a reservation
    #: identity, so they occupy a corridor as one unit instead of queuing for it
    #: one at a time.
    caravan: str | None = None
    dwell_remaining_s: float = 0.0
    #: How long this chair has been unable to move. Accumulates across replans,
    #: and is only cleared when the chair actually enters a corridor — otherwise a
    #: chair can swap between two occupied routes forever, resetting its own
    #: patience each time, and never admit that it is stuck.
    blocked_s: float = 0.0
    replan_attempts: int = 0
    #: Who is driving by hand, if anyone. See :mod:`margadarshak.manual`.
    manual: ManualControl = field(default_factory=ManualControl)
    #: Does ``node`` still say where this chair actually is? Driving by hand
    #: takes it off the guide path, and from that moment the dispatcher has no
    #: idea where it is standing until a floor tag says so. A chair whose
    #: position is unknown is not dispatchable — sending it along a route from a
    #: node it is not at is how a guided system drives into a wall.
    position_known: bool = True
    escalated: bool = False
    #: Set when the destination changes mid-journey. Applied at the next node,
    #: because a chair on a guide line between two junctions has nowhere to turn.
    pending_goal: str | None = None

    @property
    def reservation_id(self) -> str:
        """Who holds a corridor on this chair's behalf.

        A caravan claims corridors as a unit: its members travel nose to tail in
        one lane, so they must not block each other, and together they fill the
        lane exactly once. Keeping the physical spacing between them is the
        on-board follower's job, not the dispatcher's.
        """
        return self.caravan or self.id

    @property
    def battery_fraction(self) -> float:
        return self.battery_wh / BATTERY_WH

    @property
    def occupied(self) -> bool:
        return self.state in OCCUPIED_STATES

    @property
    def available(self) -> bool:
        if self.battery_fraction <= BATTERY_RESERVE_FRACTION:
            return False
        if self.manual.active or not self.position_known:
            return False
        if self.state in (ChairState.IDLE, ChairState.CHARGING):
            return True
        # A chair on its way to a staging point is still free work, but it may
        # only be redirected while it is sitting at a node: re-planning from
        # part way along a corridor would teleport it back to the last junction.
        return self.state is ChairState.STAGING and self.progress_m == 0.0

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
        scan_secret: bytes = b"margadarshak-dev-key-replace-in-deployment",
    ) -> None:
        self.tmap = tmap
        self.now = now_s
        self.chairs: dict[str, Chair] = {}
        self.requests: list[Request] = []
        self.events: list[Event] = []
        self.blocked_segments: set[str] = set()
        self.reservations = SegmentReservations(tmap)
        self._request_seq = 0
        self._group_seq = 0

        #: Every state change, as (time, chair id, state). Enough to draw a shift
        #: on a timeline, and small enough to keep for a whole day.
        self.history: list[tuple[float, str, ChairState]] = []
        self._last_states: dict[str, ChairState] = {}

        #: Where a passenger goes when their gate has not been announced yet.
        self.holding_area = holding_area
        self.call_points: dict[str, CallPoint] = {}
        #: Devices allowed to drive a chair by hand. Paired at the chair.
        self.pairings = PairingBook()
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
        self._record_state(chair)
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
        self.log(
            "request",
            f"{request.id} {passenger} {flight or '—'} {pickup} -> "
            f"{gate if gate is not None else '(to be set)'}",
        )
        return request

    def request_group(
        self, passengers: list[str], flight: str, pickup: str, gate: str
    ) -> list[Request]:
        """A family, or anyone travelling together, asks for chairs.

        They are dispatched as one caravan: the chairs move together, share the
        corridors they claim rather than queuing for them one at a time, and
        arrive together. One attendant can shepherd the group instead of making
        three separate trips, and nobody is separated from the people they are
        travelling with.
        """
        if not passengers:
            raise ValueError("a group needs at least one passenger")

        self._group_seq += 1
        group_id = f"G{self._group_seq:03d}"
        requests = [
            self.request_assistance(passenger=p, flight=flight, pickup=pickup, gate=gate)
            for p in passengers
        ]
        for request in requests:
            request.group_id = group_id
        self.log("group", f"{group_id}: {len(requests)} travelling together to {gate}")
        return requests

    def register_call_point(
        self, node: str, *, label: str = "", default_destination: str | None = None
    ) -> CallPoint:
        """Put a button on the wall at this node."""
        for name in (node, default_destination):
            if name is not None and name not in self.tmap.nodes:
                raise ValueError(f"unknown node {name}")
        call_point = CallPoint(node=node, label=label, default_destination=default_destination)
        self.call_points[node] = call_point
        return call_point

    def press_call_button(self, node: str, passenger: str = "Passenger") -> Request:
        """Somebody pressed the button. Send the nearest free chair.

        Where the button has no fixed destination, the request is raised with
        none: the chair goes, collects them, and waits to be told. It never
        guesses where somebody wants to go.
        """
        call_point = self.call_points.get(node)
        if call_point is None:
            raise ValueError(f"no call point at {node}")

        # One press is one chair. A second press while a chair is already coming
        # is somebody impatient, not somebody else.
        for existing in self.requests:
            if existing.pickup == node and existing.active and existing.from_call_point:
                self.log("call_repeat", f"{node} already has {existing.id}")
                return existing

        request = self.request_assistance(
            passenger=passenger,
            flight="",
            pickup=node,
            gate=call_point.default_destination,
        )
        request.from_call_point = True
        self.log("call_button", f"{call_point.label or node} pressed")
        return request

    def set_destination(self, request: Request, node: str) -> None:
        """Tell a waiting chair where its passenger is going.

        Called by an attendant, or by the touchscreen. A boarding pass scan does
        the same thing without anybody having to speak a shared language.
        """
        if node not in self.tmap.nodes:
            raise ValueError(f"unknown node {node}")
        request.gate = node

        chair = self.chairs.get(request.assigned_to) if request.assigned_to else None
        if chair is not None and chair.state is ChairState.AWAITING_DESTINATION:
            self._depart(chair)

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

        if flight.gate is not None and flight.gate not in self.tmap.nodes:
            # The board named a gate this map has never heard of — most likely
            # another terminal, or a renumbering the map has not caught up with.
            # Refuse now. Discovering it after the passenger is aboard strands
            # them somewhere they cannot easily walk back from.
            raise ScanRejected(
                f"{designator} boards at {flight.gate}, which is not on this map",
                f"Flight {designator} boards from a part of the airport this chair "
                "does not serve. Please ask a member of staff.",
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

        # If a chair is already here with this passenger aboard, waiting to be
        # told where to go, the scan is the answer to that question rather than a
        # fresh call for a chair.
        request = self._pending_destination_at(pickup)
        if request is not None:
            request.passenger = boarding_pass.display_name
            request.flight = designator
            self.set_destination(request, destination)
        else:
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

    def _pending_destination_at(self, node: str) -> Request | None:
        """A passenger sitting in a chair at this node, waiting to say where to."""
        for chair in self.chairs.values():
            if (
                chair.state is ChairState.AWAITING_DESTINATION
                and chair.node == node
                and chair.request is not None
            ):
                return chair.request
        return None

    def _on_gate_assigned(self, flight: str, gate: str) -> None:
        """The flight board told us a gate was set or moved."""
        self.gate_changed(flight, gate)

    def gate_changed(self, flight: str, new_gate: str) -> None:
        """The airline moved a flight. Chairs already under way are redirected.

        This is the case that a printed sign and a human pushing a wheelchair
        handle badly, and it is the most convincing thing the system does.
        """
        if new_gate not in self.tmap.nodes:
            # The flight has moved somewhere this map does not cover — another
            # terminal, most likely. We cannot drive there, and we must not
            # quietly carry on to a gate the flight has left.
            self.log(
                "escalation",
                f"{flight} moved to {new_gate}, which is not on this map; attendant needed",
            )
            for request in self.requests:
                if request.flight != flight or not request.active:
                    continue
                if self.holding_area is None:
                    continue
                request.gate = self.holding_area
                chair = self.chairs.get(request.assigned_to) if request.assigned_to else None
                if chair is not None and chair.state is ChairState.CARRYING:
                    chair.pending_goal = self.holding_area
                    self.log(
                        "rerouting",
                        f"{request.passenger} to the lounge for a staff handover",
                        chair.id,
                    )
            return

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

    # -- driving by hand -------------------------------------------------

    def pair_device(self, device_id: str, chair_id: str, mode: ControlMode):
        """Register a handset or phone against one chair.

        In a deployment this is the result of somebody pressing the pair button
        on the chair itself. It is modelled here so the rules around it can be
        tested; the dispatcher must never be able to do this on its own.
        """
        if chair_id not in self.chairs:
            raise KeyError(f"no chair {chair_id}")
        device = self.pairings.pair(device_id, chair_id, mode, self.now)
        self.log("paired", f"{device_id} may drive this chair ({mode.value})", chair_id)
        return device

    def take_manual_control(
        self, chair_id: str, *, device_id: str, operator: str
    ) -> ManualControl:
        """Hand a chair over to a joystick or a phone.

        Refuses while somebody is aboard unless the mode is passenger control:
        an attendant taking the stick on an occupied chair without the passenger
        expecting it is how somebody gets tipped out of a seat.
        """
        chair = self.chairs[chair_id]
        device = self.pairings.check(device_id, chair_id, self.now)

        if chair.state is ChairState.ESTOP:
            raise ControlRefused(
                "estopped", "The stop button is latched. Release it at the chair first."
            )
        if self._carrying_somebody(chair) and device.mode is not ControlMode.PASSENGER:
            raise ControlRefused(
                "occupied",
                "Somebody is in this chair. Use the armrest control, or let them get out.",
            )

        # It is leaving the guide path, so it gives up its claim on the corridor
        # and its route. Both would be wrong the moment it is steered anywhere.
        self.reservations.release_all(chair.reservation_id)
        chair.held_segment = None
        chair.route = None
        chair.blocked_s = 0.0
        chair.replan_attempts = 0
        chair.escalated = False

        chair.manual = ManualControl(
            mode=device.mode, operator=operator, device=device_id,
            last_command_s=self.now, since_s=self.now,
        )
        chair.state = ChairState.MANUAL
        self.log("manual_taken", f"{operator} driving ({device.mode.value})", chair_id)
        return chair.manual

    def manual_command(
        self, chair_id: str, throttle: float = 0.0, steer: float = 0.0, *,
        device_id: str | None = None,
    ) -> None:
        """One instant of stick. Keep sending these or the chair stops.

        This is the dead man, and it is deliberately the only thing holding the
        chair in motion: nothing has to notice that the operator let go, walked
        away or lost signal. The commands simply stop arriving.
        """
        chair = self.chairs[chair_id]
        if not chair.manual.active:
            raise ControlRefused("not_in_manual", "Take control of this chair first.")
        if device_id is not None:
            if device_id != chair.manual.device:
                raise ControlRefused("wrong_device", "Another device is driving this chair.")
            self.pairings.check(device_id, chair_id, self.now)

        chair.manual.command = Command(throttle=throttle, steer=steer)
        chair.manual.last_command_s = self.now

    def release_manual_control(self, chair_id: str, *, at_node: str | None = None) -> None:
        """Give the chair back to the dispatcher.

        ``at_node`` is the floor tag it is standing on. Without one the chair is
        parked but not dispatchable, because nobody — including the chair — knows
        where it is. :meth:`confirm_position` is how that gets resolved later.
        """
        chair = self.chairs[chair_id]
        if not chair.manual.active:
            return

        operator = chair.manual.operator or "someone"
        driven_s = self.now - chair.manual.since_s
        chair.manual = ManualControl()

        if at_node is not None:
            self.confirm_position(chair_id, at_node)
            chair.state = ChairState.IDLE
            self.log(
                "manual_released",
                f"{operator} handed it back at {at_node} after {driven_s:.0f}s",
                chair_id,
            )
        else:
            chair.position_known = False
            chair.state = ChairState.IDLE
            self.log(
                "manual_released",
                f"{operator} handed it back after {driven_s:.0f}s, position unknown "
                f"— needs a floor tag before it can be dispatched",
                chair_id,
            )

    def confirm_position(self, chair_id: str, node: str) -> None:
        """The chair has read a floor tag. It knows where it is again."""
        if node not in self.tmap.nodes:
            raise ValueError(f"unknown node {node}")
        chair = self.chairs[chair_id]
        was_lost = not chair.position_known
        chair.node = node
        chair.progress_m = 0.0
        chair.position_known = True
        if was_lost:
            self.log("position_found", f"read the tag at {node}", chair_id)

    def emergency_stop(self, chair_id: str, reason: str) -> None:
        """Latch a chair stopped. Only an attendant clears it.

        A caravan stops as a whole. Its members travel nose to tail, so stopping
        the front one and letting the rest drive on is exactly the collision the
        emergency stop exists to prevent.
        """
        chair = self.chairs[chair_id]
        group = [chair]
        if chair.caravan is not None:
            group = [c for c in self.chairs.values() if c.caravan == chair.caravan]

        for member in group:
            member.state = ChairState.ESTOP
            member.route = None
            member.held_segment = None
            self.log("estop", reason if member is chair else "caravan sibling stopped", member.id)

        self.reservations.release_all(chair.reservation_id)

    # -- the clock -------------------------------------------------------

    def step(self, dt_s: float = 1.0) -> None:
        self.now += dt_s
        self._dispatch()
        for chair in self.chairs.values():
            self._advance(chair, dt_s)
            self._record_state(chair)

    def _record_state(self, chair: Chair) -> None:
        """Note a state change. Sampling only on change keeps the log small."""
        if self._last_states.get(chair.id) is not chair.state:
            self._last_states[chair.id] = chair.state
            self.history.append((self.now, chair.id, chair.state))

    def run(self, duration_s: float, dt_s: float = 1.0) -> None:
        end = self.now + duration_s
        while self.now < end:
            self.step(dt_s)

    # -- dispatch --------------------------------------------------------

    def urgency(self, request: Request) -> tuple[int, float, float]:
        """Sort key deciding who gets the next free chair. Lower is sooner.

        First come, first served is the obvious rule and it is the wrong one. Two
        people ask at the same moment; one is flying in twenty minutes and one in
        three hours. Serving them in the order they arrived makes the first miss
        their flight for no reason, and the airport carries the cost.

        So the queue is ordered by how close each passenger is to their gate
        closing. Everything about this is visible: the key is a public method, the
        dispatcher logs whenever somebody is served ahead of an earlier arrival,
        and an operator can therefore explain any decision to a passenger who
        asks why the person behind them went first.

        Nobody is starved. Past ``MAX_WAIT_BEFORE_PRIORITY_S`` a passenger goes to
        the front regardless of their flight — a queue that can leave somebody
        sitting indefinitely because other people keep being more urgent is not a
        service, and an unbounded wait is the one failure a passenger will never
        forgive.
        """
        waited_s = self.now - request.created_s
        if waited_s >= MAX_WAIT_BEFORE_PRIORITY_S:
            # Waited too long. Nothing outranks this but a longer wait.
            return (0, -waited_s, request.created_s)

        closes_in = float("inf")
        if self.board is not None and request.flight:
            flight = self.board.get(request.flight)
            if flight is not None and flight.scheduled_departure_s is not None:
                closes_in = (
                    flight.scheduled_departure_s - GATE_CLOSES_BEFORE_DEPARTURE_S - self.now
                )
        return (1, closes_in, request.created_s)

    def _dispatch(self) -> None:
        """Give every waiting passenger the chair that can reach them soonest."""
        waiting = [r for r in self.requests if r.waiting]
        # Arrival order, which is what first come first served would have done.
        # Position in the list rather than creation time, so that two people who
        # ask in the same moment still have a defined order instead of neither
        # counting as ahead of the other.
        arrival_rank = {request.id: rank for rank, request in enumerate(waiting)}
        queue = sorted(waiting, key=self.urgency)

        handled: set[str] = set()
        for request in queue:
            if not request.waiting:
                continue  # a group member assigned earlier in this pass

            overtaken = [
                other
                for other in waiting
                if other.waiting
                and other is not request
                and arrival_rank[other.id] < arrival_rank[request.id]
                # Members of one caravan do not overtake each other; two
                # ungrouped requests are not "the same group" just because
                # neither has a group id.
                and not (
                    request.group_id is not None and other.group_id == request.group_id
                )
            ]

            if request.group_id is not None:
                if request.group_id in handled:
                    continue
                handled.add(request.group_id)
                self._dispatch_group(request.group_id)
            else:
                self._dispatch_one(request)

            if not request.waiting and overtaken:
                # Say so. A queue that reorders itself silently is one an
                # attendant cannot defend when a passenger asks why.
                self.log(
                    "prioritised",
                    f"{request.id} {request.passenger} went ahead of "
                    f"{len(overtaken)} earlier request(s): flight {request.flight} sooner",
                )

    def _candidates_for(self, request: Request) -> list[tuple[float, Chair, Route]]:
        """Every chair that could take this job, soonest first."""
        candidates: list[tuple[float, Chair, Route]] = []
        for chair in self.chairs.values():
            if not chair.available:
                continue
            approach = self._plan_for(chair, chair.node, request.pickup)
            if approach is None:
                continue
            journey = self._worst_case_journey(chair, request)
            if journey is None:
                continue
            if not self._has_battery_for(chair, approach, journey):
                continue
            candidates.append((approach.duration_s, chair, approach))
        candidates.sort(key=lambda item: (item[0], item[1].id))
        return candidates

    def _assign(self, request: Request, chair: Chair, approach: Route, caravan: str | None) -> None:
        request.assigned_to = chair.id
        chair.request = request
        chair.caravan = caravan
        chair.state = ChairState.TO_PICKUP
        self._set_route(chair, approach)
        self.log(
            "assigned",
            f"{request.id} {request.passenger} -> pickup at {request.pickup} "
            f"(eta {approach.duration_s:.0f}s)",
            chair.id,
        )

    def _dispatch_one(self, request: Request) -> None:
        candidates = self._candidates_for(request)
        if candidates:
            _, chair, approach = candidates[0]
            self._assign(request, chair, approach, caravan=None)

    def _dispatch_group(self, group_id: str) -> None:
        """Dispatch a caravan, or dispatch nothing.

        A group is never split. Sending two chairs now and a third in ten minutes
        separates a family and gives the airport three problems instead of one,
        so the group waits until the whole caravan can go.
        """
        members = [r for r in self.requests if r.group_id == group_id and r.waiting]
        if not members:
            return

        candidates = self._candidates_for(members[0])
        if len(candidates) < len(members):
            return

        for request, (_, chair, approach) in zip(members, candidates):
            self._assign(request, chair, approach, caravan=group_id)
        self.log("caravan", f"{group_id}: {len(members)} chairs travelling as one")

    def _worst_case_journey(self, chair: Chair, request: Request) -> Route | None:
        """The onward journey, for sizing the battery reserve.

        A call button raises a request with no destination yet, so there is
        nothing to plan to. Reserve for the furthest gate on the map instead: a
        chair that sets off and then cannot complete the journey it is given has
        stranded somebody, which is far worse than a chair that declined the job.
        """
        if request.gate is not None:
            return self._plan_for(chair, request.pickup, request.gate)

        furthest: Route | None = None
        for gate in self.tmap.nodes_of_kind(NodeKind.GATE):
            candidate = self._plan_for(chair, request.pickup, gate.id)
            if candidate is None:
                continue
            if furthest is None or candidate.distance_m > furthest.distance_m:
                furthest = candidate
        return furthest

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

    def travel_time(self, start: str, goal: str) -> float | None:
        """Seconds for an unencumbered chair to get from one node to another.

        Used for planning where chairs should wait; takes closed corridors into
        account but not corridors another chair happens to be in right now.
        """
        route = plan(self.tmap, start, goal, blocked_segments=frozenset(self.blocked_segments))
        return None if route is None else route.duration_s

    def send_to_staging(self, chair_id: str, node: str) -> bool:
        """Park an idle chair somewhere more useful. Returns False if it cannot go."""
        chair = self.chairs[chair_id]
        if not chair.available:
            return False
        if chair.node == node:
            chair.state = ChairState.IDLE
            return True

        route = self._plan_for(chair, chair.node, node)
        if route is None:
            self.log("unroutable", f"cannot stage at {node}", chair_id)
            return False

        chair.state = ChairState.STAGING
        self._set_route(chair, route)
        self.log("staging", f"moving to {node} to wait ({route.duration_s:.0f}s)", chair_id)
        return True

    def apply_staging(self, moves) -> int:
        """Carry out a set of recommendations from :mod:`margadarshak.prepositioning`."""
        return sum(1 for move in moves if self.send_to_staging(move.chair_id, move.to_node))

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
            # The stick does not outrank the stop button, and releasing the stop
            # does not hand control back to whoever was driving.
            chair.manual = ManualControl()
            return

        if chair.manual.active:
            self._drive_by_hand(chair, dt_s)
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

        if chair.state is ChairState.IDLE and chair.route is None:
            if (
                chair.battery_fraction <= BATTERY_RESERVE_FRACTION
                and self.tmap.nodes[chair.node].kind is not NodeKind.DOCK
            ):
                # Staged away from a charger and running low. Go home while there
                # is still enough charge to get there.
                self.log("low_battery", f"{chair.battery_fraction:.0%}, returning", chair.id)
                self._send_home(chair)
            return

        if chair.route is None:
            return

        if chair.leg >= len(chair.route.segments):
            self._arrived(chair)
            return

        segment = self.tmap.segments[chair.route.segments[chair.leg]]

        # Claim the corridor before entering it.
        if chair.held_segment != segment.id:
            if not self.reservations.acquire(segment.id, chair.reservation_id):
                self._wait_for_corridor(chair, segment.id, dt_s)
                return
            if chair.held_segment is not None and not self._caravan_still_in(
                chair, chair.held_segment
            ):
                self.reservations.release(chair.held_segment, chair.reservation_id)
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

    def _drive_by_hand(self, chair: Chair, dt_s: float) -> None:
        """A chair under a joystick or a phone, for one tick.

        No route, no corridor reservation and no node arithmetic: once somebody
        is steering, the chair is off the graph and the dispatcher's model of
        where it is no longer holds. All that is tracked is the battery it is
        spending and whether the operator is still there.
        """
        speed = abs(chair.manual.velocity_mps(self.now))
        if speed > 0.0:
            chair.position_known = False
            chair.battery_wh = max(0.0, chair.battery_wh - speed * dt_s * WH_PER_M)
        elif chair.manual.expired(self.now):
            if not chair.manual.command.is_stop:
                chair.manual.command = Command()
                self.log("deadman", "no command for 0.5 s; stopped", chair.id)

    def _caravan_still_in(self, chair: Chair, segment_id: str) -> bool:
        """Would releasing this corridor drop it while a caravan sibling is in it?"""
        if chair.caravan is None:
            return False
        return any(
            other is not chair
            and other.caravan == chair.caravan
            and other.held_segment == segment_id
            for other in self.chairs.values()
        )

    def _moving_state(self, chair: Chair) -> ChairState:
        """What a chair goes back to after being held up.

        An empty chair is told apart by where it is heading: towards a dock it is
        going home, anywhere else it is moving into position. Guessing "going
        home" for every empty chair is how a staging chair ends up reporting
        itself docked at a junction.
        """
        if chair.request is not None:
            return (
                ChairState.CARRYING
                if chair.request.picked_up_s is not None
                else ChairState.TO_PICKUP
            )
        if chair.route is not None:
            destination = self.tmap.nodes[chair.route.destination]
            if destination.kind is not NodeKind.DOCK:
                return ChairState.STAGING
        return ChairState.RETURNING

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
                if not self.reservations.can_enter(sid, chair.reservation_id)
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

        if chair.blocked_s < WAIT_BEFORE_ESCALATION_S:
            return

        # No way round and nobody has moved. Before calling anybody: is there
        # actually a person involved? An empty chair has nothing to lose by
        # giving up its place, and a jam between two empty chairs needs no
        # attendant at all — it needs one of them to go away. So it does.
        #
        # This matters more than it looks. Without it, one jam between two
        # chairs repositioning themselves holds a corridor forever, every chair
        # that arrives behind them joins the queue, and a fleet that was merely
        # badly placed becomes a fleet that has stopped. Whoever is sitting at
        # the kerb then waits for a chair that is never coming.
        if not self._carrying_somebody(chair):
            self._give_way(chair, segment_id)
            return

        if not chair.escalated:
            # Somebody is aboard, so this chair is not the one to move: reversing
            # a corridor with a passenger in the seat is exactly what the design
            # refuses to do. Two occupied chairs nose to nose in a single-file
            # corridor genuinely need a human. The real fix is a passing bay in
            # the floor plan — see docs/safety.md.
            chair.escalated = True
            self.log(
                "escalation",
                f"deadlocked at {chair.node} waiting on {segment_id}; attendant needed",
                chair.id,
            )

    @staticmethod
    def _carrying_somebody(chair: Chair) -> bool:
        """Is there a passenger in the seat right now?

        Not the same as having a job. A chair on its way to collect somebody is
        empty: the passenger is still at the kerb, and nothing about them is made
        worse by this chair standing down and another one going instead.
        """
        return chair.request is not None and chair.request.picked_up_s is not None

    def _give_way(self, chair: Chair, segment_id: str) -> None:
        """An empty chair stands down so a blocked corridor clears.

        It drops whatever corridor it is holding, hands back any passenger it had
        been sent to collect, and goes home. Handing the passenger back matters:
        they are still waiting, and the dispatcher should be free to send
        whichever chair can now actually reach them rather than the one that has
        just proved it cannot.
        """
        self.reservations.release_all(chair.reservation_id)
        chair.held_segment = None
        chair.blocked_s = 0.0
        chair.replan_attempts = 0
        chair.escalated = False

        request = chair.request
        if request is not None:
            request.assigned_to = None
            chair.request = None
            self.log(
                "gave_way",
                f"{segment_id} would not clear; {request.id} back to the queue",
                chair.id,
            )
        else:
            self.log("gave_way", f"{segment_id} would not clear; standing down", chair.id)

        chair.caravan = None
        self._send_home(chair)

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
            if not self._caravan_still_in(chair, chair.held_segment):
                self.reservations.release(chair.held_segment, chair.reservation_id)
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

        elif chair.state is ChairState.STAGING:
            chair.state = ChairState.IDLE
            self.log("staged", f"waiting at {chair.node}", chair.id)

        elif chair.state is ChairState.RETURNING:
            chair.state = ChairState.CHARGING
            self.log("docked", f"on charge at {chair.node} ({chair.battery_fraction:.0%})", chair.id)

    def _dwell_finished(self, chair: Chair) -> None:
        chair.dwell_remaining_s = 0.0

        if chair.state is ChairState.BOARDING and chair.request is not None:
            chair.request.picked_up_s = self.now
            if chair.request.gate is None:
                # A call button summoned this chair and nobody has said where to.
                # Wait, with the passenger aboard, until a scan or an attendant
                # says. Never guess a destination for somebody.
                chair.state = ChairState.AWAITING_DESTINATION
                self.log("awaiting_destination", f"aboard at {chair.node}", chair.id)
                return
            self._depart(chair)

        elif chair.state is ChairState.ALIGHTING:
            chair.request = None
            chair.caravan = None
            self._send_home(chair)

    def _depart(self, chair: Chair) -> None:
        """Set off for the destination now that one is known."""
        request = chair.request
        if request is None or request.gate is None:
            return
        onward = self._plan_for(chair, chair.node, request.gate)
        if onward is None:
            self.log("unroutable", f"no way to {request.gate}", chair.id)
            chair.state = ChairState.AWAITING_DESTINATION
            return
        chair.state = ChairState.CARRYING
        self._set_route(chair, onward)
        self.log(
            "departing",
            f"{request.passenger} to {request.gate} "
            f"({onward.distance_m:.0f} m, eta {onward.duration_s:.0f}s)",
            chair.id,
        )

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

    def assistance_counts(self) -> dict[str, int]:
        """Requests seen per flight, for the demand forecast to learn from.

        Counts requests raised, not journeys completed: a passenger who asked
        for a chair and gave up still represents demand, and a forecast trained
        only on the people the system managed to serve would learn to be exactly
        as short-staffed as it already is.

        Follow-on legs are excluded. A passenger parked in the lounge because
        their gate was unannounced generates a second request when the gate
        appears, but they are one person needing one chair, and counting them
        twice would inflate every route with early-arriving passengers — which
        is to say, precisely the routes that need assistance most.
        """
        counts: dict[str, int] = {}
        for request in self.requests:
            if request.follow_on_of is not None:
                continue
            if not request.flight:
                continue
            designator = request.flight.upper()
            counts[designator] = counts.get(designator, 0) + 1
        return counts

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
