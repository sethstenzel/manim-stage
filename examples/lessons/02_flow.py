"""Lesson 02: Animation flow and tweening.

Ideas from the Motion Canvas "Animation flow" guide (``all``, ``sequence``, ``chain``,
``delay``, ``loop``) and its "Tweening" guide (a ``tween`` callback, timing functions),
mapped onto Manim: each helper returns an ordinary ``AnimationGroup``/``Succession``,
and Manim's ``rate_func`` plays the part of the timing function.

    manim-stage studio 02_flow.py FlowHelpers
    manim-stage studio 02_flow.py Tweening

Try in the Studio:
- the timeline shows each helper's members on nested lanes; ``sequence`` is a staircase;
- select a block in ``Tweening`` to see its rate function's curve.
"""

import numpy as np
from manim import (
    DOWN,
    LEFT,
    PI,
    RIGHT,
    UP,
    Circle,
    Create,
    Dot,
    FadeIn,
    FadeOut,
    Flash,
    Indicate,
    Line,
    ManimColor,
    Rotate,
    Square,
    Text,
    VGroup,
    interpolate_color,
    linear,
    rate_functions,
)

from manim_stage import StageScene, all_of, chain, delay, loop, project, sequence, tween


class FlowHelpers(StageScene):
    """One step per helper; the caption names the helper that is playing."""

    def construct(self):
        theme = project.theme()

        def say(text):
            new = Text(text, font_size=34, color=theme.accent).to_edge(UP)
            return FadeIn(new), new

        dots = VGroup(*[Dot(radius=0.18, color=theme.primary) for _ in range(6)])
        dots.arrange(RIGHT, buff=0.6).shift(DOWN * 1.5)
        square = Square(1.4, color=theme.secondary).shift(UP * 0.4)

        anim, caption = say("sequence(0.2, …): start every 0.2 s")
        self.play(anim)
        self.play(sequence(0.2, *(FadeIn(d, scale=0.3) for d in dots)))

        self.play(FadeOut(caption))
        anim, caption = say("chain(…): one after another")
        self.play(anim)
        self.play(chain(Create(square), square.animate.set_fill(theme.secondary, 0.4)))

        self.play(FadeOut(caption))
        anim, caption = say("all_of(…): together")
        self.play(anim)
        self.play(all_of(Indicate(square, color=theme.accent), Flash(dots[0], color=theme.accent)))

        self.play(FadeOut(caption))
        anim, caption = say("delay(0.5, …): wait, then animate")
        self.play(anim)
        self.play(delay(0.5, Rotate(square, PI / 4)))

        self.play(FadeOut(caption))
        anim, caption = say("loop(6, i → …): repeat")
        self.play(anim)
        self.play(loop(6, lambda i: dots[i].animate(run_time=0.25).shift(UP * 0.5)))
        self.wait(0.5)


class Tweening(StageScene):
    """The same move with three timing functions, then a tween driving a colour."""

    def construct(self):
        theme = project.theme()
        rows = [
            ("linear", linear),
            ("smooth", rate_functions.smooth),
            ("ease_out_bounce", rate_functions.ease_out_bounce),
        ]
        start, end = LEFT * 4, RIGHT * 4
        balls, labels, tracks = [], [], []
        for k, (name, _) in enumerate(rows):
            y = UP * (1.2 - 1.4 * k)
            tracks.append(Line(start + y, end + y, color=theme.muted, stroke_width=2))
            balls.append(Circle(0.25, color=theme.primary, fill_opacity=1).move_to(start + y))
            labels.append(Text(name, font_size=24, color=theme.muted).next_to(start + y, UP))
        self.play(*(FadeIn(m) for m in tracks + balls + labels))

        # tween(run_time, fn): fn(t) runs every frame, t goes 0 → 1 through rate_func
        def mover(ball, y):
            return lambda t: ball.move_to(start + (end - start) * t + y)

        self.play(
            *(
                tween(2.0, mover(b, UP * (1.2 - 1.4 * k)), rate_func=f)
                for k, (b, (_, f)) in enumerate(zip(balls, rows, strict=True))
            )
        )

        # A timing function is just a Python function of t.
        def stepped(t):
            return np.floor(t * 4) / 4

        self.play(
            tween(
                1.5,
                lambda t: [
                    b.set_fill(
                        interpolate_color(ManimColor(theme.primary), ManimColor(theme.accent), t)
                    )
                    for b in balls
                ],
                rate_func=stepped,
            )
        )
        self.wait(0.5)
