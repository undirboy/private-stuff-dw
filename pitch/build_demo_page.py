#!/usr/bin/env python3
"""The shift report, framed for somebody who has never heard of the project.

    python3 pitch/build_demo_page.py

Writes ``pitch/demo.html``: the same scripted shift as ``python3 -m sim.demo``,
rendered with a short introduction above it. This is the copy meant to be linked
from an application form, where the reader arrives cold.

The introduction is there mainly to say two things the dashboard alone would let
a reader assume wrongly — that this is a simulation, and that no passenger has
ever been carried. A convincing dashboard that does not say so implies the
opposite, which is the one mistake this project cannot afford to make.

The shift itself is imported from ``sim.demo`` rather than copied, so the page
and the laptop demo can never drift apart.
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from margadarshak import render_dashboard  # noqa: E402
from sim.demo import run_shift  # noqa: E402
from tools.testcount import count as _count  # noqa: E402

#: Asked of pytest at generation time, never typed.
TEST_COUNT = _count()

INTRO = f"""
<p><strong>This is the output of a working dispatcher, not a mock-up.</strong>
Margadarshak is a wheelchair that takes airport passengers to their gate by
following a guide line laid into the terminal floor. The chair itself stays
deliberately simple; everything requiring judgement — which chair, which
corridor, which gate, whose battery — happens here.</p>

<p>The shift below was produced by running <code>python3 -m sim.demo</code>
against an example terminal. It covers the situations that are hard to show with
a model chair on a table: a passenger who scans a boarding pass and says nothing
else, a gate that has not been announced yet, a gate that <em>moves</em> while
somebody is being carried to it, a family travelling as one caravan, a call
button at a gate, chairs moving towards the kerb before a rush, a corridor closed
under a moving chair, and chairs returning themselves to charge.</p>

<p><strong>Nothing here has carried a real passenger.</strong> The dispatcher is
built and covered by {TEST_COUNT} automated tests. The hardware is designed, drawn to
4&nbsp;mm MDF and costed at ₹4,759 for two chairs — and not yet cut. It is being
built for the December exhibition.</p>
"""


def main() -> int:
    fleet = run_shift(narrate=False)
    if fleet is None:
        print("The scripted shift did not complete — see python3 -m sim.demo")
        return 1

    summary = fleet.summary()
    if summary["delivered"] != summary["requests"]:
        print(
            f"Refusing to publish: {summary['requests'] - summary['delivered']} of "
            f"{summary['requests']} passengers were not delivered."
        )
        return 1

    out = render_dashboard(
        fleet,
        pathlib.Path(__file__).resolve().parent / "demo.html",
        title="Margadarshak — a shift, as an airport operator would see it",
        intro=INTRO,
    )
    print(
        f"Wrote {out}  ({out.stat().st_size / 1000:.0f} KB, "
        f"{summary['delivered']}/{summary['requests']} passengers delivered)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
