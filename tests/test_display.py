"""The panel: pre-shaped pixels, composed with the standard library.

The point of these is not that text appears. It is that the four properties the
design depends on hold: nothing reaches the panel that was not shaped at build
time, lines break only where Devanagari may be broken, every message in every
language fits the panel it was sized for, and the package still imports nothing
but the standard library.
"""

from __future__ import annotations

import pathlib

import pytest

from margadarshak import Fleet, build_example_terminal, screen_for
from margadarshak.announce import CATALOGUE, DISPLAY_ORDER, placeholders
from margadarshak.display import Screen, Unrenderable

#: Stand-ins for the values a message is filled with at runtime.
SAMPLE = {
    "gate": "4",
    "terminal": "1",
    "minutes": "2",
    "flight": "AI612",
    "name": "MRS PEREIRA",
}


@pytest.fixture(scope="module")
def panel():
    return Screen()


def params_for(message_id: str, language: str) -> dict:
    return {
        key: SAMPLE[key]
        for key in placeholders(CATALOGUE[message_id][language])
    }


# -- everything fits ------------------------------------------------------


@pytest.mark.parametrize("language", DISPLAY_ORDER)
def test_every_message_fits_the_panel(panel, language):
    """The check that chose the panel size, kept so a longer message fails here.

    A message that does not fit is not a cosmetic problem. The passenger reads
    the clipped half and acts on it, which for a gate number is worse than a
    blank screen.
    """
    too_tall = []
    for message_id in CATALOGUE:
        params = params_for(message_id, language)
        if panel.lines_needed(message_id, language, **params) > panel.lines_per_panel:
            too_tall.append(message_id)
    assert not too_tall, (
        f"these need more than {panel.lines_per_panel} lines in {language}: "
        f"{too_tall}. Shorten them, or fit a taller panel and rebuild the atlas."
    )


@pytest.mark.parametrize("language", DISPLAY_ORDER)
def test_no_single_word_is_wider_than_the_panel(panel, language):
    """Wrapping cannot rescue a word that does not fit on a line by itself."""
    for message_id in CATALOGUE:
        params = params_for(message_id, language)
        assert panel.overflows(message_id, language, **params) == 0, (
            f"{message_id} in {language} has a word wider than the panel"
        )


# -- nothing unshaped reaches the panel -----------------------------------


def test_text_with_no_glyphs_is_refused_rather_than_dropped(panel):
    """A screen that silently drops what it cannot draw shows a wrong gate."""
    with pytest.raises(Unrenderable, match="no glyph"):
        panel.spell("গেট")  # Bengali: a script the atlas was never built for


def test_a_message_the_atlas_predates_is_refused():
    """A message edited without rebuilding the atlas must fail loudly.

    Its own Screen, not the shared one: this test removes a run, and a fixture
    other tests share is not the place to do that.
    """
    panel = Screen()
    panel.runs.pop("welcome|mr|0|0")

    with pytest.raises(Unrenderable, match="rebuild the atlas"):
        panel.runs_for("welcome", "mr", name="MRS PEREIRA")


def test_a_missing_parameter_is_refused(panel):
    with pytest.raises(Unrenderable, match="gate"):
        panel.runs_for("taking_to_gate", "en")


def test_the_atlas_covers_what_a_boarding_pass_can_contain(panel):
    """BCBP is ASCII, so a name or flight code off a scan must be spellable."""
    for text in ("AI612", "6E204", "MRS PEREIRA", "D'SOUZA", "SG-118"):
        assert panel.spell(text)


# -- lines break only where Devanagari may be broken ----------------------


def test_wrapping_happens_at_spaces_and_nowhere_else(panel):
    """No conjunct spans a space and no matra attaches across one.

    Every run on a wrapped line is either one the atlas holds whole or a space,
    so a break can never land inside a shaped cluster.
    """
    words = panel.runs_for("no_gate_yet", "kok")
    lines = panel.wrap(words)
    assert len(lines) > 1, "this message is long enough to wrap; the test needs one that does"

    known = set(panel.runs.values())
    for line in lines:
        for run in line:
            assert run in known, "a wrapped line may only contain runs from the atlas"


def test_wrapping_keeps_every_word(panel):
    words = panel.runs_for("no_gate_yet", "mr")
    flat = [run for word in words for run in word]
    wrapped = [run for line in panel.wrap(words) for run in line
               if run is not panel.runs["space"]]
    assert wrapped == flat, "wrapping must not lose or reorder a word"


def test_a_narrow_panel_wraps_more(panel):
    words = panel.runs_for("taking_to_gate", "en", gate="4")
    assert len(panel.wrap(words, width=400)) < len(panel.wrap(words, width=60))


# -- composing a frame ----------------------------------------------------


def test_a_frame_is_the_size_of_the_panel(panel):
    frame = panel.compose(panel.wrap(panel.runs_for("taking_to_gate", "en", gate="4")))
    assert frame.width == panel.width and frame.height == panel.height
    assert len(frame.packed()) == frame.stride * frame.height


def test_a_frame_actually_has_something_drawn_on_it(panel):
    frame = panel.compose(panel.wrap(panel.runs_for("taking_to_gate", "kok", gate="4")))
    assert any(frame.packed()), "the panel came back blank"


def test_a_screenful_from_the_dispatcher_renders_in_every_language(panel):
    fleet = Fleet(build_example_terminal())
    fleet.add_chair("CH-01", "dock_w")
    fleet.request_assistance("Mrs Pereira", "AI-612", pickup="kerb", gate="g4")
    fleet.run(duration_s=200)

    content = screen_for(fleet, fleet.chairs["CH-01"])
    for language in DISPLAY_ORDER:
        frame = panel.frame_for(content, language)
        assert any(frame.packed()), f"{language} came back blank"


def test_the_local_languages_come_before_english(panel):
    """The ordering is a decision, and it is the opposite of the airport default."""
    assert DISPLAY_ORDER[-1] == "en"
    assert DISPLAY_ORDER[0] == "kok"


# -- the constraint the whole design exists to keep -----------------------


def test_the_package_still_imports_nothing_but_the_standard_library():
    """Shaping moved to a build tool precisely so this stays true."""
    import ast

    third_party = {"PIL", "numpy", "requests", "pptx", "cairosvg", "fontTools"}
    package = pathlib.Path(__file__).resolve().parent.parent / "margadarshak"

    offenders = []
    for path in sorted(package.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names = [node.module.split(".")[0]]
            offenders += [(path.name, name) for name in names if name in third_party]

    assert not offenders, (
        f"these would make the dispatcher depend on third-party code: {offenders}. "
        f"Shaping and rendering belong in tools/, not in the package."
    )
