"""Call points, languages, caravans and pre-positioning."""

from __future__ import annotations

import pytest

from margadarshak import ChairState, Fleet, FlightBoard, FlightStatus, build_example_terminal
from margadarshak.announce import (
    CATALOGUE,
    DISPLAY_ORDER,
    LANGUAGES,
    MissingTranslation,
    announce,
    format_number,
    placeholders,
    say,
    validate_catalogue,
)
from margadarshak.boardingpass import encode
from margadarshak.prepositioning import (
    DemandPoint,
    forecast_demand,
    plan_staging,
)


def find(fleet: Fleet, kind: str):
    return [e for e in fleet.events if e.kind == kind]


# ======================================================================
# Languages
# ======================================================================


def test_catalogue_is_complete_and_consistent():
    """A message added in English alone must fail the build, not fall back forever."""
    assert validate_catalogue() == []


def test_every_message_exists_in_every_language():
    for message_id, messages in CATALOGUE.items():
        for language in LANGUAGES:
            assert language in messages, f"{message_id} is missing {language}"
            assert messages[language].strip(), f"{message_id} in {language} is empty"


def test_placeholders_match_across_translations():
    """The bug this catches: a translator drops {gate} and the screen reads wrong."""
    for message_id, messages in CATALOGUE.items():
        expected = placeholders(messages["en"])
        for language in LANGUAGES:
            assert placeholders(messages[language]) == expected, (
                f"{message_id} in {language}"
            )


def test_translations_are_not_just_the_english_copied():
    """Catches the lazy failure of pasting English into every slot."""
    for message_id, messages in CATALOGUE.items():
        for language in ("hi", "mr", "kok"):
            assert messages[language] != messages["en"], f"{message_id} in {language}"


def test_konkani_and_marathi_are_not_the_same_text():
    """They are different languages. Sharing a script does not make them one."""
    identical = [mid for mid, m in CATALOGUE.items() if m["mr"] == m["kok"]]
    assert identical == [], f"identical Marathi and Konkani copy: {identical}"


def test_a_message_renders_with_its_parameters():
    assert say("taking_to_gate", "en", gate=4) == "Taking you to Gate 4."


def test_devanagari_scripts_get_devanagari_digits():
    assert format_number(4, "mr") == "४"
    assert format_number(12, "hi") == "१२"
    assert format_number(4, "en") == "4"
    assert "४" in say("taking_to_gate", "mr", gate=4)


def test_announce_returns_every_language_at_once():
    message = announce("arrived_at_gate", gate=5)
    assert set(message.by_language) == set(LANGUAGES)
    assert len(message.screen_lines) == len(LANGUAGES)


def test_the_screen_shows_local_languages_before_english():
    assert DISPLAY_ORDER[-1] == "en"
    assert DISPLAY_ORDER[0] == "kok"


def test_an_unknown_language_falls_back_rather_than_failing():
    """A chair that has stopped and cannot say why is worse than one in English."""
    assert say("stopped_for_staff", "fr") == CATALOGUE["stopped_for_staff"]["en"]


def test_an_unknown_message_is_an_error():
    with pytest.raises(MissingTranslation):
        say("no_such_message", "en")


def test_a_missing_parameter_is_an_error_not_a_blank():
    with pytest.raises(MissingTranslation, match="gate"):
        say("taking_to_gate", "en")


# ======================================================================
# Call points
# ======================================================================


@pytest.fixture
def fleet():
    f = Fleet(build_example_terminal(), holding_area="lounge")
    f.add_chair("CH-01", "dock_w")
    f.register_call_point("g3", label="Gate 3 call point")
    f.register_call_point("lounge", label="Lounge", default_destination="kerb")
    return f


def test_a_call_point_must_be_a_real_place(fleet):
    with pytest.raises(ValueError):
        fleet.register_call_point("nowhere")
    with pytest.raises(ValueError):
        fleet.register_call_point("g1", default_destination="nowhere")


def test_pressing_an_unregistered_button_is_an_error(fleet):
    with pytest.raises(ValueError, match="no call point"):
        fleet.press_call_button("g5")


