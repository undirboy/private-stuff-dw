"""How many tests the suite has, asked rather than remembered.

The count is quoted on the poster, the one-page explainer, the laptop demo page
and the application deck, because "it is covered by a test suite" is worth more
to a reader with a number attached. It went stale twice in one afternoon, for
the same reason the build cost did: several files carrying a number by hand with
nothing comparing them.

So nothing carries it by hand any more. The generators call :func:`count` and it
asks pytest, which is the only thing that actually knows.
"""

from __future__ import annotations

import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent


def count(timeout_s: float = 120.0) -> int:
    """Tests pytest would collect. Raises rather than guess."""
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q"],
        cwd=ROOT, capture_output=True, text=True, timeout=timeout_s,
    )
    match = re.search(r"(\d+)\s+tests? collected", result.stdout)
    if match is None:
        raise RuntimeError(
            "could not read a test count from pytest --collect-only:\n"
            + result.stdout[-600:] + result.stderr[-600:]
        )
    return int(match.group(1))


if __name__ == "__main__":
    print(count())
