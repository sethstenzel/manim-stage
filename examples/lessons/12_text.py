"""Lesson 12: Text and formulas.

Ideas from Manim's text examples (``Text`` with per-word colours, ``MarkupText``,
``TransformMatchingShapes``) and its ``MovingFrameBox`` example (a box that moves
between the terms of a formula), and from the Motion Canvas "LaTeX" guide (a
formula that changes into the next one).

- ``Typography`` uses only Pango text and runs anywhere.
- ``Formula`` uses ``MathTex``, so it needs LaTeX (``manim-stage doctor`` checks).
  Set ``theme.tex_template`` in the project (e.g. ``font:french_cursive``) to
  change every formula's font.

    manim-stage studio 12_text.py Typography
    manim-stage studio 12_text.py Formula

Try in the Studio: the Text tab previews fonts and builds ``MathTex`` colour maps.
"""

from manim import (
    DOWN,
    UP,
    AddTextLetterByLetter,
    Create,
    FadeIn,
    FadeOut,
    MarkupText,
    MathTex,
    ReplacementTransform,
    SurroundingRectangle,
    Text,
    TransformMatchingShapes,
    TransformMatchingTex,
    Write,
)

from manim_stage import StageScene, project


class Typography(StageScene):
    def construct(self):
        theme = project.theme()
        hello = Text(
            "Signals drive scenes",
            font_size=54,
            t2c={"Signals": theme.primary, "scenes": theme.accent},
        )
        self.play(Write(hello))
        self.play(hello.animate.to_edge(UP))

        markup = MarkupText(
            f'Pango markup: <b>bold</b>, <i>italic</i>, <span fgcolor="{theme.success}">'
            "colour</span> and <u>underline</u>",
            font_size=30,
        )
        self.play(FadeIn(markup, shift=UP * 0.2))

        typed = Text("typed one letter at a time…", font_size=30, color=theme.muted)
        self.play(AddTextLetterByLetter(typed.next_to(markup, DOWN, buff=0.7)))

        # Letters that occur in both words move to their new place.
        a = Text("listen", font_size=60, color=theme.secondary).to_edge(DOWN, buff=1)
        b = Text("silent", font_size=60, color=theme.accent).move_to(a)
        self.play(FadeIn(a))
        self.play(TransformMatchingShapes(a, b), run_time=1.5)
        self.wait(0.5)


class Formula(StageScene):
    """Needs LaTeX."""

    def construct(self):
        theme = project.theme()
        colors = {"a": theme.primary, "b": theme.secondary, "c": theme.accent}

        def formula(*parts):
            eq = MathTex(*parts, font_size=72)
            for letter, color in colors.items():
                eq.set_color_by_tex(letter, color)
            return eq

        eq1 = formula("a^2", "+", "b^2", "=", "c^2")
        eq2 = formula("a^2", "=", "c^2", "-", "b^2")
        self.play(Write(eq1))

        box = SurroundingRectangle(eq1[0], color=theme.highlight, buff=0.1)
        self.play(Create(box))
        self.play(box.animate.become(SurroundingRectangle(eq1[2], color=theme.highlight, buff=0.1)))
        self.play(box.animate.become(SurroundingRectangle(eq1[4], color=theme.highlight, buff=0.1)))
        self.play(FadeOut(box))

        self.play(TransformMatchingTex(eq1, eq2), run_time=1.5)
        eq3 = formula("a", "=", r"\sqrt{c^2 - b^2}")
        self.play(ReplacementTransform(eq2, eq3))
        self.wait(0.5)
