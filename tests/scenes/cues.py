"""StageScene cue scenes (spec F03). Line numbers matter to tests that read them."""

from manim import Circle, Create, FadeIn, FadeOut, Square, Triangle

from manim_stage import StageScene


class Narrated(StageScene):
    def construct(self):
        sq = Square()
        self.play(Create(sq), run_time=1)
        self.cue("intro", at=2.0, description="after 'here is a square'")  # CUE_INTRO
        self.play(FadeIn(Circle()), run_time=0.5)
        self.cue("swap", after=1.0)  # CUE_SWAP
        self.play(FadeIn(Triangle()), run_time=0.5)
        self.cue("marker")  # CUE_MARKER
        self.play(FadeOut(sq), run_time=0.5)


class Looping(StageScene):
    def construct(self):
        for i in range(3):
            self.play(FadeIn(Square()), run_time=0.2)
            self.cue(f"step_{i}", after=0.3)


class Duplicate(StageScene):
    def construct(self):
        self.cue("same", after=0.2)
        self.cue("same", after=0.2)  # DUPLICATE
