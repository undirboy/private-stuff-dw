"""Security, which is the thing that cuts a kerb-to-gate journey in half.

A chair that has not been inspected and swabbed cannot be airside. The passenger
gets out at the archway, is screened on foot, and is met on the other side. None
of that is a software decision, so the only thing software can get wrong here is
to pretend otherwise — to plan a route through a CISF post, or to send a landside
chair to an airside gate. These tests are that nothing in the package does.
"""

from __future__ import annotations

import json

import pytest

from margadarshak.fleet import Fleet
from margadarshak.graph import Node, NodeKind, TerminalMap, Zone
from margadarshak.mapfile import dumps, loads
from margadarshak.router import plan
from margadarshak.terminal import build_example_terminal, build_two_level_terminal


def across_security() -> TerminalMap:
    tmap = TerminalMap("archway")
    tmap.add(Node("kerb", NodeKind.PICKUP, 0, 0, tag_id="K"))
    tmap.add(Node("dock_l", NodeKind.DOCK, 5, 5, tag_id="DL"))
    tmap.add(Node("arch_in", NodeKind.PICKUP, 20, 0, tag_id="A1"))
    tmap.add(Node("arch_out", NodeKind.PICKUP, 20, 20, tag_id="A2", zone=Zone.AIRSIDE))
    tmap.add(Node("dock_a", NodeKind.DOCK, 25, 25, tag_id="DA", zone=Zone.AIRSIDE))
    tmap.add(
        Node("gate", NodeKind.GATE, 40, 20, tag_id="G", code="1", zone=Zone.AIRSIDE)
    )
    tmap.connect("kerb", "dock_l", width_m=2.0)
    tmap.connect("kerb", "arch_in", width_m=2.0)
    tmap.connect("arch_in", "arch_out", width_m=1.2, screening=True)
    tmap.connect("arch_out", "dock_a", width_m=2.0)
    tmap.connect("arch_out", "gate", width_m=2.0)
    return tmap


# -- the map ---------------------------------------------------------------


def test_a_map_that_says_nothing_about_security_is_one_zone():
    """Which is what every map in this repository meant before today."""
    tmap = build_example_terminal()
    assert tmap.screening_points() == []
    assert {n.zone for n in tmap.nodes.values()} == {Zone.LANDSIDE}
    assert tmap.validate() == []


def test_the_two_level_example_puts_the_archway_where_it_belongs():
    tmap = build_two_level_terminal()
    assert tmap.validate() == []
    points = tmap.screening_points()
    assert len(points) == 1
    assert {points[0].a, points[0].b} == {"sec_lane", "sec_exit"}
    assert tmap.zone_of("sec_q") is Zone.LANDSIDE
    assert tmap.zone_of("g3") is Zone.AIRSIDE


def test_a_survey_that_forgets_to_mark_the_archway_is_rejected():
    """Otherwise the map is quietly claiming a chair may drive around security."""
    tmap = TerminalMap("unmarked")
    tmap.add(Node("kerb", NodeKind.PICKUP, 0, 0, tag_id="K"))
    tmap.add(Node("dock_l", NodeKind.DOCK, 5, 0, tag_id="DL"))
    tmap.add(Node("dock_a", NodeKind.DOCK, 25, 0, tag_id="DA", zone=Zone.AIRSIDE))
    tmap.add(Node("gate", NodeKind.GATE, 20, 0, tag_id="G", code="1",
                  zone=Zone.AIRSIDE))
    tmap.connect("kerb", "dock_l", width_m=2.0)
    tmap.connect("kerb", "gate", width_m=2.0)
    tmap.connect("gate", "dock_a", width_m=2.0)
    assert any("not marked as a screening point" in p for p in tmap.validate())


