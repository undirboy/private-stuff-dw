"""Driving a chair by hand — a joystick on the chair, or a phone next to it.

A guided chair that can only follow a line is not finished. It has to be moved
off the line sometimes: out of a jam, into a lift, around a works area, onto a
stand for maintenance, or simply out of the way. Today's answer is "the attendant
pushes it", and that answer gets worse the moment the chair has geared motors,
because a powered chair with the drive engaged is harder to push than a manual
one, not easier.

So there are three ways a chair can be driven, and the whole of this module is
about keeping them apart.

**GUIDED** — the normal one. The dispatcher issues a destination and the chair
follows the line to it. Nobody is steering.

**ATTENDANT** — a joystick on the handle, or a paired phone held by staff. For
repositioning and recovery. Slow, because it is a positioning control and not a
way to get somewhere faster.

**PASSENGER** — a joystick on the armrest, so the person sitting in the chair can
drive it themselves. This is the one with consequences beyond engineering: a
chair a passenger drives is a powered wheelchair, which is a different product in
front of a regulator from a guided chair that carries them along a fixed path.
Build it, but know that is the conversation it starts. See ``docs/safety.md``.

What stays refused, and it is worth being exact about the line:

    Driving a chair from the dispatcher, over the network, is not a feature and
    will not become one.

Every control here is **local**: the radio is the chair's own short-range link to
a device beside it, paired by pressing a button on the chair itself, never the
network the dispatcher speaks on. That is what keeps the original promise — there
is no path by which somebody who reaches the dispatcher makes a chair move with a
person in it. A phone is allowed to drive a chair because the phone has to be
standing next to it. A server is not, because it does not.

Three properties do the actual safety work:

1. **Dead man.** Motion lasts only as long as commands keep arriving. Let go of
   the stick, put the phone in your pocket, walk out of range, or drop the
   link, and the chair stops within :data:`DEADMAN_TIMEOUT_S`. Nothing has to
   notice the operator left; the absence of commands *is* the stop.
2. **Manual cannot overrule a stop.** The obstacle sensors and the emergency stop
   keep their authority. A joystick can ask the chair to drive into something and
   the chair will still refuse.
3. **Driving by hand loses the chair's place.** The chair knows where it is
   because it follows a known path and reads tags along it. Push it off that path
   and it no longer knows — so it is not dispatchable again until it has read a
   floor tag and been told which one. This is the part most easily forgotten, and
   it is the one that would otherwise send a chair confidently along a route from
   a node it is not standing at.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ControlMode(Enum):
    GUIDED = "guided"
    ATTENDANT = "attendant"
    PASSENGER = "passenger"

    @property
    def is_manual(self) -> bool:
        return self is not ControlMode.GUIDED


#: Stop if no command has arrived for this long. Short enough that letting go of
#: the stick feels like a brake, long enough to ride out a dropped radio packet.
DEADMAN_TIMEOUT_S = 0.5

#: Attendant control is for positioning, not travel. Slower than the chair's
#: guided speed on purpose: a person walking alongside and steering with a thumb
#: has less warning than the sensors do.
ATTENDANT_SPEED_CAP_MPS = 0.6

#: Passenger control is a little quicker, because the person steering can see
#: where they are going and is the one who gets hurt if they are wrong. Still
#: below the guided cap.
PASSENGER_SPEED_CAP_MPS = 1.0

SPEED_CAPS = {
    ControlMode.ATTENDANT: ATTENDANT_SPEED_CAP_MPS,
    ControlMode.PASSENGER: PASSENGER_SPEED_CAP_MPS,
}

#: How long a pairing lasts without use. A handset left on a charging shelf
#: should not still be able to drive a chair across the terminal next morning.
PAIRING_IDLE_TIMEOUT_S = 15 * 60


class ControlRefused(Exception):
    """Manual control was asked for and the chair said no.

    Carries a reason meant to be shown on the handset, because an attendant
    standing next to a chair that will not move needs to know why in one line.
    """

    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason
        self.message = message


@dataclass
class Command:
    """One instant of stick: how fast, and how hard to turn.

    Both are fractions rather than speeds, so the handset never has to know the
    chair's speed cap and cannot talk it into exceeding one.
    """

    throttle: float = 0.0   # -1 (full reverse) .. +1 (full forward)
    steer: float = 0.0      # -1 (full left) .. +1 (full right)

    def __post_init__(self) -> None:
        self.throttle = _clamp(self.throttle)
        self.steer = _clamp(self.steer)

    @property
    def is_stop(self) -> bool:
        return self.throttle == 0.0 and self.steer == 0.0


def _clamp(value: float) -> float:
    return max(-1.0, min(1.0, float(value)))


@dataclass
class ManualControl:
    """Who is driving this chair by hand, and whether they still are."""

    mode: ControlMode = ControlMode.GUIDED
    operator: str | None = None
    device: str | None = None
    command: Command = field(default_factory=Command)
    #: When the last command arrived. The dead man measures from here.
    last_command_s: float = 0.0
    #: When control was taken, for the shift report.
    since_s: float = 0.0

    @property
    def active(self) -> bool:
        return self.mode.is_manual

    def speed_cap_mps(self) -> float:
        return SPEED_CAPS.get(self.mode, 0.0)

    def expired(self, now_s: float) -> bool:
        """Has the operator stopped sending commands?"""
        return self.active and (now_s - self.last_command_s) > DEADMAN_TIMEOUT_S

    def velocity_mps(self, now_s: float) -> float:
        """Metres per second the chair should be doing right now.

        Returns zero the moment the dead man has lapsed, which is the whole
        mechanism: nothing has to detect that the operator left.
        """
        if not self.active or self.expired(now_s):
            return 0.0
        return self.command.throttle * self.speed_cap_mps()


@dataclass
class PairedDevice:
    """A handset or phone allowed to drive one chair.

    Pairing happens at the chair, by pressing a button on it — never over the
    network, and never from the dispatcher. That is deliberate and it is the
    reason a compromised dispatcher still cannot make anything move: it has no
    way to introduce a device to a chair.
    """

    device_id: str
    chair_id: str
    mode: ControlMode
    paired_at_s: float
    last_used_s: float

    def valid(self, now_s: float, idle_timeout_s: float = PAIRING_IDLE_TIMEOUT_S) -> bool:
        return (now_s - self.last_used_s) <= idle_timeout_s


class PairingBook:
    """Which devices may drive which chairs, and for how long."""

    def __init__(self, idle_timeout_s: float = PAIRING_IDLE_TIMEOUT_S) -> None:
        self.idle_timeout_s = idle_timeout_s
        self._devices: dict[str, PairedDevice] = {}

    def pair(self, device_id: str, chair_id: str, mode: ControlMode,
             now_s: float) -> PairedDevice:
        if not mode.is_manual:
            raise ValueError("pair a device for attendant or passenger control, not guided")
        device = PairedDevice(
            device_id=device_id, chair_id=chair_id, mode=mode,
            paired_at_s=now_s, last_used_s=now_s,
        )
        self._devices[device_id] = device
        return device

    def unpair(self, device_id: str) -> None:
        self._devices.pop(device_id, None)

    def check(self, device_id: str, chair_id: str, now_s: float) -> PairedDevice:
        """The device may drive this chair now, or this raises saying why not."""
        device = self._devices.get(device_id)
        if device is None:
            raise ControlRefused("not_paired", "Hold this near the chair and pair it first.")
        if device.chair_id != chair_id:
            raise ControlRefused("wrong_chair", "This handset is paired to another chair.")
        if not device.valid(now_s, self.idle_timeout_s):
            self.unpair(device_id)
            raise ControlRefused("pairing_expired", "Pairing timed out. Pair again at the chair.")
        device.last_used_s = now_s
        return device

    def __len__(self) -> int:
        return len(self._devices)
