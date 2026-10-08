"""Driving by hand: who may, how fast, and what it costs the chair to be steered.

The interesting assertions here are not that the joystick works. They are the
four things that have to stay true while it does: the dead man stops the chair
without anything having to notice, a stick cannot overrule the stop button,
nobody takes the controls out from under a seated passenger, and a chair that has
been driven off the line knows it no longer knows where it is.
"""

from __future__ import annotations

import pytest

from margadarshak import (
    ChairState,
    Fleet,
    build_example_terminal,
)
from margadarshak.manual import (
    ATTENDANT_SPEED_CAP_MPS,
    DEADMAN_TIMEOUT_S,
    PASSENGER_SPEED_CAP_MPS,
    Command,
    ControlMode,
    ControlRefused,
)


@pytest.fixture
def fleet():
    f = Fleet(build_example_terminal())
    f.add_chair("CH-01", "dock_w")
    return f


def paired(fleet, mode=ControlMode.ATTENDANT, device="HS-1"):
    fleet.pair_device(device, "CH-01", mode)
    return device


def drive(fleet, chair_id, throttle, seconds, dt=0.2):
    """Hold the stick, the way a real handset does — a command every tick.

    One command and then silence is not driving; it is letting go, and the dead
    man is supposed to stop the chair. So a test that means to drive has to keep
    sending, at a rate under DEADMAN_TIMEOUT_S.
    """
    elapsed = 0.0
    while elapsed < seconds:
        fleet.manual_command(chair_id, throttle=throttle)
        fleet.step(dt)
        elapsed += dt


# -- taking the controls -------------------------------------------------


def test_an_unpaired_phone_cannot_drive_anything(fleet):
    with pytest.raises(ControlRefused, match="pair") as caught:
        fleet.take_manual_control("CH-01", device_id="SOMEONES-PHONE", operator="?")
    assert caught.value.reason == "not_paired"


def test_a_handset_paired_to_another_chair_is_refused(fleet):
    fleet.add_chair("CH-02", "dock_e")
    fleet.pair_device("HS-1", "CH-02", ControlMode.ATTENDANT)

    with pytest.raises(ControlRefused) as caught:
        fleet.take_manual_control("CH-01", device_id="HS-1", operator="Mr Dias")
    assert caught.value.reason == "wrong_chair"


def test_a_pairing_left_unused_stops_working(fleet):
    """A handset on a charging shelf should not still drive a chair tomorrow."""
    device = paired(fleet)
    fleet.now += 16 * 60

    with pytest.raises(ControlRefused) as caught:
        fleet.take_manual_control("CH-01", device_id=device, operator="Mr Dias")
    assert caught.value.reason == "pairing_expired"


def test_taking_control_drops_the_corridor_and_the_route(fleet):
    """It is leaving the guide path, so both are about to be wrong."""
    fleet.request_assistance("Mrs Pereira", "AI-612", pickup="kerb", gate="g4")
    fleet.run(duration_s=60)
    chair = fleet.chairs["CH-01"]
    assert chair.route is not None

    fleet.take_manual_control("CH-01", device_id=paired(fleet), operator="Mr Dias")

    assert chair.route is None
    assert chair.held_segment is None
    assert not any("CH-01" in fleet.reservations.holders(s) for s in fleet.tmap.segments)


# -- the stop button outranks the stick ----------------------------------


def test_a_latched_stop_cannot_be_driven_out_of(fleet):
    device = paired(fleet)
    fleet.emergency_stop("CH-01", "passenger pressed the button")

    with pytest.raises(ControlRefused) as caught:
        fleet.take_manual_control("CH-01", device_id=device, operator="Mr Dias")
    assert caught.value.reason == "estopped"


def test_the_stop_button_takes_the_chair_back_from_whoever_was_driving(fleet):
    fleet.take_manual_control("CH-01", device_id=paired(fleet), operator="Mr Dias")
    fleet.manual_command("CH-01", throttle=1.0)

    fleet.emergency_stop("CH-01", "something in the way")
    fleet.run(duration_s=2)

    chair = fleet.chairs["CH-01"]
    assert chair.state is ChairState.ESTOP
    assert not chair.manual.active, "clearing a stop must not hand the stick back"


# -- nobody is steered out from under -------------------------------------


def carry_someone(fleet):
    """Run until the chair actually has a passenger in it."""
    fleet.request_assistance("Mrs Pereira", "AI-612", pickup="kerb", gate="g4")
    for _ in range(900):
        fleet.step(1.0)
        if fleet.chairs["CH-01"].state is ChairState.CARRYING:
            return
    raise AssertionError("the chair never picked her up")


def test_an_attendant_cannot_take_the_stick_on_an_occupied_chair(fleet):
    carry_someone(fleet)

    with pytest.raises(ControlRefused) as caught:
        fleet.take_manual_control("CH-01", device_id=paired(fleet), operator="Mr Dias")
    assert caught.value.reason == "occupied"


def test_the_passenger_may_drive_the_chair_they_are_sitting_in(fleet):
    carry_someone(fleet)

    control = fleet.take_manual_control(
        "CH-01", device_id=paired(fleet, ControlMode.PASSENGER, "ARMREST-1"),
        operator="Mrs Pereira",
    )
    assert control.mode is ControlMode.PASSENGER
    assert control.speed_cap_mps() == PASSENGER_SPEED_CAP_MPS


