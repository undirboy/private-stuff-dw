"""The build cost, checked against the parts list that is its only authority.

This exists because the number drifted. The bill of materials in
``docs/components.md`` said ₹4,679 while the explainer, the poster and the
application deck all said ₹4,759 — a transposition that survived several commits
because every one of those files carried the figure by hand and nothing compared
them.

It matters more than a typo normally would. The cost *is* the pitch: the whole
argument is that this can be built for thousands rather than lakhs. A judge who
adds up the parts list and gets a different total from the one on the slide has
found the project's central claim failing its own arithmetic.

So the tables are re-added here, and every file that quotes a total has to quote
one the tables support.
"""

from __future__ import annotations

import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
COMPONENTS = ROOT / "docs" / "components.md"

#: Files that quote a build cost to a reader. Each one is a place the number can
#: drift, so each one is checked.
QUOTING_FILES = [
    "README.md",
    "docs/features.md",
    "docs/hardware.md",
    "explainer/generate_explainer.py",
    "explainer/generate_ad.py",
    "pitch/generate_deck.py",
    "pitch/build_demo_page.py",
    "pitch/seva/fill_template.py",
]

#: Totals the parts list supports: one chair, and both.
ONE_CHAIR = 2721
BOTH_CHAIRS = 4679


def rupee_totals(text: str) -> set[int]:
    """Every ₹N,NNN figure in a piece of text, as integers."""
    return {
        int(match.replace(",", ""))
        for match in re.findall(r"₹\s?([0-9]{1,2},[0-9]{3})", text)
    }


def test_the_parts_list_adds_up_to_the_total_it_states():
    text = COMPONENTS.read_text(encoding="utf-8")

    stage2 = re.search(r"### Stage 2 — chair 2.*?\*\*Stage 2\*\*", text, re.S)
    assert stage2, "the stage 2 table has moved or been renamed"

    total = 0
    for line in stage2.group().splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) != 4 or not cells[1] or cells[1].startswith("Item"):
            continue
        if not cells[2].isdigit():
            continue
        total += int(cells[2]) * int(cells[3] or 1)

    assert total == BOTH_CHAIRS - ONE_CHAIR, (
        f"stage 2 adds up to ₹{total}, but the totals table implies "
        f"₹{BOTH_CHAIRS - ONE_CHAIR}"
    )


def test_the_total_is_stated_as_the_parts_add_up():
    text = COMPONENTS.read_text(encoding="utf-8")
    assert f"₹{ONE_CHAIR:,}" in text
    assert f"₹{BOTH_CHAIRS:,}" in text


def test_the_build_stays_under_the_five_thousand_rupee_budget():
    """The constraint the whole parts list was chosen against."""
    assert BOTH_CHAIRS < 5000


@pytest.mark.parametrize("relative", QUOTING_FILES)
def test_nothing_quotes_a_total_the_parts_list_does_not_support(relative):
    path = ROOT / relative
    if not path.exists():  # pragma: no cover - the file list is checked below
        pytest.skip(f"{relative} does not exist")

    quoted = rupee_totals(path.read_text(encoding="utf-8"))
    # Four- and five-figure sums that are not build totals are legitimate — the
    # production BOM, a per-chair module price. Only flag a figure close enough
    # to a build total to be a drifted copy of one.
    suspicious = {
        value
        for value in quoted
        if any(abs(value - real) <= 200 and value != real
               for real in (ONE_CHAIR, BOTH_CHAIRS))
    }
    assert not suspicious, (
        f"{relative} quotes {sorted(suspicious)}, which is near but not equal to "
        f"the parts list's ₹{ONE_CHAIR:,} / ₹{BOTH_CHAIRS:,}. Fix the file, or the "
        f"parts list if the parts list is what changed."
    )


def test_every_file_that_quotes_a_cost_is_in_the_checked_list():
    """A new file quoting a price must be added above, or this check is a fiction."""
    missed = []
    for path in list(ROOT.glob("*.md")) + list(ROOT.glob("docs/*.md")) + \
            list(ROOT.glob("explainer/*.py")) + list(ROOT.glob("pitch/**/*.py")):
        relative = path.relative_to(ROOT).as_posix()
        if relative in QUOTING_FILES or relative == "docs/components.md":
            continue
        if rupee_totals(path.read_text(encoding="utf-8")):
            missed.append(relative)
    assert not missed, f"these quote a ₹ total but are not checked: {missed}"
