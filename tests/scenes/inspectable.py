"""Scenes for the inspector (spec F08)."""

from manim import BLUE, LEFT, RIGHT, Circle, Square, Text, VGroup

from manim_stage import StageScene


class Labeled(StageScene):
    def construct(self):
        node = self.expose(
            Circle(radius=1, color=BLUE, fill_opacity=1).shift(LEFT * 2),
            "node",
            "fill_color",
            "scale",
        )
        box = Square(side_length=1.5).shift(RIGHT * 2)
        label = Text("A", font_size=48).move_to(node)
        self.add(VGroup(node, label), box)
        self.wait(0.3)