def test_a_button_with_a_fixed_destination_just_works(fleet):
    request = fleet.press_call_button("lounge", passenger="Mr Naik")
    assert request.gate == "kerb"
    assert request.from_call_point

    fleet.run(duration_s=1500)
    assert request.delivered_s is not None
    assert fleet.chairs["CH-01"].state is ChairState.CHARGING


def test_a_button_without_a_destination_collects_first_and_asks_after(fleet):
    """The chair never guesses where somebody wants to go."""
    request = fleet.press_call_button("g3", passenger="Ms Fernandes")
    assert request.gate is None

    fleet.run(duration_s=900)
    chair = fleet.chairs["CH-01"]
    assert chair.state is ChairState.AWAITING_DESTINATION
    assert chair.node == "g3"
    assert request.picked_up_s is not None
    assert find(fleet, "awaiting_destination")

    fleet.set_destination(request, "kerb")
    fleet.run(duration_s=1500)
    assert request.delivered_s is not None


def test_a_scan_answers_the_waiting_chair_rather_than_calling_another(fleet):
    """Press the button, get in, scan. The scan is the answer, not a new request."""
    board = FlightBoard()
    board.upsert("AI612", status=FlightStatus.GATE_ASSIGNED, gate="g5")
    fleet.board = board
    board.subscribe(fleet._on_gate_assigned)

    request = fleet.press_call_button("g3", passenger="Passenger")
    fleet.run(duration_s=900)
    assert fleet.chairs["CH-01"].state is ChairState.AWAITING_DESTINATION

    scanned = fleet.scan_boarding_pass(
        encode(
            family_name="PEREIRA",
            given_name="MARIA",
            title="MRS",
            pnr="ABC123",
            origin="GOI",
            destination="BOM",
            carrier="AI",
            flight_number="612",
            day_of_year=280,
        ),
        pickup="g3",
    )

    assert scanned is request, "the scan should have answered the waiting chair"
    assert len(fleet.requests) == 1
    assert request.passenger == "Mrs Pereira"
    assert request.gate == "g5"

    fleet.run(duration_s=1200)
    assert request.delivered_s is not None


def test_pressing_twice_does_not_summon_two_chairs(fleet):
    first = fleet.press_call_button("g3")
    second = fleet.press_call_button("g3")
    assert first is second
    assert len(fleet.requests) == 1


def test_setting_an_unknown_destination_is_an_error(fleet):
    request = fleet.press_call_button("g3")
    with pytest.raises(ValueError):
        fleet.set_destination(request, "nowhere")


def test_battery_is_reserved_for_the_furthest_gate_when_nobody_has_said_where():
    """A chair that sets off and then cannot finish has stranded somebody."""
    f = Fleet(build_example_terminal())
    chair = f.add_chair("CH-01", "dock_w")
    chair.state = ChairState.IDLE
    chair.battery_wh = 4.0  # enough to reach g3, nowhere near enough to be safe
    f.register_call_point("g3")

    request = f.press_call_button("g3")
    f.run(duration_s=300)
    assert request.assigned_to is None


# ======================================================================
# Caravans
# ======================================================================


def test_a_group_travels_together_and_arrives_together():
    f = Fleet(build_example_terminal())
    for chair_id in ("CH-01", "CH-02", "CH-03"):
        f.add_chair(chair_id, "dock_w").state = ChairState.IDLE

    requests = f.request_group(
        ["Mrs Pereira", "Mr Pereira", "Miss Pereira"], "AI612", pickup="kerb", gate="g4"
    )
    assert len({r.group_id for r in requests}) == 1

    f.run(duration_s=2400)
    assert all(r.delivered_s is not None for r in requests)

    # Together means together: not spread over a quarter of an hour.
    arrivals = [r.delivered_s for r in requests]
    assert max(arrivals) - min(arrivals) < 60


