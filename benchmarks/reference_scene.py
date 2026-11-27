"""Reference 10 s scene for the preview latency benchmark: a simple teaching-style scene
(no LaTeX, so it runs on any machine with the base Manim install)."""

from manim import (
    BLUE,
    DOWN,
    GREEN,
    LEFT,
    RIGHT,
    UP,
    YELLOW,
    Create,
    FadeIn,
    FadeOut,
    LaggedStart,
    Rectangle,
    Scene,
    Text,
    VGroup,
    Write,
)


class Reference(Scene):
    def construct(self):
        title = Text("Bubble sort").to_edge(UP)
        values = [5, 2, 4, 1, 3]
        bars = VGroup(
            *[Rectangle(width=0.8, height=v * 0.6, fill_opacity=0.8, color=BLUE) for v in values]
        ).arrange(RIGHT, aligned_edge=DOWN, buff=0.3)
        labels = VGroup(
            *[
                Text(str(v), font_size=28).next_to(b, DOWN)
                for v, b in zip(values, bars, strict=True)
            ]
        )
        self.play(Write(title), run_time=1)
        self.play(LaggedStart(*[Create(b) for b in bars], lag_ratio=0.2), run_time=1.5)
        self.play(FadeIn(labels, shift=UP * 0.2), run_time=0.5)
        for i, j in [(0, 1), (1, 2), (2, 3), (3, 4)]:
            self.play(
                bars[i].animate.set_color(YELLOW), bars[j].animate.set_color(YELLOW), run_time=0.4
            )
            self.play(
                bars[i].animate.shift(RIGHT * 1.1),
                bars[j].animate.shift(LEFT * 1.1),
                labels[i].animate.shift(RIGHT * 1.1),
                labels[j].animate.shift(LEFT * 1.1),
                run_time=0.6,
            )
            bars[i], bars[j] = bars[j], bars[i]
            labels[i], labels[j] = labels[j], labels[i]
            self.play(
                bars[i].animate.set_color(BLUE), bars[j].animate.set_color(BLUE), run_time=0.25
            )
        self.play(bars[-1].animate.set_color(GREEN), run_time=0.5)
        self.play(FadeOut(VGroup(title, bars, labels)), run_time=1)
        self.play(Create(Rectangle(width=4, height=2)), run_time=1.0)
