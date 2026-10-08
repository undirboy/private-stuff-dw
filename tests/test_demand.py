"""The demand forecast: that it learns, that it says why, and that it stays honest.

The point of most of these is not that the arithmetic is right — it is fifty
lines, the arithmetic is obviously right. It is that the thing degrades the way
it is documented to: with no history it answers with the documented guess rather
than a confident number, with three flights of history it stays sceptical, and it
can always say what its answer rests on.
"""

from __future__ import annotations

import pytest

from margadarshak import (
    AssistanceLog,
    FlatRate,
    Fleet,
    FlightBoard,
    FlightStatus,
    LearnedRate,
    Observation,
    build_example_terminal,
    forecast_demand,
    mean_absolute_error,
)
from margadarshak.demand import (
    MIN_OBSERVATIONS,
    PRIOR_RATE,
    carrier_of,
    hour_of,
)

HOUR = 3600.0


def flight(designator="AI612", destination="DXB", hour=9.0):
    board = FlightBoard()
    return board.upsert(
        designator, scheduled_departure_s=hour * HOUR, destination=destination
    )


def rows(designator, destination, count, requests, hour=9.0):
    return [
        Observation(
            designator=designator,
            requests=requests,
            destination=destination,
            departure_s=hour * HOUR,
        )
        for _ in range(count)
    ]


# -- reading a flight ----------------------------------------------------


@pytest.mark.parametrize(
    "designator,expected",
    [("AI612", "AI"), ("6E204", "6E"), ("SG1118", "SG"), ("uk880", "UK")],
)
def test_the_carrier_is_read_off_the_designator(designator, expected):
    assert carrier_of(designator) == expected


def test_the_hour_is_read_off_the_schedule():
    assert hour_of(9.5 * HOUR) == 9
    assert hour_of(None) is None
    assert hour_of(26 * HOUR) == 2, "a schedule past midnight wraps"


def test_an_observation_cannot_record_negative_demand():
    with pytest.raises(ValueError):
        Observation(designator="AI612", requests=-1)
    with pytest.raises(ValueError, match="designator"):
        Observation(designator="", requests=2)


# -- the cold start ------------------------------------------------------


def test_with_no_history_it_answers_with_the_documented_guess():
    model = LearnedRate()
    assert model.rate_for(flight()) == pytest.approx(PRIOR_RATE)
    assert not model.ready


def test_it_admits_when_it_has_too_little_history_to_be_called_a_forecast():
    model = LearnedRate.fit(rows("AI612", "DXB", MIN_OBSERVATIONS - 1, 3))
    assert not model.ready, "a handful of flights is not a forecast and should not pose as one"

    model.observe(Observation(designator="AI612", requests=3, destination="DXB"))
    assert model.ready


def test_an_unseen_route_falls_back_to_what_is_known():
    """A carrier and a destination nobody has seen get the airport's own average."""
    model = LearnedRate.fit(rows("AI612", "DXB", 40, 4) + rows("6E204", "BLR", 40, 0))
    unseen = model.rate_for(flight(designator="QQ999", destination="ZZZ", hour=23.0))

    assert unseen == pytest.approx(model.global_mean) == pytest.approx(2.0)


# -- shrinkage -----------------------------------------------------------


def test_a_well_evidenced_route_is_trusted_and_a_thin_one_is_not():
    history = rows("AI612", "DXB", 60, 5) + rows("6E204", "BLR", 3, 0)
    model = LearnedRate.fit(history)

    busy = model.rate_for(flight("AI612", "DXB"))
    thin = model.rate_for(flight("6E204", "BLR"))

    assert busy > 4.5, "sixty flights at 5 should be believed"
    assert thin > 0.5, "three flights at 0 should not be"
    assert thin < busy


def test_more_evidence_moves_the_estimate_towards_the_route():
    sparse = LearnedRate.fit(rows("AI612", "DXB", 40, 1) + rows("6E204", "BLR", 2, 6))
    dense = LearnedRate.fit(rows("AI612", "DXB", 40, 1) + rows("6E204", "BLR", 40, 6))

    assert dense.rate_for(flight("6E204", "BLR")) > sparse.rate_for(flight("6E204", "BLR"))


def test_it_can_say_what_its_answer_rests_on():
    model = LearnedRate.fit(rows("AI612", "DXB", 30, 4, hour=9.0))
    chain = model.explain(flight("AI612", "DXB", hour=9.0))

    assert [step.level for step in chain] == ["airport", "hour", "carrier", "route"]
    assert chain[0].key == "all flights"
    assert chain[-1].observations == 30
    assert chain[-1].estimate == pytest.approx(model.rate_for(flight("AI612", "DXB")))
    assert all(str(step) for step in chain), "every step has to be printable for an operator"


def test_a_flight_with_no_schedule_or_route_still_gets_an_answer():
    model = LearnedRate.fit(rows("AI612", "DXB", 30, 4))
    bare = FlightBoard().upsert("AI612")  # no departure time, no destination
    chain = model.explain(bare)

    assert [step.level for step in chain] == ["airport", "carrier"]
    assert model.rate_for(bare) > 0


def test_a_group_with_no_history_leaves_the_estimate_alone():
    model = LearnedRate.fit(rows("AI612", "DXB", 30, 4, hour=9.0))
    chain = model.explain(flight("AI612", "JED", hour=9.0))
    route_step = [step for step in chain if step.level == "route"][0]

    assert route_step.observations == 0
    assert route_step.group_mean is None
    assert route_step.estimate == pytest.approx(chain[-2].estimate)


