"""Representative unmodified Manim scenes for the regression baseline (spec §10.1).

No Text/Tex: glyph rendering differs between operating systems, which would make
cross-platform golden frames meaningless. Text parity is covered per machine by
tests/test_parity.py instead.
"""

from manim import (
    BLUE,
    DOWN,
    GREEN,
    LEFT,
    ORANGE,
    PI,
    RED,
    RIGHT,
    UP,
    Arrow,
    Circle,
    Create,
    DashedLine,
    Dot,
    FadeIn,
    FadeOut,
    LaggedStart,
    NumberPlane,
    ParametricFunction,
    Rotate,
    Scene,
    Square,
    Star,
    Succession,
    Transform,
    Triangle,
    ValueTracker,
    VGroup,
    always_redraw,
    np,
)


class Shapes(Scene):
    def construct(self):
        sq = Square(color=BLUE, fill_opacity=0.5)
        self.play(Create(sq), run_time=0.6)
        self.play(Transform(sq, Circle(color=RED, fill_opacity=0.5)), run_time=0.6)
        self.play(Rotate(sq, PI / 3), sq.animate.shift(RIGHT), run_time=0.6)
        self.play(FadeOut(sq, shift=DOWN), run_time=0.4)


class Choreography(Scene):
    def construct(self):
        shapes = VGroup(Square(), Triangle(), Star(), Circle()).arrange(RIGHT, buff=0.5)
        self.play(LaggedStart(*[FadeIn(s, shift=UP) for s in shapes], lag_ratio=0.3))
        colors = [RED, GREEN, ORANGE, BLUE]
        recolor = [s.animate.set_color(c) for s, c in zip(shapes, colors, strict=True)]
        self.play(Succession(*recolor), run_time=1.2)
        self.play(shapes.animate.arrange(DOWN, buff=0.2).scale(0.6), run_time=0.8)


class Updaters(Scene):
    def construct(self):
        plane = NumberPlane(x_range=(-4, 4), y_range=(-2, 2))
        t = ValueTracker(0)
        curve = ParametricFunction(lambda u: np.array([u, np.sin(2 * u), 0]), t_range=(-4, 4))
        dot = always_redraw(lambda: Dot(curve.point_from_proportion(t.get_value()), color=RED))
        arrow = always_redraw(lambda: Arrow(LEFT * 3 + DOWN * 2, dot.get_center(), buff=0.1))
        line = always_redraw(lambda: DashedLine(dot.get_center(), [dot.get_x(), 0, 0]))
        self.add(plane, curve, dot, arrow, line)
        self.play(t.animate.set_value(1), run_time=1.5)
