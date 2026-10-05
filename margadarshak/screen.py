"""What the chair's screen shows, at any moment.

The passenger scans and the screen answers: where they are going, and roughly how
long it will take. That exchange is the whole interface. No menu, no typing, no
app, and nothing to read in a language they may not have.

This module is the one place that decides what is on the screen, so the firmware
does not have to. The chair receives finished lines of text and draws them. That
keeps the on-board code free of any opinion about language, gate numbering or
terminal layout — all of which change without warning, and none of which should
mean reflashing a chair.

    >>> content = screen_for(fleet, fleet.chairs["CH-01"])
    >>> content.primary["mr"]
    'तुम्हाला टर्मिनल १ मधील गेट ४ कडे नेत आहे.'
    >>> content.secondary["en"]
    'About 3 minutes.'

## Why two lines and not more

A 0.96" OLED at a size an elderly passenger can read from a seated position
holds about two lines. So every state produces one primary line and at most one
secondary, and the screen cycles languages rather than cramming them in. If you
fit four lines on, the text is too small for the person it is for.
"""

from __future__ import annotations

from dataclasses import dataclass

from .announce import Announcement, announce
from .fleet import Chair, ChairState, Fleet
from .graph import Node, NodeKind, TerminalMap

#: Below this, say "arriving now" rather than a minute count that keeps changing.
ARRIVING_THRESHOLD_S = 45.0


@dataclass(frozen=True)
class ScreenContent:
    """One screenful: a main line, an optional second, in every language."""

    primary: Announcement
    secondary: Announcement | None = None
    #: Draw inverted, and sound the buzzer. Reserved for a chair that has
    #: stopped and needs somebody's attention.
    attention: bool = False

    def lines(self, language: str) -> list[str]:
        out = [self.primary[language]]
        if self.secondary is not None:
            out.append(self.secondary[language])
        return out


def place_message(tmap: TerminalMap, node_id: str, *, arriving: bool) -> Announcement:
    """Name a destination the way a passenger would recognise it.

    A gate is "Gate 4, Terminal 1" when the map knows its terminal, and "Gate 4"
    when it does not — an airport with one terminal should not have "Terminal 1"
    on every screen. Anywhere that is not a gate is named by its own message, so
    the lounge is "the assistance lounge" rather than a node id.
    """
    node: Node | None = tmap.nodes.get(node_id)

    if node is None or node.kind is not NodeKind.GATE:
        if node is not None and node.kind is NodeKind.PICKUP and "lounge" in node_id:
            return announce("arrived_at_lounge" if arriving else "taking_to_lounge")
        # Nowhere with its own wording. Fall back to the lounge phrasing only for
        # the holding area; otherwise say the plain gate line with what we have.
        return announce(
            "arrived_at_gate" if arriving else "taking_to_gate",
            gate=node.code if node and node.code else node_id,
        )

    gate = node.code or node_id
    if node.terminal:
        return announce(
            "arrived_at_gate_terminal" if arriving else "taking_to_gate_terminal",
            gate=gate,
            terminal=node.terminal,
        )
    return announce("arrived_at_gate" if arriving else "taking_to_gate", gate=gate)


def eta_message(seconds_remaining: float) -> Announcement:
    """How long is left, rounded to something a person would actually say.

    Never counts down second by second: a number that changes constantly reads as
    agitation, and a passenger who is already anxious does not need it.
    """
    if seconds_remaining <= ARRIVING_THRESHOLD_S:
        return announce("arriving_now")
    minutes = max(1, round(seconds_remaining / 60))
    if minutes == 1:
        # Its own message rather than a plural rule: "1 minutes" is wrong in
        # English, and the agreement rules differ in the other three anyway.
        return announce("eta_one_minute")
    return announce("eta_minutes", minutes=minutes)


def remaining_time_s(fleet: Fleet, chair: Chair) -> float:
    """Seconds left on the chair's current route, near enough for a screen."""
    if chair.route is None or chair.leg >= len(chair.route.segments):
        return 0.0

    segment = fleet.tmap.segments[chair.route.segments[chair.leg]]
    speed = segment.max_speed_mps
    if chair.speed_cap_mps is not None:
        speed = min(speed, chair.speed_cap_mps)
    total = max(segment.length_m - chair.progress_m, 0.0) / speed

    for segment_id in chair.route.segments[chair.leg + 1 :]:
        later = fleet.tmap.segments[segment_id]
        later_speed = later.max_speed_mps
        if chair.speed_cap_mps is not None:
            later_speed = min(later_speed, chair.speed_cap_mps)
        total += later.length_m / later_speed
    return total


def screen_for(fleet: Fleet, chair: Chair) -> ScreenContent:
    """What this chair's screen should be showing right now."""
    request = chair.request

    if chair.state is ChairState.ESTOP:
        return ScreenContent(announce("stopped_for_staff"), attention=True)

    if chair.state is ChairState.BLOCKED:
        return ScreenContent(announce("obstacle_pausing"))

    if chair.state is ChairState.AWAITING_DESTINATION:
        # The chair has collected somebody and nobody has said where to. This is
        # the screen that turns a scan into the entire interaction.
        return ScreenContent(announce("scan_your_pass"))

    if chair.state is ChairState.BOARDING and request is not None:
        primary = announce("welcome", name=request.passenger)
        secondary = (
            place_message(fleet.tmap, request.gate, arriving=False)
            if request.gate is not None
            else announce("scan_your_pass")
        )
        return ScreenContent(primary, secondary)

    if chair.state is ChairState.CARRYING and request is not None and request.gate:
        return ScreenContent(
            place_message(fleet.tmap, request.gate, arriving=False),
            eta_message(remaining_time_s(fleet, chair)),
        )

    if chair.state is ChairState.ALIGHTING and request is not None and request.gate:
        return ScreenContent(place_message(fleet.tmap, request.gate, arriving=True))

    if chair.state is ChairState.TO_PICKUP:
        return ScreenContent(announce("on_my_way"))

    if chair.state in (ChairState.IDLE, ChairState.CHARGING, ChairState.STAGING):
        return ScreenContent(announce("available_here"))

    return ScreenContent(announce("available_here"))
