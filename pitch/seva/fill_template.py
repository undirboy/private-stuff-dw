"""Fill the Seva Innovation Challenge 2026 template with Margadarshak's content.

Every claim here is one the project can defend. Where a number is an estimate it
says so on the slide, because a figure a judge can disprove is worse than no
figure at all.
"""

import pathlib
import sys

from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor

HERE = pathlib.Path(__file__).resolve().parent
#: Every path is resolved against this file, never against the working
#: directory. A generator that only runs from one folder is a generator the
#: build script cannot call and somebody will eventually run from the wrong
#: place and not notice.
sys.path.insert(0, str(HERE.parent.parent))
from tools.testcount import count as _count  # noqa: E402

#: Asked of pytest at generation time, never typed.
TEST_COUNT = _count()

NAVY, ORANGE = RGBColor(0x1B, 0x2A, 0x5C), RGBColor(0xF2, 0x8C, 0x28)

# shape id -> replacement text, per slide
TEXT = {
1: {
  3: "Margadarshak",
  4: "A wheelchair that takes airport passengers to their gate by itself — "
     "built for Indian airports, at a fraction of the imported cost.",
},
2: {
  9: "Indian airports must provide wheelchair assistance free of charge, and do not have "
     "the attendants to deliver it. The root cause is arithmetic, not goodwill: demand is "
     "unpredictable and staffing for the peak is unaffordable.",
  12: "Elderly passengers, persons with disabilities, and women travelling alone — at Goa's "
      "two airports, Dabolim and Manohar International, Mopa. Worst affected are those who "
      "do not read English, since every fallback is an English sign.",
  15: "DGCA CAR Section 3, Series M, Part I requires airports and airlines to provide "
      "assistance free of charge. The figure opposite is our own estimate — roughly 1 in 100 "
      "passengers against AAI's published traffic for both airports — and we flag it as an "
      "estimate until a pilot measures it.",
  18: "Assistance today is a person pushing a chair. Once they set off they cannot be told "
      "the gate moved, and a passenger delivered to a gate is stranded until somebody "
      "remembers them. Imported autonomous chairs exist, but not at a price Indian airports "
      "can meet.",
  20: "~1,00,000",
  21: "assistance journeys a year across Goa's two airports (our estimate)",
  23: "A missed flight — and the indignity of asking a stranger for help, then waiting "
      "without knowing if anyone is coming.",
},
3: {
  8: "The passenger scans their boarding pass and sits down. The barcode names the flight; a "
     "laptop on the premises looks up the gate live and sends a chair. The chair follows a "
     "guide line laid into the floor, obeys a speed limit, and stops for obstacles.",
  14: "Passenger scans their boarding pass",
  20: "Dispatcher finds the live gate, sends the nearest chair",
  26: "Chair follows the floor line, re-routing if the gate moves",
  30: "When the airline moves a gate, the chair knows and re-routes mid-journey. A person "
      "pushing a wheelchair cannot — they set off committed, and nobody tells them. "
      "No patent filed.",
},
4: {
  21: "ESP32 controller, IR line sensors, ultrasonic obstacle stop, 2S lithium pack, 4 mm MDF "
      "chassis. Dispatcher in Python on one laptop — standard library only, no cloud and no "
      "network calls.",
  24: "₹4,759 for two demonstrator chairs (₹2,801 for one). The production retrofit module is "
      "designed at about ₹58,000 per chair. A terminal pilot needs chairs, floor marking and "
      "a survey.",
  27: "3 months: two chairs running a taped guide path at the December exhibition. 6 months: "
      "a supervised trial in one terminal zone. 12 months: a measured pilot with an airport "
      "operator.",
  30: "Airports Authority of India (Dabolim) and Manohar International Airport, Mopa. Not yet "
      "approached: the regulatory position needs a competent authority, which is part of what "
      "we are asking for.",
},
5: {
  8: "~2,000",
  10: "assistance journeys in a first-year pilot at one terminal",
  12: "3×",
  14: "passengers per attendant in caravan mode — simulated, not yet measured",
  16: "0",
  18: "attendant jobs replaced — these are posts airports cannot fill today",
  21: "Independence for passengers who today must ask a stranger for help and then depend on "
      "them. Konkani and Marathi before English, so the service reaches the people the "
      "current one fails. Nobody is left waiting at a gate to be remembered.",
  24: "Bought by the airport operator against an obligation it already carries, then "
      "maintained. No cloud fees, no vendor account and no per-journey licence — it runs on "
      "one laptop on the premises, and the airport owns and edits its own map.",
  27: "The guide path is tape and floor tags; the map is JSON the airport edits itself. "
      "Replicating means surveying a terminal, not rebuilding software. The same system fits "
      "railway stations — a far larger Indian problem.",
},
6: {
  9: "Aatriv Thosar",
  10: "Team Lead",
  11: "[Your qualification / course]",  # the one bracket left on purpose
  43: "Certification and a clear regulatory position are what stand between a working "
      "dispatcher and a chair that may legally carry a passenger.",
  44: "Thank you  |  aatriv38@gmail.com",
},
}