def test_caravan_members_share_the_security_lane_instead_of_queuing_for_it():
    """The single-file lane holds one chair. A caravan passes it as one claim."""
    f = Fleet(build_example_terminal())
    for chair_id in ("CH-01", "CH-02", "CH-03"):
        f.add_chair(chair_id, "dock_w").state = ChairState.IDLE

    f.request_group(["A", "B", "C"], "AI612", pickup="kerb", gate="g4")
    f.run(duration_s=2400)

    assert find(f, "caravan")
    queued = [e for e in find(f, "waiting") if "sec_lane~sec_exit" in e.detail]
    assert queued == [], [str(e) for e in queued]


def test_travelling_as_a_caravan_beats_travelling_as_strangers():
    """The measurement behind the feature, rather than an assertion about it."""

    def run(*, as_group: bool) -> tuple[int, float]:
        f = Fleet(build_example_terminal())
        for chair_id in ("CH-01", "CH-02", "CH-03"):
            f.add_chair(chair_id, "dock_w").state = ChairState.IDLE

        if as_group:
            requests = f.request_group(["A", "B", "C"], "AI612", pickup="kerb", gate="g4")
        else:
            requests = [
                f.request_assistance(name, "AI612", pickup="kerb", gate="g4")
                for name in ("A", "B", "C")
            ]
        f.run(duration_s=2400)
        assert all(r.delivered_s is not None for r in requests)
        spread = max(r.delivered_s for r in requests) - min(r.delivered_s for r in requests)
        return len(find(f, "waiting")), spread

    caravan_waits, caravan_spread = run(as_group=True)
    separate_waits, separate_spread = run(as_group=False)

    assert caravan_waits < separate_waits
    assert caravan_spread < separate_spread


def test_a_caravan_disbands_once_its_members_go_their_own_ways():
    """Sharing a lane is only safe while they are nose to tail on one route.

    A chair that has dropped its passenger and is heading back to a dock is no
    longer travelling with the others, so it gives up the shared claim and takes
    its chances in the corridors like anybody else.
    """
    f = Fleet(build_example_terminal())
    for chair_id in ("CH-01", "CH-02"):
        f.add_chair(chair_id, "dock_w").state = ChairState.IDLE

    f.request_group(["A", "B"], "AI612", pickup="kerb", gate="g4")
    f.run(duration_s=2400)

    assert all(c.caravan is None for c in f.chairs.values())
    assert all(c.state is ChairState.CHARGING for c in f.chairs.values())


def test_a_group_is_never_split():
    """Two chairs now and a third later separates a family. Wait instead."""
    f = Fleet(build_example_terminal())
    for chair_id in ("CH-01", "CH-02"):
        f.add_chair(chair_id, "dock_w").state = ChairState.IDLE

    requests = f.request_group(["A", "B", "C"], "AI612", pickup="kerb", gate="g4")
    f.run(duration_s=300)

    assert all(r.assigned_to is None for r in requests)
    assert not find(f, "caravan")

    f.add_chair("CH-03", "dock_w").state = ChairState.IDLE
    f.run(duration_s=2400)
    assert all(r.delivered_s is not None for r in requests)


def test_an_empty_group_is_an_error():
    f = Fleet(build_example_terminal())
    with pytest.raises(ValueError):
        f.request_group([], "AI612", pickup="kerb", gate="g4")


def test_stopping_one_chair_in_a_caravan_stops_all_of_them():
    """They travel nose to tail. Stopping the front one alone is the collision."""
    f = Fleet(build_example_terminal())
    for chair_id in ("CH-01", "CH-02"):
        f.add_chair(chair_id, "dock_w").state = ChairState.IDLE

    f.request_group(["A", "B"], "AI612", pickup="kerb", gate="g4")
    f.run(duration_s=200)
    assert all(c.caravan is not None for c in f.chairs.values())

    f.emergency_stop("CH-01", "passenger pressed the button")
    assert all(c.state is ChairState.ESTOP for c in f.chairs.values())
    assert all(not f.reservations.holders(s) for s in f.tmap.segments)


