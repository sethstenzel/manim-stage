from manim import BLUE, Circle, FadeIn, Scene, Square, VGroup

from manim_stage import demo


class Demo(Scene):
    def construct(self):
        n = demo.param("n", 3, min=1, max=8, description="how many squares")
        size = demo.param("size", 0.5, min=0.2, max=1.0)
        round_ = demo.param("round", False)
        shape = Circle if round_ else Square
        row = VGroup(*[shape().scale(size).set_color(BLUE) for _ in range(n)]).arrange()
        self.next_section("Intro")
        self.add_subcaption("Some shapes", duration=0.5)
        self.play(FadeIn(row), run_time=0.5)
        self.next_section("Outro")
        self.add_subcaption("The end", duration=0.4)
        self.wait(0.4)
