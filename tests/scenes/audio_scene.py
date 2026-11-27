"""StageScene whose sound comes from the audio workspace sidecar (spec F04)."""

from manim import FadeIn, FadeOut, Square

from manim_stage import StageScene


class Voiced(StageScene):
    def construct(self):
        sq = Square()
        self.play(FadeIn(sq), run_time=1.0)
        self.cue("explain", at=1.5)
        self.play(FadeOut(sq), run_time=1.0)
