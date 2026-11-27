"""Three short scenes joined by transitions (spec F09 accept). Each starts a beep at a
known time so audio alignment can be checked in the composed video."""

import os

from manim import BLUE, GREEN, RED, Circle, Create, FadeIn, Scene, Square, Triangle

BEEP = os.environ.get("MANIM_STAGE_TEST_SOUND", "beep.wav")


class One(Scene):
    def construct(self):
        self.add(Square(color=RED, fill_opacity=1))
        self.add_sound(BEEP, time_offset=0.5)
        self.wait(1.5)


class Two(Scene):
    def construct(self):
        self.play(Create(Circle(color=GREEN, fill_opacity=1)), run_time=1)
        self.add_sound(BEEP)
        self.wait(1)


class Three(Scene):
    def construct(self):
        self.play(FadeIn(Triangle(color=BLUE, fill_opacity=1)), run_time=0.5)
        self.wait(1)
