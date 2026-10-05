"""What the chair's screen shows."""

from __future__ import annotations

import pytest

from margadarshak import (
    ChairState,
    Fleet,
    FlightBoard,
    FlightStatus,
    ScanRejected,
    build_example_terminal,
)
from margadarshak.announce import LANGUAGES
from margadarshak.boardingpass import encode
from margadarshak.graph import Node, NodeKind, TerminalMap
from margadarshak.screen import (
    ARRIVING_THRESHOLD_S,
    eta_message,
    place_message,
    remaining_time_s,
    screen_for,
)

PEREIRA = encode(
    family_name="PEREIRA",
    given_name="MARIA",
    title="MRS",
    pnr="ABC123",
    origin="GOI",
    destination="BOM",
    carrier="AI",
    flight_number="612",
    day_of_year=280,
)


@pytest.fixture
def fleet():
    board = FlightBoard()
    board.upsert("AI612", status=FlightStatus.GATE_ASSIGNED, gate="g4")
    f = Fleet(build_example_terminal(), board=board, holding_area="lounge")
    f.add_chair("CH-01", "dock_w").state = ChairState.IDLE
    return f


def screen(fleet: Fleet):
    return screen_for(fleet, fleet.chairs["CH-01"])


# -- naming a place the passenger would recognise ------------------------


def test_a_gate_is_named_with_its_terminal():
    tmap = build_example_terminal()
    assert place_message(tmap, "g4", arriving=False)["en"] == "Taking you to Gate 4, Terminal 1."


def test_the_gate_number_comes_from_the_map_not_the_node_id():
    """The passenger is told "Gate 4", never "g4"."""
    tmap = build_example_terminal()
    for language in LANGUAGES:
        text = place_message(tmap, "g4", arriving=False)[language]
        assert "g4" not in text
        assert "4" in text or "४" in text


def test_a_single_terminal_airport_is_not_told_its_terminal_number():
    """"Terminal 1" on every screen of a one-terminal airport is noise."""
    tmap = TerminalMap("one terminal")
    tmap.add(Node("dock", NodeKind.DOCK, 0, 0, tag_id="D1"))
    tmap.add(Node("g1", NodeKind.GATE, 10, 0, "Gate 1", tag_id="G1", code="1"))
    tmap.connect("dock", "g1")

    text = place_message(tmap, "g1", arriving=False)["en"]
    assert text == "Taking you to Gate 1."
    assert "Terminal" not in text


def test_the_lounge_is_named_rather_than_called_a_gate():
    tmap = build_example_terminal()
    assert "lounge" in place_message(tmap, "lounge", arriving=False)["en"].lower()
    assert "Gate" not in place_message(tmap, "lounge", arriving=False)["en"]


def test_arriving_switches_the_wording():
    tmap = build_example_terminal()
    assert "arrived" in place_message(tmap, "g4", arriving=True)["en"]
    assert "Taking" in place_message(tmap, "g4", arriving=False)["en"]


# -- the estimate --------------------------------------------------------


def test_a_short_remainder_says_arriving_rather_than_a_number():
    """A count that keeps changing reads as agitation to an anxious passenger."""
    assert eta_message(ARRIVING_THRESHOLD_S - 1)["en"] == "Arriving now."


def test_one_minute_is_singular_in_every_language():
    message = eta_message(70)
    assert message["en"] == "About a minute."
    assert "1" not in message["en"]
    for language in LANGUAGES:
        assert "१" not in message[language]


def test_minutes_are_rounded_to_something_a_person_would_say():
    assert eta_message(200)["en"] == "About 3 minutes."
    assert eta_message(400)["en"] == "About 7 minutes."


def test_the_estimate_falls_as_the_chair_travels(fleet):
    fleet.scan_boarding_pass(PEREIRA, pickup="kerb")
    fleet.run(duration_s=200)
    first = remaining_time_s(fleet, fleet.chairs["CH-01"])
    fleet.run(duration_s=60)
    assert remaining_time_s(fleet, fleet.chairs["CH-01"]) < first


def test_a_slower_chair_is_given_a_longer_estimate():
    """A chair capped for a frail passenger must not promise the fast time."""
    quick = Fleet(build_example_terminal())
    quick.add_chair("CH-01", "dock_w").state = ChairState.IDLE
    gentle = Fleet(build_example_terminal())
    gentle.add_chair("CH-01", "dock_w", speed_cap_mps=0.5).state = ChairState.IDLE

    for f in (quick, gentle):
        f.request_assistance("Mrs Pereira", "AI612", pickup="kerb", gate="g4")
        f.run(duration_s=5)

    assert remaining_time_s(gentle, gentle.chairs["CH-01"]) > remaining_time_s(
        quick, quick.chairs["CH-01"]
    )


