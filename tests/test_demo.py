"""The demo is what gets shown to people, so it is tested like anything else.

This exists because the demo once shipped broken: an import was tidied away while
a call to it remained, and nothing caught it, because the demo was the one thing
with no test. It is run end to end here.
"""

from __future__ import annotations

import io
import runpy
from contextlib import redirect_stdout

import pytest


def run_demo() -> str:
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        try:
            runpy.run_module("sim.demo", run_name="__main__")
        except SystemExit as exit_code:
            assert exit_code.code == 0, f"demo exited with {exit_code.code}"
    return buffer.getvalue()


@pytest.fixture(scope="module")
def output() -> str:
    return run_demo()


def test_it_runs_to_completion(output):
    assert "Dashboard written to" in output


def test_every_passenger_is_delivered(output):
    served = [line for line in output.splitlines() if "journeys served" in line]
    assert served, "no summary line"
    delivered, requested = served[0].split()[-1].split("/")
    assert delivered == requested, f"only {delivered} of {requested} delivered"


def test_no_chair_needed_an_attendant(output):
    assert "attendant call-outs 0" in output


@pytest.mark.parametrize(
    "shown",
    [
        "scanned",          # a boarding pass read
        "no gate yet",      # the holding-area case
        "gate_change",      # a gate moving mid-journey
        "caravan",          # a family travelling as one
        "call_button",      # somebody summoning a chair
        "staged",           # pre-positioning before the rush
        "blocked",          # a corridor closed under a chair
        "docked",           # unaccompanied return to charge
    ],
)
def test_the_demo_still_shows_each_thing_it_is_for(output, shown):
    assert shown in output


def test_the_screen_renders_in_every_language(output):
    # The four-language block prints one line per language, tagged.
    for tag in ("[kok]", "[mr ]", "[hi ]", "[en ]"):
        assert tag in output


def test_a_rejected_scan_explains_itself_to_the_passenger(output):
    assert "chair screen:" in output
    assert "Please check with your airline" in output
