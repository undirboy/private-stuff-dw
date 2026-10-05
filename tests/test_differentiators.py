"""Priority dispatch and the open map format.

Both exist to be different from what is already on the market: one changes who
gets the next chair, the other changes who owns the map.
"""

from __future__ import annotations

import json

import pytest

from saarthi import ChairState, Fleet, FlightBoard, FlightStatus, build_example_terminal
from saarthi.fleet import GATE_CLOSES_BEFORE_DEPARTURE_S, MAX_WAIT_BEFORE_PRIORITY_S
from saarthi.graph import Guide, NodeKind
from saarthi.mapfile import MapFileError, dumps, load, loads, main, save

HOUR = 60 * 60


def find(fleet: Fleet, kind: str):
    return [e for e in fleet.events if e.kind == kind]


# ======================================================================
# Dispatch by who will miss their flight
# ======================================================================


def urgent_fleet(chairs: int = 1) -> tuple[Fleet, FlightBoard]:
    board = FlightBoard()
    board.upsert("AI612", status=FlightStatus.GATE_ASSIGNED, gate="g4",
                 scheduled_departure_s=3 * HOUR)
    board.upsert("6E204", status=FlightStatus.BOARDING, gate="g1",
                 scheduled_departure_s=40 * 60)
    f = Fleet(build_example_terminal(), board=board)
    for index in range(chairs):
        f.add_chair(f"CH-{index + 1:02d}", "dock_w").state = ChairState.IDLE
    return f, board


def test_the_passenger_whose_flight_closes_first_is_taken_first():
    """The whole point. Arriving first is not the same as needing to leave first."""
    f, _ = urgent_fleet(chairs=1)

    relaxed = f.request_assistance("Mrs Pereira", "AI612", pickup="kerb", gate="g4")
    urgent = f.request_assistance("Mr Naik", "6E204", pickup="kerb", gate="g1")

    f.step()
    assert urgent.assigned_to is not None, "the passenger about to miss a flight waits"
    assert relaxed.assigned_to is None


def test_overtaking_is_logged_so_an_attendant_can_explain_it():
    f, _ = urgent_fleet(chairs=1)
    f.request_assistance("Mrs Pereira", "AI612", pickup="kerb", gate="g4")
    f.request_assistance("Mr Naik", "6E204", pickup="kerb", gate="g1")
    f.step()

    prioritised = find(f, "prioritised")
    assert prioritised, "a silently reordered queue is one nobody can defend"
    assert "Mr Naik" in prioritised[0].detail


def test_order_is_unchanged_when_nobody_is_more_urgent():
    """No flight information, no reordering. First come, first served stands."""
    f = Fleet(build_example_terminal())
    f.add_chair("CH-01", "dock_w").state = ChairState.IDLE

    first = f.request_assistance("First", "", pickup="kerb", gate="g4")
    f.request_assistance("Second", "", pickup="kerb", gate="g1")
    f.step()

    assert first.assigned_to is not None
    assert not find(f, "prioritised")


def test_urgency_is_measured_against_the_gate_closing_not_departure():
    """A passenger has to beat the gate closing, which is the earlier deadline."""
    f, board = urgent_fleet()
    request = f.request_assistance("Mr Naik", "6E204", pickup="kerb", gate="g1")

    _, closes_in, _ = f.urgency(request)
    departure = board.get("6E204").scheduled_departure_s
    assert closes_in == pytest.approx(departure - GATE_CLOSES_BEFORE_DEPARTURE_S - f.now)
    assert closes_in < departure


def test_a_request_with_no_flight_sorts_behind_one_with_a_deadline():
    f, _ = urgent_fleet()
    no_flight = f.request_assistance("Call button", "", pickup="g3", gate="kerb")
    flying = f.request_assistance("Mr Naik", "6E204", pickup="kerb", gate="g1")
    assert f.urgency(flying) < f.urgency(no_flight)


