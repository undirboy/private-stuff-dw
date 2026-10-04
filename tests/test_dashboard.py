"""The operator's shift report."""

from __future__ import annotations

import re

import pytest

from saarthi import ChairState, Fleet, build_example_terminal, render_dashboard
from saarthi.dashboard import BANDS, render, spans, utilisation


@pytest.fixture
def shift():
    f = Fleet(build_example_terminal(), holding_area="lounge")
    for chair_id in ("CH-01", "CH-02"):
        f.add_chair(chair_id, "dock_w").state = ChairState.IDLE
    f.request_assistance("Mrs Pereira", "AI612", pickup="kerb", gate="g4")
    f.request_assistance("Mr Naik", "6E204", pickup="kerb", gate="g1")
    f.run(duration_s=2400)
    return f


def test_an_empty_fleet_renders_without_falling_over():
    f = Fleet(build_example_terminal())
    assert spans(f) == []
    page = render(f)
    assert "No shift recorded" in page


def test_spans_cover_the_whole_shift_for_every_chair(shift):
    for chair_id in shift.chairs:
        chair_spans = [s for s in spans(shift) if s.chair == chair_id]
        assert chair_spans
        covered = sum(s.duration_s for s in chair_spans)
        assert covered == pytest.approx(shift.now, rel=0.02)


def test_spans_do_not_overlap(shift):
    for chair_id in shift.chairs:
        chair_spans = sorted(
            (s for s in spans(shift) if s.chair == chair_id), key=lambda s: s.start_s
        )
        for earlier, later in zip(chair_spans, chair_spans[1:]):
            assert earlier.end_s <= later.start_s


def test_adjacent_spans_are_merged_when_the_band_is_unchanged(shift):
    """Idle and charging are two states but one thing for an operator to look at."""
    for chair_id in shift.chairs:
        chair_spans = sorted(
            (s for s in spans(shift) if s.chair == chair_id), key=lambda s: s.start_s
        )
        for earlier, later in zip(chair_spans, chair_spans[1:]):
            assert earlier.band != later.band


def test_utilisation_is_a_distribution(shift):
    used = utilisation(shift)
    assert set(used) == {key for key, _, _ in BANDS}
    assert sum(used.values()) == pytest.approx(1.0)
    assert used["carrying"] > 0


def test_the_page_reports_the_numbers_an_operator_is_held_to(shift):
    page = render(shift, title="Morning shift")
    assert "Morning shift" in page
    assert "Worst wait" in page
    assert "Mean wait for a chair" in page
    assert "Attendant call-outs" in page
    for request in shift.requests:
        assert request.passenger in page


def test_the_chart_is_never_the_only_way_in(shift):
    """A table view exists for everything the timeline shows."""
    page = render(shift)
    assert page.count("<table") >= 2
    for _, label, _ in BANDS:
        assert label in page


def test_dark_mode_is_declared_under_both_scopes(shift):
    page = render(shift)
    assert "prefers-color-scheme: dark" in page
    assert '[data-theme="dark"]' in page
    assert ':not([data-theme="light"])' in page


def test_passenger_names_are_escaped():
    """A name is passenger-supplied text and goes into HTML."""
    f = Fleet(build_example_terminal())
    f.add_chair("CH-01", "dock_w").state = ChairState.IDLE
    f.request_assistance('<script>alert("x")</script>', "AI612", pickup="kerb", gate="g4")
    f.run(duration_s=60)

    page = render(f)
    assert "<script>alert" not in page
    assert "&lt;script&gt;" in page


def test_segment_positions_stay_inside_the_track(shift):
    page = render(shift)
    for left, width in re.findall(r"left:([\d.]+)%;width:([\d.]+)%", page):
        assert 0 <= float(left) <= 100
        assert float(left) + float(width) <= 100.5


def test_it_writes_the_file(tmp_path, shift):
    out = render_dashboard(shift, tmp_path / "shift.html", title="Shift")
    assert out.exists()
    assert out.read_text(encoding="utf-8").startswith("<!doctype html>")
