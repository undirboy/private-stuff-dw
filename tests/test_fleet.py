"""Dispatcher and fleet-behaviour tests."""

from __future__ import annotations

import pytest

from margadarshak import ChairState, Fleet, Node, NodeKind, TerminalMap, build_example_terminal, plan
from margadarshak.fleet import BATTERY_WH, SegmentReservations


@pytest.fixture
def fleet():
    f = Fleet(build_example_terminal())
    f.add_chair("CH-01", "dock_w")
    return f


def kinds(fleet: Fleet) -> list[str]:
    return [e.kind for e in fleet.events]


def find(fleet: Fleet, kind: str):
    return [e for e in fleet.events if e.kind == kind]


# -- the ordinary journey ------------------------------------------------


def test_a_passenger_is_collected_and_delivered(fleet):
    request = fleet.request_assistance("Mrs Pereira", "AI-612", pickup="kerb", gate="g4")
    fleet.run(duration_s=1200)

    assert request.assigned_to == "CH-01"
    assert request.picked_up_s is not None
    assert request.delivered_s is not None
    assert request.picked_up_s < request.delivered_s
    assert fleet.summary()["delivered"] == 1


def test_the_chair_puts_itself_back_on_charge(fleet):
    """Nobody has to walk out and fetch the chair. This is the labour saving."""
    fleet.request_assistance("Mr Naik", "6E-204", pickup="kerb", gate="g1")
    fleet.run(duration_s=2400)

    chair = fleet.chairs["CH-01"]
    assert chair.state is ChairState.CHARGING
    assert fleet.tmap.nodes[chair.node].kind.value == "dock"
    assert find(fleet, "returning")


def test_battery_drains_while_working_and_refills_at_the_dock(fleet):
    fleet.request_assistance("Mrs Pereira", "AI-612", pickup="kerb", gate="g5")
    fleet.run(duration_s=600)
    mid_journey = fleet.chairs["CH-01"].battery_wh
    assert mid_journey < BATTERY_WH

    fleet.run(duration_s=3600)
    assert fleet.chairs["CH-01"].battery_wh > mid_journey


def test_a_flat_chair_is_not_dispatched():
    f = Fleet(build_example_terminal())
    chair = f.add_chair("CH-01", "dock_w")
    chair.state = ChairState.IDLE
    chair.battery_wh = BATTERY_WH * 0.02

    request = f.request_assistance("Mrs Pereira", "AI-612", pickup="kerb", gate="g5")
    f.run(duration_s=120)
    assert request.assigned_to is None


# -- dispatch choices ----------------------------------------------------


def test_the_nearer_chair_is_sent():
    f = Fleet(build_example_terminal())
    far = f.add_chair("CH-FAR", "dock_e")
    near = f.add_chair("CH-NEAR", "dock_w")
    for chair in (far, near):
        chair.state = ChairState.IDLE

    request = f.request_assistance("Mr Naik", "6E-204", pickup="kerb", gate="g1")
    f.step()
    assert request.assigned_to == "CH-NEAR"


def test_two_passengers_get_two_different_chairs():
    f = Fleet(build_example_terminal())
    for chair_id in ("CH-01", "CH-02"):
        f.add_chair(chair_id, "dock_w").state = ChairState.IDLE

    a = f.request_assistance("Mrs Pereira", "AI-612", pickup="kerb", gate="g4")
    b = f.request_assistance("Mr Naik", "6E-204", pickup="lounge", gate="g1")
    f.run(duration_s=60)

    assert a.assigned_to is not None
    assert b.assigned_to is not None
    assert a.assigned_to != b.assigned_to


def test_a_passenger_waits_rather_than_being_dropped_when_no_chair_is_free(fleet):
    first = fleet.request_assistance("Mrs Pereira", "AI-612", pickup="kerb", gate="g4")
    fleet.step()
    second = fleet.request_assistance("Mr Naik", "6E-204", pickup="kerb", gate="g1")
    fleet.run(duration_s=60)

    assert first.assigned_to == "CH-01"
    assert second.assigned_to is None  # still queued, not lost

    fleet.run(duration_s=2400)
    assert second.delivered_s is not None  # picked up once the chair freed up


# -- the interesting cases ----------------------------------------------


def test_a_gate_change_mid_journey_diverts_the_chair(fleet):
    request = fleet.request_assistance("Mrs Pereira", "AI-612", pickup="kerb", gate="g4")
    fleet.run(duration_s=260)  # collected and under way
    assert fleet.chairs["CH-01"].state is ChairState.CARRYING

    fleet.gate_changed("AI-612", "g2")
    fleet.run(duration_s=1200)

    assert request.gate == "g2"
    assert fleet.chairs["CH-01"].request is None
    assert find(fleet, "replanned")
    delivered = find(fleet, "delivered")
    assert delivered and "g2" in delivered[0].detail


