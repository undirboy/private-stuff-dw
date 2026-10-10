"""Changing floors.

Every real terminal journey crosses a level, and almost everything about a lift
is unlike a corridor: the chair is not driving, the wait is set by where the car
is rather than by how wide anything is, and the floor the chair comes out on is
something it has to be able to confirm. These tests are mostly about the survey
mistakes that would strand somebody upstairs.
"""

from __future__ import annotations

import json

import pytest

from margadarshak.fleet import Fleet
from margadarshak.graph import Guide, Lift, Node, NodeKind, TerminalMap
from margadarshak.mapfile import dumps, loads
from margadarshak.router import plan, traverse_time
from margadarshak.terminal import build_two_level_terminal


def two_levels(**lift_kwargs) -> TerminalMap:
    """The smallest map with an upstairs: a dock below, a gate above."""
    tmap = TerminalMap("stack")
    tmap.add(Node("dock", NodeKind.DOCK, 0, 0, tag_id="D1"))
    tmap.add(Node("down", NodeKind.LIFT, 10, 0, tag_id="LD"))
    tmap.add(Node("up", NodeKind.LIFT, 10, 0, tag_id="LU", level=1))
    tmap.add(Node("gate", NodeKind.GATE, 20, 0, tag_id="G1", code="1", level=1))
    tmap.connect("dock", "down", width_m=2.0)
    tmap.connect("down", "up", lift=Lift("car", **lift_kwargs))
    tmap.connect("up", "gate", width_m=2.0)
    return tmap


# -- the model -------------------------------------------------------------


def test_a_flat_map_is_still_a_flat_map():
    """Levels are new, and every existing map means what it always meant."""
    tmap = two_levels()
    assert tmap.levels() == [0, 1]
    assert TerminalMap("flat").levels() == []
    assert Node("n", NodeKind.JUNCTION, 0, 0).level == 0


def test_a_lift_ride_is_quoted_by_the_car_and_not_by_a_speed():
    lift = Lift("car", call_s=25.0, door_s=6.0, ride_s_per_level=9.0)
    segment = two_levels(call_s=25.0, door_s=6.0, ride_s_per_level=9.0).segments["down~up"]
    assert segment.is_lift
    assert segment.levels_crossed == 1
    # Call, doors open, one level, doors close.
    assert segment.transit_s == pytest.approx(25.0 + 12.0 + 9.0)
    assert traverse_time(segment) == pytest.approx(segment.transit_s)
    assert lift.capacity_chairs == 1


def test_slowing_a_chair_down_does_not_slow_the_lift():
    """A frail passenger's speed cap applies to driving, which a lift is not.

    Capping the lift too would quietly make every route through one look worse
    for exactly the passengers most likely to need it.
    """
    segment = two_levels().segments["down~up"]
    assert traverse_time(segment, speed_cap_mps=0.1) == pytest.approx(segment.transit_s)

    corridor = two_levels().segments["dock~down"]
    assert traverse_time(corridor, speed_cap_mps=0.1) > traverse_time(corridor)


def test_the_car_sets_the_capacity_and_not_the_landing():
    """A wide landing does not make the car bigger."""
    tmap = TerminalMap("wide")
    tmap.add(Node("a", NodeKind.LIFT, 0, 0, tag_id="A"))
    tmap.add(Node("b", NodeKind.LIFT, 0, 0, tag_id="B", level=1))
    tmap.connect("a", "b", width_m=6.0, lift=Lift("car"))
    assert tmap.segments["a~b"].capacity == 1

    tmap.add(Node("c", NodeKind.LIFT, 0, 0, tag_id="C", level=2))
    tmap.connect("b", "c", width_m=0.8, lift=Lift("goods", capacity_chairs=3))
    assert tmap.segments["b~c"].capacity == 3


def test_a_lift_segment_is_carried_whatever_the_survey_says():
    """There is no line in a lift car to choose between."""
    tmap = two_levels()
    assert tmap.segments["down~up"].guide is Guide.CARRIED
    other = TerminalMap("x")
    other.add(Node("a", NodeKind.LIFT, 0, 0, tag_id="A"))
    other.add(Node("b", NodeKind.LIFT, 0, 0, tag_id="B", level=1))
    other.connect("a", "b", guide=Guide.MAGNETIC, lift=Lift("car"))
    assert other.segments["a~b"].guide is Guide.CARRIED


def test_two_landings_in_one_shaft_are_not_zero_metres_apart_in_time():
    tmap = two_levels()
    assert tmap.distance("down", "up") == 0.0  # horizontal, and they are stacked
    assert tmap.segments["down~up"].length_m > 0.0  # the landings it drives over
    assert tmap.segments["down~up"].transit_s > 0.0


# -- routing ---------------------------------------------------------------


def test_a_route_can_go_upstairs():
    route = plan(two_levels(), "dock", "gate")
    assert route is not None
    assert route.nodes == ["dock", "down", "up", "gate"]
    assert route.duration_s > two_levels().segments["down~up"].transit_s


