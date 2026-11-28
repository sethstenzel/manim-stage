"""Lesson 01: Signals, computed values and bindings.

Ideas from the Motion Canvas "Signals" guide (a radius signal whose dependants update
on their own) and Manim's ``ArgMinExample`` (a dot driven by a ``ValueTracker``),
rebuilt with manim-stage's ``Signal`` (a real ``ValueTracker``), ``computed`` and
``bind``. You never write an updater by hand.

    manim-stage studio 01_signals.py RadiusSignal
    manim-stage studio 01_signals.py ArgMin

Try in the Studio:
- scrub the timeline. Each ``radius.animate.set_value`` is one block, and every
  bound mobject follows it;
- open the Inspector: the area readout and the circle are ordinary Mobjects.
"""

import numpy as np
from manim import DOWN, LEFT, RIGHT, UP, Axes, Circle, DecimalNumber, Dot, FadeIn, Line, Text

from manim_stage import Signal, StageScene, computed, project


class RadiusSignal(StageScene):
    """One signal (the radius) drives a circle, a readout and a colour."""

    def construct(self):
        theme = project.theme()
        radius = Signal(1.0, name="radius")
        area = computed(lambda: np.pi * radius() ** 2)  # cached; recomputed on change

        circle = Circle(stroke_width=6).shift(LEFT * 2.5)
        self.bind(
            circle,
            width=lambda: 2 * radius(),
            height=lambda: 2 * radius(),
            # past an area of 6 the circle turns to the warning colour
            color=lambda: theme.warning if area() > 6 else theme.primary,
        )
        spoke = Line(stroke_width=4, color=theme.accent)
        self.bind(
            spoke,
            update=lambda m: m.put_start_and_end_on(
                circle.get_center(), circle.get_center() + RIGHT * radius()
            ),
        )

        r_label = Text("radius", font_size=30, color=theme.muted)
        a_label = Text("area = π r²", font_size=30, color=theme.muted)
        r_value = DecimalNumber(
            0, num_decimal_places=2, font_size=44, color=theme.accent, mob_class=Text
        )
        a_value = DecimalNumber(
            0, num_decimal_places=2, font_size=44, color=theme.text, mob_class=Text
        )
        self.bind(r_value, value=radius)  # a Signal is callable, so it is a valid source
        self.bind(a_value, value=area)
        r_label.move_to(RIGHT * 1.2 + UP * 1.2, aligned_edge=LEFT)
        r_value.next_to(r_label, DOWN, aligned_edge=LEFT)
        a_label.next_to(r_value, DOWN, buff=0.5, aligned_edge=LEFT)
        a_value.next_to(a_label, DOWN, aligned_edge=LEFT)

        title = Text("Signals", font_size=44, color=theme.text).to_edge(UP)
        self.play(FadeIn(title), FadeIn(circle), FadeIn(spoke))
        self.play(FadeIn(r_label), FadeIn(r_value), FadeIn(a_label), FadeIn(a_value))

        # Animate the signal: everything bound to it follows, frame by frame.
        self.play(radius.animate.set_value(1.8), run_time=1.5)
        self.play(radius.animate.set_value(0.6), run_time=1.0)
        self.play(radius.animate.set_value(1.2), run_time=0.8)
        self.wait(0.5)


class ArgMin(StageScene):
    """Slide a dot along a curve to its minimum; position and colour are computed."""

    def construct(self):
        theme = project.theme()
        axes = Axes(x_range=[0, 10, 1], y_range=[0, 100, 10], x_length=9, y_length=5).shift(
            DOWN * 0.4
        )

        def f(x):
            return 2 * (x - 5) ** 2

        curve = axes.plot(f, color=theme.primary)
        x = Signal(1.0, name="x")
        y = computed(lambda: f(x()))
        at_min = computed(lambda: abs(x() - 5) < 0.05)

        dot = Dot(radius=0.12)
        self.bind(
            dot,
            position=lambda: axes.c2p(x(), y()),
            color=lambda: theme.success if at_min() else theme.accent,
        )
        x_text = (
            Text("x =", font_size=30, color=theme.muted).to_corner(UP + LEFT).shift(RIGHT * 1.5)
        )
        x_val = DecimalNumber(
            0, num_decimal_places=2, font_size=34, color=theme.text, mob_class=Text
        )
        self.bind(x_val, value=x, update=lambda m: m.next_to(x_text, RIGHT))

        self.play(FadeIn(axes), FadeIn(curve))
        self.play(FadeIn(dot), FadeIn(x_text), FadeIn(x_val))
        self.play(x.animate.set_value(9.0), run_time=1.5)
        self.play(x.animate.set_value(5.0), run_time=1.5)  # turns green at the minimum
        self.wait(0.5)