def test_nobody_is_starved_however_urgent_everyone_else_is():
    """The failure a passenger never forgives: waiting indefinitely."""
    f, _ = urgent_fleet()
    forgotten = f.request_assistance("Mrs Pereira", "AI612", pickup="kerb", gate="g4")
    f.now += MAX_WAIT_BEFORE_PRIORITY_S + 1

    urgent = f.request_assistance("Mr Naik", "6E204", pickup="kerb", gate="g1")
    assert f.urgency(forgotten) < f.urgency(urgent)

    f.step()
    assert forgotten.assigned_to is not None


def test_a_long_wait_outranks_a_merely_long_wait():
    f, _ = urgent_fleet()
    older = f.request_assistance("Older", "AI612", pickup="kerb", gate="g4")
    f.now += 60
    newer = f.request_assistance("Newer", "AI612", pickup="kerb", gate="g4")
    f.now += MAX_WAIT_BEFORE_PRIORITY_S

    assert f.urgency(older) < f.urgency(newer)


def test_priority_does_not_break_an_ordinary_shift():
    f, _ = urgent_fleet(chairs=2)
    requests = [
        f.request_assistance("Mrs Pereira", "AI612", pickup="kerb", gate="g4"),
        f.request_assistance("Mr Naik", "6E204", pickup="kerb", gate="g1"),
    ]
    f.run(duration_s=2400)
    assert all(r.delivered_s is not None for r in requests)


def test_a_group_is_never_overtaken_by_its_own_members():
    """A caravan sorts as one thing, not three competing requests."""
    f, _ = urgent_fleet(chairs=3)
    f.request_group(["A", "B", "C"], "6E204", pickup="kerb", gate="g1")
    f.run(duration_s=2400)

    assert f.summary()["delivered"] == 3
    assert not find(f, "prioritised"), "group members should not overtake each other"


# ======================================================================
# The map as a file the airport owns
# ======================================================================


def test_a_map_survives_a_round_trip():
    original = build_example_terminal()
    restored = loads(dumps(original))

    assert restored.name == original.name
    assert set(restored.nodes) == set(original.nodes)
    assert set(restored.segments) == set(original.segments)
    assert restored.validate() == []


def test_every_detail_that_matters_survives():
    original = build_example_terminal()
    restored = loads(dumps(original))

    for node_id, node in original.nodes.items():
        other = restored.nodes[node_id]
        assert (other.kind, other.label, other.tag_id) == (node.kind, node.label, node.tag_id)
        assert (other.code, other.terminal) == (node.code, node.terminal)
        assert (other.x, other.y) == pytest.approx((node.x, node.y))

    for segment_id, segment in original.segments.items():
        other = restored.segments[segment_id]
        assert other.guide == segment.guide
        assert other.width_m == segment.width_m
        assert other.max_speed_mps == segment.max_speed_mps
        # Lengths are stored to the millimetre; a corridor does not need more.
        assert other.length_m == pytest.approx(segment.length_m, abs=0.001)
        assert other.capacity == segment.capacity


def test_the_dogleg_length_is_not_silently_recomputed():
    """The security lane is longer than the straight line between its ends."""
    original = build_example_terminal()
    restored = loads(dumps(original))
    assert restored.segments["sec_lane~sec_exit"].length_m == pytest.approx(22.0)
    assert restored.distance("sec_lane", "sec_exit") < 22.0


def test_the_file_is_something_a_person_can_read_and_edit():
    data = json.loads(dumps(build_example_terminal()))
    assert data["format"] == "saarthi.terminal-map"
    assert {"version", "name", "nodes", "segments"} <= set(data)
    # Plain keys, no encoded blobs, no identifiers only this software understands.
    assert set(data["nodes"][0]) == {
        "id", "kind", "x", "y", "label", "tag", "code", "terminal"
    }


def test_an_edited_speed_limit_takes_effect():
    """The facilities-team workflow: open it, change a number, put it back."""
    data = json.loads(dumps(build_example_terminal()))
    for segment in data["segments"]:
        if {segment["a"], segment["b"]} == {"sp1", "sp2"}:
            segment["max_speed_mps"] = 0.4
    edited = loads(json.dumps(data))
    assert edited.segments["sp1~sp2"].max_speed_mps == 0.4