def test_the_lift_ride_is_in_the_quoted_journey_time():
    """Not decoration: the battery check and the dispatcher both read this."""
    slow = plan(two_levels(call_s=120.0), "dock", "gate")
    quick = plan(two_levels(call_s=10.0), "dock", "gate")
    assert slow.duration_s - quick.duration_s == pytest.approx(110.0)
    assert slow.distance_m == pytest.approx(quick.distance_m)


def test_no_phantom_turn_at_a_lift():
    """Two stacked landings have no heading between them.

    ``atan2(0, 0)`` is due east, so without care the planner charges the chair
    for a pivot it never made — and charges it twice, once each way.
    """
    straight = plan(two_levels(), "dock", "gate")
    expected = sum(
        traverse_time(straight_segment)
        for straight_segment in (two_levels().segments[s] for s in straight.segments)
    )
    assert straight.duration_s == pytest.approx(expected)


def test_the_planner_picks_the_quicker_car():
    """Two lifts, and which one wins depends on the car, not on the drawing."""
    near_slow = build_two_level_terminal()
    assert "lb_w1" in plan(near_slow, "sec_exit", "g5").nodes

    far_quick = build_two_level_terminal()
    far_quick.segments["lb_e0~lb_e1"] = type(far_quick.segments["lb_e0~lb_e1"])(
        **{
            **far_quick.segments["lb_e0~lb_e1"].__dict__,
            "lift": Lift("lift_e", call_s=2.0),
        }
    )
    assert "lb_e1" in plan(far_quick, "sec_exit", "g5").nodes


def test_a_closed_lift_is_routed_around():
    """One car out of service, and the other one is still a way upstairs."""
    tmap = build_two_level_terminal()
    route = plan(tmap, "sec_exit", "g1", blocked_segments=frozenset({"lb_w0~lb_w1"}))
    assert route is not None
    assert "lb_e1" in route.nodes


def test_with_every_lift_closed_there_is_no_route_upstairs():
    """And the honest answer is None, not a route through the stairwell."""
    tmap = build_two_level_terminal()
    assert (
        plan(
            tmap,
            "sec_exit",
            "g1",
            blocked_segments=frozenset({"lb_w0~lb_w1", "lb_e0~lb_e1"}),
        )
        is None
    )


# -- the survey ------------------------------------------------------------


def test_the_two_level_example_is_a_sound_survey():
    tmap = build_two_level_terminal()
    assert tmap.validate() == []
    assert tmap.levels() == [0, 1]
    assert len(tmap.lifts()) == 2


def test_a_guide_line_cannot_climb():
    """The commonest drawing mistake: a ramp where there are stairs."""
    tmap = TerminalMap("climbing")
    tmap.add(Node("dock", NodeKind.DOCK, 0, 0, tag_id="D"))
    tmap.add(Node("gate", NodeKind.GATE, 10, 0, tag_id="G", code="1", level=1))
    tmap.connect("dock", "gate", width_m=2.0)
    assert any("cannot climb" in p for p in tmap.validate())


def test_a_lift_that_goes_nowhere():
    tmap = TerminalMap("flat lift")
    tmap.add(Node("dock", NodeKind.DOCK, 0, 0, tag_id="D"))
    tmap.add(Node("a", NodeKind.LIFT, 10, 0, tag_id="A"))
    tmap.connect("dock", "a", width_m=2.0)
    tmap.add(Node("b", NodeKind.LIFT, 10, 5, tag_id="B"))
    tmap.connect("a", "b", lift=Lift("car"))
    assert any("starts and ends on level 0" in p for p in tmap.validate())


def test_a_landing_with_no_floor_tag():
    """A chair out of a lift that cannot confirm its floor is a lost chair."""
    tmap = TerminalMap("untagged")
    tmap.add(Node("dock", NodeKind.DOCK, 0, 0, tag_id="D"))
    tmap.add(Node("down", NodeKind.LIFT, 10, 0, tag_id="LD"))
    tmap.add(Node("up", NodeKind.LIFT, 10, 0, level=1))  # no tag
    tmap.connect("dock", "down", width_m=2.0)
    tmap.connect("down", "up", lift=Lift("car"))
    problems = tmap.validate()
    assert any("cannot confirm which level it is on" in p for p in problems)


def test_a_gap_declared_in_a_line_that_is_not_there():
    tmap = two_levels()
    tmap.segments["down~up"] = type(tmap.segments["down~up"])(
        **{**tmap.segments["down~up"].__dict__, "gap_m": 0.5}
    )
    assert any("a line that is not there" in p for p in tmap.validate())


def test_carried_without_a_lift_to_carry_it():
    tmap = TerminalMap("carried")
    tmap.add(Node("dock", NodeKind.DOCK, 0, 0, tag_id="D"))
    tmap.add(Node("a", NodeKind.PICKUP, 10, 0, tag_id="A"))
    tmap.connect("dock", "a", guide=Guide.CARRIED, width_m=2.0)
    assert any("nothing says what carries it" in p for p in tmap.validate())