def test_a_caravan_never_overfills_a_corridor_beyond_itself():
    """Sharing a lane is for siblings. An outsider still has to wait its turn."""
    f = Fleet(build_example_terminal())
    for chair_id in ("CH-01", "CH-02", "CH-03", "CH-04"):
        f.add_chair(chair_id, "dock_w").state = ChairState.IDLE

    f.request_group(["A", "B", "C"], "AI612", pickup="kerb", gate="g4")
    f.request_assistance("Solo", "6E204", pickup="kerb", gate="g1")

    for _ in range(2500):
        f.step()
        for segment_id, segment in f.tmap.segments.items():
            holders = f.reservations.holders(segment_id)
            assert len(holders) <= segment.capacity, f"{segment_id}: {holders}"

    assert f.summary()["delivered"] == 4


# ======================================================================
# Pre-positioning
# ======================================================================


def board_with_departures(times: list[float]) -> FlightBoard:
    board = FlightBoard()
    for index, departure in enumerate(times):
        board.upsert(
            f"AI{600 + index}",
            status=FlightStatus.GATE_ASSIGNED,
            gate="g1",
            scheduled_departure_s=departure,
        )
    return board


def test_no_flights_means_no_demand_and_no_moves():
    assert forecast_demand(FlightBoard(), now_s=0.0) == []
    f = Fleet(build_example_terminal())
    assert plan_staging(f, [], ["sec_q"]) == []


def test_demand_appears_a_couple_of_hours_before_departure():
    two_hours = 2 * 60 * 60
    board = board_with_departures([two_hours + 600])  # passengers due in 10 minutes

    assert forecast_demand(board, now_s=0.0, horizon_s=45 * 60) != []
    # The same flight is not yet interesting an hour earlier.
    assert forecast_demand(board, now_s=0.0, horizon_s=5 * 60) == []


def test_demand_is_split_across_the_pickup_points():
    board = board_with_departures([2 * 60 * 60 + 600])
    demand = forecast_demand(board, now_s=0.0, assistance_rate=10.0)

    assert {p.node for p in demand} == {"kerb", "sec_q"}
    assert sum(p.expected_requests for p in demand) == pytest.approx(10.0)
    # Busiest first, so the greedy planner serves it first.
    assert demand[0].node == "kerb"


def test_a_departed_flight_generates_no_demand():
    board = board_with_departures([2 * 60 * 60 + 600])
    board.set_status("AI600", FlightStatus.DEPARTED)
    assert forecast_demand(board, now_s=0.0) == []


def test_chairs_are_moved_towards_expected_demand():
    f = Fleet(build_example_terminal())
    for chair_id in ("CH-01", "CH-02"):
        f.add_chair(chair_id, "dock_e")  # the wrong end of the building

    demand = [DemandPoint("kerb", 8.0)]
    moves = plan_staging(f, demand, ["sec_q", "g5"])

    assert len(moves) == 1
    assert moves[0].to_node == "sec_q"  # nearer the kerb than g5 is
    assert moves[0].serving == "kerb"
    assert moves[0].saves_s > 0


def test_a_chair_already_well_placed_is_left_alone():
    f = Fleet(build_example_terminal())
    chair = f.add_chair("CH-01", "dock_w")
    chair.node = "sec_q"  # already sitting where the demand is

    assert plan_staging(f, [DemandPoint("sec_q", 8.0)], ["sec_q"]) == []


def test_a_flat_chair_is_not_sent_across_the_building():
    f = Fleet(build_example_terminal())
    chair = f.add_chair("CH-01", "dock_e")
    chair.battery_wh = chair.battery_wh * 0.3  # above the dispatch floor, below staging

    assert plan_staging(f, [DemandPoint("kerb", 8.0)], ["sec_q"]) == []


def test_two_demand_points_get_two_different_chairs():
    f = Fleet(build_example_terminal())
    for chair_id in ("CH-01", "CH-02", "CH-03", "CH-04"):
        f.add_chair(chair_id, "dock_e")

    moves = plan_staging(f, [DemandPoint("kerb", 8.0), DemandPoint("g1", 5.0)], ["sec_q", "sp1"])
    assert len(moves) == 2
    assert len({m.chair_id for m in moves}) == len(moves)
    assert len({m.to_node for m in moves}) == len(moves)
    assert {m.serving for m in moves} == {"kerb", "g1"}, (
        "a quiet pickup point is not abandoned because a busier one exists"
    )


