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
ONE_CHAIR = 2801
BOTH_CHAIRS = 4759


def rupee_totals(text: str) -> set[int]:
    """Every ₹N,NNN figure in a piece of text, as integers."""
    return {
        int(match.replace(",", ""))
        for match in re.findall(r"₹\s?([0-9]{1,2},[0-9]{3})", text)
    }


def add_up(section: str) -> int:
    """Sum a parts table: the ₹ column times the quantity column."""
    total = 0
    for line in section.splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 4 or not cells[1] or cells[1].startswith("Item"):
            continue
        if not cells[2].isdigit():
            continue
        quantity = cells[3] if cells[3].isdigit() else "1"
        total += int(cells[2]) * int(quantity)
    return total


def test_stage_one_adds_up_to_the_total_it_states():
    text = COMPONENTS.read_text(encoding="utf-8")
    stage1 = re.search(r"### Stage 1 — order now.*?\*\*Stage 1, Robu\*\*[^\n]*", text, re.S)
    assert stage1, "the stage 1 table has moved or been renamed"

    stated = re.findall(r"\*\*₹([0-9,]+)\*\*", stage1.group())[-1]
    assert add_up(stage1.group()) == int(stated.replace(",", ""))


def test_stage_two_adds_up_to_the_total_it_states():
    text = COMPONENTS.read_text(encoding="utf-8")
    stage2 = re.search(r"### Stage 2 — chair 2.*?\*\*Stage 2\*\*", text, re.S)
    assert stage2, "the stage 2 table has moved or been renamed"

    total = add_up(stage2.group())
    assert total == BOTH_CHAIRS - ONE_CHAIR, (
        f"stage 2 adds up to ₹{total}, but the totals table implies "
        f"₹{BOTH_CHAIRS - ONE_CHAIR}"
    )


def test_the_total_is_stated_as_the_parts_add_up():
    text = COMPONENTS.read_text(encoding="utf-8")
    assert f"₹{ONE_CHAIR:,}" in text
    assert f"₹{BOTH_CHAIRS:,}" in text


#: The production retrofit module's indicative BOM in docs/hardware.md. Planning
#: estimates rather than quotes, but they still have to add up and still have to
#: match everywhere they are quoted.
PRODUCTION_MODULE = 57700


def test_the_production_bill_of_materials_adds_up():
    text = (ROOT / "docs" / "hardware.md").read_text(encoding="utf-8")
    table = re.search(r"\| Item \| Indicative ₹.*?\*\*Total\*\*[^\n]*", text, re.S)
    assert table, "the production BOM table has moved or been renamed"

    total = 0
    for line in table.group().splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 3 or cells[0].startswith(("Item", "---", "**Total")):
            continue
        figure = cells[1].replace(",", "")
        if figure.isdigit():
            total += int(figure)

    assert total == PRODUCTION_MODULE, (
        f"the production BOM adds up to ₹{total:,}, but the stated total is "
        f"₹{PRODUCTION_MODULE:,}"
    )


def test_the_production_figure_is_quoted_consistently():
    """It is quoted to the nearest thousand in prose; those must agree too."""
    rounded = round(PRODUCTION_MODULE / 1000)
    for relative in ("README.md", "docs/hardware.md", "docs/components.md",
                     "pitch/seva/fill_template.py"):
        text = (ROOT / relative).read_text(encoding="utf-8")
        wrong = [
            value for value in re.findall(r"₹\s?([0-9]{2}),000", text)
            if int(value) != rounded
        ] + [
            value for value in re.findall(r"₹([0-9]{2})k", text)
            if int(value) != rounded
        ]
        assert not wrong, f"{relative} quotes ₹{wrong}k, not ₹{rounded}k"


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


#: Files that quote prices but must not be held to the current ones.
#:
#: ``docs/chat-log.md`` is the conversation that built this, kept unedited. It
#: contains every figure the project ever had, including the ones that were
#: wrong and the turn where each was corrected. Making a historical record agree
#: with today's parts list would delete the history, which is the only thing it
#: is for.
NOT_CURRENT_FIGURES = {"docs/components.md", "docs/chat-log.md"}


def test_every_file_that_quotes_a_cost_is_in_the_checked_list():
    """A new file quoting a price must be added above, or this check is a fiction."""
    missed = []
    for path in list(ROOT.glob("*.md")) + list(ROOT.glob("docs/*.md")) + \
            list(ROOT.glob("explainer/*.py")) + list(ROOT.glob("pitch/**/*.py")):
        relative = path.relative_to(ROOT).as_posix()
        if relative in QUOTING_FILES or relative in NOT_CURRENT_FIGURES:
            continue
        if rupee_totals(path.read_text(encoding="utf-8")):
            missed.append(relative)
    assert not missed, f"these quote a ₹ total but are not checked: {missed}"


# -- the other number that drifts ----------------------------------------
#
# The test count is quoted on the poster, the explainer and the application deck,
# and it went stale twice in one afternoon for exactly the same reason the cost
# did. The generators now ask pytest for it (tools/testcount.py), so only the
# hand-written docs can still drift — which is what this checks.

def test_no_document_quotes_a_stale_test_count():
    from tools.testcount import count

    actual = count()
    quoted: dict[int, list[str]] = {}
    for relative in ["README.md", "docs/features.md"]:
        text = (ROOT / relative).read_text(encoding="utf-8")
        for match in re.findall(r"(\d{2,4})\s+(?:automated\s+)?tests", text):
            quoted.setdefault(int(match), []).append(relative)

    wrong = {number: files for number, files in quoted.items() if number != actual}
    assert not wrong, f"the suite has {actual} tests; these say otherwise: {wrong}"
