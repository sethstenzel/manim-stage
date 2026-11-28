"""Lesson 03: Code that explains itself (``AnimatedCode``).

Ideas from the Motion Canvas "Code" guides: highlighting lines and words, selecting a
range, and animating an edit so that kept tokens slide into place while changed ones
cross-fade. ``AnimatedCode`` is a Manim ``VGroup`` of token mobjects, so any Manim
animation (``Indicate``, ``Circumscribe``…) works on any part of it.

    manim-stage studio 03_code.py CodeTour

Try in the Studio:
- change ``code_style`` in the Project tab (e.g. ``dracula``); the code restyles;
- the Inspector picks single tokens, which are ordinary Mobjects.
"""

from manim import DOWN, UP, Circumscribe, Create, FadeIn, FadeOut, Text

from manim_stage import AnimatedCode, StageScene, project

V1 = """\
def total(prices):
    result = 0
    for p in prices:
        result = result + p
    return result
"""

V2 = """\
def total(prices, tax=0.0):
    result = 0
    for p in prices:
        result += p
    return result * (1 + tax)
"""

V3 = """\
def total(prices, tax=0.0):
    return sum(prices) * (1 + tax)
"""


class CodeTour(StageScene):
    def construct(self):
        theme = project.theme()
        caption = Text("Reading code", font_size=32, color=theme.accent).to_edge(UP)
        code = AnimatedCode(V1, font_size=26).shift(DOWN * 0.3)
        self.play(FadeIn(caption), FadeIn(code))

        # 1. Highlight: everything else dims.
        self.play(code.highlight_lines(3, 4))
        self.play(Circumscribe(code.get(code.find("result + p")), color=theme.accent))

        # 2. Select a range with a box (any CodeRange: find, word, lines).
        box = code.surround(code.find("return result"), color=theme.accent)
        self.play(code.reset_highlight(), Create(box))
        self.play(FadeOut(box))

        # 3. Animate an edit: kept tokens slide, new ones fade in.
        self.play(caption.animate.become(_caption("Editing code", theme)))
        self.play(code.animate_to(V2), run_time=1.5)
        self.play(code.highlight_lines(1, 5))
        self.play(code.reset_highlight())

        # 4. Targeted edits compute the new source for you.
        self.play(code.replace(code.find("result += p"), "result += round(p, 2)"))
        self.play(code.animate_to(V3), run_time=1.5)  # lines removed, the rest close up
        self.play(code.replace(code.find("0.0"), "0.2"))  # a new default tax rate
        self.wait(0.5)


def _caption(text, theme):
    return Text(text, font_size=32, color=theme.accent).to_edge(UP)