def test_it_writes_and_reads_a_file(tmp_path):
    path = save(build_example_terminal(), tmp_path / "terminal.json")
    assert path.exists()
    assert load(path).validate() == []


@pytest.mark.parametrize(
    "payload, expect",
    [
        ("not json at all", "not valid JSON"),
        ("[]", "must contain a JSON object"),
        ('{"nodes": [], "segments": []}', "no 'version'"),
        ('{"version": 99, "nodes": [], "segments": []}', "version 99"),
        ('{"version": 1, "segments": []}', "no 'nodes'"),
        ('{"version": 1, "nodes": []}', "no 'segments'"),
    ],
)
def test_a_broken_file_says_what_is_wrong(payload, expect):
    with pytest.raises(MapFileError, match=expect):
        loads(payload)


def test_an_unknown_node_kind_lists_the_valid_ones():
    """The person reading this error has a text editor, not a debugger."""
    payload = json.dumps(
        {
            "version": 1,
            "nodes": [{"id": "g1", "kind": "platform", "x": 0, "y": 0}],
            "segments": [],
        }
    )
    with pytest.raises(MapFileError) as excinfo:
        loads(payload)
    assert "platform" in str(excinfo.value)
    assert "gate" in str(excinfo.value)


def test_an_unknown_guide_type_lists_the_valid_ones():
    payload = json.dumps(
        {
            "version": 1,
            "nodes": [
                {"id": "a", "kind": "dock", "x": 0, "y": 0, "tag": "D1"},
                {"id": "b", "kind": "gate", "x": 10, "y": 0, "tag": "G1"},
            ],
            "segments": [{"a": "a", "b": "b", "guide": "breadcrumbs"}],
        }
    )
    with pytest.raises(MapFileError) as excinfo:
        loads(payload)
    assert "breadcrumbs" in str(excinfo.value)
    assert "magnetic_tape" in str(excinfo.value)


def test_a_segment_to_a_node_that_does_not_exist_is_caught():
    payload = json.dumps(
        {
            "version": 1,
            "nodes": [{"id": "a", "kind": "dock", "x": 0, "y": 0, "tag": "D1"}],
            "segments": [{"a": "a", "b": "ghost"}],
        }
    )
    with pytest.raises(MapFileError, match="ghost"):
        loads(payload)


def test_the_command_line_validates_a_map(tmp_path, capsys):
    path = save(build_example_terminal(), tmp_path / "terminal.json")
    assert main([str(path), "--validate"]) == 0
    assert "map is valid" in capsys.readouterr().out


def test_the_command_line_reports_a_broken_map(tmp_path, capsys):
    tmap = build_example_terminal()
    data = json.loads(dumps(tmap))
    data["nodes"] = [n for n in data["nodes"] if n["id"] != "g5"]
    data["segments"] = [s for s in data["segments"] if "g5" not in (s["a"], s["b"])]
    # Leave an untagged gate behind so validation has something to complain about.
    for node in data["nodes"]:
        if node["id"] == "g4":
            node["tag"] = None
    path = tmp_path / "broken.json"
    path.write_text(json.dumps(data))

    assert main([str(path), "--validate"]) == 1
    assert "floor tag" in capsys.readouterr().out


def test_the_command_line_reports_a_missing_file(capsys):
    assert main(["/no/such/map.json"]) == 1
    assert "map.json" in capsys.readouterr().out


def test_a_loaded_map_actually_drives_a_fleet(tmp_path):
    """The point of the format: a map an airport edited still runs the system."""
    path = save(build_example_terminal(), tmp_path / "terminal.json")
    f = Fleet(load(path))
    f.add_chair("CH-01", "dock_w").state = ChairState.IDLE

    request = f.request_assistance("Mrs Pereira", "AI612", pickup="kerb", gate="g4")
    f.run(duration_s=2400)
    assert request.delivered_s is not None


def test_guide_types_round_trip_by_name_not_by_number():
    """Names so a person can read them, and so reordering the enum cannot corrupt a map."""
    text = dumps(build_example_terminal())
    assert Guide.RFID.value in text
    assert Guide.PAINTED.value in text
    assert NodeKind.DOCK.value in text
