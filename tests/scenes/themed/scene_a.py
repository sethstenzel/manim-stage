"""Two scenes of one project that use the project theme (spec F07 accept)."""

from manim import Square

from manim_stage import StageScene, project


class SceneA(StageScene):
    def construct(self):
        theme = project.theme()
        size = project.var("size", 4.0, min=1, max=6, description="square side")
        self.add(Square(side_length=size, color=theme.accent, fill_opacity=1))
        self.wait(0.2)