# Shapes to remove: slide 1's guidance box, slide 6's three empty team cards and
# the mentor line. The template says to delete guidance boxes, and an empty slot
# for a teammate who does not exist reads worse than no slot at all.
DELETE = {1: [17, 18, 19], 6: [12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23,
                              24, 25, 26, 27, 28, 29, 30]}

# Circles to fill solid: the stage marker on slide 4 (Proof of Concept) and the
# one support box we are ticking on slide 6.
FILL_ORANGE = {4: [11], 6: [41]}


def by_id(slide):
    return {sh.shape_id: sh for sh in slide.shapes}


def set_text(shape, text):
    """Replace the text, keeping the first run's formatting."""
    paras = shape.text_frame.paragraphs
    first = paras[0]
    if not first.runs:
        raise SystemExit(f"shape {shape.shape_id} has no run to copy formatting from")
    first.runs[0].text = text
    for run in first.runs[1:]:
        run._r.getparent().remove(run._r)
    for para in paras[1:]:
        para._p.getparent().remove(para._p)


def main():
    prs = Presentation(HERE / "template.pptx")
    slides = list(prs.slides)

    for number, slide in enumerate(slides, start=1):
        shapes = by_id(slide)

        for shape_id in DELETE.get(number, []):
            shape = shapes.get(shape_id)
            if shape is None:
                raise SystemExit(f"slide {number}: no shape {shape_id} to delete")
            shape._element.getparent().remove(shape._element)

        shapes = by_id(slide)
        for shape_id, text in TEXT.get(number, {}).items():
            shape = shapes.get(shape_id)
            if shape is None:
                raise SystemExit(f"slide {number}: no shape {shape_id} to fill")
            set_text(shape, text)

        for shape_id in FILL_ORANGE.get(number, []):
            shape = shapes[shape_id]
            shape.fill.solid()
            shape.fill.fore_color.rgb = ORANGE

    # --- slide 3: the comparison table -----------------------------------
    table = next(sh for sh in slides[2].shapes if sh.has_table).table
    rows = [
        ("Cost", "Attendant per trip", "₹58,000 per chair"),
        ("Speed / time", "Unpredictable wait", "Pre-positioned; wait reported"),
        ("Reach / access", "English signage", "4 languages, Konkani first"),
        ("Ease of use", "Ask, then depend", "Scan, then sit"),
    ]
    for index, values in enumerate(rows, start=1):
        for column, value in enumerate(values):
            cell = table.cell(index, column)
            para = cell.text_frame.paragraphs[0]
            para.runs[0].text = value
            for run in para.runs[1:]:
                run._r.getparent().remove(run._r)

    # --- slide 1: the chair, in the space the guidance box left ----------
    # The art is 1500x840, so height follows width; keep both pictures off the
    # text around them rather than trusting the default placement.
    art = Inches(4.2), Inches(4.2 / 1.786)
    slides[0].shapes.add_picture(str(HERE / "chair.png"), Inches(5.20), Inches(2.30),
                                 width=art[0], height=art[1])
    caption = slides[0].shapes.add_textbox(Inches(5.20), Inches(4.78),
                                           Inches(4.20), Inches(0.30))
    run = caption.text_frame.paragraphs[0].add_run()
    run.text = "the guide line it follows, laid into the terminal floor"
    run.font.size = Pt(9)
    run.font.italic = True
    run.font.color.rgb = RGBColor(0xC3, 0xCA, 0xE0)

    # Status, on the title slide rather than buried at the end. A judge reading
    # only the first slide should still know what does and does not exist.
    status = slides[0].shapes.add_textbox(Inches(0.50), Inches(4.25),
                                          Inches(4.40), Inches(0.90))
    frame = status.text_frame
    frame.word_wrap = True
    for index, (text, colour, bold) in enumerate([
        ("Proof of concept", RGBColor(0xF2, 0x8C, 0x28), True),
        (f"Dispatcher built and tested — {TEST_COUNT} automated tests. Demonstrator fleet "
         "costed at ₹4,759. Nothing has yet carried a passenger.",
         RGBColor(0xC3, 0xCA, 0xE0), False),
    ]):
        para = frame.paragraphs[0] if index == 0 else frame.add_paragraph()
        run = para.add_run()
        run.text = text
        run.font.size = Pt(11) if bold else Pt(9.5)
        run.font.bold = bold
        run.font.color.rgb = colour

    # --- slide 6: one card, so widen it and add the prototype picture ----
    card = by_id(slides[5])[6]
    card.width = Inches(4.75)
    slides[5].shapes.add_picture(str(HERE / "chair.png"), Inches(0.55), Inches(2.85),
                                 width=Inches(2.90), height=Inches(2.90 / 1.786))

    out = HERE / "margadarshak-seva-2026.pptx"
    prs.save(out)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