# -- the dead man ---------------------------------------------------------


def test_the_chair_stops_when_the_commands_stop(fleet):
    fleet.take_manual_control("CH-01", device_id=paired(fleet), operator="Mr Dias")
    fleet.manual_command("CH-01", throttle=1.0)
    chair = fleet.chairs["CH-01"]

    assert chair.manual.velocity_mps(fleet.now) == ATTENDANT_SPEED_CAP_MPS

    fleet.now += DEADMAN_TIMEOUT_S + 0.1
    assert chair.manual.velocity_mps(fleet.now) == 0.0, (
        "letting go of the stick has to stop the chair with nothing else noticing"
    )


def test_the_dead_man_is_logged_so_a_dropped_link_is_visible(fleet):
    fleet.take_manual_control("CH-01", device_id=paired(fleet), operator="Mr Dias")
    fleet.manual_command("CH-01", throttle=1.0)
    fleet.run(duration_s=3)

    assert any(event.kind == "deadman" for event in fleet.events)


def test_attendant_control_is_slower_than_the_chair_drives_itself(fleet):
    """It is a positioning control, not a way to get somewhere faster."""
    assert ATTENDANT_SPEED_CAP_MPS < PASSENGER_SPEED_CAP_MPS
    assert PASSENGER_SPEED_CAP_MPS < 1.2, "both stay under the guided walking pace"


def test_the_handset_cannot_talk_the_chair_past_its_speed_cap(fleet):
    fleet.take_manual_control("CH-01", device_id=paired(fleet), operator="Mr Dias")
    fleet.manual_command("CH-01", throttle=99.0)

    chair = fleet.chairs["CH-01"]
    assert chair.manual.command.throttle == 1.0
    assert chair.manual.velocity_mps(fleet.now) == ATTENDANT_SPEED_CAP_MPS


def test_a_second_device_cannot_butt_in(fleet):
    fleet.take_manual_control("CH-01", device_id=paired(fleet), operator="Mr Dias")
    fleet.pair_device("HS-2", "CH-01", ControlMode.ATTENDANT)

    with pytest.raises(ControlRefused) as caught:
        fleet.manual_command("CH-01", throttle=1.0, device_id="HS-2")
    assert caught.value.reason == "wrong_device"


# -- being steered loses the chair's place --------------------------------


def test_a_chair_driven_by_hand_no_longer_knows_where_it_is(fleet):
    fleet.take_manual_control("CH-01", device_id=paired(fleet), operator="Mr Dias")
    drive(fleet, "CH-01", throttle=0.8, seconds=2)

    assert not fleet.chairs["CH-01"].position_known


def test_a_lost_chair_is_not_dispatched(fleet):
    """Routing from a node it is not standing at is how a guided system crashes."""
    fleet.take_manual_control("CH-01", device_id=paired(fleet), operator="Mr Dias")
    drive(fleet, "CH-01", throttle=0.8, seconds=2)
    fleet.release_manual_control("CH-01")

    chair = fleet.chairs["CH-01"]
    assert not chair.position_known
    assert not chair.available

    fleet.request_assistance("Mrs Pereira", "AI-612", pickup="kerb", gate="g4")
    fleet.run(duration_s=300)
    assert fleet.requests[0].assigned_to is None, "a chair that is lost must not take work"


def test_reading_a_floor_tag_puts_it_back_to_work(fleet):
    fleet.take_manual_control("CH-01", device_id=paired(fleet), operator="Mr Dias")
    drive(fleet, "CH-01", throttle=0.8, seconds=2)
    fleet.release_manual_control("CH-01")

    fleet.confirm_position("CH-01", "sec_q")

    chair = fleet.chairs["CH-01"]
    assert chair.position_known and chair.node == "sec_q" and chair.available
    assert any(event.kind == "position_found" for event in fleet.events)

    fleet.request_assistance("Mrs Pereira", "AI-612", pickup="kerb", gate="g4")
    fleet.run(duration_s=600)
    assert fleet.requests[0].assigned_to == "CH-01"


def test_handing_back_at_a_known_tag_needs_no_second_step(fleet):
    fleet.take_manual_control("CH-01", device_id=paired(fleet), operator="Mr Dias")
    drive(fleet, "CH-01", throttle=0.8, seconds=2)

    fleet.release_manual_control("CH-01", at_node="sec_q")

    chair = fleet.chairs["CH-01"]
    assert chair.position_known and chair.node == "sec_q"
    assert chair.state is ChairState.IDLE and chair.available


def test_a_chair_being_driven_takes_no_dispatch_work(fleet):
    fleet.take_manual_control("CH-01", device_id=paired(fleet), operator="Mr Dias")

    fleet.request_assistance("Mrs Pereira", "AI-612", pickup="kerb", gate="g4")
    fleet.run(duration_s=120)

    assert fleet.requests[0].assigned_to is None


# -- the command itself ---------------------------------------------------


@pytest.mark.parametrize("value,expected", [(5.0, 1.0), (-5.0, -1.0), (0.5, 0.5)])
def test_a_command_is_clamped_whatever_the_handset_sends(value, expected):
    assert Command(throttle=value).throttle == expected
    assert Command(steer=value).steer == expected