def test_an_archway_that_crosses_nothing_is_rejected():
    tmap = across_security()
    tmap.connect("kerb", "dock_a", width_m=2.0)  # landside to airside, unmarked
    problems = tmap.validate()
    assert any("not marked as a screening point" in p for p in problems)

    inner = TerminalMap("inner")
    inner.add(Node("a", NodeKind.DOCK, 0, 0, tag_id="A"))
    inner.add(Node("b", NodeKind.PICKUP, 10, 0, tag_id="B"))
    inner.connect("a", "b", width_m=2.0, screening=True)
    assert any("both ends are landside" in p for p in inner.validate())


def test_each_side_of_security_needs_its_own_dock():
    """Chairs cannot cross, so a zone with no charger is a zone with no fleet."""
    tmap = TerminalMap("one dock")
    tmap.add(Node("kerb", NodeKind.PICKUP, 0, 0, tag_id="K"))
    tmap.add(Node("dock_l", NodeKind.DOCK, 5, 0, tag_id="DL"))
    tmap.add(Node("arch_in", NodeKind.PICKUP, 20, 0, tag_id="A1"))
    tmap.add(Node("arch_out", NodeKind.PICKUP, 20, 20, tag_id="A2",
                  zone=Zone.AIRSIDE))
    tmap.add(Node("gate", NodeKind.GATE, 40, 20, tag_id="G", code="1",
                  zone=Zone.AIRSIDE))
    tmap.connect("kerb", "dock_l", width_m=2.0)
    tmap.connect("kerb", "arch_in", width_m=2.0)
    tmap.connect("arch_in", "arch_out", width_m=1.2, screening=True)
    tmap.connect("arch_out", "gate", width_m=2.0)
    assert any("no airside dock" in p for p in tmap.validate())
    assert across_security().validate() == []


# -- routing ---------------------------------------------------------------


def test_no_route_exists_through_security():
    assert plan(across_security(), "kerb", "gate") is None
    assert plan(build_two_level_terminal(), "kerb", "g1") is None


def test_each_side_routes_normally_within_itself():
    tmap = across_security()
    assert plan(tmap, "kerb", "arch_in") is not None
    assert plan(tmap, "arch_out", "gate") is not None


def test_a_landside_chair_cannot_be_sent_to_an_airside_gate():
    """The security property, enforced where it cannot be forgotten."""
    fleet = Fleet(across_security())
    fleet.add_chair("land1", "dock_l")
    assert fleet.travel_time("dock_l", "gate") is None
    assert not fleet.send_to_staging("land1", "gate")


# -- the journey -----------------------------------------------------------


def test_a_journey_across_security_is_two_journeys():
    fleet = Fleet(across_security())
    fleet.add_chair("land1", "dock_l")
    fleet.add_chair("air1", "dock_a")

    leg1 = fleet.request_journey("Passenger", "AI101", "kerb", "gate")
    assert leg1.gate == "arch_in", "the landside chair goes as far as the archway"
    assert leg1.onward_gate == "gate"

    fleet.run(600.0)
    assert leg1.delivered_s is not None
    assert fleet.chairs["land1"].node != "gate"

    leg2 = fleet.cleared_screening(leg1)
    assert leg2.pickup == "arch_out"
    assert leg2.gate == "gate"
    assert leg2.follow_on_of == leg1.id

    fleet.run(600.0)
    assert leg2.delivered_s is not None
    assert fleet.chairs["air1"].node in ("gate", "dock_a", "arch_out")


def test_a_journey_within_one_zone_is_still_one_journey():
    """The caller does not have to know where security is."""
    fleet = Fleet(across_security())
    fleet.add_chair("air1", "dock_a")
    request = fleet.request_journey("Passenger", "AI101", "arch_out", "gate")
    assert request.gate == "gate"
    assert request.onward_gate is None


