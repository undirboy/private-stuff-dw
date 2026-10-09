#!/usr/bin/env python3
"""Rebuild every generated artefact, in order, with one command.

    python3 tools/build.py            # rebuild everything
    python3 tools/build.py --check    # rebuild into a scratch copy and diff

Eleven things in this repository are generated from source: the chassis STLs,
the cutting templates, the blueprint, the display atlas, the explainer, the
poster, the laptop demo page, and two decks. Keeping them current was a matter
of remembering, and remembering failed twice in one afternoon — once shipping a
build cost eighty rupees out, once a stale test count, both into a deck that was
about to be submitted.

So there is one command, it runs them in dependency order, and ``--check``
fails if anything committed differs from what its generator produces now. That
check is what CI runs, and it is the difference between "the artefacts are
current" being a claim and being a fact.
"""

from __future__ import annotations

import argparse
import filecmp
import pathlib
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent

#: Generators, in the order they must run. The display atlas comes before
#: anything that reads the message catalogue; the chair art before the decks
#: that place it; the test count before anything that prints it.
STEPS: list[tuple[str, str]] = [
    ("hardware/chassis/generate_chassis.py", "printable deck, bracket and riser"),
    ("hardware/chassis/generate_mdf_template.py", "1:1 cutting template, drive platform"),
    ("hardware/chassis/generate_mdf_body_template.py", "1:1 cutting template, chair body"),
    ("hardware/chassis/generate_blueprint.py", "assembly blueprint"),
    ("tools/render_display.py", "shaped bitmap atlas for the panel"),
    ("pitch/seva/make_chair.py", "chair art in the challenge's palette"),
    ("explainer/generate_explainer.py", "one-page explainer"),
    ("explainer/generate_ad.py", "square poster"),
    ("pitch/generate_deck.py", "six-slide deck"),
    ("pitch/build_demo_page.py", "the shift report, framed for a stranger"),
    ("pitch/seva/fill_template.py", "the challenge's own template, filled"),
]

#: Artefacts whose generators are deterministic, so a byte comparison is
#: meaningful. PDFs and .pptx files embed a creation time and are left out —
#: the figures inside them are guarded by tests/test_costs.py instead.
GUARDED = [
    "explainer/explainer.svg",
    "explainer/ad.svg",
    "margadarshak/display_atlas.json",
    "hardware/chassis/deck.stl",
    "hardware/chassis/sensor_bracket.stl",
    "hardware/chassis/castor_riser_20mm.stl",
    "pitch/seva/chair.png",
]


def run(script: str, *, cwd: pathlib.Path) -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / script)],
        cwd=cwd, capture_output=True, text=True, timeout=600,
    )
    if result.returncode != 0:
        raise SystemExit(
            f"\n{script} failed:\n{result.stdout[-2000:]}{result.stderr[-2000:]}"
        )


def build(cwd: pathlib.Path) -> None:
    width = max(len(step) for step, _ in STEPS)
    for script, what in STEPS:
        print(f"  {script:<{width}}  {what}")
        run(script, cwd=cwd)


def check() -> int:
    """Rebuild into a copy of the tree and report anything that differs."""
    with tempfile.TemporaryDirectory() as temp:
        copy = pathlib.Path(temp) / "repo"
        shutil.copytree(
            ROOT, copy,
            ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc", "_slides"),
        )
        build(copy)

        stale = [
            path for path in GUARDED
            if not filecmp.cmp(ROOT / path, copy / path, shallow=False)
        ]

    if stale:
        print("\nThese are not what their generators produce now:")
        for path in stale:
            print(f"  ! {path}")
        print("\nRun: python3 tools/build.py")
        return 1

    print(f"\nAll {len(GUARDED)} guarded artefacts match their generators.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="do not write; fail if anything committed is stale")
    args = parser.parse_args()

    if args.check:
        print("Checking generated artefacts against their sources:")
        return check()

    print("Rebuilding generated artefacts:")
    build(ROOT)
    print("\nDone. Re-run the test suite and commit whatever changed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
