"""Unmodified Manim scenes used by the event-capture tests. Line numbers matter."""

import os

from manim import (
    LEFT,
    PI,
    RIGHT,
    UP,
    AnimationGroup,
    Circle,
    Create,
    FadeIn,
    LaggedStart,
    Rotate,
    Scene,
    Square,
    Succession,
    Triangle,
)

SOUND = os.environ.get("MANIM_STAGE_TEST_SOUND", "beep.wav")


class Lesson(Scene):
    def construct(self):
        sq, c, t = Square(), Circle().shift(LEFT * 3), Triangle().shift(RIGHT * 3)
        self.play(Create(sq), run_time=0.5)  # line 28
        self.add_sound(SOUND, time_offset=0.1)  # line 29
        self.play(AnimationGroup(FadeIn(c), sq.animate.shift(UP), run_time=1.0))
        self.play(LaggedStart(FadeIn(t), FadeIn(c), FadeIn(sq), lag_ratio=0.5, run_time=1.5))
        self.next_section("loop")  # line 32
        for _ in range(3):
            self.play(Rotate(sq, PI / 4), run_time=1 / 3)  # line 34
        self.wait(0.7)


class Nested(Scene):
    def construct(self):
        a, b, c, d = Square(), Circle(), Triangle(), Square().shift(UP)
        self.play(
            AnimationGroup(
                LaggedStart(FadeIn(a), FadeIn(b), lag_ratio=1.0),
                Succession(FadeIn(c), FadeIn(d)),
            )
        )


class MixedRunTimes(Scene):
    def construct(self):
        a, b = Square(), Circle()
        self.play(FadeIn(a, run_time=2), FadeIn(b, run_time=1))


class Broken(Scene):
    def construct(self):
        self.play(FadeIn(Square()), run_time=0.2)
        raise ValueError("boom")  # line 58


PROBE_LOG: list[list[float]] = []


class Probe(Scene):
    """Records each square's opacity on every frame, as Manim actually animated it."""

    def construct(self):
        from manim import Dot, smooth

        squares = [Square(fill_opacity=1).shift(RIGHT * i) for i in range(3)]
        probe = Dot().set_opacity(0)
        probe.add_updater(lambda m: PROBE_LOG.append([s.get_fill_opacity() for s in squares]))
        self.add(probe)
        self.play(
            LaggedStart(
                *[FadeIn(s) for s in squares], lag_ratio=0.35, run_time=1.7, rate_func=smooth
            )
        )
