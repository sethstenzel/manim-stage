"""Three scenes of one lesson, styled by the project theme (spec §11 M3 gate).

- ``project.theme()`` colours everything, so one change in ``.manim-stage/project.json``
  (or the Studio's Project panel) restyles all three scenes;
- ``project.var("speed")`` scales the pacing;
- ``Signal``/``bind`` drive the bars; ``sequence``/``chain`` time the animations;
- ``self.expose(...)`` makes the title colour editable in the Studio inspector;
- ``lesson.sequence.json`` joins the scenes with a fade and a slide.

    manim-stage compose lesson.sequence.json -q low_quality
"""

import numpy as np
from manim import DOWN, LEFT, RIGHT, UP, Create, FadeIn, Rectangle, Text, VGroup, Write

from manim_stage import Signal, StageScene, chain, computed, project, sequence


def speed() -> float:
    return project.var("speed", 1.0, min=0.25, max=4, description="pacing multiplier")


class Intro(StageScene):
    def construct(self):
        theme = project.theme()
        title = self.expose(
            Text("Sorting, visually", font_size=56, color=theme.text), "title", "color"
        )
        sub = Text("bubble sort in three scenes", font_size=28, color=theme.muted).next_to(
            title, DOWN
        )
        self.play(chain(Write(title), FadeIn(sub, shift=UP * 0.2)), run_time=2 / speed())
        self.wait(0.5)


class Bars(StageScene):
    def construct(self):
        theme = project.theme()
        values = Signal([5, 2, 4, 1, 3])
        biggest = computed(lambda: int(np.argmax(values())))
        bars = VGroup(*[Rectangle(width=0.6, height=1, fill_opacity=0.9) for _ in range(5)])
        bars.arrange(RIGHT, buff=0.25, aligned_edge=DOWN).shift(DOWN)
        for i, bar in enumerate(bars):
            self.bind(
                bar,
                height=lambda i=i: values()[i] * 0.5,
                align=DOWN,
                color=lambda i=i: theme.accent if biggest() == i else theme.primary,
            )
        self.play(sequence(0.15, *(Create(b) for b in bars)), run_time=1.2 / speed())
        self.play(values.animate.set_value([2, 4, 1, 3, 5]), run_time=1.5 / speed())
        self.wait(0.3)


class Outro(StageScene):
    def construct(self):
        theme = project.theme()
        done = Text("sorted ✓", font_size=56, color=theme.success)
        note = Text("O(n²) comparisons", font_size=30, color=theme.muted).next_to(done, DOWN)
        self.play(chain(FadeIn(done, shift=LEFT * 0.3), Write(note)), run_time=1.5 / speed())
        self.wait(0.5)
