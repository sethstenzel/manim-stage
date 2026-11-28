"""Lesson 07: Inspector and exposed properties.

Idea from the Motion Canvas inspector (select a node, read its properties), extended:
``self.expose(mobject, name, *properties)`` makes chosen properties editable in the
Studio. Edits preview instantly, save to ``.manim-stage/properties.json`` (undoable)
and can be copied back as Python. Unexposed objects stay inspectable and read-only.

    manim-stage studio 07_inspector.py Orbit

Try in the Studio:
- Inspector tab → Inspect frame (Ctrl+I), then click the sun or the planet;
- change the planet's ``fill_color`` or ``scale`` → Preview → Save; the orbit
  animation uses the edited planet;
- Copy as Python gives the same change as Manim calls, e.g. ``planet.scale(1.5)``.
"""

from manim import DEGREES, DOWN, LEFT, UP, Circle, Dot, FadeIn, Rotate, Text

from manim_stage import StageScene, project


class Orbit(StageScene):
    def construct(self):
        theme = project.theme()
        sun = self.expose(
            Circle(0.7, color=theme.accent, fill_opacity=1), "sun", "fill_color", "scale"
        )
        orbit = Circle(2.6, color=theme.muted, stroke_width=2)  # read-only in the Inspector
        planet = self.expose(
            Dot(radius=0.22, color=theme.primary).move_to(orbit.point_at_angle(0)),
            "planet",
            "fill_color",
            "scale",
        )
        title = self.expose(
            Text("Click me in the Inspector", font_size=30, color=theme.text).to_corner(UP + LEFT),
            "title",
            "color",
            "position",
        )
        hint = Text("sun · planet · title are exposed", font_size=22, color=theme.muted)

        self.play(FadeIn(sun), FadeIn(orbit), FadeIn(planet), FadeIn(title))
        self.play(FadeIn(hint.to_edge(DOWN)))
        self.play(Rotate(planet, 360 * DEGREES, about_point=sun.get_center()), run_time=3)
        self.wait(0.5)
