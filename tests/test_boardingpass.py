"""Boarding pass parsing, and the scan-to-chair flow."""

from __future__ import annotations

import datetime as dt

import pytest

from saarthi import (
    BoardingPassError,
    ChairState,
    Fleet,
    FlightBoard,
    FlightStatus,
    ScanRejected,
    build_example_terminal,
)
from saarthi.boardingpass import HEADER_LENGTH, encode, parse

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
    seat="012A",
    sequence_number="0043",
)


# -- parsing -------------------------------------------------------------


def test_encoded_pass_is_the_right_length():
    assert len(PEREIRA) == HEADER_LENGTH


def test_mandatory_fields_round_trip():
    bp = parse(PEREIRA)
    assert bp.passenger_family_name == "PEREIRA"
    assert bp.passenger_given_name == "MARIA"
    assert bp.passenger_title == "MRS"
    assert bp.pnr == "ABC123"
    assert bp.origin == "GOI"
    assert bp.destination == "BOM"
    assert bp.carrier == "AI"
    assert bp.seat == "012A"
    assert bp.legs == 1


def test_flight_designator_drops_the_padding_zeros():
    assert parse(PEREIRA).flight_designator == "AI612"


def test_display_name_is_what_the_screen_should_say():
    assert parse(PEREIRA).display_name == "Mrs Pereira"


def test_display_name_without_a_title_falls_back_to_the_given_name():
    scan = encode(
        family_name="NAIK",
        given_name="SURESH",
        pnr="XYZ789",
        origin="GOI",
        destination="DEL",
        carrier="6E",
        flight_number="204",
        day_of_year=280,
    )
    assert parse(scan).display_name == "Suresh Naik"


def test_numeric_carrier_codes_are_accepted():
    """Several large carriers have a digit in the designator, 6E among them."""
    scan = encode(
        family_name="NAIK",
        given_name="SURESH",
        pnr="XYZ789",
        origin="GOI",
        destination="DEL",
        carrier="6E",
        flight_number="204",
        day_of_year=280,
    )
    assert parse(scan).flight_designator == "6E204"


def test_ordinal_date_resolves_against_a_given_year():
    bp = parse(PEREIRA)
    assert bp.flight_date(year=2026) == dt.date(2026, 10, 7)


def test_trailing_newline_from_the_scanner_is_tolerated():
    assert parse(PEREIRA + "\r\n").flight_designator == "AI612"


def test_conditional_section_after_the_header_is_ignored():
    """Airlines append their own data. We read 60 characters and stop."""
    assert parse(PEREIRA + ">5180 K0940 2A0123456789 0").flight_designator == "AI612"


@pytest.mark.parametrize(
    "scan, because",
    [
        ("", "empty"),
        ("SHORT", "too short"),
        ("X" + PEREIRA[1:], "wrong format code"),
        ("M0" + PEREIRA[2:], "zero legs"),
        (PEREIRA[:2] + "NOSEPARATOR" + PEREIRA[13:], "no name separator"),
        (PEREIRA[:30] + "12X" + PEREIRA[33:], "bad origin"),
        (PEREIRA[:44] + "999" + PEREIRA[47:], "day 999"),
    ],
)
def test_bad_scans_are_rejected_with_a_reason(scan, because):
    with pytest.raises(BoardingPassError):
        parse(scan)


def test_a_bag_tag_is_rejected_helpfully():
    with pytest.raises(BoardingPassError, match="bag tag"):
        parse("M1SHORT")


def test_pnr_digest_is_stable_and_keyed():
    bp = parse(PEREIRA)
    assert bp.pnr_digest(b"key-a") == bp.pnr_digest(b"key-a")
    assert bp.pnr_digest(b"key-a") != bp.pnr_digest(b"key-b")
    assert bp.pnr not in bp.pnr_digest(b"key-a")


# -- scan to chair -------------------------------------------------------


def make_fleet(**flight_kwargs):
    board = FlightBoard()
    board.upsert("AI612", **flight_kwargs)
    fleet = Fleet(build_example_terminal(), board=board, holding_area="lounge")
    fleet.add_chair("CH-01", "dock_w")
    return fleet, board


def test_a_scan_dispatches_a_chair_to_the_right_gate():
    fleet, _ = make_fleet(status=FlightStatus.GATE_ASSIGNED, gate="g4")
    request = fleet.scan_boarding_pass(PEREIRA, pickup="kerb")

    assert request.passenger == "Mrs Pereira"
    assert request.flight == "AI612"
    assert request.gate == "g4"
    assert not request.awaiting_gate

    fleet.run(duration_s=1200)
    assert request.delivered_s is not None
    assert fleet.chairs["CH-01"].state is ChairState.CHARGING


def test_the_pass_itself_never_names_the_gate():
    """The point of the flight board: the barcode carries the flight, not the gate.

    The same scan produces a different destination when the board says otherwise,
    which is only possible because the gate is looked up and not read off the pass.
    """
    first, board_a = make_fleet(status=FlightStatus.GATE_ASSIGNED, gate="g1")
    second, board_b = make_fleet(status=FlightStatus.GATE_ASSIGNED, gate="g5")
    assert first.scan_boarding_pass(PEREIRA, pickup="kerb").gate == "g1"
    assert second.scan_boarding_pass(PEREIRA, pickup="kerb").gate == "g5"