def test_a_gate_change_before_pickup_is_simply_honoured(fleet):
    request = fleet.request_assistance("Mrs Pereira", "AI-612", pickup="kerb", gate="g4")
    fleet.step()
    fleet.gate_changed("AI-612", "g5")
    fleet.run(duration_s=2400)

    assert request.gate == "g5"
    assert request.delivered_s is not None
    assert fleet.chairs["CH-01"].node in ("dock_w", "dock_e", "g5")


def test_a_closed_corridor_is_routed_around(fleet):
    fleet.request_assistance("Mrs Pereira", "AI-612", pickup="kerb", gate="g5")
    fleet.run(duration_s=300)

    fleet.block_segment("sp2~sp3", "spill")
    fleet.run(duration_s=1200)

    assert find(fleet, "rerouting"), "closing the corridor should have triggered a replan"
    assert not find(fleet, "unroutable")
    assert fleet.requests[0].delivered_s is not None
    assert fleet.chairs["CH-01"].state is ChairState.CHARGING


def test_blocking_an_unknown_segment_is_an_error(fleet):
    with pytest.raises(ValueError):
        fleet.block_segment("nowhere~nohow", "typo")


def test_emergency_stop_latches_and_frees_the_corridor(fleet):
    fleet.request_assistance("Mrs Pereira", "AI-612", pickup="kerb", gate="g4")
    fleet.run(duration_s=120)
    chair = fleet.chairs["CH-01"]
    assert chair.held_segment is not None
    held = chair.held_segment

    fleet.emergency_stop("CH-01", "passenger pressed the button")
    assert chair.state is ChairState.ESTOP
    assert chair.route is None
    assert fleet.reservations.holders(held) == set()

    # Latched: time alone does not release it.
    fleet.run(duration_s=600)
    assert chair.state is ChairState.ESTOP


# -- keeping chairs out of each other's way ------------------------------


def test_a_single_file_corridor_admits_one_chair():
    tmap = build_example_terminal()
    reservations = SegmentReservations(tmap)
    assert reservations.acquire("sec_lane~sec_exit", "CH-01")
    assert not reservations.acquire("sec_lane~sec_exit", "CH-02")

    reservations.release("sec_lane~sec_exit", "CH-01")
    assert reservations.acquire("sec_lane~sec_exit", "CH-02")


def test_a_wide_spine_admits_several_chairs():
    tmap = build_example_terminal()
    reservations = SegmentReservations(tmap)
    assert tmap.segments["sp1~sp2"].capacity == 3
    assert reservations.acquire("sp1~sp2", "CH-01")
    assert reservations.acquire("sp1~sp2", "CH-02")
    assert reservations.acquire("sp1~sp2", "CH-03")
    assert not reservations.acquire("sp1~sp2", "CH-04")


def test_reacquiring_is_idempotent():
    reservations = SegmentReservations(build_example_terminal())
    assert reservations.acquire("sec_lane~sec_exit", "CH-01")
    assert reservations.acquire("sec_lane~sec_exit", "CH-01")
    reservations.release("sec_lane~sec_exit", "CH-01")
    assert reservations.holders("sec_lane~sec_exit") == set()


def test_no_two_chairs_ever_overfill_a_corridor():
    """The invariant that matters: run a busy shift and check it every tick."""
    f = Fleet(build_example_terminal())
    for chair_id in ("CH-01", "CH-02", "CH-03", "CH-04"):
        f.add_chair(chair_id, "dock_w").state = ChairState.IDLE

    f.request_assistance("P1", "AI-612", pickup="kerb", gate="g5")
    f.request_assistance("P2", "6E-204", pickup="kerb", gate="g1")
    f.request_assistance("P3", "SG-118", pickup="sec_q", gate="g3")
    f.request_assistance("P4", "UK-880", pickup="lounge", gate="g2")

    for _ in range(3000):
        f.step()
        for segment_id, segment in f.tmap.segments.items():
            holders = f.reservations.holders(segment_id)
            assert len(holders) <= segment.capacity, (
                f"{len(holders)} chairs in {segment_id} which holds {segment.capacity}"
            )

    assert f.summary()["delivered"] == 4


