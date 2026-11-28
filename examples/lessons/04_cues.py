"""Lesson 04: Named cues (time events).

Idea from the Motion Canvas "Time Events" guide: instead of guessing how long to
wait for the narrator (``self.wait(3.1415)``), name the moment and drag it on the
timeline. In manim-stage that is ``self.cue("name")``, a named, adjustable
``Scene.wait``. Positions live in ``.manim-stage/cues.json`` beside this file, so
re-timing never touches Python.

    manim-stage studio 04_cues.py TimeEvents
    manim-stage validate 04_cues.py
    manim-stage timeline 04_cues.py TimeEvents

Try in the Studio:
- drag a cue flag on the Cues lane; hold Shift to ripple every later cue with it;
- Ctrl+Z undoes a drag. ``at=`` is the default absolute time, ``after=`` a pause.
"""

from manim import DOWN, LEFT, RIGHT, UP, Arrow, FadeIn, GrowArrow, RoundedRectangle, Text, VGroup

from manim_stage import StageScene, project


def card(label, color):
    box = RoundedRectangle(corner_radius=0.2, width=2.4, height=1.3, color=color)
    box.set_fill(color, 0.15)
    return VGroup(box, Text(label, font_size=30).move_to(box))


class TimeEvents(StageScene):
    def construct(self):
        theme = project.theme()
        title = Text("Wait for the narrator, not for a number", font_size=34).to_edge(UP)
        idea = card("idea", theme.primary).shift(LEFT * 4)
        sketch = card("sketch", theme.secondary)
        ship = card("ship it", theme.success).shift(RIGHT * 4)
        a1 = Arrow(idea.get_right(), sketch.get_left(), color=theme.muted)
        a2 = Arrow(sketch.get_right(), ship.get_left(), color=theme.muted)

        self.play(FadeIn(title))
        self.play(FadeIn(idea, shift=UP * 0.3))

        # "First you have an idea…" The scene waits here until 2.5 s
        # (or wherever the cue is dragged to).
        self.cue("explain_idea", at=2.5, description="narrator: 'first you have an idea'")
        self.play(GrowArrow(a1), FadeIn(sketch, shift=UP * 0.3))

        # A cue relative to the previous animation: 1 s pause by default.
        self.cue("explain_sketch", after=1.0, description="'then you sketch it'")
        self.play(GrowArrow(a2), FadeIn(ship, shift=UP * 0.3))

        self.cue("wrap_up", after=0.8)
        note = Text("Drag the cues; the code stays the same.", font_size=26)
        self.play(FadeIn(note.set_color(theme.muted).to_edge(DOWN)))
        self.wait(0.5)
