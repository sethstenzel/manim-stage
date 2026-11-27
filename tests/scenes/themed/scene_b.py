from manim import Circle

from manim_stage import StageScene, project


class SceneB(StageScene):
    def construct(self):
        self.add(Circle(radius=2, color=project.theme().accent, fill_opacity=1))
        self.wait(0.2)