def _two_corridor_map() -> TerminalMap:
    """Dock and gate joined by two single-file corridors, north and south.

    Small enough that there is exactly one thing to test: when one corridor is
    occupied, does the chair take the other?
    """
    tmap = TerminalMap("two corridors")
    tmap.add(Node("dock", NodeKind.DOCK, 0, 0, tag_id="D1"))
    tmap.add(Node("fork", NodeKind.JUNCTION, 10, 0))
    tmap.add(Node("north", NodeKind.JUNCTION, 30, 12))
    tmap.add(Node("south", NodeKind.JUNCTION, 30, -12))
    tmap.add(Node("merge", NodeKind.JUNCTION, 50, 0))
    tmap.add(Node("gate", NodeKind.GATE, 60, 0, tag_id="G1"))
    tmap.add(Node("kerb", NodeKind.PICKUP, -10, 0, tag_id="K1"))

    tmap.connect("kerb", "dock", width_m=1.8)
    tmap.connect("dock", "fork", width_m=1.8)
    tmap.connect("merge", "gate", width_m=1.8)
    # Both corridors single file, north marginally the quicker.
    tmap.connect("fork", "north", width_m=0.9, length_m=20, max_speed_mps=1.0)
    tmap.connect("north", "merge", width_m=0.9, length_m=20, max_speed_mps=1.0)
    tmap.connect("fork", "south", width_m=0.9, length_m=22, max_speed_mps=1.0)
    tmap.connect("south", "merge", width_m=0.9, length_m=22, max_speed_mps=1.0)
    assert tmap.validate() == []
    return tmap


def test_the_quicker_corridor_is_the_default():
    route = plan(_two_corridor_map(), "fork", "merge")
    assert route is not None
    assert "north" in route.nodes


def test_a_chair_routes_around_a_corridor_another_chair_is_sitting_in():
    f = Fleet(_two_corridor_map())
    # A chair has stopped dead in the north corridor and is not going anywhere.
    stalled = f.add_chair("CH-STALL", "dock")
    stalled.state = ChairState.ESTOP
    f.reservations.acquire("fork~north", "CH-STALL")

    f.add_chair("CH-MOVE", "dock").state = ChairState.IDLE
    f.request_assistance("Ms Fernandes", "SG-118", pickup="kerb", gate="gate")
    f.run(duration_s=900)

    assert f.requests[0].delivered_s is not None, "passenger was never delivered"
    assert find(f, "detour"), "the chair should have gone round, not waited forever"
    # It went the south way, and it never muscled into the occupied corridor.
    assert "CH-MOVE" not in f.reservations.holders("fork~north")
    assert "CH-STALL" in f.reservations.holders("fork~north")


def test_a_chair_with_no_way_round_escalates_to_an_attendant():
    """The honest failure mode: nose to nose with no passing bay, ask for help."""
    tmap = _two_corridor_map()
    f = Fleet(tmap)
    stalled = f.add_chair("CH-STALL", "dock")
    stalled.state = ChairState.ESTOP
    f.reservations.acquire("fork~north", "CH-STALL")
    f.reservations.acquire("fork~south", "CH-STALL")

    f.add_chair("CH-MOVE", "dock").state = ChairState.IDLE
    f.request_assistance("Ms Fernandes", "SG-118", pickup="kerb", gate="gate")
    f.run(duration_s=600)

    assert f.requests[0].delivered_s is None
    escalations = find(f, "escalation")
    assert escalations, "a chair stuck with no alternative must call for an attendant"
    assert "attendant" in escalations[0].detail
    assert f.summary()["escalations"] == 1


def test_an_empty_chair_gives_way_instead_of_waiting_for_an_attendant():
    """The jam that stopped a whole fleet, and the reason it no longer can.

    Two chairs repositioning themselves can meet in a single-file corridor with
    no way round. Nobody is sitting in either of them, so nobody needs to come
    and sort it out: one of them simply leaves. Before this, both waited for an
    attendant who never arrived, every chair that came up behind them joined the
    queue, and a fleet that was merely badly placed stopped completely.
    """
    f = Fleet(_two_corridor_map())
    stalled = f.add_chair("CH-STALL", "dock")
    stalled.state = ChairState.ESTOP
    f.reservations.acquire("fork~north", "CH-STALL")
    f.reservations.acquire("fork~south", "CH-STALL")

    f.add_chair("CH-MOVE", "dock").state = ChairState.IDLE
    f.send_to_staging("CH-MOVE", "merge")
    f.run(duration_s=600)

    assert find(f, "gave_way"), "an empty chair with no way round should stand down"
    assert not find(f, "escalation"), "and should not call an attendant to do it for it"

    chair = f.chairs["CH-MOVE"]
    assert chair.state in (ChairState.RETURNING, ChairState.CHARGING)
    assert not any(
        "CH-MOVE" in f.reservations.holders(segment_id)
        for segment_id in f.tmap.segments
    ), "a chair that has given way must not still be holding a corridor"