def test_no_chair_is_sent_before_an_attendant_says_they_are_through():
    """Screening takes as long as it takes, and a timer would guess."""
    fleet = Fleet(across_security())
    fleet.add_chair("land1", "dock_l")
    fleet.add_chair("air1", "dock_a")
    leg1 = fleet.request_journey("Passenger", "AI101", "kerb", "gate")
    fleet.run(600.0)

    # Nobody has cleared them, so the airside chair has no reason to move.
    assert fleet.chairs["air1"].node == "dock_a"
    assert all(r.pickup != "arch_out" for r in fleet.requests)

    fleet.cleared_screening(leg1)
    assert any(r.pickup == "arch_out" for r in fleet.requests)


def test_clearing_screening_before_the_passenger_arrives_is_refused():
    fleet = Fleet(across_security())
    fleet.add_chair("land1", "dock_l")
    leg1 = fleet.request_journey("Passenger", "AI101", "kerb", "gate")
    with pytest.raises(ValueError, match="has not reached security"):
        fleet.cleared_screening(leg1)


def test_clearing_a_journey_that_never_crossed_security_is_refused():
    fleet = Fleet(across_security())
    fleet.add_chair("air1", "dock_a")
    request = fleet.request_journey("Passenger", "AI101", "arch_out", "gate")
    fleet.run(600.0)
    with pytest.raises(ValueError, match="not a journey interrupted by screening"):
        fleet.cleared_screening(request)


def test_clearing_twice_is_refused():
    """An attendant pressing the button again does not summon a second chair."""
    fleet = Fleet(across_security())
    fleet.add_chair("land1", "dock_l")
    fleet.add_chair("air1", "dock_a")
    leg1 = fleet.request_journey("Passenger", "AI101", "kerb", "gate")
    fleet.run(600.0)
    fleet.cleared_screening(leg1)
    with pytest.raises(ValueError):
        fleet.cleared_screening(leg1)


def test_the_booking_digest_follows_the_passenger_through():
    """So the airside chair's screen says the same flight, with no second scan."""
    fleet = Fleet(across_security())
    fleet.add_chair("land1", "dock_l")
    fleet.add_chair("air1", "dock_a")
    leg1 = fleet.request_journey("Passenger", "AI101", "kerb", "gate")
    leg1.pnr_digest = "a1b2c3d4a1b2c3d4"
    fleet.run(600.0)
    leg2 = fleet.cleared_screening(leg1)
    assert leg2.pnr_digest == leg1.pnr_digest
    assert leg2.flight == "AI101"


def test_the_handover_is_in_the_log_for_the_shift_report():
    fleet = Fleet(across_security())
    fleet.add_chair("land1", "dock_l")
    fleet.add_chair("air1", "dock_a")
    leg1 = fleet.request_journey("Passenger", "AI101", "kerb", "gate")
    fleet.run(600.0)
    fleet.cleared_screening(leg1)
    kinds = [event.kind for event in fleet.events]
    assert "screening" in kinds
    assert "screened" in kinds


def test_a_journey_with_no_archway_between_the_two_zones_is_refused():
    """Better a loud error at request time than a chair sent nowhere."""
    tmap = across_security()
    broken = Fleet(tmap)
    broken.add_chair("land1", "dock_l")
    for segment in list(tmap.segments):
        if tmap.segments[segment].screening:
            del tmap.segments[segment]
            tmap._adjacency["arch_in"].remove(segment)
            tmap._adjacency["arch_out"].remove(segment)
    with pytest.raises(ValueError, match="no screening point"):
        broken.request_journey("Passenger", "AI101", "kerb", "gate")


# -- the map file ----------------------------------------------------------


def test_zones_and_archways_survive_the_round_trip():
    restored = loads(dumps(build_two_level_terminal()))
    assert restored.validate() == []
    assert restored.zone_of("g1") is Zone.AIRSIDE
    assert restored.zone_of("kerb") is Zone.LANDSIDE
    assert len(restored.screening_points()) == 1


def test_an_unknown_zone_is_rejected_by_name():
    data = json.loads(dumps(build_two_level_terminal()))
    data["nodes"][0]["zone"] = "apron"
    with pytest.raises(Exception, match="expected one of"):
        loads(json.dumps(data))
