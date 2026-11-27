"""Compatibility corpus: unmodified Manim scenes, one per feature family (backlog 4.4).

Plain Manim only (no manim-stage imports), no LaTeX, no external files. Every scene
ends with a play (``--format png-sequence`` leaves out frozen-wait frames, so parity
compares plays). ``tests/test_compat_suite.py`` checks each one.
"""

import numpy as np
from manim import (
    BLUE,
    DEGREES,
    DOWN,
    GREEN,
    LEFT,
    ORANGE,
    PI,
    RED,
    RIGHT,
    UP,
    YELLOW,
    Axes,
    Circle,
    Create,
    Cube,
    Difference,
    Dot,
    FadeIn,
    FadeOut,
    GrowFromCenter,
    ImageMobject,
    Indicate,
    LaggedStart,
    Line,
    MarkupText,
    MoveAlongPath,
    NumberPlane,
    Paragraph,
    Polygon,
    Rotate,
    Scene,
    Square,
    Star,
    Succession,
    Surface,
    Text,
    ThreeDScene,
    Transform,
    TransformMatchingShapes,
    Union,
    ValueTracker,
    VGroup,
    Write,
    ZoomedScene,
    always_redraw,
    linear,
    there_and_back,
)


class Geometry(Scene):
    def construct(self):
        a = Square(2).set_fill(BLUE, 0.5).shift(LEFT)
        b = Circle(1.2).set_fill(RED, 0.5).shift(RIGHT * 0.5)
        self.play(Create(a), Create(b))
        self.play(
            FadeIn(Union(a, b, color=YELLOW).shift(DOWN * 2)),
            FadeIn(Difference(a, b, color=GREEN).shift(UP * 2)),
        )
        self.play(Rotate(Star(color=ORANGE).shift(RIGHT * 4), PI / 2))


class Typography(Scene):
    def construct(self):
        t = Text("Hello, Manim", font_size=48)
        m = MarkupText('<b>bold</b> and <span fgcolor="#FFC857">colour</span>').next_to(t, DOWN)
        p = Paragraph("two", "lines", alignment="center", font_size=28).to_edge(DOWN)
        self.play(Write(t))
        self.play(FadeIn(m), FadeIn(p))
        self.play(TransformMatchingShapes(t, Text("Hello, Stage", font_size=48)))


class Graphing(Scene):
    def construct(self):
        plane = NumberPlane(
            x_range=[-4, 4], y_range=[-3, 3], background_line_style={"stroke_opacity": 0.4}
        )
        axes = Axes(x_range=[-3, 3], y_range=[-2, 2], x_length=6, y_length=4)
        curve = axes.plot(lambda x: np.sin(2 * x), color=YELLOW)
        self.play(Create(plane), run_time=0.8)
        self.play(Create(axes), Create(curve))
        dot = Dot(color=RED).move_to(curve.get_start())
        self.play(MoveAlongPath(dot, curve), rate_func=linear)


class Updaters(Scene):
    def construct(self):
        t = ValueTracker(0)
        dot = always_redraw(
            lambda: Dot(
                RIGHT * np.cos(t.get_value()) * 2 + UP * np.sin(t.get_value()) * 2, color=YELLOW
            )
        )
        line = always_redraw(lambda: Line(np.zeros(3), dot.get_center()))
        label = Text("0.00", font_size=30).to_corner(UP + LEFT)
        label.add_updater(
            lambda m: m.become(Text(f"{t.get_value():.2f}", font_size=30).to_corner(UP + LEFT))
        )
        self.add(line, dot, label)
        self.play(t.animate.set_value(2 * PI), run_time=2, rate_func=linear)
        self.play(t.animate.set_value(PI), rate_func=there_and_back)


class Composition(Scene):
    def construct(self):
        squares = VGroup(*[Square(0.6) for _ in range(6)]).arrange(RIGHT)
        self.play(LaggedStart(*[GrowFromCenter(s) for s in squares], lag_ratio=0.3))
        self.play(Succession(*[Indicate(s) for s in squares[:3]]))
        self.play(Transform(squares, Circle(2)), FadeOut(squares.copy()))


class Images(Scene):
    def construct(self):
        x = np.linspace(0, 1, 64)
        rgb = np.stack([*np.meshgrid(x, x), np.full((64, 64), 0.5)], axis=-1)
        img = ImageMobject((rgb * 255).astype(np.uint8)).scale(4)
        self.play(FadeIn(img))
        self.play(img.animate.shift(LEFT * 2).scale(0.5))


class Sections(Scene):
    def construct(self):
        self.next_section("one")
        self.play(Create(Circle()))
        self.next_section("two", skip_animations=False)
        self.play(Create(Square().shift(RIGHT * 3)))


class CameraMove(Scene):
    def construct(self):
        self.add(Polygon([-2, -1, 0], [2, -1, 0], [0, 2, 0], color=BLUE), Dot(RIGHT * 3))
        self.play(self.camera.frame.animate.scale(0.5).move_to(RIGHT * 3))
        self.play(self.camera.frame.animate.scale(2).move_to(np.zeros(3)))


class Zoomed(ZoomedScene):
    def construct(self):
        self.add(Text("zoom me", font_size=30))
        self.activate_zooming()
        self.play(self.zoomed_camera.frame.animate.shift(RIGHT * 0.5))


class ThreeD(ThreeDScene):
    def construct(self):
        self.set_camera_orientation(phi=65 * DEGREES, theta=-45 * DEGREES)
        surf = Surface(
            lambda u, v: np.array([u, v, 0.4 * np.sin(u) * np.cos(v)]),
            u_range=[-2, 2],
            v_range=[-2, 2],
            resolution=(8, 8),
        )
        self.play(Create(Cube(side_length=1).shift(UP * 2)), FadeIn(surf))
        self.move_camera(theta=0 * DEGREES, run_time=1)


SCENES = [
    "Geometry",
    "Typography",
    "Graphing",
    "Updaters",
    "Composition",
    "Images",
    "Sections",
    "CameraMove",
    "Zoomed",
    "ThreeD",
]