def test_giving_way_hands_the_passenger_back_to_the_queue():
    """A chair on the way to collect somebody is empty. It can stand down too.

    The passenger is still at the kerb, and what they need is whichever chair can
    actually reach them — not the one that has just proved it cannot.
    """
    f = Fleet(_two_corridor_map())
    stalled = f.add_chair("CH-STALL", "dock")
    stalled.state = ChairState.ESTOP
    f.reservations.acquire("fork~north", "CH-STALL")
    f.reservations.acquire("fork~south", "CH-STALL")

    f.add_chair("CH-MOVE", "dock").state = ChairState.IDLE
    # The passenger is waiting past the jam, so the chair cannot reach them.
    request = f.request_assistance("Mr Dias", "SG-118", pickup="gate", gate="kerb")
    f.run(duration_s=600)

    handbacks = find(f, "gave_way")
    assert handbacks, "an empty chair on its way to a passenger can still stand down"
    assert request.id in handbacks[0].detail
    assert "back to the queue" in handbacks[0].detail

    # The dispatcher is free to try again — and with one chair and one jam, it
    # does. What must never happen is the passenger being quietly dropped.
    assert request.active, "the passenger is still owed a chair"
    assert request in f.requests


def test_a_chair_with_somebody_aboard_does_not_give_way():
    """The limit, and it is deliberate. A passenger is not reversed out of a jam."""
    f = Fleet(_two_corridor_map())
    stalled = f.add_chair("CH-STALL", "dock")
    stalled.state = ChairState.ESTOP
    f.reservations.acquire("fork~north", "CH-STALL")
    f.reservations.acquire("fork~south", "CH-STALL")

    f.add_chair("CH-MOVE", "dock").state = ChairState.IDLE
    f.request_assistance("Ms Fernandes", "SG-118", pickup="kerb", gate="gate")
    f.run(duration_s=600)

    assert find(f, "escalation"), "two occupied chairs nose to nose need a human"
    assert not find(f, "gave_way")
    assert f.chairs["CH-MOVE"].request is not None, "the passenger is not abandoned"


def test_a_jam_between_repositioning_chairs_does_not_strand_the_passengers():
    """The end-to-end version: the fleet recovers and everybody still gets served."""
    f = Fleet(_two_corridor_map())
    stalled = f.add_chair("CH-STALL", "dock")
    stalled.state = ChairState.ESTOP
    f.reservations.acquire("fork~north", "CH-STALL")

    for chair_id in ("CH-01", "CH-02", "CH-03"):
        f.add_chair(chair_id, "dock").state = ChairState.IDLE
        f.send_to_staging(chair_id, "merge")
    f.run(duration_s=300)

    f.request_assistance("Mrs Pereira", "AI-612", pickup="kerb", gate="gate")
    f.run(duration_s=1800)

    assert f.requests[0].delivered_s is not None, (
        "a jam between empty chairs must not cost a passenger their journey"
    )


# -- reporting -----------------------------------------------------------


def test_summary_counts_what_an_operator_would_be_asked_about(fleet):
    assert fleet.summary() == {
        "requests": 0,
        "delivered": 0,
        "outstanding": 0,
        "mean_wait_s": 0.0,
        "worst_wait_s": 0.0,
        "escalations": 0,
    }

    fleet.request_assistance("Mrs Pereira", "AI-612", pickup="kerb", gate="g4")
    fleet.run(duration_s=1200)

    summary = fleet.summary()
    assert summary["requests"] == 1
    assert summary["delivered"] == 1
    assert summary["outstanding"] == 0
    assert summary["worst_wait_s"] > 0


def test_a_chair_cannot_be_docked_somewhere_that_is_not_a_dock(fleet):
    with pytest.raises(ValueError):
        fleet.add_chair("CH-99", "g1")


# -- coming back from a stop ---------------------------------------------
#
# A regression, and the worst one found: the emergency stop had no release.
# docs/safety.md said only an attendant may clear it, and no attendant could,
# because no such call existed. A chair that stopped was out of service for
# good — with whoever was sitting in it still sitting there.


def test_an_attendant_can_release_a_latched_stop():
    f = Fleet(build_example_terminal())
    f.add_chair("CH-01", "dock_w")
    f.emergency_stop("CH-01", "passenger pressed it")
    assert f.chairs["CH-01"].state is ChairState.ESTOP

    f.clear_emergency_stop("CH-01", by="Mr Dias", at_node="dock_w")

    assert f.chairs["CH-01"].state is not ChairState.ESTOP
    assert find(f, "estop_cleared")


