"""Narrated StageScene (voiceover adapter, spec F04). The recording comes from
MANIM_STAGE_TEST_NARRATION (a 2 s file written by the test)."""

import os

from manim import Circle, Create, FadeIn, Square

from manim_stage import StageScene

VOICE = os.environ.get("MANIM_STAGE_TEST_NARRATION", "narration.wav")
TEXT = "Here is our array. <bookmark mark='swap'/> Now we swap the first two."


class Narrated(StageScene):
    def construct(self):
        self.play(Create(Square()), run_time=0.5)
        with self.narration("intro", file=VOICE, text=TEXT) as n:
            self.play(FadeIn(Circle()), run_time=0.3)
            n.wait_until("swap")
            self.play(Circle().animate.shift([1, 0, 0]), run_time=0.3)