def test_scanning_twice_does_not_summon_two_chairs():
    fleet, _ = make_fleet(status=FlightStatus.GATE_ASSIGNED, gate="g4")
    first = fleet.scan_boarding_pass(PEREIRA, pickup="kerb")
    second = fleet.scan_boarding_pass(PEREIRA, pickup="kerb")
    assert first is second
    assert len(fleet.requests) == 1
    assert [e.kind for e in fleet.events].count("rescan") == 1


def test_the_booking_reference_is_not_retained():
    fleet, _ = make_fleet(status=FlightStatus.GATE_ASSIGNED, gate="g4")
    request = fleet.scan_boarding_pass(PEREIRA, pickup="kerb")

    assert request.pnr_digest is not None
    assert "ABC123" not in repr(request)
    assert all("ABC123" not in str(event) for event in fleet.events)


def test_an_unknown_flight_is_refused_with_something_the_passenger_can_act_on():
    fleet, _ = make_fleet(status=FlightStatus.GATE_ASSIGNED, gate="g4")
    other_airline = encode(
        family_name="FERNANDES",
        given_name="ANA",
        pnr="QQQ111",
        origin="GOI",
        destination="BLR",
        carrier="SG",
        flight_number="118",
        day_of_year=280,
    )
    with pytest.raises(ScanRejected) as excinfo:
        fleet.scan_boarding_pass(other_airline, pickup="kerb")
    assert "SG118" in excinfo.value.message
    assert "airline" in excinfo.value.message
    assert fleet.requests == []


def test_a_departed_flight_is_refused():
    fleet, _ = make_fleet(status=FlightStatus.DEPARTED, gate="g4")
    with pytest.raises(ScanRejected, match="departed"):
        fleet.scan_boarding_pass(PEREIRA, pickup="kerb")


def test_an_unreadable_scan_tells_the_passenger_to_try_again():
    fleet, _ = make_fleet(status=FlightStatus.GATE_ASSIGNED, gate="g4")
    with pytest.raises(ScanRejected) as excinfo:
        fleet.scan_boarding_pass("not a boarding pass at all", pickup="kerb")
    assert "try again" in excinfo.value.message.lower()


# -- the case that actually happens: no gate yet -------------------------


def test_no_gate_yet_sends_the_passenger_to_the_lounge():
    fleet, _ = make_fleet(status=FlightStatus.SCHEDULED, gate=None)
    request = fleet.scan_boarding_pass(PEREIRA, pickup="kerb")

    assert request.gate == "lounge"
    assert request.awaiting_gate

    fleet.run(duration_s=1200)
    assert request.delivered_s is not None
    assert fleet.chairs["CH-01"].node in ("lounge", "dock_w", "dock_e")


def test_when_the_gate_is_announced_a_chair_comes_back_for_them():
    """The second leg. Nobody has to remember the passenger is sitting there."""
    fleet, board = make_fleet(status=FlightStatus.SCHEDULED, gate=None)
    first = fleet.scan_boarding_pass(PEREIRA, pickup="kerb")
    fleet.run(duration_s=1500)
    assert first.delivered_s is not None
    assert len(fleet.requests) == 1

    board.assign_gate("AI612", "g5")

    assert len(fleet.requests) == 2
    second = fleet.requests[1]
    assert second.follow_on_of == first.id
    assert second.pickup == "lounge"
    assert second.gate == "g5"
    assert second.passenger == "Mrs Pereira"

    fleet.run(duration_s=1500)
    assert second.delivered_s is not None


def test_a_gate_announced_while_still_under_way_just_diverts():
    """No second leg needed: the chair is already moving, so change its mind."""
    fleet, board = make_fleet(status=FlightStatus.SCHEDULED, gate=None)
    request = fleet.scan_boarding_pass(PEREIRA, pickup="kerb")
    fleet.run(duration_s=260)
    assert fleet.chairs["CH-01"].state is ChairState.CARRYING

    board.assign_gate("AI612", "g2")
    assert len(fleet.requests) == 1, "should divert, not raise a second request"
    assert request.gate == "g2"
    assert not request.awaiting_gate

    fleet.run(duration_s=1200)
    assert request.delivered_s is not None
    assert [e for e in fleet.events if e.kind == "replanned"]


def test_a_repeated_feed_update_does_not_reroute_anybody():
    """Flight feeds repeat themselves. Only an actual change counts."""
    fleet, board = make_fleet(status=FlightStatus.GATE_ASSIGNED, gate="g4")
    fleet.scan_boarding_pass(PEREIRA, pickup="kerb")
    fleet.run(duration_s=200)

    for _ in range(5):
        board.assign_gate("AI612", "g4")
    assert [e.kind for e in fleet.events].count("gate_change") == 0


def test_the_board_rejects_a_gate_for_a_flight_it_does_not_know():
    _, board = make_fleet(status=FlightStatus.GATE_ASSIGNED, gate="g4")
    with pytest.raises(KeyError):
        board.assign_gate("XX999", "g1")


def test_a_fleet_with_no_board_says_so_rather_than_guessing():
    fleet = Fleet(build_example_terminal())
    fleet.add_chair("CH-01", "dock_w")
    with pytest.raises(ScanRejected, match="no flight board"):
        fleet.scan_boarding_pass(PEREIRA, pickup="kerb")


def test_no_gate_and_no_holding_area_is_refused_rather_than_guessed():
    board = FlightBoard()
    board.upsert("AI612", status=FlightStatus.SCHEDULED)
    fleet = Fleet(build_example_terminal(), board=board)  # no holding_area
    fleet.add_chair("CH-01", "dock_w")
    with pytest.raises(ScanRejected, match="holding area"):
        fleet.scan_boarding_pass(PEREIRA, pickup="kerb")