def test_a_passenger_stopped_mid_journey_still_gets_where_they_are_going():
    f = Fleet(build_example_terminal())
    f.add_chair("CH-01", "dock_w")
    request = f.request_assistance("Mrs Pereira", "AI-612", pickup="kerb", gate="g4")
    for _ in range(900):
        f.step(1.0)
        if f.chairs["CH-01"].state is ChairState.CARRYING:
            break

    f.emergency_stop("CH-01", "she pressed the button")
    f.run(duration_s=120)
    assert request.delivered_s is None

    f.clear_emergency_stop("CH-01", by="Mr Dias", at_node="sp2")
    f.run(duration_s=1800)
    assert request.delivered_s is not None, (
        "a stop is a pause, not the end of somebody's journey"
    )


def test_clearing_a_stop_without_a_floor_tag_leaves_the_chair_lost():
    """A stop can latch part way down a corridor, so where it is must be told."""
    f = Fleet(build_example_terminal())
    f.add_chair("CH-01", "dock_w")
    f.emergency_stop("CH-01", "test")

    f.clear_emergency_stop("CH-01", by="Mr Dias")

    chair = f.chairs["CH-01"]
    assert not chair.position_known
    assert not chair.available, "it must not be routed from a node it may not be at"


def test_clearing_a_stop_that_is_not_latched_does_nothing():
    f = Fleet(build_example_terminal())
    f.add_chair("CH-01", "dock_w")
    f.clear_emergency_stop("CH-01", by="Mr Dias", at_node="dock_w")
    assert not find(f, "estop_cleared")


def test_a_stopped_caravan_is_dissolved_rather_than_half_stopped():
    """They are no longer nose to tail at a known spacing, so they are not a convoy."""
    f = Fleet(build_example_terminal())
    for index in range(3):
        f.add_chair(f"CH-{index:02d}", "dock_e")
    f.request_group(["A", "B", "C"], "UK880", pickup="kerb", gate="g5")
    f.run(duration_s=200)
    assert any(chair.caravan for chair in f.chairs.values())

    f.emergency_stop("CH-00", "test")

    assert all(chair.caravan is None for chair in f.chairs.values())


def test_a_whole_stopped_caravan_can_be_released_and_still_delivers():
    f = Fleet(build_example_terminal())
    for index in range(3):
        f.add_chair(f"CH-{index:02d}", "dock_e")
    f.request_group(["A", "B", "C"], "UK880", pickup="kerb", gate="g5")
    f.run(duration_s=200)
    f.emergency_stop("CH-00", "test")

    for chair_id, chair in f.chairs.items():
        f.clear_emergency_stop(chair_id, by="Mr Dias", at_node=chair.node)
    f.run(duration_s=3000)

    assert all(r.delivered_s is not None for r in f.requests)


# -- a chair with nothing left in it --------------------------------------


def test_a_flat_chair_asks_to_be_pushed_rather_than_driving_on_nothing():
    """It would otherwise model a journey across a terminal on an empty pack."""
    f = Fleet(build_example_terminal())
    chair = f.add_chair("CH-01", "dock_w")
    chair.node = "sec_q"
    chair.battery_wh = chair.battery_wh * 0.001

    f._send_home(chair)

    assert chair.state is not ChairState.RETURNING
    assert any("flat" in event.detail for event in f.events)


def test_stopping_a_caravan_frees_the_corridors_it_held_as_a_unit():
    """A regression, and a sharp one.

    A caravan holds corridors under one shared id (``Chair.reservation_id``).
    Dissolving the caravan before releasing them changed that id out from under
    the release, so the convoy's corridors stayed held by nobody — permanently,
    and invisibly, until the next chair to want one simply waited forever.
    """
    f = Fleet(build_example_terminal())
    for chair_id in ("CH-01", "CH-02", "CH-03"):
        f.add_chair(chair_id, "dock_e")
    f.request_group(["A", "B", "C"], "UK880", pickup="kerb", gate="g5")

    # Catch them while they are actually in a corridor: a caravan standing at a
    # node holds nothing, and this test is about what happens to what it holds.
    for _ in range(2000):
        f.step(1.0)
        in_convoy = [c for c in f.chairs.values() if c.caravan is not None]
        if in_convoy and any(f.reservations.holders(seg) for seg in f.tmap.segments):
            break
    else:
        pytest.fail("the caravan never took a corridor, so there is nothing to test")

    f.emergency_stop(in_convoy[0].id, "passenger pressed it")

    held = {s: f.reservations.holders(s) for s in f.tmap.segments
            if f.reservations.holders(s)}
    assert not held, f"corridors still held after the caravan stopped: {held}"
