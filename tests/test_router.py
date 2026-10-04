"""Route planning tests."""

from __future__ import annotations

import math

import pytest

from saarthi import NodeKind, build_example_terminal, plan
from saarthi.graph import Node, NodeKind as NK, TerminalMap
from saarthi.router import traverse_time


@pytest.fixture
def tmap():
    return build_example_terminal()


def test_example_map_is_valid(tmap):
    assert tmap.validate() == []


def test_every_gate_is_reachable_from_every_dock(tmap):
    docks = tmap.nodes_of_kind(NodeKind.DOCK)
    gates = tmap.nodes_of_kind(NodeKind.GATE)
    assert docks and gates
    for dock in docks:
        for gate in gates:
            assert plan(tmap, dock.id, gate.id) is not None, f"{dock.id} -> {gate.id}"


def test_route_endpoints_and_continuity(tmap):
    route = plan(tmap, "kerb", "g4")
    assert route is not None
    assert route.origin == "kerb"
    assert route.destination == "g4"
    assert len(route.segments) == len(route.nodes) - 1

    # Every segment really does join consecutive nodes on the path.
    for index, segment_id in enumerate(route.segments):
        segment = tmap.segments[segment_id]
        assert {segment.a, segment.b} == {route.nodes[index], route.nodes[index + 1]}


def test_duration_accounts_for_speed_limits_not_just_distance(tmap):
    route = plan(tmap, "kerb", "g4")
    assert route is not None
    # The security lane alone is 22 m at 0.5 m/s, so a pure-distance estimate at
    # the map's top speed is nowhere near the real duration.
    naive = route.distance_m / tmap.top_speed_mps
    assert route.duration_s > naive


def test_same_node_route_is_empty(tmap):
    route = plan(tmap, "g1", "g1")
    assert route is not None
    assert route.segments == []
    assert route.duration_s == 0.0


def test_unknown_node_is_rejected(tmap):
    with pytest.raises(ValueError):
        plan(tmap, "kerb", "gate_99")


def test_blocking_the_spine_forces_the_service_corridor(tmap):
    direct = plan(tmap, "sp1", "sp5")
    assert direct is not None
    assert "sp2~sp3" in direct.segments

    detour = plan(tmap, "sp1", "sp5", blocked_segments=frozenset({"sp2~sp3"}))
    assert detour is not None
    assert "sp2~sp3" not in detour.segments
    assert "sv1~sv2" in detour.segments
    assert detour.duration_s > direct.duration_s


def test_no_route_when_the_only_way_through_is_closed(tmap):
    # Severing the security lane cuts landside from airside entirely.
    assert plan(tmap, "kerb", "g1", blocked_segments=frozenset({"sec_lane~sec_exit"})) is None


def test_speed_cap_slows_the_journey_without_changing_the_path(tmap):
    fast = plan(tmap, "kerb", "g3")
    slow = plan(tmap, "kerb", "g3", speed_cap_mps=0.6)
    assert fast is not None and slow is not None
    assert slow.duration_s > fast.duration_s
    assert math.isclose(slow.distance_m, fast.distance_m)


def test_speed_cap_never_speeds_a_segment_up(tmap):
    segment = tmap.segments["sp1~sp2"]  # 1.4 m/s
    assert traverse_time(segment, speed_cap_mps=5.0) == traverse_time(segment)


def test_turn_penalty_prefers_the_straight_run():
    """Given two equal-length routes, the planner takes the one with fewer turns."""
    tmap = TerminalMap("turn test")
    tmap.add(Node("start", NK.PICKUP, 0, 0, tag_id="T1"))
    tmap.add(Node("straight_mid", NK.JUNCTION, 50, 0))
    tmap.add(Node("dogleg_up", NK.JUNCTION, 25, 25))
    tmap.add(Node("dogleg_down", NK.JUNCTION, 75, 25))
    tmap.add(Node("end", NK.GATE, 100, 0, tag_id="T2"))
    tmap.add(Node("dock", NK.DOCK, -10, 0, tag_id="T3"))
    tmap.connect("dock", "start")

    # Both ways are forced to the same length and speed, so only turns differ.
    tmap.connect("start", "straight_mid", length_m=50, max_speed_mps=1.0)
    tmap.connect("straight_mid", "end", length_m=50, max_speed_mps=1.0)
    tmap.connect("start", "dogleg_up", length_m=50, max_speed_mps=1.0)
    tmap.connect("dogleg_up", "dogleg_down", length_m=0.1, max_speed_mps=1.0)
    tmap.connect("dogleg_down", "end", length_m=50, max_speed_mps=1.0)

    assert tmap.validate() == []
    route = plan(tmap, "start", "end")
    assert route is not None
    assert route.nodes == ["start", "straight_mid", "end"]


def test_validate_catches_a_gate_with_no_floor_tag():
    tmap = TerminalMap("bad map")
    tmap.add(Node("dock", NK.DOCK, 0, 0, tag_id="D1"))
    tmap.add(Node("gate", NK.GATE, 10, 0))  # no tag: arrival cannot be confirmed
    tmap.connect("dock", "gate")
    problems = tmap.validate()
    assert any("floor tag" in p for p in problems)


def test_validate_catches_an_unreachable_node():
    tmap = TerminalMap("severed map")
    tmap.add(Node("dock", NK.DOCK, 0, 0, tag_id="D1"))
    tmap.add(Node("gate", NK.GATE, 10, 0, tag_id="G1"))
    tmap.add(Node("island", NK.GATE, 99, 99, tag_id="G2"))
    tmap.add(Node("island_spur", NK.JUNCTION, 95, 99))
    tmap.connect("dock", "gate")
    tmap.connect("island", "island_spur")
    problems = tmap.validate()
    assert any("unreachable" in p for p in problems)


def test_segment_capacity_follows_corridor_width(tmap):
    assert tmap.segments["sec_lane~sec_exit"].capacity == 1  # 0.9 m, single file
    assert tmap.segments["sp1~sp2"].capacity == 3  # 2.8 m spine
    assert tmap.segments["sv1~sv2"].capacity == 1  # 1.0 m service corridor


def test_duplicate_and_self_segments_are_rejected(tmap):
    with pytest.raises(ValueError):
        tmap.connect("sp1", "sp2")
    with pytest.raises(ValueError):
        tmap.connect("sp1", "sp1")
