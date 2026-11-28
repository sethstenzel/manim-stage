"""Lesson 09: Moving the camera.

Ideas from the Motion Canvas "Camera" guide (center on one shape while zooming, move
to another, reset) and Manim's ``FollowingGraphCamera`` example (the frame tracks a dot
along a curve). Manim already has the camera, ``MovingCameraScene``; ``StageMixin`` adds
cues and theming to it, and the Studio reads the camera on every frame.

    manim-stage studio 09_camera.py CenterOn
    manim-stage studio 09_camera.py FollowDot

Try in the Studio:
- scrub: the status bar reads the camera centre and zoom (e.g. ``width 7.11 (2.00×)``);
- clicks in the viewport still pick the right Mobject while zoomed in.

Note: Motion Canvas can also rotate its camera. A Manim ``MovingCameraScene`` frame
pans and zooms only, so this lesson leaves rotation out.
"""

from manim import (
    DOWN,
    LEFT,
    RIGHT,
    UP,
    Axes,
    Circle,
    Dot,
    FadeIn,
    MoveAlongPath,
    MovingCameraScene,
    Restore,
    Square,
    Text,
    VGroup,
    linear,
)

from manim_stage import StageMixin, project


class CenterOn(StageMixin, MovingCameraScene):
    def construct(self):
        theme = project.theme()
        frame = self.camera.frame
        square = Square(1.0, color=theme.secondary, fill_opacity=1).move_to(RIGHT * 2 + UP)
        circle = Circle(0.6, color=theme.error, fill_opacity=1).move_to(LEFT * 2 + DOWN)
        tag_s = Text("square", font_size=18).next_to(square, UP, buff=0.1)
        tag_c = Text("circle", font_size=18).next_to(circle, DOWN, buff=0.1)
        self.play(FadeIn(square), FadeIn(circle), FadeIn(tag_s), FadeIn(tag_c))

        frame.save_state()
        self.cue("zoom_square", after=0.3)
        self.play(frame.animate.move_to(VGroup(square, tag_s)).set(width=4), run_time=2)
        self.cue("go_circle", after=0.3)
        self.play(frame.animate.move_to(VGroup(circle, tag_c)), run_time=1.5)
        self.play(Restore(frame), run_time=1)  # reset
        self.wait(0.3)


class FollowDot(StageMixin, MovingCameraScene):
    def construct(self):
        theme = project.theme()
        frame = self.camera.frame
        axes = Axes(x_range=[-1, 10], y_range=[-1, 10])
        curve = axes.plot(lambda x: 0.1 * x**2 + 1, x_range=[0, 9], color=theme.primary)
        dot = Dot(axes.i2gp(0, curve), color=theme.accent, radius=0.12)
        self.add(axes, curve, dot)

        frame.save_state()
        self.play(frame.animate.scale(0.5).move_to(dot))
        frame.add_updater(lambda f: f.move_to(dot))  # the camera follows the dot
        self.play(MoveAlongPath(dot, curve, rate_func=linear), run_time=3)
        frame.clear_updaters()
        self.play(Restore(frame))
        self.wait(0.3)