# -- the screen through a journey ----------------------------------------


def test_an_idle_chair_invites_somebody_to_press_the_button(fleet):
    assert "button" in screen(fleet).primary["en"].lower()


def test_scanning_puts_the_gate_and_terminal_on_the_screen(fleet):
    """What the passenger asked for: scan, and the screen answers."""
    fleet.scan_boarding_pass(PEREIRA, pickup="kerb")
    fleet.run(duration_s=300)

    content = screen(fleet)
    assert fleet.chairs["CH-01"].state is ChairState.CARRYING
    assert content.primary["en"] == "Taking you to Gate 4, Terminal 1."
    assert content.secondary is not None
    assert "minute" in content.secondary["en"]


def test_the_screen_greets_the_passenger_while_they_board(fleet):
    fleet.scan_boarding_pass(PEREIRA, pickup="kerb")
    fleet.run(duration_s=160)

    content = screen(fleet)
    assert fleet.chairs["CH-01"].state is ChairState.BOARDING
    assert "Mrs Pereira" in content.primary["en"]
    assert content.secondary is not None
    assert "Gate 4" in content.secondary["en"]


def test_arrival_is_announced(fleet):
    request = fleet.scan_boarding_pass(PEREIRA, pickup="kerb")
    while request.delivered_s is None and fleet.now < 1200:
        fleet.step()

    assert fleet.chairs["CH-01"].state is ChairState.ALIGHTING
    assert screen(fleet).primary["en"] == "We have arrived at Gate 4, Terminal 1."


def test_a_call_button_chair_asks_for_a_boarding_pass(fleet):
    fleet.register_call_point("g3", label="Gate 3")
    fleet.press_call_button("g3", passenger="Mr Dias")
    fleet.run(duration_s=900)

    assert fleet.chairs["CH-01"].state is ChairState.AWAITING_DESTINATION
    assert "boarding pass" in screen(fleet).primary["en"].lower()


def test_an_emergency_stop_asks_for_attention(fleet):
    fleet.scan_boarding_pass(PEREIRA, pickup="kerb")
    fleet.run(duration_s=200)
    fleet.emergency_stop("CH-01", "button pressed")

    content = screen(fleet)
    assert content.attention is True
    assert "staff" in content.primary["en"].lower()


def test_being_held_up_is_explained_rather_than_left_blank(fleet):
    """A chair that stops without saying why is the worst case for a passenger."""
    fleet.scan_boarding_pass(PEREIRA, pickup="kerb")
    fleet.run(duration_s=200)
    fleet.chairs["CH-01"].state = ChairState.BLOCKED
    assert "way" in screen(fleet).primary["en"].lower()


def test_every_state_produces_something_readable_in_every_language(fleet):
    """No state may leave the screen blank or half-translated."""
    fleet.register_call_point("g3")
    fleet.scan_boarding_pass(PEREIRA, pickup="kerb")

    seen: set[ChairState] = set()
    for _ in range(1500):
        fleet.step()
        chair = fleet.chairs["CH-01"]
        seen.add(chair.state)
        content = screen_for(fleet, chair)
        for language in LANGUAGES:
            lines = content.lines(language)
            assert 1 <= len(lines) <= 2, "an OLED this size holds two readable lines"
            assert all(line.strip() for line in lines)

    assert {ChairState.TO_PICKUP, ChairState.BOARDING, ChairState.CARRYING} <= seen


# -- the bug this feature exposed ----------------------------------------


def test_a_gate_the_map_does_not_know_is_refused_at_the_scan():
    """Not after the passenger is aboard and cannot easily walk back."""
    board = FlightBoard()
    board.upsert("AI612", status=FlightStatus.GATE_ASSIGNED, gate="t2_gate_17")
    f = Fleet(build_example_terminal(), board=board, holding_area="lounge")
    f.add_chair("CH-01", "dock_w").state = ChairState.IDLE

    with pytest.raises(ScanRejected) as excinfo:
        f.scan_boarding_pass(PEREIRA, pickup="kerb")

    assert "not on this map" in excinfo.value.reason
    assert "does not serve" in excinfo.value.message
    assert f.requests == []


def test_a_gate_moving_to_an_unknown_part_of_the_airport_does_not_strand_a_chair(fleet):
    """A mid-journey move to a gate off this map must not silently lose the chair."""
    fleet.scan_boarding_pass(PEREIRA, pickup="kerb")
    fleet.run(duration_s=300)

    fleet.gate_changed("AI612", "t2_gate_17")
    fleet.run(duration_s=900)

    # An attendant is called, and the passenger is taken somewhere staffed
    # rather than to a gate their flight has left.
    assert [e for e in fleet.events if e.kind == "escalation"]
    assert fleet.requests[0].gate == "lounge"
    assert fleet.requests[0].delivered_s is not None