def test_half_the_fleet_stays_on_charge():
    """Staging is a bet on a forecast, and this is the size of the bet."""
    f = Fleet(build_example_terminal())
    for index in range(8):
        f.add_chair(f"CH-{index:02d}", "dock_e")

    moves = plan_staging(f, [DemandPoint("kerb", 50.0)], ["sec_q", "sp1", "sp2", "checkin"])
    assert len(moves) == 4, "no more than half of eight chairs, and no more spots than exist"


def test_no_more_chairs_are_sent_out_than_passengers_expected():
    """The limit that makes the forecast matter at all.

    Without it the fleet sends the same number of chairs out whatever the board
    says, and a better forecast changes nothing on the floor.
    """
    f = Fleet(build_example_terminal())
    for index in range(8):
        f.add_chair(f"CH-{index:02d}", "dock_e")
    nodes = ["sec_q", "sp1", "sp2", "checkin"]

    quiet = plan_staging(f, [DemandPoint("kerb", 1.0)], nodes)
    busy = plan_staging(f, [DemandPoint("kerb", 9.0)], nodes)

    assert len(quiet) == 1
    assert len(busy) > len(quiet)


def test_an_unknown_staging_node_is_an_error():
    f = Fleet(build_example_terminal())
    f.add_chair("CH-01", "dock_w")
    with pytest.raises(ValueError, match="staging node"):
        plan_staging(f, [DemandPoint("kerb", 1.0)], ["nowhere"])


def test_applying_the_plan_actually_moves_the_chairs():
    f = Fleet(build_example_terminal())
    f.add_chair("CH-01", "dock_e")

    moves = plan_staging(f, [DemandPoint("kerb", 8.0)], ["sec_q"])
    assert f.apply_staging(moves) == 1

    f.run(duration_s=1200)
    chair = f.chairs["CH-01"]
    assert chair.node == "sec_q"
    assert chair.state is ChairState.IDLE
    assert find(f, "staged")


def test_a_staged_chair_still_takes_work():
    """The point of staging is to answer faster, not to take a chair out of service."""
    f = Fleet(build_example_terminal())
    f.add_chair("CH-01", "dock_e")
    f.apply_staging(plan_staging(f, [DemandPoint("kerb", 8.0)], ["sec_q"]))
    f.run(duration_s=1200)

    request = f.request_assistance("Mrs Pereira", "AI612", pickup="kerb", gate="g4")
    f.run(duration_s=2400)
    assert request.delivered_s is not None


def test_staging_beats_sitting_on_the_charger_for_response_time():
    """The claim the feature exists to make, measured rather than asserted."""

    def wait_for_a_passenger(*, stage: bool) -> float:
        f = Fleet(build_example_terminal())
        f.add_chair("CH-01", "dock_e")
        if stage:
            f.apply_staging(plan_staging(f, [DemandPoint("kerb", 8.0)], ["sec_q"]))
            f.run(duration_s=1200)  # let it get into position first

        request = f.request_assistance("Mrs Pereira", "AI612", pickup="kerb", gate="g4")
        f.run(duration_s=3000)
        assert request.picked_up_s is not None
        return request.wait_time_s(f.now)

    assert wait_for_a_passenger(stage=True) < wait_for_a_passenger(stage=False)


def test_a_staged_chair_goes_home_before_it_goes_flat():
    f = Fleet(build_example_terminal())
    chair = f.add_chair("CH-01", "dock_e")
    f.apply_staging(plan_staging(f, [DemandPoint("kerb", 8.0)], ["sec_q"]))
    f.run(duration_s=1200)
    assert chair.node == "sec_q"

    chair.battery_wh = chair.battery_wh * 0.1
    f.run(duration_s=3600)
    assert find(f, "low_battery")
    assert f.tmap.nodes[chair.node].kind.value == "dock"