def test_prior_strength_must_be_positive():
    with pytest.raises(ValueError, match="prior_strength"):
        LearnedRate(prior_strength=0)


# -- measuring it --------------------------------------------------------


def test_a_learned_rate_beats_a_flat_one_when_routes_actually_differ():
    history = rows("AI612", "JED", 50, 5) + rows("6E204", "BLR", 50, 0)
    model = LearnedRate.fit(history)

    assert mean_absolute_error(model, history) < mean_absolute_error(FlatRate(), history)


def test_a_flat_rate_is_not_beaten_when_nothing_differs():
    """If every route is the same, there is nothing to learn, and it should not pretend."""
    history = rows("AI612", "JED", 30, 2) + rows("6E204", "BLR", 30, 2)
    model = LearnedRate.fit(history)

    assert mean_absolute_error(model, history) == pytest.approx(0.0, abs=0.2)


def test_the_error_of_an_empty_comparison_is_zero_not_a_crash():
    assert mean_absolute_error(FlatRate(), []) == 0.0


# -- keeping it ----------------------------------------------------------


def test_a_fitted_model_survives_a_round_trip_through_a_file():
    model = LearnedRate.fit(rows("AI612", "DXB", 30, 4) + rows("6E204", "BLR", 20, 1))
    restored = LearnedRate.from_json(model.to_json())

    assert restored.n_observations == model.n_observations
    assert restored.ready == model.ready
    for designator, destination in (("AI612", "DXB"), ("6E204", "BLR"), ("QQ1", "ZZZ")):
        assert restored.rate_for(flight(designator, destination)) == pytest.approx(
            model.rate_for(flight(designator, destination))
        )


def test_a_log_survives_a_round_trip_through_a_file():
    log = AssistanceLog()
    for row in rows("AI612", "DXB", 3, 4):
        log.record(row)
    restored = AssistanceLog.from_json(log.to_json())

    assert len(restored) == 3
    assert restored.observations()[0].destination == "DXB"


# -- collecting the data in the first place ------------------------------


def test_the_log_records_the_flights_nobody_needed_a_chair_for():
    """The row most easily lost, and the one that keeps the forecast honest."""
    board = FlightBoard()
    board.upsert("AI612", status=FlightStatus.DEPARTED, destination="DXB",
                 scheduled_departure_s=9 * HOUR)
    board.upsert("6E204", status=FlightStatus.DEPARTED, destination="BLR",
                 scheduled_departure_s=9 * HOUR)

    log = AssistanceLog()
    assert log.observe_board(board, {"AI612": 4}) == 2

    by_flight = {row.designator: row.requests for row in log.observations()}
    assert by_flight == {"AI612": 4, "6E204": 0}


def test_a_flight_that_has_not_gone_yet_is_not_recorded():
    board = FlightBoard()
    board.upsert("AI612", status=FlightStatus.BOARDING)
    board.upsert("6E204", status=FlightStatus.DEPARTED)

    log = AssistanceLog()
    assert log.observe_board(board, {}) == 1
    assert log.observations()[0].designator == "6E204"


def test_the_fleet_counts_requests_per_flight_for_the_log():
    fleet = Fleet(build_example_terminal())
    fleet.add_chair("CH-01", "dock_w")
    fleet.request_assistance("A", "AI612", pickup="kerb", gate="g4")
    fleet.request_assistance("B", "ai612", pickup="kerb", gate="g4")
    fleet.request_assistance("C", "6E204", pickup="kerb", gate="g1")

    assert fleet.assistance_counts() == {"AI612": 2, "6E204": 1}


def test_a_second_leg_is_not_counted_as_a_second_passenger():
    """One passenger parked in the lounge and fetched later is still one passenger."""
    fleet = Fleet(build_example_terminal())
    fleet.add_chair("CH-01", "dock_w")
    first = fleet.request_assistance("A", "SG118", pickup="kerb", gate="lounge")
    second = fleet.request_assistance("A", "SG118", pickup="lounge", gate="g5")
    second.follow_on_of = first.id

    assert fleet.assistance_counts() == {"SG118": 1}


# -- what it is for ------------------------------------------------------


def test_the_forecast_changes_when_the_model_says_the_routes_differ():
    board = FlightBoard()
    for designator, destination in (("AI612", "JED"), ("6E204", "BLR")):
        board.upsert(designator, status=FlightStatus.GATE_ASSIGNED, gate="g1",
                     destination=destination, scheduled_departure_s=2 * HOUR)

    busy = LearnedRate.fit(rows("AI612", "JED", 50, 6) + rows("6E204", "BLR", 50, 6))
    quiet = LearnedRate.fit(rows("AI612", "JED", 50, 0) + rows("6E204", "BLR", 50, 0))

    heavy = forecast_demand(board, now_s=0.0, rate_model=busy)
    light = forecast_demand(board, now_s=0.0, rate_model=quiet)

    assert sum(p.expected_requests for p in heavy) > sum(p.expected_requests for p in light)


def test_without_a_model_the_flat_rate_is_still_what_happens():
    board = FlightBoard()
    board.upsert("AI612", status=FlightStatus.GATE_ASSIGNED, gate="g1",
                 scheduled_departure_s=2 * HOUR)

    demand = forecast_demand(board, now_s=0.0)
    assert sum(p.expected_requests for p in demand) == pytest.approx(PRIOR_RATE)
