"""Lesson 11: Demo parameters (live sliders while you present).

Idea from Manim's ``PointWithTrace`` and ``SineCurveUnitCircle`` examples (a point
drawing a curve), turned into an explorable demo: ``demo.param(...)`` declares a knob
with a default. The Studio's Demo tab shows a slider, check box, drop-down or colour
button for each one and re-renders as you drag. Renders and exports use the defaults
unless you bake the values in.

    manim-stage studio 11_demo_params.py Lissajous

Try in the Studio (Demo tab):
- drag ``a`` and ``b`` to get a different figure for each ratio; ``phase`` turns it;
- pick another ``color``; untick ``show_dot``; Reset returns to the defaults.
"""

import numpy as np
from manim import (
    DOWN,
    UP,
    Create,
    Dot,
    FadeIn,
    MoveAlongPath,
    ParametricFunction,
    Text,
    linear,
)

from manim_stage import StageScene, demo, project


class Lissajous(StageScene):
    def construct(self):
        theme = project.theme()
        a = demo.param("a", 3, min=1, max=7, description="x frequency")
        b = demo.param("b", 2, min=1, max=7, description="y frequency")
        phase = demo.param("phase", 0.5, min=0.0, max=3.14, step=0.1)
        color = demo.param("color", theme.primary)
        show_dot = demo.param("show_dot", True)

        def point(t):
            return np.array([3 * np.sin(a * t + phase), 2.6 * np.sin(b * t), 0]) + DOWN * 0.3

        curve = ParametricFunction(point, t_range=[0, 2 * np.pi, 0.01], color=color)
        title = Text(f"x = sin({a}t + {phase:.1f}),  y = sin({b}t)", font_size=28)
        self.play(FadeIn(title.set_color(theme.muted).to_edge(UP)))

        draw = Create(curve, rate_func=linear)
        if show_dot:
            dot = Dot(point(0), color=theme.accent, radius=0.1)
            self.add(dot)
            self.play(draw, MoveAlongPath(dot, curve, rate_func=linear), run_time=4)
        else:
            self.play(draw, run_time=4)
        self.wait(0.5)
