"""Lesson 10: Slides, sections and the web player.

Idea from the Motion Canvas "Presentation" guide: mark where each slide begins and
step through them. Manim already has this concept, ``self.next_section(...)``. The
Studio's Sections tab jumps to and loops any section, and ``manim-stage web`` turns
sections into chapters of a static web player (Prev/Next with ``[`` and ``]``).

    manim-stage studio 10_slides.py Slides
    manim-stage web 10_slides.py Slides -q low_quality

Try in the Studio:
- Sections tab: click a section to jump to it; Loop sets the in/out range to it;
- Export section… exports one; Export all… writes one video per section
  (Manim's ``--save_sections``).
"""

from manim import DOWN, LEFT, UP, FadeIn, FadeOut, FadeTransform, Indicate, Text, VGroup

from manim_stage import StageScene, project, sequence


class Slides(StageScene):
    def construct(self):
        theme = project.theme()
        heading = Text("FIRST SLIDE", font_size=56, color=theme.text)

        self.next_section("First slide")
        self.play(FadeIn(heading, shift=UP * 0.3))
        self.wait(1)

        self.next_section("Second slide")
        second = Text("SECOND SLIDE", font_size=56, color=theme.primary)
        self.play(FadeTransform(heading, second))
        points = VGroup(
            *[
                Text(f"• point {k}", font_size=30, color=theme.muted)
                for k in ("one", "two", "three")
            ]
        ).arrange(DOWN, aligned_edge=LEFT)
        points.next_to(second, DOWN, buff=0.6)
        self.play(sequence(0.3, *(FadeIn(p, shift=UP * 0.2) for p in points)))
        self.wait(1)

        # Kept out of renders, listed as "(skipped)" in the Sections tab.
        self.next_section("Outtakes", skip_animations=True)
        self.play(Indicate(second))
        self.wait(1)

        self.next_section("Last slide")
        self.play(
            FadeOut(points),
            FadeTransform(second, Text("LAST SLIDE", font_size=56, color=theme.accent)),
        )
        self.wait(1)
