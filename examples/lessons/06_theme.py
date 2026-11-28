"""Lesson 06: Project theme and variables.

Idea from the Motion Canvas "Project variables" guide (values shared by every scene),
extended with a semantic colour theme. ``project.theme()`` and ``project.var(...)``
read ``.manim-stage/project.json`` beside this file, which every lesson in this folder
shares. Change it once and all the lessons restyle.

    manim-stage studio 06_theme.py ThemePalette

Try in the Studio:
- Project tab: change *accent* and *background*, press Apply; this scene and every
  other lesson follow, and no ``.py`` file changes;
- change the *speed* variable (0.25–4): every lesson's pacing scales.
"""

from manim import DOWN, UP, FadeIn, RoundedRectangle, Text, VGroup

from manim_stage import StageScene, project, sequence

ROLES = ["primary", "secondary", "accent", "highlight", "success", "warning", "error", "muted"]


def speed() -> float:
    return project.var("speed", 1.0, min=0.25, max=4, description="pacing multiplier")


class ThemePalette(StageScene):
    def construct(self):
        theme = project.theme()
        title = Text("One theme, every scene", font_size=40, color=theme.text).to_edge(UP)

        swatches = VGroup()
        for role in ROLES:
            chip = RoundedRectangle(corner_radius=0.15, width=1.4, height=1.0)
            chip.set_fill(theme.color(role), 1).set_stroke(width=0)
            name = Text(role, font_size=20, color=theme.muted).next_to(chip, DOWN, buff=0.15)
            code = Text(theme.color(role), font_size=16, color=theme.text)
            swatches.add(VGroup(chip, name, code.next_to(name, DOWN, buff=0.08)))
        swatches.arrange_in_grid(rows=2, buff=(0.5, 0.5))

        self.play(FadeIn(title), run_time=0.8 / speed())
        self.play(
            sequence(0.12, *(FadeIn(s, shift=UP * 0.3) for s in swatches)),
            run_time=2 / speed(),
        )
        bg = Text(f"background {theme.background}", font_size=22, color=theme.muted)
        self.play(FadeIn(bg.to_edge(DOWN)), run_time=0.6 / speed())
        self.wait(0.5)
