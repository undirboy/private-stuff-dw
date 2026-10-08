#!/usr/bin/env python3
"""The six-slide deck the application form asks for.

    python3 pitch/generate_deck.py

Writes ``deck.pdf`` — six 16:9 slides, in the order a judge reads them: what is
wrong, what we built, how it works, why it is not the imported product, what it
would change, and where it honestly stands today.

Two rules held throughout, because they are the project's whole position:

- **Never imply the technology is new.** Guided airport wheelchairs are deployed
  at around twenty-five airports abroad. A judge finds that in one search, and a
  deck that claimed novelty would lose the room at that moment. The claim is cost
  and Indian context.
- **Never imply anything has carried a passenger.** It has not. Slide six says so
  in as many words, which is the slide that makes the other five believable.

The chair is drawn from the real geometry in ``generate_blueprint.py``, so the
picture on slide one is of the thing that was actually designed.
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "explainer"))

import generate_explainer as E  # noqa: E402
from generate_explainer import BLUE, FAINT, INK, MID, RULE, TINT  # noqa: E402

import sys as _sys, pathlib as _pathlib
_sys.path.insert(0, str(_pathlib.Path(__file__).resolve().parent.parent))
from tools.testcount import count as _count

#: Asked of pytest at generation time, never typed. See tools/testcount.py.
TEST_COUNT = _count()

W, H = 280.0, 157.5  # 16:9
M = 18.0
FOOTER_Y = H - 15  # the rule above the slide number; body text stays above it
OUT = pathlib.Path(__file__).resolve().parent


class Slide(E.Sheet):
    """One slide. Same drawing helpers as the explainer, different page."""

    def __init__(self) -> None:
        super().__init__()
        #: Indices into ``self.p`` that the footer owns. The layout check exempts
        #: them, because the footer is the one thing meant to sit below the rule.
        self.chrome: set[int] = set()

    def render(self) -> str:
        return (
            f'<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}mm" height="{H}mm" '
            f'viewBox="0 0 {W} {H}">\n'
            f'  <rect width="{W}" height="{H}" fill="#ffffff"/>\n  '
            + "\n  ".join(self.p)
            + "\n</svg>\n"
        )

    def eyebrow(self, text: str) -> None:
        self.text(M, 22, text.upper(), 4.0, BLUE, "bold", spacing="1.2")

    def heading(self, text: str, size: float = 11.0) -> None:
        self.text(M, 38, text, size, INK, "bold")

    def footer(self, number: int) -> None:
        self.line(M, FOOTER_Y, W - M, FOOTER_Y, RULE, 0.3)
        start = len(self.p)
        self.text(M, H - 9, "MARGADARSHAK", 3.4, MID, "bold", spacing="0.6")
        self.text(W - M, H - 9, f"{number} / 6", 3.4, MID, anchor="end")
        self.chrome.update(range(start, len(self.p)))

    def bullet(self, x: float, y: float, title: str, body: list[str]) -> float:
        """A headed paragraph. Returns the y to carry on from."""
        self.text(x, y, title, 5.2, INK, "bold")
        self.lines(x, y + 7, body, 4.0, MID, 5.4)
        return y + 7 + len(body) * 5.4


def slide1() -> Slide:
    """Title. One claim, the chair, and the line it follows."""
    s = Slide()
    s.text(M, 40, "MARGADARSHAK", 16.0, INK, "bold", spacing="1.0")
    s.text(M, 50, "मार्गदर्शक — the one who shows the way", 5.0, MID)

    s.text(M, 70, "A wheelchair that takes airport", 9.0, INK, "bold")
    s.text(M, 82, "passengers to their gate by itself.", 9.0, INK, "bold")
    s.text(M, 94, "It follows a line laid into the floor — so it needs no", 4.6, MID)
    s.text(M, 100.5, "self-navigation, and costs a fraction of what that would.", 4.6, MID)

    E.draw_chair(s, ox=212, floor_y=118, k=0.40, guide=False)
    s.line(150, 119.5, W - M, 119.5, BLUE, 1.3, "3,2")
    s.text(150, 127, "the guide line it follows", 3.4, BLUE)

    s.text(M, 127, "Safe, inclusive and affordable mobility for women,", 4.0, BLUE, "bold")
    s.text(M, 133, "elderly and persons with disabilities", 4.0, BLUE, "bold")
    s.footer(1)
    return s


def slide2() -> Slide:
    """The problem. Three named failures, not a general lament."""
    s = Slide()
    s.eyebrow("The problem")
    s.heading("Assistance is promised by law and")
    s.text(M, 51, "cannot be delivered by staff.", 11.0, INK, "bold")

    s.text(M, 66, "Indian airports must provide wheelchair assistance free of charge, and do not", 4.4, MID)
    s.text(M, 72.5, "have the attendants to do it. The shortfall shows up in three specific ways.", 4.4, MID)

    col = (W - 2 * M - 12) / 3
    items = [
        ("You wait, and nobody\ncan tell you how long",
         ["No queue you can see.", "No estimate. No way to", "know if anyone is coming."]),
        ("Delivered to a gate,\nthen forgotten",
         ["The attendant leaves.", "You are stranded until", "somebody remembers you."]),
        ("The gate moves and\nnobody tells them",
         ["The person pushing set off", "committed and out of", "contact. Routine. Costly."]),
    ]
    for index, (title, body) in enumerate(items):
        x = M + index * (col + 6)
        s.rect(x, 84, col, 40, TINT, "none", rx=1.5)
        for line_index, part in enumerate(title.split("\n")):
            s.text(x + 5, 93 + line_index * 6, part, 4.8, INK, "bold")
        s.lines(x + 5, 110, body, 3.8, MID, 5.0)

    s.text(M, 133, "It lands hardest on elderly passengers, persons with disabilities and women "
                   "travelling alone —", 4.0, INK)
    s.text(M, 139, "and worse again on anyone who does not read English, because every fallback "
                   "in an airport is an English sign.", 4.0, INK)
    s.footer(2)
    return s


def slide3() -> Slide:
    """How it works. Three steps and the one fact the whole thing turns on."""
    s = Slide()
    s.eyebrow("How it works")
    s.heading("Scan. Sit. It takes you there.")

    steps = [
        ("1", "The passenger scans their boarding pass.",
         "Nothing typed, nothing to read, no app, no shared language needed."),
        ("2", "A laptop in the airport finds the gate.",
         "The barcode names the flight. The gate is looked up live, on the premises."),
        ("3", "The chair follows the guide line.",
         "No map of the world, no cloud. It obeys a speed limit and stops for obstacles."),
    ]
    y = 56
    for number, title, body in steps:
        s.circle(M + 4, y - 1.6, 4.2, "none", BLUE, 0.5)
        s.text(M + 4, y + 0.2, number, 4.4, BLUE, "bold", anchor="middle")
        s.text(M + 13, y, title, 5.4, INK, "bold")
        s.text(M + 13, y + 6.5, body, 4.0, MID)
        y += 20

    s.rect(M, 108, W - 2 * M, 30, TINT, "none", rx=1.5)
    s.text(M + 6, 118, "The boarding pass does not contain the gate — and that is the argument.",
           5.0, INK, "bold")
    s.lines(M + 6, 126, [
        "It is printed at check-in; the airport assigns the gate later, and moves it. So the scan names the",
        "flight, and the gate is looked up live — a passenger can scan before a gate exists, wait in the",
        "lounge, and a chair comes back for them the moment it is announced. Nobody has to remember them.",
    ], 3.8, MID, 5.0)
    s.footer(3)
    return s


def slide4() -> Slide:
    """Differentiation. Says plainly that the technology is not new."""
    s = Slide()
    s.eyebrow("What makes it different")
    s.heading("Not the technology. The decisions.")

    s.rect(M, 48, W - 2 * M, 17, "#fff8e8", "#e8d9b0", 0.4, rx=1.5)
    s.text(M + 6, 56, "Guided airport wheelchairs are deployed, not novel.", 4.6, INK, "bold")
    s.text(M + 6, 61.5,
           "WHILL operates at around 25 airports abroad. No Indian deployment was found. "
           "Our claim is cost and context — never invention.", 3.8, MID)

    col = (W - 2 * M - 10) / 2
    left = [
        ("Cheap because of what it refuses to do",
         ["An airport is a building somebody owns and can",
          "survey. So: no self-navigation, no learned",
          "perception, no cloud. That is the whole saving."]),
        ("Four languages, Konkani and Marathi first",
         ["English last — the opposite of the airport default.",
          "The build fails if a message is added in English",
          "alone. Most of why the service fails people today."]),
    ]
    right = [
        ("Ordered by who will miss their flight",
         ["Not who asked first. Overtaking is logged so an",
          "attendant can explain it to anyone who asks, and",
          "nobody waits more than fifteen minutes."]),
        ("Nothing leaves the airport",
         ["Runs on one laptop on the premises. No cloud, no",
          "vendor account, no passenger data leaving. The",
          "booking reference is never stored."]),
    ]
    y = 76
    for block, x in ((left, M), (right, M + col + 10)):
        yy = y
        for title, body in block:
            yy = s.bullet(x, yy, title, body) + 7
    s.footer(4)
    return s


def slide5() -> Slide:
    """Impact and cost. The numbers, with the estimate marked as an estimate."""
    s = Slide()
    s.eyebrow("Impact")
    s.heading("What it would change, and what it costs.")

    figures = [
        ("~1,00,000", "assistance journeys a year", "across Goa's two airports (estimated)"),
        ("₹4,759", "the demonstrator fleet", "two working chairs, built from MDF"),
        ("4", "languages, enforced", "Konkani, Marathi, Hindi, English"),
        ("0", "passenger records kept", "nothing leaves the building"),
    ]
    col = (W - 2 * M - 18) / 4
    for index, (big, mid, small) in enumerate(figures):
        x = M + index * (col + 6)
        s.text(x, 64, big, 10.5, BLUE, "bold")
        s.text(x, 72, mid, 4.2, INK, "bold")
        s.text(x, 78, small, 3.4, MID)

    s.line(M, 88, W - M, 88, RULE, 0.3)

    y = 100
    y = s.bullet(M, y, "For the passenger", [
        "A chair that comes, tells you where you are going in your",
        "own language, and does not leave you at a gate to be forgotten.",
    ])
    s.bullet(M + (W - 2 * M) / 2 + 5, 100, "For the airport", [
        "A statutory obligation met with the staff it can actually hire,",
        "and a shift report that evidences it was met.",
    ])

    s.text(M, 134, "The same guided-path system applies unchanged to railway stations — a far "
                   "larger version of the same problem.", 3.8, MID)
    s.footer(5)
    return s


def slide6() -> Slide:
    """Status. The slide that makes the other five believable."""
    s = Slide()
    s.eyebrow("Where it stands")
    s.heading("Built: the brain. Not built: the chair.")

    col = (W - 2 * M - 10) / 2
    s.rect(M, 48, col, 52, TINT, "none", rx=1.5)
    s.text(M + 6, 57, "Working today", 5.2, INK, "bold")
    s.lines(M + 6, 66, [
        "Dispatcher, routing, boarding-pass scanning,",
        "live gate changes, four languages, caravans for",
        "families, call buttons, pre-positioning, battery",
        "reserve, corridor safety, shift reporting.",
        "",
        f"{TEST_COUNT} automated tests. Runs on a laptop.",
    ], 3.9, MID, 5.2)

    s.rect(M + col + 10, 48, col, 52, "#fff5f5", "#f0d8d8", 0.4, rx=1.5)
    s.text(M + col + 16, 57, "Not built", 5.2, INK, "bold")
    s.lines(M + col + 16, 66, [
        "Every physical part. The chassis is designed and",
        "drawn to 4 mm MDF, the parts are costed, and",
        "nothing has been cut.",
        "",
        "Nothing here has carried a passenger, and we",
        "make no claim that it has.",
    ], 3.9, MID, 5.2)

    s.text(M, 112, "By the December exhibition", 5.2, INK, "bold")
    s.lines(M, 120, [
        "Two working demonstrator chairs on a taped guide path, running this same dispatcher: boarding pass in,",
        "gate out, the gate moved mid-journey, a call button, and a shift report at the end.",
    ], 4.0, MID, 5.4)
    s.lines(M, 134, [
        "Open questions we are not pretending to have answered: regulatory classification, airport operator",
        "approval, and a Konkani speaker's review of the copy. Marathi has been read.",
    ], 4.0, MID, 5.4)
    s.footer(6)
    return s


FONTS = {
    "normal": "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    "bold": "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
}


def check_fits(slides: list[Slide]) -> list[str]:
    """Measure every line against the real font and report anything off the page.

    Eyeballing a render catches a line that overflows by a word and misses one
    that overflows by a character, and a deck is uploaded once. So the widths are
    measured against the same FreeSans the renderer uses, through the font's own
    advance-width table, rather than estimated from a character count.
    """
    import re

    from fontTools.ttLib import TTFont

    metrics = {}
    for weight, path in FONTS.items():
        if not pathlib.Path(path).exists():
            return [f"font missing: {path}"]
        font = TTFont(path)
        cmap = font.getBestCmap()
        metrics[weight] = (cmap, font["hmtx"].metrics, font["head"].unitsPerEm,
                           font.getGlyphOrder())

    def width(text: str, size: float, weight: str, spacing: float) -> float:
        cmap, hmtx, upem, order = metrics["bold" if weight == "bold" else "normal"]
        total = 0.0
        for character in text:
            glyph = cmap.get(ord(character))
            if glyph is None or glyph not in hmtx:
                glyph = order[0]
            total += hmtx[glyph][0] / upem * size + spacing
        return total

    pattern = re.compile(
        r'<text x="([\d.-]+)" y="([\d.-]+)".*?font-size="([\d.]+)".*?'
        r'font-weight="(\w+)".*?text-anchor="(\w+)"(?: letter-spacing="([\d.]+)")?>(.*?)</text>'
    )
    problems = []
    for number, slide in enumerate(slides, start=1):
        for index, element in enumerate(slide.p):
            match = pattern.match(element)
            if match is None:
                continue
            if index in slide.chrome:
                continue
            x, y, size, weight, anchor, spacing, text = match.groups()
            x, y, size = float(x), float(y), float(size)
            w = width(text, size, weight, float(spacing or 0))
            left = x - w if anchor == "end" else (x - w / 2 if anchor == "middle" else x)
            right = left + w
            if right > W - M + 0.5:
                problems.append(
                    f"slide {number}: overflows right margin by {right - (W - M):.1f} mm "
                    f'at y={y:.0f} — "{text[:52]}..."'
                )
            if left < M - 0.5:
                problems.append(f"slide {number}: starts left of the margin at y={y:.0f}")
            if y > FOOTER_Y - 1:
                problems.append(
                    f"slide {number}: collides with the footer rule "
                    f'(y={y:.0f}, rule at {FOOTER_Y:.0f}) — "{text[:40]}"'
                )
    return problems


def main() -> int:
    import cairosvg
    from pypdf import PdfWriter

    slides = [slide1(), slide2(), slide3(), slide4(), slide5(), slide6()]

    problems = check_fits(slides)
    if problems:
        print("Layout check failed — the deck was NOT written:")
        for problem in problems:
            print(f"  ! {problem}")
        return 1
    print(f"Layout check passed: {len(slides)} slides, every line inside the margins.")
    writer = PdfWriter()
    tmp = OUT / "_slides"
    tmp.mkdir(exist_ok=True)

    for index, slide in enumerate(slides, start=1):
        svg = tmp / f"slide{index}.svg"
        pdf = tmp / f"slide{index}.pdf"
        svg.write_text(slide.render(), encoding="utf-8")
        cairosvg.svg2pdf(url=str(svg), write_to=str(pdf))
        writer.append(str(pdf))

    out = OUT / "deck.pdf"
    with open(out, "wb") as handle:
        writer.write(handle)

    cairosvg.svg2png(url=str(tmp / "slide1.svg"), write_to=str(OUT / "deck-slide1.png"),
                     output_width=1600)
    size_mb = out.stat().st_size / 1_000_000
    print(f"Wrote {out}  ({len(slides)} slides, {size_mb:.2f} MB, limit is 15 MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
