"""Chair illustration in the Seva template's own palette, transparent PNG."""
import pathlib, sys
R = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(R / "explainer"))
import generate_explainer as E

NAVY, ORANGE, MID, TINT = "#1B2A5C", "#F28C28", "#6B7280", "#E8EEF9"
E.INK, E.BLUE, E.MID, E.FAINT, E.RULE, E.TINT = NAVY, ORANGE, MID, "#C3CAE0", "#D9DEEA", TINT

W, H = 150.0, 84.0

class Art(E.Sheet):
    def render(self):
        return (f'<?xml version="1.0" encoding="UTF-8"?>\n'
                f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}mm" height="{H}mm" '
                f'viewBox="0 0 {W} {H}">\n  ' + "\n  ".join(self.p) + "\n</svg>\n")

s = Art()
# No caption baked in: both slides that use this art have a navy background, and
# a caption rendered here would have to be light — which would then be invisible
# anywhere else. The caption is a text box on the slide instead.
E.draw_chair(s, ox=64, floor_y=76, k=0.33, guide=False)
s.line(4, 77.4, W - 4, 77.4, ORANGE, 1.5, "3.2,2.2")

out = pathlib.Path(__file__).resolve().parent
svg = out / "chair.svg"
svg.write_text(s.render(), encoding="utf-8")
import cairosvg
cairosvg.svg2png(url=str(svg), write_to=str(out / "chair.png"),
                 output_width=1500, background_color=None)
print("wrote chair.png")
