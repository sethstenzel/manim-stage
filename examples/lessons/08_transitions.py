"""Lesson 08: Transitions, within a scene and between scenes.

Idea from the Motion Canvas "Transitions" guide: two scenes, where the second one
slides in over the first. In manim-stage:

- ``enter(self, "slide", LEFT)`` / ``exit(self, "fade")`` bring everything on screen in
  or out *within* a scene (plain ``FadeIn``/``FadeOut`` underneath);
- ``lessons.sequence.json`` joins rendered scenes with overlapping fade, slide or wipe
  transitions, frame-exact and with audio, using ``manim-stage compose``.

    manim-stage studio 08_transitions.py FirstScene
    manim-stage compose lessons.sequence.json -q low_quality   # → lessons.mp4
"""

from manim import DOWN, LEFT, RIGHT, UP, Circle, RoundedRectangle, Square, Text, Triangle, VGroup

from manim_stage import StageScene, enter, exit, project, sequence


class FirstScene(StageScene):
    def construct(self):
        theme = project.theme()
        shapes = VGroup(
            Circle(0.8, color=theme.primary, fill_opacity=0.6),
            Square(1.5, color=theme.secondary, fill_opacity=0.6),
            Triangle(color=theme.accent, fill_opacity=0.6).scale(0.9),
        ).arrange(RIGHT, buff=0.8)
        label = Text("first scene", font_size=36, color=theme.text).to_edge(UP)
        self.add(shapes, label)
        self.play(enter(self, "zoom", run_time=0.8))  # everything on screen zooms in
        self.play(sequence(0.15, *(s.animate.shift(UP * 0.4) for s in shapes)))
        self.play(sequence(0.15, *(s.animate.shift(DOWN * 0.4) for s in shapes)))
        self.wait(0.3)


class SecondScene(StageScene):
    def construct(self):
        theme = project.theme()
        panel = RoundedRectangle(corner_radius=0.3, width=8, height=3.6, color=theme.accent)
        panel.set_fill(theme.accent, 0.12)
        label = Text("second scene", font_size=36, color=theme.text).move_to(panel)
        self.add(panel, label)
        self.play(enter(self, "slide", LEFT, run_time=0.8))  # slides in from the left
        self.play(panel.animate.set_fill(theme.accent, 0.3))
        self.wait(0.5)
        self.play(exit(self, "fade", run_time=0.6))  # fades everything out