def test_one_lift_to_a_level_with_gates_is_called_out():
    """Not a bug in the code. A floor plan that strands people when a car fails.

    Said at survey time, because that is when a second lift in the plan is free.
    """
    problems = two_levels().validate()
    assert any("strands every passenger on that level" in p for p in problems)

    assert build_two_level_terminal().validate() == []


def test_a_level_with_no_gates_needs_no_second_lift():
    """A back-of-house mezzanine is not a stranding risk."""
    tmap = TerminalMap("mezzanine")
    tmap.add(Node("dock", NodeKind.DOCK, 0, 0, tag_id="D"))
    tmap.add(Node("down", NodeKind.LIFT, 10, 0, tag_id="LD"))
    tmap.add(Node("up", NodeKind.LIFT, 10, 0, tag_id="LU", level=1))
    tmap.add(Node("store", NodeKind.JUNCTION, 20, 0, level=1))
    tmap.connect("dock", "down", width_m=2.0)
    tmap.connect("down", "up", lift=Lift("car"))
    tmap.connect("up", "store", width_m=2.0)
    assert tmap.validate() == []


# -- the map file ----------------------------------------------------------


def test_levels_and_lifts_survive_the_round_trip():
    restored = loads(dumps(build_two_level_terminal()))
    assert restored.validate() == []
    assert restored.nodes["g3"].level == 1
    lift = restored.segments["lb_e0~lb_e1"].lift
    assert lift is not None
    assert lift.id == "lift_e"
    assert lift.call_s == pytest.approx(35.0)
    assert restored.segments["lb_e0~lb_e1"].levels_crossed == 1


def test_a_facilities_engineer_can_slow_a_lift_down_by_hand():
    """The whole point of the file: change a number, put it back."""
    data = json.loads(dumps(build_two_level_terminal()))
    for segment in data["segments"]:
        if segment.get("lift", {}).get("id") == "lift_w":
            segment["lift"]["call_s"] = 90.0
    edited = loads(json.dumps(data))
    assert edited.segments["lb_w0~lb_w1"].lift.call_s == pytest.approx(90.0)
    # And the route planner now sends chairs the other way.
    assert "lb_e1" in plan(edited, "sec_exit", "g5").nodes


def test_a_map_file_from_before_lifts_existed_still_loads():
    """Version 1 described one flat floor, which is what it still means."""
    data = json.loads(dumps(build_two_level_terminal()))
    data["version"] = 1
    for node in data["nodes"]:
        node.pop("level", None)
    for segment in data["segments"]:
        segment.pop("lift", None)
    old = loads(json.dumps(data))
    assert old.levels() == [0]
    assert old.lifts() == []


def test_a_lift_entry_that_is_not_an_object_says_so():
    data = json.loads(dumps(build_two_level_terminal()))
    data["segments"][0]["lift"] = "the big one"
    with pytest.raises(Exception) as exc:
        loads(json.dumps(data))
    assert "describing the car" in str(exc.value)


# -- driving it ------------------------------------------------------------


def test_a_chair_collects_downstairs_and_delivers_upstairs():
    """The journey that a flat map cannot describe at all."""
    tmap = build_two_level_terminal()
    fleet = Fleet(tmap)
    fleet.add_chair("c1", "dock_w")
    request = fleet.request_assistance("Passenger", "AI101", "sec_exit", "g1")

    rode_the_lift = False
    levels_visited = set()
    for _ in range(1200):
        fleet.step(1.0)
        chair = fleet.chairs["c1"]
        if chair.held_segment is not None and tmap.segments[chair.held_segment].is_lift:
            rode_the_lift = True
        levels_visited.add(tmap.nodes[chair.node].level)
        if request.delivered_s is not None:
            break

    assert request.delivered_s is not None, "passenger never reached the gate"
    assert rode_the_lift
    assert levels_visited == {0, 1}
    assert tmap.nodes["g1"].level == 1


def test_only_one_chair_is_in_the_car_at_a_time():
    """A chair, a passenger and a bag fill a small car."""
    tmap = build_two_level_terminal()
    fleet = Fleet(tmap)
    for chair_id in ("c1", "c2"):
        fleet.add_chair(chair_id, "dock_w")

    seen_together = False
    for _ in range(1200):
        fleet.step(1.0)
        holders = fleet.reservations.holders("lb_w0~lb_w1")
        if len(holders) > 1:
            seen_together = True
    assert not seen_together


def test_the_lift_costs_the_journey_time_it_says_it_does():
    """A chair sent upstairs takes the car's seconds, not a corridor's."""
    tmap = two_levels(call_s=30.0, door_s=5.0, ride_s_per_level=10.0)
    fleet = Fleet(tmap)
    fleet.add_chair("c1", "dock")
    route = plan(tmap, "dock", "gate")

    elapsed = 0.0
    assert fleet.send_to_staging("c1", "gate")
    while fleet.chairs["c1"].route is not None and elapsed < 600:
        fleet.step(1.0)
        elapsed += 1.0

    assert fleet.chairs["c1"].node == "gate"
    # Within a tick of the planned duration, lift included.
    assert elapsed == pytest.approx(route.duration_s, abs=2.0)
